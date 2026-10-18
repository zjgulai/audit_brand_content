#!/usr/bin/env node
/**
 * report_render.mjs — T1-11：唯一报告与群消息渲染器
 *
 * 唯一输入是冻结的 RenderSnapshot（含只读 ReviewIR + 冻结的 coverage/evidence/
 * unassessed/receipt/counts）。本文件不接 finding_store / decision_table /
 * coverage_composer / metrics_read_model，不写盘、不联网、不改输入。
 *
 * 报告六区块标题与字段逐字按 Playbook §4.3.3；群消息按 §4.3.2 每档一句 +
 * 报告链接；去 AI 味按 §4.3.4 的四阻断 / 三警告分级执行。
 */

import { createHash } from "node:crypto";
import { lintCopy } from "../reply-cards/registry.mjs";

export const BLOCK_TITLES = [
  "## 结论",
  "## 命中的问题",
  "## 覆盖证明",
  "## 依据清单",
  "## 未审说明",
  "## 执行回执",
];

export const LABELS = ["BLOCK", "REVIEW", "未审查", "待自决", "PASS"];

export const V1_KEYS = ["字幕", "内嵌文字", "关键帧", "音轨", "完整画面语义"];

export const LINT_LEVELS = {
  chatbotResidue: "block",
  conclusionTail: "block",
  hedgeStack: "block",
  internalLeak: "block",
  padding: "warn",
  ruleOfThree: "warn",
  connectorStack: "warn",
};

const REPORT_SCOPE = new Set(["chatbotResidue", "internalLeak"]);
const MESSAGE_SCOPE = new Set(Object.keys(LINT_LEVELS));
const FAILURE_KINDS = ["fetch_error", "parse_error", "empty", "unsupported"];
const FORBIDDEN_INPUT_KEYS = [
  "finding_store", "decision_table", "coverage_composer",
  "metrics_read_model", "store",
];
const REASON_ZH = {
  no_capability: "无能力",
  no_rule: "无规则",
  not_wired: "未接线",
};
const SEVERITY_RANK = { L0: 0, L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 };

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = canonicalJson(value[key]);
    return out;
  }
  return value;
}

export function sourceIrFingerprint(ir) {
  const canonical = JSON.stringify(canonicalJson(ir));
  return createHash("sha256").update(canonical, "utf8").digest("hex");
}

function asArray(v) {
  return Array.isArray(v) ? v : [];
}

function textOrNone(v) {
  if (v === null || v === undefined || v === "") return "无";
  if (Array.isArray(v)) return v.length ? v.join("、") : "无";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function locationText(loc) {
  if (!loc || typeof loc !== "object") return "无";
  if (Array.isArray(loc.bbox)) return `bbox=[${loc.bbox.join(",")}]`;
  return textOrNone(loc);
}

function reasonText(why) {
  return REASON_ZH[why] || textOrNone(why);
}

/** 对一段文案跑去 AI 味检查；scope = report | message。 */
export function lintText(text, scope = "message") {
  const allowed = scope === "report" ? REPORT_SCOPE : MESSAGE_SCOPE;
  const hits = lintCopy(String(text))
    .filter((h) => allowed.has(h.id))
    .map((h) => ({ ...h, level: LINT_LEVELS[h.id] || h.level }));
  if (String(text).includes("[[card:")) {
    hits.push({
      id: "internalLeak",
      level: "block",
      why: "卡片原始标记漏进正文",
      count: 1,
      sample: "[[card:",
    });
  }
  return hits;
}

export function validateSnapshot(snapshot) {
  const errors = [];
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
    return ["snapshot 必须是对象"];
  }
  for (const key of FORBIDDEN_INPUT_KEYS) {
    if (key in snapshot) errors.push(`违规依赖：渲染器不许出现 ${key}`);
  }
  const ir = snapshot.ir;
  if (!ir || typeof ir !== "object" || Array.isArray(ir)) {
    return [...errors, "snapshot.ir 必须是冻结 ReviewIR"];
  }
  if (!ir.ir_id) errors.push("ir.ir_id 缺失");
  if (!ir.decision || !LABELS.includes(ir.decision.state)) {
    errors.push("decision.state 不在五标签");
  }
  if (ir.decision && ir.decision.release_status !== "待放行") {
    errors.push("decision.release_status 必须固定为「待放行」");
  }
  const coverageState = ir.coverage && ir.coverage.coverage_state;
  if (ir.decision && ir.decision.state === "PASS" && coverageState !== "full") {
    errors.push(`L1-6: PASS 必须 coverage=full，实际 ${coverageState}`);
  }

  const fc = snapshot.failure_kind_counts;
  if (!fc || typeof fc !== "object" || Array.isArray(fc)) {
    errors.push("failure_kind_counts 缺失");
  } else {
    for (const k of FAILURE_KINDS) {
      if (typeof fc[k] !== "number") errors.push(`failure_kind_counts.${k} 缺失或非数字`);
    }
  }
  const ub = snapshot.unknown_bucket_counts;
  if (!ub || typeof ub !== "object" || Array.isArray(ub)) {
    errors.push("unknown_bucket_counts 必须是对象");
  }

  const video = snapshot.video;
  if (video) {
    const covers = video.covers;
    for (const key of V1_KEYS) {
      if (!covers || !(key in covers)) {
        errors.push(`V1 视频 covers 缺项：${key}`);
      }
    }
    for (const key of ["frames", "duration_seconds", "interval_seconds"]) {
      if (typeof video[key] !== "number") {
        errors.push(`V2 缺少视频读数：${key}`);
      }
    }
  }
  return errors;
}

function assertVideoClaim(text, snapshot, errors) {
  if (!String(text).includes("视频已审")) return;
  const covers = snapshot.video && snapshot.video.covers;
  const missing = V1_KEYS.filter((k) => !covers || !(k in covers));
  if (missing.length) {
    errors.push(`V4「视频已审」必须带 V1 五项，缺：${missing.join("、")}`);
  }
}

function evidenceMap(snapshot) {
  const map = {};
  for (const e of asArray(snapshot.evidence)) {
    if (e && e.evidence_id) map[e.evidence_id] = e;
  }
  return map;
}

function findingLine(f, evmap) {
  const evidence = f.evidence_id
    ? (evmap[f.evidence_id] ? evmap[f.evidence_id].evidence_id : f.evidence_id)
    : "无";
  return `- ${f.finding_id} · 控制点：${textOrNone(f.control_code)} · `
    + `严重度：${textOrNone(f.severity)} · 确认状态：${textOrNone(f.status)} · `
    + `位置：${locationText(f.location)} · 原文：${textOrNone(f.quote)} · `
    + `依据：${evidence}`;
}

function evidenceLine(e) {
  return `- 依据编号：${textOrNone(e.evidence_id)} · `
    + `来源类型：${textOrNone(e.source_type)} · `
    + `出处：${textOrNone(e.source)} · 生效期：${textOrNone(e.valid_from)}`
    + `${e.valid_to ? " 至 " + e.valid_to : ""}`;
}

function receiptLine(receipt, key, label) {
  return `- ${label}：${textOrNone(receipt ? receipt[key] : null)}`;
}

export function renderReport(snapshot) {
  const errors = validateSnapshot(snapshot);
  if (errors.length) {
    return { ok: false, blocked: true, markdown: null, errors, hits: [], warnings: [] };
  }
  const ir = snapshot.ir;
  const evmap = evidenceMap(snapshot);
  const findings = asArray(ir.findings);
  const coverage = ir.coverage || {};
  const video = snapshot.video;
  const lines = [];

  lines.push("# 内容审查报告");
  lines.push(`IR：${ir.ir_id}（${textOrNone(ir.ir_version)}）`);
  lines.push(`source_ir_version: ${textOrNone(ir.source_ir_version)}`);
  lines.push(`source_ir_fingerprint: ${sourceIrFingerprint(ir)}`);
  lines.push("");

  lines.push("## 结论");
  lines.push(`- 状态：${textOrNone(ir.decision.state)}`);
  lines.push(`- 判定依据：${textOrNone(ir.decision.basis || ir.decision.layer)}`);
  lines.push("- 放行状态：待放行");
  lines.push(`- 并行义务：${textOrNone(ir.decision.obligations)}`);
  lines.push("");

  lines.push("## 命中的问题");
  if (!findings.length) {
    lines.push("无");
  } else {
    for (const f of findings) lines.push(findingLine(f, evmap));
  }
  lines.push("");

  lines.push("## 覆盖证明");
  lines.push(`- 评过的模态：${textOrNone(coverage.modalities_evaluated)}`);
  lines.push(`- 规则版本：${textOrNone(coverage.rules_version)}`);
  lines.push(`- 适用控制点：${textOrNone(coverage.control_points_applied)}`);
  const reasons = asArray(coverage.not_evaluated_reason)
    .map((r) => `${r.what}（${reasonText(r.why)}）`);
  lines.push(`- 未跑的为什么：${reasons.length ? reasons.join("；") : "无"}`);
  if (video) {
    lines.push(`- 视频已审：${V1_KEYS.map((k) => `${k}=${video.covers[k]}`).join("；")}`);
    lines.push(`- 抽帧数：${video.frames}；总时长：${video.duration_seconds}s；`
      + `抽帧间隔：${video.interval_seconds}s`);
  }
  lines.push("");

  lines.push("## 依据清单");
  const evidence = asArray(snapshot.evidence);
  if (!evidence.length) lines.push("无");
  else for (const e of evidence) lines.push(evidenceLine(e));
  lines.push("");

  lines.push("## 未审说明");
  const unassessed = asArray(snapshot.unassessed);
  if (!unassessed.length) {
    lines.push("- 未审部分：无");
    lines.push("- 原因：无");
    lines.push("- 责任人：无");
  } else {
    for (const u of unassessed) {
      lines.push(`- 未审部分：${textOrNone(u.part)} · `
        + `原因：${reasonText(u.reason)} · 责任人：${textOrNone(u.owner)}`);
    }
  }
  const fc = snapshot.failure_kind_counts;
  lines.push(`- failure_kind 计数：${FAILURE_KINDS.map((k) => `${k}=${fc[k]}`).join(" ")}`);
  const unknown = Object.entries(snapshot.unknown_bucket_counts || {});
  lines.push(`- 未知桶计数：${unknown.length
    ? unknown.map(([k, v]) => `${k}=${v}`).join(" ")
    : "无"}`);
  lines.push("");

  lines.push("## 执行回执");
  const receipt = snapshot.receipt || {};
  lines.push(receiptLine(receipt, "skill", "skill"));
  lines.push(receiptLine(receipt, "version", "版本"));
  lines.push(receiptLine(receipt, "fingerprint", "指纹"));
  lines.push(`- 跳过的步骤：${textOrNone(receipt.skipped_steps)}`);
  lines.push(`- 规则快照：${textOrNone(receipt.rule_snapshot || ir.rule_snapshot)}`);

  const markdown = lines.join("\n") + "\n";
  const claimErrors = [];
  assertVideoClaim(markdown, snapshot, claimErrors);
  const hits = lintText(markdown, "report");
  const blocking = hits.filter((h) => h.level === "block");
  const warnings = hits.filter((h) => h.level === "warn");
  if (claimErrors.length || blocking.length) {
    return {
      ok: false,
      blocked: true,
      markdown: null,
      errors: [
        ...claimErrors,
        ...blocking.map((h) => `阻断级 AI 味：${h.id} ${h.sample || ""}`),
      ],
      hits,
      warnings,
    };
  }
  return { ok: true, blocked: false, markdown, errors: [], hits, warnings };
}

function worstFinding(findings) {
  const confirmed = findings.filter((f) => f.status === "confirmed");
  const pool = confirmed.length ? confirmed : findings;
  return pool.slice().sort(
    (a, b) => (SEVERITY_RANK[b.severity] || 0) - (SEVERITY_RANK[a.severity] || 0),
  )[0] || null;
}

export function renderMessage(snapshot) {
  const errors = validateSnapshot(snapshot);
  if (errors.length) {
    return { ok: false, blocked: true, text: null, errors, hits: [], warnings: [] };
  }
  const ir = snapshot.ir;
  const state = ir.decision.state;
  let detail = "";
  if (state === "BLOCK") {
    const f = worstFinding(asArray(ir.findings));
    detail = f
      ? `${f.severity} · ${f.control_code} · “${f.quote || "无"}” · 位置：${locationText(f.location)}`
      : "最严重命中缺失";
  } else if (state === "REVIEW") {
    detail = ir.decision.review_reason || "需要人看";
  } else if (state === "未审查") {
    const u = asArray(snapshot.unassessed)[0];
    detail = u ? `${u.part}：${reasonText(u.reason)}` : "未审原因未提供";
  } else if (state === "待自决") {
    detail = ir.decision.self_decide || "请提交人确认是否修改";
  } else if (state === "PASS") {
    detail = `覆盖：${textOrNone((ir.coverage || {}).modalities_evaluated)}`;
  }
  let text = `【${state}】${detail} · 报告：${snapshot.report_url || "无"}`;
  text = text.replace(/[\r\n]+/g, " ");

  const claimErrors = [];
  assertVideoClaim(text, snapshot, claimErrors);
  const hits = lintText(text, "message");
  const blocking = hits.filter((h) => h.level === "block");
  const warnings = hits.filter((h) => h.level === "warn");
  if (claimErrors.length || blocking.length) {
    return {
      ok: false,
      blocked: true,
      text: null,
      errors: [
        ...claimErrors,
        ...blocking.map((h) => `阻断级 AI 味：${h.id} ${h.sample || ""}`),
      ],
      hits,
      warnings,
    };
  }
  return { ok: true, blocked: false, text, errors: [], hits, warnings };
}

export function renderAll(snapshot) {
  const report = renderReport(snapshot);
  const message = renderMessage(snapshot);
  return {
    ok: report.ok && message.ok,
    report,
    message,
    warnings: [...(report.warnings || []), ...(message.warnings || [])],
    errors: [...(report.errors || []), ...(message.errors || [])],
  };
}
