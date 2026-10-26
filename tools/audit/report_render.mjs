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

function reasonText(why, label) {
  // ① IR 自带的可读标签优先（唯一来源）；② 老快照没有 label 时退回 REASON_ZH；
  // ③ 都没有就原样显示 why，不许静默说成「未说明」——那是另一种把缺口藏起来。
  const own = typeof label === "string" ? label.trim() : "";
  if (own) return own;
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

/**
 * 工作流耗时那一行。口径与 `base/workflow_timing.py` 的 `format_line()` **逐字同构**：
 * 总耗时（N 步求和）+ 最慢三步。改一处必须改另一处，`verify_workflow_timing` 的 D 组
 * 会检查两侧都在读同一个快照键。
 *
 * ★ 未测时**不许**出现「0」「ms 数值」「很快」—— 空步骤集与「跑得极快」长得一样，
 *   写 0 就是把「没测」说成「测过了、很快」。
 */
function timingLine(timing) {
  if (!timing || timing.status !== "ok") {
    const why = (timing && timing.reason) || "原因不明";
    return `未测（${why}）`;
  }
  const total = Number(timing.total_ms).toFixed(2);
  const steps = timing.step_count;
  const slow = (timing.slowest || [])
    .map((s) => `${s.name} ${Number(s.duration_ms).toFixed(2)} ms`)
    .join("、");
  return slow
    ? `总耗时 ${total} ms（${steps} 步求和）；最慢：${slow}`
    : `总耗时 ${total} ms（${steps} 步求和）`;
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

  // ★ T-433：画面语义单独成节，措辞固定「候选 · 待人工确认」。
  //
  //   为什么固定措辞、且不许说「已通过」：一条没有 control_code 的观察
  //   今天就不是 finding（finding 准入是三要素合取，见 base/finding_store.py:69）。
  //   把观察写成「已通过」，复核时**无法申诉** —— 没有 control_code 就无法对照规则。
  //
  //   为什么空的时候写「未评」而不是「正常」：空有两种成因 ——「没接入」
  //   与「看了没发现」。前者在 snapshot.multimodal_note 里，后者不该被当成前者。
  //   两者都**不许**读成「画面没问题」。
  lines.push("## 画面语义（候选 · 待人工确认）");
  const observations = asArray(snapshot.multimodal_observations);
  const okObs = observations.filter((o) => o && o.status === "ok");
  const badObs = observations.filter((o) => o && o.status !== "ok");
    if (!okObs.length && !badObs.length) {
    const why = String(snapshot.multimodal_note || "").trim();
    lines.push(`- 本项未评：${why || "未提供原因（按未评处理）"}`);
    // ★ 措辞注意：这里**不许**出现「画面正常 / 已通过 / 没问题」这类词，
    //   连「不是『画面正常』」这种否定式也不许 —— 去 AI 味与未审词表两道尺
    //   都是按字面匹配的，一句否定句会让它们把整节判红，而读者也可能只扫到那几个字。
    lines.push("- 覆盖状态：未评 —— 不得据此放行，须人工复核画面");
  } else {
    if (okObs.length) {
      lines.push("以下为机器观察，**候选 · 待人工确认**；不是 finding，不得直接放行：");
      for (const o of okObs) {
        const bits = [`- [${textOrNone(o.task)}] ${textOrNone(o.statement)}`];
        if (o.confidence !== null && o.confidence !== undefined) {
          bits.push(`置信 ${Number(o.confidence).toFixed(2)}`);
        }
        if (o.bbox) bits.push(`位置：${o.bbox}`);
        if (o.ts) bits.push(`时间：${o.ts}`);
        if (o.model) bits.push(`模型：${o.model}`);
        lines.push(bits.join("；"));
      }
    } else {
      lines.push("- 无有效观察（下面逐条说明为什么）");
    }
    if (badObs.length) {
      lines.push(`- 未评部分（${badObs.length} 条，原因如下）—— 未评不是没问题：`);
      for (const o of badObs) {
        lines.push(`  - [${textOrNone(o.task)}] ${textOrNone(o.status)}：`
          + `${textOrNone(o.reason)}`);
      }
    }
    lines.push("- 覆盖状态：部分覆盖 —— 画面语义为候选观察，须人工确认");
  }
  lines.push("");

  lines.push("## 覆盖证明");
  lines.push(`- 评过的模态：${textOrNone(coverage.modalities_evaluated)}`);
  lines.push(`- 规则版本：${textOrNone(coverage.rules_version)}`);
  lines.push(`- 适用控制点：${textOrNone(coverage.control_points_applied)}`);
  // ★ 2026-10-23 T-120c：措辞优先取 IR 里的 `label`（与 why 一一对应、由
  //   coverage_composer 给出），REASON_ZH 只是**老快照**的兜底。
  //   不在这里再维护一份 no_control_points → 中文的映射：那会让同一条原因有两份措辞，
  //   而报告与界面各说各的正是这次要修的病。
  const reasons = asArray(coverage.not_evaluated_reason)
    .map((r) => `${r.what}（${reasonText(r.why, r.label)}）`);
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
  // ★ T-451：工作流耗时。**只读快照里那一份**（生产者是 orchestrator），
  //   渲染器不自己算 —— 两边各算一份就是两个口径。
  //   ★ 未测时写「未测（原因）」，不写 0 ms —— 空步骤集与「跑得极快」必须长得不一样。
  lines.push(`- 工作流耗时：${timingLine(receipt.workflow_timing)}`);

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

/**
 * 并行义务短标记（M4 / 验收表 #62）。
 *
 * 验收表原文：「构造『BLOCK + has_candidate=true』样本，断言消息在关键句后
 * 出现对应并行义务标记（如『· 另有 1 条疑似待确认』）且数量/类别正确；
 * 构造无并行义务样本，断言不出现该标记（反向对照）。」
 *
 * ★ 2026-10-24 补：此前 `renderMessage` **一次都没读过** `decision.obligations`，
 *   也没数过 candidate —— 群消息里一个字都没有，而验证器也没有任何断言。
 *   也就是说这条要求从未实现，读数却挂在 `passed` 上。
 *
 * ## 标记由什么决定（两条独立来源，都要）
 *
 *   1. `decision.obligations` 里的已知项 → 逐项出短标记（`partial_coverage` 等）；
 *   2. `findings` 里 `status === "candidate"` 的条数 → 出「另有 N 条疑似待确认」。
 *
 * ## 什么情况下**不**出标记（这一半才是防「永远打标记」的）
 *
 *   · `obligations` 为空数组或缺失，且 0 条 candidate → 返回空串，调用方不拼接。
 *   · 未知的 obligation 原样透出，不静默丢弃（丢字段 = 藏缺口）。
 */
const OBLIGATION_ZH = {
  partial_coverage: "部分覆盖",
};

export function parallelObligationMark(ir) {
  const parts = [];
  const obligations = asArray((ir.decision || {}).obligations);
  for (const ob of obligations) {
    const text = typeof ob === "string" ? ob : textOrNone(ob);
    if (!text) continue;
    parts.push(OBLIGATION_ZH[text] ? `${OBLIGATION_ZH[text]}（${text}）` : text);
  }
  const candidateCount = asArray(ir.findings).filter(
    (f) => f && f.status === "candidate",
  ).length;
  if (candidateCount > 0) {
    parts.push(`另有 ${candidateCount} 条疑似待确认`);
  }
  return parts.length ? ` · ${parts.join(" · ")}` : "";
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
  // M4：并行义务短标记插在**关键句之后、报告链接之前**。
  const mark = parallelObligationMark(ir);
  let text = `【${state}】${detail}${mark} · 报告：${snapshot.report_url || "无"}`;
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
