#!/usr/bin/env node
// verify_report_render.mjs — T1-11：report_renderer 六区块 + 五标签 + 去 AI 味 + V1/V2
//
// 退出码：0 全过 / 1 有红 / 2 未测（模块导入失败或验收器自身异常）。

let R;
try {
  R = await import("./audit/report_render.mjs");
} catch (e) {
  console.error(`UNTESTED: 无法导入 tools/audit/report_render.mjs: ${e.message}`);
  process.exit(2);
}

import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";

let passed = 0;
let failed = 0;

function report(ok, name, detail = "") {
  if (ok) {
    console.log(`PASS: ${name}`);
    passed++;
  } else {
    console.error(`FAIL: ${name} ${detail}`);
    failed++;
  }
}

function baseSnapshot() {
  return {
    report_url: "https://example.test/reports/ir-1.md",
    ir: {
      ir_id: "ir-1",
      ir_version: "ir-v1",
      source_ir_version: "cu-1",
      content_unit_ref: { unit_id: "cu-1", kind: "image" },
      findings: [{
        finding_id: "f-1",
        control_code: "H01",
        status: "confirmed",
        severity: "L4",
        produced_by: "rule",
        derived_from: null,
        authority_state: "ok",
        detected_by: "P0",
        location: { type: "image", bbox: [0.1, 0.2, 0.4, 0.6] },
        quote: "未坐安全座椅",
        evidence_id: "E-1",
      }],
      decision: {
        state: "BLOCK",
        layer: "DP2",
        release_status: "待放行",
        obligations: ["partial_coverage"],
        basis: "confirmed L4 命中",
        review_reason: "需要法务判断",
        self_decide: "是否修改文案",
      },
      coverage: {
        coverage_state: "partial",
        modalities_evaluated: ["图片"],
        rules_version: "rules-v1",
        control_points_applied: ["H01"],
        not_evaluated_reason: [{ what: "视频音轨", why: "no_capability" }],
      },
      receipt_ref: "rc-1",
      rule_snapshot: "rs-1",
      kb_snapshot: "kb-1",
      control_points_version: "cp-v1",
      created_at: "2026-10-19T00:00:00Z",
    },
    evidence: [{
      evidence_id: "E-1",
      source_type: "内部",
      source: "PMO/audit/示例.md",
      valid_from: "2026-10-01",
      valid_to: "2026-12-31",
    }],
    unassessed: [{
      part: "视频音轨",
      reason: "no_capability",
      owner: "media_pipeline",
    }],
    receipt: {
      skill: "content-review",
      version: "1.0",
      fingerprint: "rc-1",
      skipped_steps: ["ASR"],
      rule_snapshot: "rs-1",
    },
    failure_kind_counts: {
      fetch_error: 0, parse_error: 0, empty: 0, unsupported: 0,
    },
    unknown_bucket_counts: {},
  };
}

function withIr(patch) {
  const s = baseSnapshot();
  s.ir = { ...s.ir, ...patch };
  return s;
}

function block(md, title) {
  const i = md.indexOf(title);
  if (i < 0) return "";
  const rest = md.slice(i + title.length);
  const j = rest.search(/^## /m);
  return j < 0 ? rest : rest.slice(0, j);
}

function clone(x) {
  return JSON.parse(JSON.stringify(x));
}

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) out[key] = canonicalJson(value[key]);
    return out;
  }
  return value;
}

function irFingerprint(ir) {
  return createHash("sha256")
    .update(JSON.stringify(canonicalJson(ir)), "utf8")
    .digest("hex");
}

try {
  // C0 六区块标题逐字且各一次
  const r0 = R.renderReport(baseSnapshot());
  report(r0.ok === true && typeof r0.markdown === "string",
         "C0 干净 IR → 报告渲染成功", JSON.stringify(r0.errors || []));
  for (const t of R.BLOCK_TITLES) {
    const n = r0.markdown.split(t).length - 1;
    report(n === 1, `C0 区块标题逐字且恰好一次：${t}`, `count=${n}`);
  }
  report(!r0.markdown.includes("## 问题列表"),
         "C0/F2 不许同义替换标题（问题列表）", "");

  // R1 报告 front matter：source_ir_version + source_ir_fingerprint（IR sha256 全 64 位）
  const expectedFp = irFingerprint(baseSnapshot().ir);
  report(r0.markdown.includes("source_ir_version: cu-1")
         && r0.markdown.includes(`source_ir_fingerprint: ${expectedFp}`)
         && /^[0-9a-f]{64}$/.test(expectedFp),
         "R1 报告带 source_ir_version + 64 位 IR 指纹",
         JSON.stringify({ expectedFp, has: r0.markdown.slice(0, 160) }));

  // C1 六区块字段逐字
  const fields = {
    "## 结论": ["状态", "判定依据", "放行状态", "并行义务"],
    "## 命中的问题": ["控制点", "严重度", "确认状态", "位置", "原文", "依据"],
    "## 覆盖证明": ["评过的模态", "规则版本", "适用控制点", "未跑的为什么"],
    "## 依据清单": ["依据编号", "来源类型", "出处", "生效期"],
    "## 未审说明": ["未审部分", "原因", "责任人"],
    "## 执行回执": ["skill", "版本", "指纹", "跳过的步骤", "规则快照"],
  };
  for (const [title, names] of Object.entries(fields)) {
    const b = block(r0.markdown, title);
    const missing = names.filter((n) => !b.includes(n));
    report(missing.length === 0, `C1/F2 ${title} 字段逐字齐全`,
           `missing=${JSON.stringify(missing)}`);
  }
  report(r0.markdown.includes("待放行"),
         "C1 放行状态固定为「待放行」", "");

  // C2 空块写「无」，不省略
  const empty = baseSnapshot();
  empty.ir.findings = [];
  empty.ir.decision.obligations = [];
  empty.ir.decision.basis = "";
  empty.ir.coverage.modalities_evaluated = [];
  empty.ir.coverage.control_points_applied = [];
  empty.ir.coverage.not_evaluated_reason = [];
  empty.evidence = [];
  empty.unassessed = [];
  empty.receipt = {};
  const r2 = R.renderReport(empty);
  report(r2.ok === true, "C2 空内容仍渲染成功", JSON.stringify(r2.errors || []));
  for (const t of R.BLOCK_TITLES) {
    report(r2.markdown.includes(t), `C2/F1 空内容不省略区块：${t}`, "");
  }
  for (const t of ["## 结论", "## 命中的问题", "## 覆盖证明", "## 依据清单", "## 未审说明", "## 执行回执"]) {
    report(block(r2.markdown, t).includes("无"), `C2/F1 ${t} 空内容写「无」`, "");
  }

  // C3 五标签群消息：每档恰好一句 + 报告链接；BLOCK 带严重度/控制点/原文/位置
  const labels = {
    BLOCK: ["L4", "H01", "未坐安全座椅", "0.1"],
    REVIEW: ["需要法务判断"],
    未审查: ["无能力"],
    待自决: ["是否修改文案"],
    PASS: ["图片"],
  };
  for (const [label, needles] of Object.entries(labels)) {
    const s = baseSnapshot();
    s.ir.decision.state = label;
    if (label === "PASS") {
      s.ir.decision.obligations = [];
      s.ir.coverage.coverage_state = "full";
    }
    const m = R.renderMessage(s);
    const text = m.text || "";
    report(m.ok === true && text && !text.includes("\n")
           && text.startsWith(`【${label}】`)
           && text.includes(s.report_url)
           && !text.includes("[[card:")
           && needles.every((n) => text.includes(n)),
           `C3 五标签消息：${label} → 一句 + 报告链接`,
           JSON.stringify({ ok: m.ok, text, errors: m.errors, warnings: m.warnings }));
  }

  // C4 四种 failure_kind 计数（全 0 也写）
  report(["fetch_error", "parse_error", "empty", "unsupported"]
         .every((k) => r0.markdown.includes(`${k}=0`)),
         "C4 四种 failure_kind 全 0 也写", "");
  const s4 = baseSnapshot();
  s4.failure_kind_counts.unsupported = 1;
  const r4 = R.renderReport(s4);
  report(r4.ok && r4.markdown.includes("unsupported=1"),
         "C4 failure_kind 非 0 正确显示", "");

  // C5 未知桶计数
  report(r0.markdown.includes("未知桶计数"),
         "C5 空未知桶也写「未知桶计数」", "");
  const s5 = baseSnapshot();
  s5.unknown_bucket_counts = { unknown_content_type: 2 };
  const r5 = R.renderReport(s5);
  report(r5.ok && r5.markdown.includes("unknown_content_type=2"),
         "C5 未知桶计数显示键与值", "");

  // C6 七条 lint 等级（四条阻断 / 三条警告）
  const lintSamples = {
    chatbotResidue: "好问题，我来回答。",
    conclusionTail: "综上所述，结论就是这样。",
    padding: "我们需要进行讨论。",
    hedgeStack: "可能 或许 大概 需要人看。",
    ruleOfThree: "今天天气不错。\n明天天气不错。\n后天天气不错。",
    connectorStack: "甲，此外，因此乙。",
    internalLeak: "tool_calls 出现在正文里。",
  };
  const expectedLevels = {
    chatbotResidue: "block", conclusionTail: "block",
    hedgeStack: "block", internalLeak: "block",
    padding: "warn", ruleOfThree: "warn", connectorStack: "warn",
  };
  for (const [id, text] of Object.entries(lintSamples)) {
    const hits = R.lintText(text, "message");
    const hit = hits.find((h) => h.id === id);
    report(hit && hit.level === expectedLevels[id],
           `C6 ${id} → ${expectedLevels[id]}`,
           JSON.stringify(hits));
  }
  const reportScope = R.lintText("我们需要进行讨论。", "report");
  report(!reportScope.some((h) => h.id === "padding"),
         "C6 padding 不适用于报告正文", JSON.stringify(reportScope));

  // C7 阻断级必须拦
  const blocking = [
    ["chatbotResidue", (s) => { s.ir.decision.basis = "好问题"; }, "report"],
    ["internalLeak", (s) => { s.ir.decision.basis = "tool_calls"; }, "report"],
    ["conclusionTail", (s) => { s.ir.decision.state = "REVIEW"; s.ir.decision.review_reason = "综上所述，需要人看"; }, "message"],
    ["hedgeStack", (s) => { s.ir.decision.state = "REVIEW"; s.ir.decision.review_reason = "可能 或许 大概 需要人看"; }, "message"],
    ["internalLeak", (s) => { s.ir.decision.state = "REVIEW"; s.ir.decision.review_reason = "[[card:query-answer]]"; }, "message"],
  ];
  for (const [id, mutate, scope] of blocking) {
    const s = baseSnapshot();
    mutate(s);
    const out = scope === "report" ? R.renderReport(s) : R.renderMessage(s);
    const hit = (out.hits || []).find((h) => h.id === id);
    report(out.ok === false && out.blocked === true && hit && hit.level === "block",
           `C7 阻断级 ${id}（${scope}）必须拦下`,
           JSON.stringify({ ok: out.ok, blocked: out.blocked, hits: out.hits, errors: out.errors }));
  }

  // C8 警告级必须照发（不许也拦）
  const s8 = baseSnapshot();
  s8.ir.findings[0].quote = "我们需要进行讨论";
  const m8 = R.renderMessage(s8);
  report(m8.ok === true && typeof m8.text === "string"
         && (m8.warnings || []).some((h) => h.id === "padding"),
         "C8 警告级 padding 照发并记录", JSON.stringify(m8));

  // C9 视频 V1 五项 + V2 三数；缺一项必须红
  const video = {
    frames: 30, duration_seconds: 60, interval_seconds: 2,
    covers: {
      字幕: "yes", 内嵌文字: "yes", 关键帧: "yes",
      音轨: "no", 完整画面语义: "partial",
    },
  };
  const s9 = baseSnapshot();
  s9.video = video;
  const r9 = R.renderReport(s9);
  report(r9.ok === true && R.V1_KEYS.every((k) => r9.markdown.includes(k))
         && r9.markdown.includes("视频已审")
         && r9.markdown.includes("30") && r9.markdown.includes("60")
         && r9.markdown.includes("2"),
         "C9 视频：V1 五项 + V2 三数齐全", JSON.stringify(r9.errors || []));
  const s9bad = baseSnapshot();
  s9bad.video = clone(video);
  delete s9bad.video.covers.音轨;
  const r9bad = R.renderReport(s9bad);
  report(r9bad.ok === false && (r9bad.errors || []).some((e) => String(e).includes("V1")),
         "R5 视频缺 V1 一项 → 红", JSON.stringify(r9bad.errors));
  const s9bad2 = baseSnapshot();
  s9bad2.video = clone(video);
  delete s9bad2.video.frames;
  const r9bad2 = R.renderReport(s9bad2);
  report(r9bad2.ok === false && (r9bad2.errors || []).some((e) => String(e).includes("V2")),
         "C9 视频缺 V2 数字 → 红", JSON.stringify(r9bad2.errors));
  const s9claim = baseSnapshot();
  s9claim.ir.decision.state = "REVIEW";
  s9claim.ir.decision.review_reason = "视频已审";
  const m9claim = R.renderMessage(s9claim);
  report(m9claim.ok === false
         && (m9claim.errors || []).some((e) => String(e).includes("V4")),
         "R5 消息说「视频已审」但无五项 → 红", JSON.stringify(m9claim.errors));

  // L1-6：PASS + coverage != full 属非法输入，报告与消息都必须拒绝
  const sL16 = baseSnapshot();
  sL16.ir.decision.state = "PASS";
  sL16.ir.coverage.coverage_state = "partial";
  const rL16 = R.renderReport(sL16);
  const mL16 = R.renderMessage(sL16);
  report(rL16.ok === false && mL16.ok === false
         && (rL16.errors || []).some((e) => String(e).includes("L1-6"))
         && (mL16.errors || []).some((e) => String(e).includes("L1-6")),
         "L1-6 PASS + coverage=partial → 报告/消息均拒绝",
         JSON.stringify({ report: rL16.errors, message: mL16.errors }));

  // C10 A-1：唯一输入，不许接活数据源；报告器不写盘；输入不被改
  const s10 = baseSnapshot();
  s10.finding_store = {};
  const r10 = R.renderReport(s10);
  report(r10.ok === false && (r10.errors || []).some((e) => String(e).includes("违规依赖")),
         "C10 塞 store → 违规依赖", JSON.stringify(r10.errors));
  const src = readFileSync(new URL("./audit/report_render.mjs", import.meta.url), "utf8");
  report(!src.includes("writeFile") && !src.includes("createWriteStream")
         && !src.includes("fetch("),
         "C10 渲染器不写盘/不联网", "");
  const before = clone(baseSnapshot());
  R.renderReport(baseSnapshot());
  report(JSON.stringify(before) === JSON.stringify(baseSnapshot()),
         "C10 渲染不改输入（冻结只读）", "");

  // C11 报告链接与卡片原字符
  const m11 = R.renderMessage(baseSnapshot());
  report(m11.ok && (m11.text || "").includes(baseSnapshot().report_url)
         && !(m11.text || "").includes("[[card:"),
         "C11 群消息带报告链接且无卡片原字符", JSON.stringify(m11.text));

  // C12/C13 ★ C-78 ①：渲染的键必须是 control_code，不是分类条目
  //
  //   ★ 这两条看的是**渲染出来的文本**，不是源码里有没有这个词。
  //     源码写了 `f.control_code` 但模板没输出它，静态扫描照样绿。
  const snap_key = baseSnapshot();
  const md_key = (R.renderReport(snap_key).markdown || "");
  report(md_key.includes("控制点：H01"),
         "C12 ★ 渲染输出以 control_code 为键（控制点：H01）",
         md_key.slice(0, 160));

  // 反向对照：给 finding 塞 subclass_code，渲染器不许拿它当键
  const snap_sub = JSON.parse(JSON.stringify(snap_key));
  snap_sub.ir.findings[0].subclass_code = "SC-99";
  const md_sub = (R.renderReport(snap_sub).markdown || "");
  report(md_sub.includes("H01") && !md_sub.includes("SC-99"),
         "C13 ★ 反向对照：带 subclass_code 时仍以 control_code 为键，subclass 不渲染",
         md_sub.slice(0, 160));

  console.log("----------------------------------------");
  if (failed === 0) {
    console.log(`✅ ${passed}/${passed + failed} 全过`);
    process.exit(0);
  }
  console.error(`❌ ${passed} passed, ${failed} failed`);
  process.exit(1);
} catch (e) {
  console.error(`UNTESTED: 验收器自身异常: ${e && e.stack ? e.stack : e}`);
  process.exit(2);
}
