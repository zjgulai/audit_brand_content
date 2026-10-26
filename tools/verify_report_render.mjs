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

// ═══════════ 变异补票（2026-10-23）═══════════
//
// 来源：PMO/audit/变异探针审计-剩余5组43行-20261023.md 第四节 —— 本验收器名下
// 有 9 条 survived：#37×3、#57×1、#58×1、#60×2、#61×1、#67×1。
// 规矩（AGENTS.md §2.4.1「没红过的断言不算验证过它」）：
//   · 每条新断言的判断逻辑拆成下面这些纯函数；
//   · `--controls` 用**同一把尺**喂坏样本（必须翻红）与好样本（不许误报）；
//   · 判断只写一份，主流程与对照共用 —— 不许两份实现各自漂移。

const V1_ENUM = ["yes", "no", "partial"]; // Playbook V1 的三种覆盖取值（C9 夹具同源）
const EXPECTED_URL = "https://example.test/reports/ir-1.md"; // baseSnapshot 的 report_url
// 判据点名的空泛话术是「请人工看一下」：
const EMPTY_REVIEW_REASONS = ["请人工看一下", "需要人工看一下"];
// ★ 词表刻意不含生产现有兜底「需要人看」（report_render.mjs 渲染空 review_reason 时
//   仍会输出它）—— 判据点名的是「请人工看一下」这个形状；把「需要人看」一并收进来
//   会让基线常红，而那要等生产把兜底改成具体原因类别才能修，不在本行范围内
//   （生产侧缺口已登记在 rows note，不是被静默吸收）。

/** #37 V2：三个数必须带单位出现在视频行里（60s / 2s；抽帧数不带 s）。 */
function hasUnits(md) {
  return Boolean(md_videoNum(md, "duration")) && Boolean(md_videoNum(md, "interval"));
}

/** #37b V1 值枚举：返回不在 yes/no/partial 里的键（空数组 = 全部在枚举内）。 */
function V1_KEYS_OUTSIDE(covers) {
  return Object.keys(covers || {}).filter((k) => !V1_ENUM.includes(covers[k]));
}

/** 从视频行抠出 duration/interval 数值；抠不到返回 null（由调用方判红）。 */
function md_videoNum(md, which) {
  const line = (md || "").split("\n").find((l) => l.includes("总时长"));
  if (!line) return null;
  const m = which === "duration"
    ? line.match(/总时长：(\d+(?:\.\d+)?)s/)
    : line.match(/抽帧间隔：(\d+(?:\.\d+)?)s/);
  return m ? m[1] : null;
}

/** #37 V4 文案掩蔽修复：V1 缺键错误必须逐键点名（`V1 视频 covers 缺项：<键>`）。 */
function v1MissingKeys(errors) {
  const names = [];
  for (const e of errors || []) {
    const m = String(e).match(/V1 视频 covers 缺项：(.+)$/);
    if (m) names.push(...m[1].split("、"));
  }
  return names;
}

/** #60a BLOCK：消息里那条命中必须与 IR 里最高严重度的 confirmed 逐字一致。 */
function blockWorstMatches(snapshot, text) {
  const confirmed = (snapshot.ir.findings || []).filter((f) => f.status === "confirmed");
  const pool = confirmed.length ? confirmed : (snapshot.ir.findings || []);
  const worst = pool.slice().sort(
    (a, b) => (SEV_RANK[b.severity] || 0) - (SEV_RANK[a.severity] || 0),
  )[0];
  if (!worst) return false;
  return String(text || "").includes(worst.severity)
    && String(text || "").includes(worst.control_code)
    && String(text || "").includes(worst.quote);
}

const SEV_RANK = { L0: 0, L1: 1, L2: 2, L3: 3, L4: 4, L5: 5 };

/** #60b/#67 判红尺：给定文本，返回命中的禁则（空数组 = 通过）。 */
function textViolations(text) {
  const s = String(text || "");
  const out = [];
  if (EMPTY_REVIEW_REASONS.some((w) => s.includes(w))) {
    out.push("空泛话术：请人工看一下");
  }
  for (const w of V4_FORBIDDEN) {
    if (s.includes(w)) out.push(`未审文案冒充已审：${w}`);
  }
  return out;
}

// 判据 #67 点名的表述族（「等表述」按同一语义收）：B65 的四个词 + PASS 标签。
const V4_FORBIDDEN = ["已审", "已通过", "没问题", "无需处理", "审批完成", "【PASS】"];

/** #61：按 。 切句，取【标签】与「 · 报告：」之间的句子数。 */
function sentenceCount(text) {
  const m = String(text || "").match(/^【([^】]+)】([\s\S]*?) · 报告：/);
  if (!m) return -1;
  const body = m[2];
  const parts = body.split("。").filter((p) => p.trim().length > 0);
  return parts.length;
}

/**
 * #61 主判据（判据原文）：
 *   ① 「按约定的句子边界切分，恰有 1 个句子」—— 。 是句界；
 *   ② 「消息由模板从结构化字段生成」—— 五档各有一句**模板句**，
 *      结构化字段替换进固定骨架；模板之外的内容（自由文本尾巴）就是第二句。
 * 实测：往 text 里塞「 另请尽快处理。」的变异在 。 口径下合并成了一句（survived），
 * 但它**破坏了模板骨架** —— 骨架对拍后必红。这就是判据 ② 的执行点。
 */
function messageTemplateShape(text, state, expectedTail) {
  const head = `【${state}】`;
  if (!String(text || "").startsWith(head)) return false;
  const tail = ` · 报告：${EXPECTED_URL}`;
  if (!String(text).endsWith(tail)) return false;
  return String(text).slice(head.length, text.length - tail.length) === expectedTail;
}

/** #58：md 命中块的每条 finding_id 必须指得回 IR。 */
function findingIdsResolvable(md, ir) {
  const sec = section(md, "## 命中的问题");
  if (sec === null) return false;
  const known = new Set((ir.findings || []).map((f) => f.finding_id));
  const listed = [...sec.matchAll(/^- ([^·]+?) · 控制点：/gm)].map((m) => m[1].trim());
  return listed.length > 0 && listed.every((id) => known.has(id));
}

/** 按标题切出区块内容；没有该标题返回 null（与 block() 的 "" 区分开）。 */
function section(md, title) {
  const i = (md || "").indexOf(title);
  if (i < 0) return null;
  const rest = md.slice(i + title.length);
  const j = rest.search(/^## /m);
  return j < 0 ? rest : rest.slice(0, j);
}

/** #57：md 结论块的状态必须与 IR.decision.state 逐字一致。 */
function mdStateMatchesIr(md, state) {
  const sec = section(md, "## 结论");
  if (sec === null) return false;
  const m = sec.match(/^- 状态：(.+)$/m);
  return Boolean(m) && m[1].trim() === String(state);
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

  // ── C4b（验收表 #62 · M4）并行义务短标记：成对正反 ─────────────────────
  //
  // 验收表原文：「构造『BLOCK + has_candidate=true』样本，断言消息在关键句后
  // 出现对应并行义务标记（如『· 另有 1 条疑似待确认』）且数量/类别正确；
  // 构造无并行义务样本，断言不出现该标记（反向对照）。」
  //
  // ★ 2026-10-24 补。此前 `renderMessage` 一次都没读过 `decision.obligations`，
  //   群消息里也没有 candidate 计数 —— 这条要求从未实现，验证器也 0 断言。
  //
  // ★ 只测「有义务时出现标记」是不够的：一个**永远打标记**的实现也能过。
  //   所以第二条必须断言「无义务 + 0 candidate 时**不出现**」。
  {
    const withOb = baseSnapshot();
    withOb.ir.decision.state = "BLOCK";
    withOb.ir.decision.obligations = ["partial_coverage"];
    withOb.ir.findings = [
      { ...baseSnapshot().ir.findings[0] },
      {
        ...baseSnapshot().ir.findings[0],
        finding_id: "f-2",
        status: "candidate",
        produced_by: "semantic",
        confirmed_by_rule_class: true,
      },
    ];
    const mOb = R.renderMessage(withOb);
    const tOb = mOb.text || "";
    // 数量必须对：1 条 candidate → 「另有 1 条」，不是「另有 2 条」也不是笼统一句
    report(mOb.ok === true
           && tOb.includes("另有 1 条疑似待确认")
           && tOb.includes("部分覆盖")
           // 标记必须在**关键句之后、报告链接之前**（不是拼在末尾当脚注）
           && tOb.indexOf("另有 1 条") > tOb.indexOf("H01")
           && tOb.indexOf("另有 1 条") < tOb.indexOf("· 报告："),
           "C4b★ BLOCK+1 条 candidate → 并行义务短标记出现且数量正确",
           JSON.stringify({ ok: mOb.ok, text: tOb }));

    const noOb = baseSnapshot();
    noOb.ir.decision.state = "BLOCK";
    noOb.ir.decision.obligations = [];
    noOb.ir.findings = [{ ...baseSnapshot().ir.findings[0] }];   // 0 条 candidate
    const mNo = R.renderMessage(noOb);
    const tNo = mNo.text || "";
    report(mNo.ok === true
           && !tNo.includes("另有")
           && !tNo.includes("部分覆盖")
           && !tNo.includes("疑似待确认"),
           "C4b★ 反向对照：无并行义务 → 短标记不出现",
           JSON.stringify({ ok: mNo.ok, text: tNo }));

    // 第二条反向对照：2 条 candidate → 数量必须跟着变（证明它真在数）
    const twoOb = baseSnapshot();
    twoOb.ir.decision.state = "BLOCK";
    twoOb.ir.decision.obligations = [];
    twoOb.ir.findings = [
      { ...baseSnapshot().ir.findings[0] },
      { ...baseSnapshot().ir.findings[0], finding_id: "f-2", status: "candidate" },
      { ...baseSnapshot().ir.findings[0], finding_id: "f-3", status: "candidate" },
    ];
    const mTwo = R.renderMessage(twoOb);
    report(mTwo.ok === true && (mTwo.text || "").includes("另有 2 条疑似待确认"),
           "C4b★ 2 条 candidate → 计数变成 2（证明真在数，不是写死）",
           JSON.stringify({ text: mTwo.text }));
  }

  // ── C4c（验收表 #66 · L4-1 SEC-8-8）最严重 finding 不被数量吞掉 ─────────
  //
  // 验收表原文：「用 L 刻度构造『1 个 confirmed L4/L5 + 2 个 L1/L2』的样本
  // （不用 P），跑输出，断言群里消息直接显示那条 L4/L5 的严重度、控制点、
  // 逐字原文、位置，而不是只出分类汇总；若只出汇总或最严重条被数量盖掉即红。」
  //
  // ★ 2026-10-24 补。此前 `baseSnapshot()` 的 findings 数组**只有 1 条**，
  //   于是「按 severity 挑最严重那条」这个行为**从未被测过** ——
  //   把 `worstFinding` 改成 `findings[0]` 也照样全绿。
  {
    const mix = baseSnapshot();
    mix.ir.decision.state = "BLOCK";
    mix.ir.decision.obligations = [];
    const L4 = {
      ...baseSnapshot().ir.findings[0],
      finding_id: "f-mid",
      control_code: "H07",
      severity: "L4",
      quote: "国家级认证",
      location: { type: "image", bbox: [0.3, 0.3, 0.5, 0.5] },
    };
    // ★ 顺序刻意让 L1/L2 排在最前 —— 若实现是「取第一条」，这里必红
    mix.ir.findings = [
      { ...baseSnapshot().ir.findings[0], finding_id: "f-low1", control_code: "H02",
        severity: "L1", quote: "轻微提示一", location: { type: "image", bbox: [0.7, 0.7, 0.8, 0.8] } },
      { ...baseSnapshot().ir.findings[0], finding_id: "f-low2", control_code: "H03",
        severity: "L2", quote: "轻微提示二", location: { type: "image", bbox: [0.9, 0.1, 0.95, 0.2] } },
      L4,
    ];
    const mMix = R.renderMessage(mix);
    const tMix = mMix.text || "";
    report(mMix.ok === true
           && tMix.includes("L4")
           && tMix.includes("H07")
           && tMix.includes("国家级认证")
           && tMix.includes("0.3")
           // 不许被前两条吞掉：消息里不该出现低危那条的原文/控制点
           && !tMix.includes("H02")
           && !tMix.includes("H03"),
           "C4c★ 1×L4 + 2×L1/L2 → 群里显示的是 L4 那条（不被顺序与数量吞掉）",
           JSON.stringify({ ok: mMix.ok, text: tMix }));

    // 反向对照：删掉 L4 那条，消息必须变（证明它真在按 severity 挑，
    // 而不是「恰好因为数组里只有一条能打印」）
    const noL4 = baseSnapshot();
    noL4.ir.decision.state = "BLOCK";
    noL4.ir.decision.obligations = [];
    noL4.ir.findings = [
      mix.ir.findings[0],
      mix.ir.findings[1],
    ];
    const mNoL4 = R.renderMessage(noL4);
    report(mNoL4.ok === true
           && !(mNoL4.text || "").includes("H07")
           && !(mNoL4.text || "").includes("国家级认证")
           && (mNoL4.text || "").includes("L2"),
           "C4c★ 反向对照：删掉 L4 → 消息随之改变（按 severity 挑，不是取第一条）",
           JSON.stringify({ text: mNoL4.text }));
  }

  // ── C4d（验收表 #66 后半 · L4-1 SEC-8-8）多条同质 finding 不刷屏 ───────
  //
  // 验收表 #66 原文第二句：「**再构造多条同质 finding，断言群消息仍按 M1
  // 只有一句、不逐条刷屏。**」
  //
  // ★ 2026-10-24 05 指出：这一句与 #60 的覆盖**不重叠** ——
  //   #60 判据原文是「对五个标签**各构造一条**消息」，单条口径；
  //   #66 后半是多条口径。`#60a` 只覆盖了 #66 的前半（取最严重那条）。
  //   此前 `verify_report_render.mjs` 里**没有任何「多条同质 finding」的样本**，
  //   这一句从未有执行点。
  //
  // 关掉它的最小条件（05 给的口径）：3 条同质 confirmed finding，
  // 断言 `【BLOCK】` 在消息里只出现一次、命中行只有一条。
  {
    const homo = baseSnapshot();
    homo.ir.decision.state = "BLOCK";
    homo.ir.decision.obligations = [];
    // 三条同质：同控制点、同严重度、同原文 —— 「同质」是指它们不构成区分度，
    // 若实现按数组长度循环输出，就会重复三遍同样的句子。
    const base = baseSnapshot().ir.findings[0];
    homo.ir.findings = [0, 1, 2].map((i) => ({
      ...base,
      finding_id: `f-homo-${i}`,
    }));
    const mHomo = R.renderMessage(homo);
    const tHomo = mHomo.text || "";
    const labelCount = (tHomo.match(/【BLOCK】/g) || []).length;
    // 「命中行」= 消息里出现控制点的次数。三者同质，正确实现只该出现一次。
    const hitCount = (tHomo.match(/H01/g) || []).length;
    report(
      mHomo.ok === true
        && labelCount === 1
        && hitCount === 1
        && !tHomo.includes("\n"),
      "C4d★ 3 条同质 finding → 群消息仍只有一句（【BLOCK】1 次、命中 1 条，不逐条刷屏）",
      JSON.stringify({ ok: mHomo.ok, labelCount, hitCount, text: tHomo }),
    );

    // 反向对照：单条 finding 时同样是 1 次 —— 若判据写成「恰好 3 条就输出 3 次」
    // 或「条数必须 > 1 才通过」，这条会露出它其实没在数。
    const one = baseSnapshot();
    one.ir.decision.state = "BLOCK";
    one.ir.decision.obligations = [];
    one.ir.findings = [{ ...base }];
    const mOne = R.renderMessage(one);
    const tOne = mOne.text || "";
    report(
      mOne.ok === true
        && (tOne.match(/【BLOCK】/g) || []).length === 1
        && (tOne.match(/H01/g) || []).length === 1,
      "C4d★ 反向对照：1 条 finding 也是 1 次（证明不是按条数循环输出）",
      JSON.stringify({ text: tOne }),
    );
  }

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

  // ── 变异补票 #63：2 层 hedge 堆叠必须**不**触发（负样本）──
  // 判据原文：「再构造 2 层 hedge 堆叠样本断言不触发」。没有这条负样本时，
  // 阈值 3→2 的变异无人发现（实测 survived）。两层=不触发、三层=阻断，两边都得站住。
  report(R.lintText("可能 或许 需要人看。", "message").every((h) => h.id !== "hedgeStack"),
         "C6/#63 2 层 hedge 不触发（负样本）",
         JSON.stringify(R.lintText("可能 或许 需要人看。", "message")));
  report(R.lintText("可能 或许 大概 需要人看。", "message")
           .some((h) => h.id === "hedgeStack" && h.level === "block"),
         "C6/#63 3 层 hedge 仍阻断（正向不松动）", "");

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

  // ── 变异补票 #37a：V1 五键逐键负样本，错误必须**逐键点名**该键 ──
  // 背景：V4 文案含子串 V1，`includes("V1")` 会被顺带满足 —— 那是掩蔽不是独立验证。
  // 修法：断言错误文本恰为 `V1 视频 covers 缺项：<键>`，且五个键各构造一次。
  {
    let allNamed = true;
    const detail = {};
    for (const key of R.V1_KEYS) {
      const s = baseSnapshot();
      s.video = clone(video);
      delete s.video.covers[key];
      const r = R.renderReport(s);
      const named = v1MissingKeys(r.errors);
      detail[key] = named;
      if (!(r.ok === false && named.includes(key))) allNamed = false;
    }
    report(allNamed, "#37a V1 逐键负样本：错误必须点名缺失键",
           JSON.stringify(detail));
    // 旧 R5 那条子串匹配继续保留，但它不再独自承担 V1 这一支
  }

  // ── 变异补票 #37b：覆盖声明必须如实回显输入的 covers ──
  // 注：生产 validateSnapshot 目前**只查键存在、不查值域**（report_render.mjs 的 V1
  //   循环里没有取值检查）——「值属于约定枚举」这一半需要生产实现才能直接断言，
  //   未实现（AGENTS.md §2.4：不许写恒真断言充数，缺已在 note 登记）。
  //   这里断言可观察的另一半：md 里的 `<键>=<值>` 必须等于输入 snapshot.video.covers
  //   的值 —— 值被硬编码（全部写成 yes）时此处必红。
  {
    const s = baseSnapshot(); // fixture：音轨=no、完整画面语义=partial（枚举内取值）
    s.video = clone(video);
    const r = R.renderReport(s);
    const line = (r.markdown || "").split("\n").find((l) => l.includes("视频已审")) || "";
    const echoed = R.V1_KEYS.every((k) => line.includes(`${k}=${s.video.covers[k]}`));
    report(r.ok === true && echoed,
           "#37b 视频覆盖值如实回显输入（音轨=no、完整画面语义=partial）",
           line || "(无视频行)");
    const outside = V1_KEYS_OUTSIDE(s.video.covers);
    report(outside.length === 0,
           "#37b fixture 取值在枚举内（yes/no/partial）", JSON.stringify(outside));
  }

  // ── 变异补票 #37c：三个数都存在且**单位明确**（60s / 2s）──
  report(r9.ok === true && hasUnits(r9.markdown) && r9.markdown.includes("抽帧数：30"),
         "#37c 视频 V2 三数带单位（总时长 60s / 间隔 2s）",
         (r9.markdown || "").split("\n").find((l) => l.includes("总时长")) || "");
  {
    const s = baseSnapshot();
    s.video = clone(video);
    s.video.duration_seconds = 60;
    s.video.interval_seconds = 2;
    const r = R.renderReport(s);
    report(r.ok === true && md_videoNum(r.markdown, "duration") === "60"
           && md_videoNum(r.markdown, "interval") === "2",
           "#37c 视频行数值可解析且来自 60/2", "");
  }

  // ── 变异补票 #57：md 状态必须与 IR.decision.state 对拍（BLOCK fixture）──
  {
    const s = baseSnapshot(); // decision.state = "BLOCK"
    const r = R.renderReport(s);
    report(r.ok === true && mdStateMatchesIr(r.markdown, "BLOCK"),
           "#57 md 结论块状态 == IR.decision.state（BLOCK）", "");
    const s2 = withIr({ decision: { ...baseSnapshot().ir.decision, state: "待自决" } });
    const r2 = R.renderReport(s2);
    report(r2.ok === true && mdStateMatchesIr(r2.markdown, "待自决"),
           "#57 md 结论块状态 == IR.decision.state（待自决）", "");
  }

  // ── 变异补票 #58：命中块逐条 finding_id 必须指得回 IR ──
  {
    const s = baseSnapshot();
    s.ir.findings.push({
      finding_id: "f-2", control_code: "H02", status: "candidate", severity: "L2",
      produced_by: "rule", derived_from: null, authority_state: "ok",
      detected_by: "P1", location: { type: "image", bbox: [0.5, 0.5, 0.6, 0.6] },
      quote: "第二处", evidence_id: "E-1",
    });
    const r = R.renderReport(s);
    report(r.ok === true && findingIdsResolvable(r.markdown, s.ir),
           "#58 命中块 finding_id 全部指回 IR（f-1,f-2）", "");
  }

  // ── 变异补票 #60b：REVIEW 原因为空的坏样本 → 消息不许落进空泛话术 ──
  // 判据原文点名的空泛话术就是「请人工看一下」；兜底改成它时这条必须红。
  {
    const s = baseSnapshot();
    s.ir.decision.state = "REVIEW";
    s.ir.decision.review_reason = ""; // 原因为空（判据点名的反向对照样本）
    const m = R.renderMessage(s);
    const v = textViolations(m.text || "");
    report(m.ok === true && v.length === 0,
           "#60b REVIEW 空原因 → 消息不含空泛话术（请人工看一下）",
           JSON.stringify({ text: m.text, violations: v }));
  }

  // ── 变异补票 #60a：BLOCK 取最高严重度（双 finding fixture）──
  {
    const s = baseSnapshot();
    s.ir.findings.push({
      finding_id: "f-5", control_code: "H05", status: "confirmed", severity: "L5",
      produced_by: "rule", derived_from: null, authority_state: "ok",
      detected_by: "P2", location: { type: "image", bbox: [0.7, 0.7, 0.8, 0.8] },
      quote: "五级命中", evidence_id: "E-1",
    });
    const m = R.renderMessage(s);
    report(m.ok === true && blockWorstMatches(s, m.text),
           "#60a BLOCK 消息取最高严重度 finding（L5/H05/五级命中）",
           JSON.stringify(m.text));
    const sAlt = baseSnapshot();
    sAlt.ir.findings[0].severity = "L1";
    sAlt.ir.findings[0].control_code = "H99";
    sAlt.ir.findings[0].quote = "一级命中";
    sAlt.ir.findings.push({
      finding_id: "f-5", control_code: "H05", status: "confirmed", severity: "L5",
      produced_by: "rule", derived_from: null, authority_state: "ok",
      detected_by: "P2", location: { type: "image", bbox: [0.7, 0.7, 0.8, 0.8] },
      quote: "五级命中", evidence_id: "E-1",
    });
    const mAlt = R.renderMessage(sAlt);
    report(mAlt.ok === true && mAlt.text.includes("L5") && mAlt.text.includes("H05")
           && mAlt.text.includes("五级命中") && !mAlt.text.includes("L1")
           && !mAlt.text.includes("H99") && !mAlt.text.includes("一级命中"),
           "#60a 双 finding 取 L5 不取 L1（反向：消息不含低级那条）",
           JSON.stringify(mAlt.text));
  }

  // ── 变异补票 #61：BLOCK/REVIEW 消息恰一句（。切句）──
  {
    const sB = baseSnapshot();
    const mB = R.renderMessage(sB);
    report(sentenceCount(mB.text) === 1, "#61 BLOCK 消息【标签】与链接间恰 1 句",
           `sentenceCount=${sentenceCount(mB.text)} text=${mB.text}`);
    const sR = baseSnapshot();
    sR.ir.decision.state = "REVIEW";
    sR.ir.decision.review_reason = "需要法务判断";
    const mR = R.renderMessage(sR);
    report(sentenceCount(mR.text) === 1, "#61 REVIEW 消息恰 1 句",
           `sentenceCount=${sentenceCount(mR.text)}`);
    // 坏样本：2 句 review_reason → 消息文本含 2 句，尺子必须数得出来
    report(sentenceCount("【REVIEW】原因一。原因二。 · 报告：https://x") === 2,
           "#61 坏样本 2 句 → 尺子数出 2（检测器自身非恒真）", "");
    // 换行折叠契约：review_reason 带换行进来，消息必须把换行折掉（不破句界也不破单行）
    {
      const sN = baseSnapshot();
      sN.ir.decision.state = "REVIEW";
      sN.ir.decision.review_reason = "需要法务判断\n另请核实时间线";
      const mN = R.renderMessage(sN);
      report(mN.ok === true && !mN.text.includes("\n") && sentenceCount(mN.text) === 1,
             "#61b 多行 review_reason → 消息仍单行（换行被折叠）",
             JSON.stringify(mN.text));
    }
    // 模板骨架对拍（判据②的执行点）：五档各等于「【标签】+ 固定骨架字段句 +
    // ` · 报告：` + URL」。骨架外多出的尾巴（哪怕不带 。）→ 对拍不等 → 红。
    {
      const withState = (state) => withIr({
        decision: {
          ...baseSnapshot().ir.decision,
          state,
          // ★ 2026-10-24：这一组测的是「模板骨架逐字」，不是并行义务标记
          //   （那是 #62 / C4b 自己的成对角逐）。骨架对拍必须在不含标记的
          //   样本上做，否则测的就变成「标记也拼进了骨架」——
          //   而那是另一个断言，混在一起会让两条判据互相掩护。
          obligations: [],
        },
      });
      const five = [
        ["BLOCK", withState("BLOCK"), "L4 · H01 · “未坐安全座椅” · 位置：bbox=[0.1,0.2,0.4,0.6]"],
        ["REVIEW", withState("REVIEW"), "需要法务判断"],
        ["未审查", withState("未审查"), "视频音轨：无能力"],
        ["待自决", withState("待自决"), "是否修改文案"],
        ["PASS", withIr({
          decision: { ...baseSnapshot().ir.decision, state: "PASS", obligations: [] },
          coverage: { ...baseSnapshot().ir.coverage, coverage_state: "full" },
        }), "覆盖：图片"],
      ];
      for (const [state, s, body] of five) {
        const m = R.renderMessage(s);
        const shape = messageTemplateShape(m.text, state, body)
          ? true
          : `≠模板：${JSON.stringify(m.text)}`;
        report(m.ok === true && shape === true,
               `#61c ${state} 消息 = 模板骨架逐字对拍`, String(shape));
      }
    }
  }

  // ── 变异补票 #60b/#67：未审/REVIEW 文案过禁词尺（好样本不许误报）──
  {
    const mB0 = R.renderMessage(baseSnapshot());
    const mU0 = (() => {
      const s = baseSnapshot();
      s.ir.decision.state = "未审查";
      return R.renderMessage(s);
    })();
    report(mB0.ok === true && textViolations(mB0.text).length === 0
           && mU0.ok === true && textViolations(mU0.text).length === 0,
           "#60b/#67 好 BLOCK/未审查 消息过禁词尺（不许误报）",
           JSON.stringify({ b: textViolations(mB0.text), u: textViolations(mU0.text) }));
  }

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

  // ── 变异补票 #67：未审文案不许冒充已审（词表断言，报告 + 消息两侧）──
  {
    const u = baseSnapshot().unassessed[0];
    const snapshots = [];
    // 未审查消息：part/reason 原文直进正文
    {
      const s = baseSnapshot();
      s.ir.decision.state = "未审查";
      snapshots.push(R.renderMessage(s));
    }
    // 报告「未审说明」区块文本（parse_status=failed 与 coverage missing 两个来源）
    {
      const s = baseSnapshot();
      s.unassessed = [
        u,
        { part: "解析失败的内容", reason: "parse_status=failed", owner: "media_pipeline" },
        { part: "覆盖缺口的内容", reason: "coverage missing", owner: "media_pipeline" },
      ];
      snapshots.push(R.renderReport(s));
    }
    // BLOCK 报告全文也在词表检查范围内（判据说的是「未审样本中」的生成文案）
    {
      const s = baseSnapshot();
      snapshots.push(R.renderReport(s));
    }
    const bad = [];
    for (const out of snapshots) {
      const txt = out.text != null ? out.text : (out.markdown || "");
      if (!out.ok) bad.push({ notOk: true, errors: out.errors });
      else for (const v of textViolations(txt)) bad.push({ v, sample: txt.slice(0, 60) });
    }
    report(bad.length === 0,
           "#67 未审文案词表断言（已审/已通过/没问题/…）零命中",
           JSON.stringify(bad));
  }

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

  // ── T-433：画面语义成节（L1 观察，候选 · 待人工确认）─────────────
  //
  //   ★ 断言全部看**渲染出来的文本**，不看源码里有没有这个词 ——
  //     源码写了 snapshot.multimodal_observations 但模板没输出它，静态扫描照样绿。
  const obsSnap = baseSnapshot();
  obsSnap.multimodal_observations = [
    { status: "ok", task: "scene_semantics", statement: "画面演示婴儿睡眠场景",
      confidence: 0.82, bbox: "中央", model: "glm-5.3-flash" },
    { status: "ok", task: "mark_symbol", statement: "背景出现认证徽章",
      confidence: 0.4, model: "glm-5.3-flash" },
  ];
  const md_obs = (R.renderReport(obsSnap).markdown || "");
  report(md_obs.includes("## 画面语义"), "T433-1 有观察时渲染画面语义节", "");
  report(md_obs.includes("候选") && md_obs.includes("待人工确认"),
         "T433-2 ★ 措辞逐字含「候选」与「待人工确认」", "");
  report(md_obs.includes("画面演示婴儿睡眠场景")
         && md_obs.includes("背景出现认证徽章"),
         "T433-3 每条观察逐字进报告", "");
  report(md_obs.includes("0.82"), "T433-4 带置信度时渲染出来", "");
  report(!md_obs.includes("已通过") && !md_obs.includes("画面语义正常")
         && !md_obs.includes("画面正常"),
         "T433-5 ★★ 不许出现「已通过 / 画面语义正常 / 画面正常」这类冒充表述", "");

  // 空观察 + note：必须是「未评」，不许写「正常」
  const emptyObs = baseSnapshot();
  emptyObs.multimodal_observations = [];
  emptyObs.multimodal_note = "未接入多模态分析";
  const md_empty = (R.renderReport(emptyObs).markdown || "");
  report(md_empty.includes("## 画面语义"), "T433-6 无观察时该节仍在（不整节省略）", "");
  report(md_empty.includes("未评"), "T433-7 ★★ 无观察 → 写「未评」，不写「正常」", "");
  report(md_empty.includes("未接入多模态分析"),
         "T433-8 未评要带原因（note 逐字渲染）", "");
  report(!md_empty.includes("画面正常") && !md_empty.includes("没有问题"),
         "T433-9 ★★ 空观察绝不许读成「画面正常」", "");

  // 只有失败/未测观察：必须逐条给原因，且不许落成「无有效观察」就完事
  const badObs = baseSnapshot();
  badObs.multimodal_observations = [
    { status: "untested", task: "scene_semantics",
      reason: "provider 未返回该任务的结果（overall=untested）" },
    { status: "error", task: "mark_symbol", reason: "网关返回 HTTP 429" },
  ];
  const md_bad = (R.renderReport(badObs).markdown || "");
  report(md_bad.includes("429") && md_bad.includes("provider 未返回该任务的结果"),
         "T433-10 ★ 未测/出错条目逐条渲染原因（未评不是没问题）", "");
  report(md_bad.includes("未评"), "T433-11 失败观察也落「未评」措辞", "");

  console.log("----------------------------------------");
  const ranControls = process.argv.includes("--controls");
  const controlsOk = ranControls ? checkControls(report) : null;
  console.log(`controls_ok: ${controlsOk === null ? "未测（加 --controls 跑反向对照）" : controlsOk}`);
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

/* ═══════════ --controls：新断言的反向对照 ═══════════
 *
 * AGENTS.md §2.4.1：没红过的断言不算验证过它。上面主流程的新断言每条都要在这里
 * 喂一次**坏样本**（尺子必须翻红）+ 一次**好样本**（不许误报）。坏样本直接喂给
 * 上面的纯函数（主流程用的同一把尺），能红 = 尺子真的在判；好样本必须绿。
 *
 * 判定：0 全过 / 1 有对照不红（新断言是恒真的） / 2 未测。
 */

import process from "node:process";

function checkControls(reportFn) {
  let cp = 0;
  let cf = 0;

  // 统一口径：fn 返回 pass（= 输入表现符合要求，断言会放行）。
  // badMustRed=true 的行：pass 必须是 false（尺子把它判红）才算对照成立。
  function probe(name, badMustRed, fn) {
    let pass;
    try {
      pass = fn() === true;
    } catch (e) {
      reportFn(false, `CTRL ${name}`, `自身异常: ${e && e.message}`);
      cf++;
      return;
    }
    const okNow = badMustRed ? !pass : pass;
    reportFn(okNow, `CTRL ${badMustRed ? "坏样本必须红" : "好样本不许红"}：${name}`,
             `pass=${pass}`);
    if (okNow) cp++;
    else cf++;
  }

  // #37a 尺（v1MissingKeys）：掩蔽形状 —— V4 文案错误不含逐键点名 → 必须判红
  probe("V1 缺键错误未逐键点名（V4 掩蔽形状）", true, () => {
    const named = v1MissingKeys(["V4「视频已审」必须带 V1 五项，缺：音轨"]);
    return named.includes("音轨");
  });
  probe("V1 缺键错误逐键点名（正向）", false, () => {
    const named = v1MissingKeys(["V1 视频 covers 缺项：音轨"]);
    return named.includes("音轨") && named.length === 1;
  });

  // #37b V1 值枚举（坏样本直接喂枚举判定，与 #37b 同一把尺）
  probe("V1 值域外（covers.字幕=不一定）→ 枚举判定红", true, () => {
    const covers = { 字幕: "不一定", 内嵌文字: "yes", 关键帧: "yes", 音轨: "no", 完整画面语义: "partial" };
    return V1_KEYS_OUTSIDE(covers).length === 0;
  });
  probe("V1 值在枚举内 → 枚举判定绿（不许误报）", false, () => {
    const covers = { 字幕: "yes", 内嵌文字: "no", 关键帧: "partial", 音轨: "yes", 完整画面语义: "no" };
    return V1_KEYS_OUTSIDE(covers).length === 0;
  });

  // #37c 单位尺
  probe("视频行单位被删（总时长：60 无 s）→ 尺红", true, () =>
    hasUnits("- 抽帧数：30；总时长：60；抽帧间隔：2s"));
  probe("视频行带单位（60s/2s）→ 尺绿", false, () =>
    hasUnits("- 抽帧数：30；总时长：60s；抽帧间隔：2s"));

  // #57 状态对拍尺
  probe("md 状态与 IR 不一致（硬编码 PASS 假绿形状）→ 尺红", true, () =>
    mdStateMatchesIr("## 结论\n- 状态：PASS\n- 放行状态：待放行", "BLOCK"));
  probe("md 状态与 IR 一致 → 尺绿", false, () =>
    mdStateMatchesIr("## 结论\n- 状态：BLOCK\n- 放行状态：待放行", "BLOCK"));

  // #58 finding_id 反查尺
  probe("命中行缺 finding_id（指不回 IR）→ 尺红", true, () =>
    findingIdsResolvable(
      "## 命中的问题\n- 控制点：H01 · 严重度：L4 · 确认状态：confirmed\n",
      { findings: [{ finding_id: "f-1" }] },
    ));
  probe("命中行 finding_id 指回 IR → 尺绿", false, () =>
    findingIdsResolvable(
      "## 命中的问题\n- f-1 · 控制点：H01 · 严重度：L4\n",
      { findings: [{ finding_id: "f-1" }] },
    ));

  // #60a 最高严重度尺
  probe("BLOCK 消息取低严重度那条（丢 L5 取 L4）→ 尺红", true, () => {
    const snap = {
      ir: { findings: [
        { finding_id: "f-1", control_code: "H01", status: "confirmed", severity: "L4", quote: "四" },
        { finding_id: "f-2", control_code: "H02", status: "confirmed", severity: "L5", quote: "五" },
      ] },
    };
    return blockWorstMatches(snap, "【BLOCK】L4 · H01 · “四” · 报告：https://x");
  });
  probe("BLOCK 消息取最高严重度那条 → 尺绿", false, () => {
    const snap = {
      ir: { findings: [
        { finding_id: "f-1", control_code: "H01", status: "confirmed", severity: "L4", quote: "四" },
        { finding_id: "f-2", control_code: "H02", status: "confirmed", severity: "L5", quote: "五" },
      ] },
    };
    return blockWorstMatches(snap, "【BLOCK】L5 · H02 · “五” · 报告：https://x");
  });

  // #60b 空泛话术尺
  probe("REVIEW 原因是空泛话术「请人工看一下」→ 尺红", true, () =>
    textViolations("【REVIEW】请人工看一下 · 报告：https://x").length === 0);
  probe("REVIEW 原因具体（需要法务判断）→ 尺绿", false, () =>
    textViolations("【REVIEW】需要法务判断 · 报告：https://x").length === 0);

  // #61 句数尺
  probe("消息正文两句（2 句坏样本）→ 尺红", true, () =>
    sentenceCount("【REVIEW】原因一。原因二。 · 报告：https://x") === 1);
  probe("消息正文一句 → 尺绿", false, () =>
    sentenceCount("【BLOCK】L4 · H01。 · 报告：https://x") === 1);

  // #67 冒充已审词表尺
  for (const word of V4_FORBIDDEN) {
    probe(`未审文案含「${word}」→ 词表尺红`, true, () =>
      textViolations(`未审说明：视频音轨（无能力）${word}`).length === 0);
  }
  probe("未审文案干净（无冒充表述）→ 词表尺绿", false, () =>
    textViolations("未审说明：视频音轨（无能力）责任人：media_pipeline").length === 0);

  console.log("----------------------------------------");
  if (cf === 0) {
    console.log(`✅ controls ${cp}/${cp + cf} 全过`);
    return true;
  }
  console.error(`❌ controls ${cp} passed, ${cf} failed`);
  return false;
}
