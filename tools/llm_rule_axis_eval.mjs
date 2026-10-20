#!/usr/bin/env node
/**
 * llm_rule_axis_eval.mjs —— 用 LLM 做「规则 → 七轴」归类的评测器
 *
 * 契约来源：`PMO/implement/规则归类-LLM提示词-v1.md`。本文件是它的**执行点**：
 * 提示词、输入白名单、禁用字段、输出契约、门槛，四者在这里各有一行代码。
 *
 * 为什么要有这个文件（而不是直接跑一段临时脚本）：
 *   纯文本分类器拆掉泄漏后真实基线是 axis_exact 22.07% / UNKNOWN 57.42%，已实测不可用。
 *   改用 LLM 之后，「模型能不能做这件事」本身必须有个可复现的读数，
 *   否则「改用 LLM」就只是一句打算。
 *
 * ── 三条纪律，各自有断言（`--selftest` 里逐条正反例）────────────────
 *
 * ① **输入白名单**。`primary_initial` / `primary_reviewed` / `quality_tag` /
 *    `policy_fragment` 一律不进 prompt。这几个字段是标注结果或派生标签 ——
 *    喂给模型等于告诉它答案，得到的 95% 会是「换了一种泄漏」。
 *
 * ② **`subcategory_original` 是强提示**。已实测：子类 → 多数轴 56/56 与 gold 相同。
 *    所以 `--blind` 必须能真的把它藏掉，而**藏没藏掉**要能被反向对照证明
 *    （盲测里出现子类名 → 红；非盲测里不出现 → 红）。只有一边的断言是恒真的。
 *
 * ③ **未测 ≠ 通过**。没有网络 / 模型不可用 / 一条都没跑成 → 退 2 并说「未测」，
 *    不许把 0 条结果算成 0% 准确率（那会让「没跑」看起来像「跑砸了」，
 *    下一轮就会有人去调提示词，而真因是没跑）。
 *
 * ── 用法 ─────────────────────────────────────────────────────────
 *
 *   node tools/llm_rule_axis_eval.mjs --selftest          # 纯函数自证，不联网
 *   node tools/llm_rule_axis_eval.mjs --dry-run --limit 2 # 只打印将发出的 prompt
 *   node tools/llm_rule_axis_eval.mjs --sample <path>     # 真跑（默认 65 条样本）
 *   node tools/llm_rule_axis_eval.mjs --sample <path> --blind   # 隐藏子类名盲测
 *
 * 退出码：0 = 达标；1 = 未达标（有读数）；2 = 未测（没跑成 / 跑不出来）。
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_SAMPLE = '/tmp/llm_eval_sample.json';

/** 门槛：与契约文档 §5 一致。改这里就是改门槛，会同时影响结论行。 */
export const THRESHOLDS = Object.freeze({ axisExact: 0.95, unknownRate: 0.05 });

/** 复跑稳定性门槛：unstable 超过 2% 时，即使 stable_correct 达标也不能判「达标」。 */
export const UNSTABLE_MAX = 0.02;

/**
 * 契约违规率上限。
 *
 * 契约违规 = 解析成功、但字段之间自相矛盾（目前只看 `x_test` 与 `primary`）。
 * 它与「答错」是两件事：前者要改契约或提示词，后者要改判据。
 * 一旦这个比例过高，说明模型根本没按契约作答，此时**任何 axis_exact 都不该被当结果**。
 *
 * 阈值 10% 不是拍的：65 条 × 5 轮里，解析失败是 1.85%，
 * 而契约违规若超过 10%，等于每十条就有一条答案自相矛盾 —— 那份读数的方差会盖过任何改进。
 */
export const CONTRACT_VIOLATION_MAX = 0.10;

/** 七轴，按判定顺序。顺序本身是契约的一部分（先命中先归）。 */
export const AXES = Object.freeze(['CHAN', 'RIGHT', 'SCENE', 'DISC', 'BRAND', 'FACT', 'CLAIM']);

/** 离散取值的封闭集合 —— 模型给了集合外的值一律当解析失败，不许宽松收下。 */
export const NATURES = Object.freeze(['prohibition', 'mandate', 'disclosure', 'substantiation', 'recommendation']);
export const JURISDICTIONS = Object.freeze(['GLOBAL', 'US', 'CA', 'EU', 'UK', 'CN', 'BR', 'AU', 'SG', 'AT', 'BH', 'PLATFORM', 'MULTI']);
export const CONFIDENCES = Object.freeze(['high', 'medium', 'low']);

/**
 * 禁用字段 —— 单点定义，`--selftest` 会断言 prompt 构造器只读白名单。
 * 这四个不是「不推荐」，是「不许」：它们是标注结果。
 */
export const FORBIDDEN_INPUT_FIELDS = Object.freeze([
  'primary_initial', 'primary_reviewed', 'quality_tag', 'policy_fragment',
]);

/** 允许进 prompt、且**非盲测时**才给的参考字段。盲测遮掉，理由见文件头 ②。 */
export const HINT_FIELDS = Object.freeze(['subcategory_original', 'category_original', 'nature_raw']);

const SYSTEM_PROMPT = `你是一个内容合规规则的分类器。任务：判断一条规则要求的是哪一种审查动作。

七轴（按判定顺序，先命中先归）：
1 CHAN 渠道 — 这条内容能不能在这个平台/地区/版位/以这种素材投放
2 RIGHT 权利 — 使用真人/未成年人/AI 人物/第三方标识，授权链成立吗
3 SCENE 场景 — 内容演示的动作，受众照做会不会受伤
4 DISC 披露 — 必须让受众看到的信息元素，说全了吗
5 BRAND 品牌 — 事实全真、证据齐全，是否仍因调性/立场/情绪操纵/贬损竞品而不该这样说
6 FACT 事实 — 这句话说的知识/参数/功能/场景，与可核验事实一致吗
7 CLAIM 宣称 — 这条对外宣称，拿得出与断言强度相称、可核查、范围匹配的证据吗

关键分界（最常判错的地方）：
- 「改成 2~3 天」= FACT（改数值）；「补充一句就医提示」= DISC（加披露）。两者都出现时，
  看规则的主动作是什么：改数值 → FACT；加一句独立的告知 → DISC。
- **「补充说明 / 补充：X」要过一道测试再判**（规范 DSC11–DSC12 / FCT10）：
  把 X 拿掉，**原句**是否变假或不可执行？

  **「原句」的定义（照下面逐字取，不许自己找一句读着通顺的）：**
  规则正文形如「原表述：A；修订为：B；修订原因：C」时，**原句 = A**，X = B 里「补充」后面那串。
  规则正文只有「修订为：B」而没有「原表述：A」时，才把 B 里的主句当原句、把补充串当 X。
  **不许**把 B 里已经含了 X 的那句当成「原句」—— 那样 X 永远拿不掉，测试会恒真。

  **原句是标题/提问式时（如「X 怎么办？」「为什么会 Y」），拿掉 X 会让它失去答案 ——
  这算「不可执行」，x_test 填 false，判 FACT。** 不要因为它字面上仍是问句就判 true。
  · 变假/不可执行 → X 是主命题缺失的事实成分 → FACT（FCT10）。
    例：「补充说明：体重增长趋势应符合 WHO 生长曲线」→ 拿掉后「规律稳步增长」无参照 → FACT。
  · 仍为真且可执行，只是受众少知道一件事 → DISC（DSC12）。
    例：「补充安全提示：全程需有人守护」→ 拿掉后操作要领仍成立 → DISC。
  「补充」这个词本身不决定轴，**拿掉 X 之后原句还成不成立**才决定轴。
- 「研究人群 ≠ 推荐对象」= FACT（适用人群事实错误）；「没有证据支持这个断言」= CLAIM。
- 「补充证据来源」是修订元语言，不构成 DISC；只有要求「向受众展示某条信息」才是 DISC。
- 「画面/镜头/示范」出现但动作是「补充说明」→ 先做上面那道 X 测试；只有动作本身不安全 → SCENE。
- 「标语/焦虑/紧迫感/贬损」→ BRAND；但「竞品对比没数据」→ CLAIM。
- 规则正文里的「原表述：… 修订为：… 修订原因：…」是格式，不是义务类型；
  真正的动作在「修订为」后面那句祈使句里。

判定步骤：
1. 先找「修订为 / 应 / 必须 / 需 / 建议」后面的祈使动作
2. 问这个动作修复的是什么：换渠道(CHAN) / 拿授权(RIGHT) / 改动作(SCENE) /
   补受众可见信息(DISC) / 改表达(BRAND) / 改与来源不符的事实(FACT) / 补证据或降断言(CLAIM)
3. 只选一个 primary。确实同时有两个独立动作时才填 secondary（删掉前者后者仍独立成立）
4. 判不了就返回 unknown，code 用 U3（指代不明）或 U9（七轴均不命中）

**必须先把 X 测试的结论写进 x_test 字段，再据此选 primary。** 顺序不许反：
先选轴、再编一句测试结论，是这次要禁掉的写法。

x_test 三个取值，只许照下面定义填：
- "n/a" —— 这条规则不是「补充／补充说明／补充提示：X」的形式，X 测试不适用
- "false" —— 是补充型，且拿掉 X 后原句为假或不可执行 → 必须 primary=FACT
- "true" —— 是补充型，且拿掉 X 后原句仍为真且可执行 → 见下面两条分支

x_test 为 "true" 时再分两支，**这一步不许跳过**：
- X 属于 DSC12 的封闭枚举（风险 / 禁忌 / 就医提示 / 免责 / 身份关系 / 法定标识）→ primary=DISC
- X 不属于上述六类（例如「优点 / 理由 / 适用人群 / 使用要领 / 行为建议」）→
  **primary=null，unknown="U9"**（规范 §2.6 的「七轴均未命中且不属于任何预处理桶 = 规范缺口」）。
  **不许硬塞进 DISC，也不许改判 FACT，也不许自造新码** ——
  评测器里任何不在规范 §2.6 表内的 UNKNOWN 码都是私造的，规范才是唯一真值。

输出严格 JSON，字段名必须逐字如下，不要改名、不要加字段、不要 markdown 围栏、不要解释：

{"x_test":"true|false|n/a","x":"被拿掉的那串 X 的逐字引用，n/a 时填 null",
 "primary":"CHAN|RIGHT|SCENE|DISC|BRAND|FACT|CLAIM","secondary":null或同上,
 "rule_nature":"prohibition|mandate|disclosure|substantiation|recommendation",
 "jurisdiction":"GLOBAL|US|CA|EU|UK|CN|BR|AU|SG|AT|BH|PLATFORM|MULTI",
 "confidence":"high|medium|low","reason":"一句话，按第几条判定条件命中","unknown":null}

判不了时只输出：{"x_test":<按上面填>,"x":<同上>,"primary":null,"unknown":"U3","reason":"为什么判不了"}
primary 与 unknown 不许同时非空。
x_test 为 false 时 primary 必须是 FACT；为 true 且 X 属 DSC12 枚举时必须是 DISC。
这条约束会被机器校验，违反会被记成契约违规而不是答错。`;

/* ───────────────────────── 纯函数（可被 --selftest 直接断言） ───────────────────────── */

/**
 * 构造用户消息。
 *
 * @param {object} rule  样本一条
 * @param {{blind?: boolean}} opts  blind=true 时遮掉全部 HINT_FIELDS
 * @returns {string}
 */
export function buildUserMessage(rule, { blind = false } = {}) {
  const lines = [
    '规则正文：',
    String(rule.rule_text ?? ''),
    '',
    '结构化条件（可能为空）：',
    String(rule.condition ?? ''),
  ];
  if (!blind) {
    lines.push(
      '',
      '仅作参考、不得作为判定依据：',
      `- 原一级分类：${rule.category_original ?? rule.category ?? ''}`,
      `- 原子类名：${rule.subcategory_original ?? rule.subcategory ?? ''}`,
      `- 原表性质：${rule.nature_raw ?? ''}`,
    );
  }
  return lines.join('\n');
}

/**
 * 解析模型输出。**只接受符合契约的 JSON**，不合契约返回 null。
 *
 * 不宽松收下的理由：宽容解析会把「模型没按契约答」变成「模型答了但答错」，
 * 两者在读数上长得一样，而下一步动作完全不同（前者改提示词，后者改判据）。
 *
 * ── 2026-10-20 加 `x_test`：把「X 测试」从自由叙述变成必填字段 ──────────
 *
 * 起因是一个实测：`r-b2530a099df678b3` 在 15 轮里给出 FACT×9 / DISC×6，
 * 两边的 reason 都写「按 X 测试」，但**对测试结果的判断相反**
 * （一边说「拿掉后主命题变错」，一边说「拿掉后原文仍成立」）。
 *
 * 也就是说：同一个测试、同一条规则，模型在**叙述层**给了两个互斥的结论，
 * 而叙述层没有任何东西会因此变红。这跟「判据打架」是两件事 ——
 * 规范定不定得住，与模型执行得稳不稳，实测下来几乎无关
 * （unique 组平均 1.42 种答案 / ambiguous 组 1.43 种，见 §4.16）。
 *
 * 修法不是改提示词措辞，是**让测试结果成为可校验的字段**：
 * 模型必须先填 `x_test`，再据此选 primary；两者矛盾 = 契约违规，单独计数，
 * **不计入 axis_exact**（否则契约违规会被算成答错，掩盖真因）。
 *
 * @returns {null | {primary:string|null, secondary:string|null, rule_nature:string|null,
 *                  jurisdiction:string|null, confidence:string, reason:string, unknown:string|null,
 *                  x_test:string|null, x:string|null, contract_violation:string|null}}
 */
export function parseVerdict(raw) {
  if (typeof raw !== 'string' || !raw.trim()) return null;
  let body = raw.trim();
  // 允许模型加围栏（契约说不要，但实测会有），剥掉再判
  const fence = body.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) body = fence[1].trim();
  // 仍然不是纯 JSON 时，取第一个 { 到最后一个 }
  if (!body.startsWith('{')) {
    const a = body.indexOf('{');
    const b = body.lastIndexOf('}');
    if (a < 0 || b <= a) return null;
    body = body.slice(a, b + 1);
  }

  let obj;
  try {
    obj = JSON.parse(body);
  } catch {
    return null;
  }
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null;

  const pick = (v, allowed) => (typeof v === 'string' && allowed.includes(v) ? v : null);

  const unknown = typeof obj.unknown === 'string' && obj.unknown.trim() ? obj.unknown.trim() : null;
  const primary = pick(obj.primary, AXES);

  // 契约：判不了就 primary=null + unknown 非空；判得了就 primary ∈ 七轴。
  // 两者都不满足 = 不合契约（例如 primary 拼错、或既给 primary 又给 unknown）。
  if (primary === null && unknown === null) return null;
  if (primary !== null && unknown !== null) return null;

  const secondaryRaw = obj.secondary;
  const secondary = secondaryRaw === null || secondaryRaw === undefined ? null : pick(secondaryRaw, AXES);

  // ── x_test 契约校验 ───────────────────────────────────────────────
  // 缺失或取值不在封闭集合 = 契约违规（不是答错）。
  const xTestRaw = obj.x_test;
  const xTest = ['true', 'false', 'n/a'].includes(xTestRaw) ? xTestRaw : null;
  const xRaw = typeof obj.x === 'string' && obj.x.trim() ? obj.x.trim() : null;

  let violation = null;
  if (xTest === null) {
    violation = `x_test 缺失或取值非法（收到 ${JSON.stringify(xTestRaw)}）`;
  } else if (xTest === 'false' && primary !== 'FACT') {
    // 拿掉 X 后原句为假/不可执行 → 规范要求 FACT；判成别的轴就是自相矛盾
    violation = `x_test=false 但 primary=${primary}（规范要求 FACT）`;
  } else if (xTest === 'true' && primary === 'FACT') {
    // 拿掉 X 后原句仍真且可执行 → FCT10 判它不成立；仍判 FACT 就是自相矛盾
    // 注意：DSC12 不在枚举内、按 §2.6 U9 报缺口的情形，由下面的分支放行
    violation = `x_test=true 但 primary=FACT（FCT10 的去除测试不成立）`;
  } else if (xTest !== 'n/a' && xTest !== null && !xRaw) {
    violation = `x_test=${xTest} 但 x 为空（必须逐字引用被拿掉的那串 X）`;
  }

  return {
    primary,
    secondary,
    rule_nature: pick(obj.rule_nature, NATURES),
    jurisdiction: pick(obj.jurisdiction, JURISDICTIONS),
    confidence: pick(obj.confidence, CONFIDENCES) ?? 'low',
    reason: typeof obj.reason === 'string' ? obj.reason.trim() : '',
    unknown,
    x_test: xTest,
    x: xRaw,
    contract_violation: violation,
  };
}

/**
 * 计分。**空输入返回 `tested:false`**，由调用方落「未测」，不许算成 0%。
 *
 * @param {Array<{gold:string, verdict:object|null, error?:string}>} rows
 * @returns {{tested:boolean, n:number, nRun:number, nParsed:number,
 *            axisExact:number, exact:number, unknown:number, secondaryExact:number, nSecondary:number,
 *            pass:boolean, failures:string[]}}
 */
export function score(rows) {
  const n = rows.length;
  const parsed = rows.filter((r) => r.verdict);
  const nParsed = parsed.length;
  // 契约违规：解析成功、但字段之间自相矛盾（目前只看 x_test 与 primary）。
  // **单列、不进分母** —— 它和「答错」是两件事：前者要改契约/提示词，后者要改判据。
  const violations = parsed.filter((r) => r.verdict.contract_violation);
  const nContractViolation = violations.length;
  const clean = parsed.filter((r) => !r.verdict.contract_violation);
  const nClean = clean.length;
  if (n === 0 || nParsed === 0) {
    return {
      tested: false, n, nRun: rows.filter((r) => !r.transportFailure).length, nParsed,
      axisExact: null, exact: 0, unknown: 0, secondaryExact: null, nSecondary: 0,
      nContractViolation: 0, contractViolationRate: null,
      pass: false, failures: ['一条都没解析成功 —— 未测，不是 0%'],
    };
  }
  // 全部都是契约违规时，等于没有可用读数 —— 同样是「未测」
  if (nClean === 0) {
    return {
      tested: false, n, nRun: rows.filter((r) => !r.transportFailure).length, nParsed,
      axisExact: null, exact: 0, unknown: 0, secondaryExact: null, nSecondary: 0,
      nContractViolation, contractViolationRate: 1,
      pass: false, failures: [`${nContractViolation}/${nParsed} 条契约违规 —— 没有可用读数，未测`],
    };
  }

  const exact = clean.filter((r) => r.verdict.primary === r.gold).length;
  const unknown = clean.filter((r) => r.verdict.primary === null).length;

  // secondary 只在**两边都给了**的时候才计 —— gold 没标次要轴的条目不该算作答错
  const withSecondary = clean.filter((r) => r.goldSecondary && r.verdict.secondary);
  const nSecondary = withSecondary.length;
  const secondaryExact = nSecondary
    ? withSecondary.filter((r) => r.verdict.secondary === r.goldSecondary).length / nSecondary
    : null;

  const axisExact = exact / nClean;
  const unknownRate = unknown / nClean;
  const contractViolationRate = nContractViolation / nParsed;

  const failures = [];
  if (axisExact < THRESHOLDS.axisExact) failures.push(`axis_exact ${axisExact.toFixed(4)} < ${THRESHOLDS.axisExact}`);
  if (unknownRate > THRESHOLDS.unknownRate) failures.push(`unknown_rate ${unknownRate.toFixed(4)} > ${THRESHOLDS.unknownRate}`);
  // 解析失败的条数必须显式扣出来 —— 否则「解析失败」会被算成「答错」
  if (nParsed < n) failures.push(`解析失败 ${n - nParsed}/${n}（未计入分母，但记在这里）`);
  // 契约违规率高到一定程度，说明契约本身没被遵守 —— 此时任何准确率都不该被当结果
  if (contractViolationRate > CONTRACT_VIOLATION_MAX) {
    failures.push(`契约违规 ${nContractViolation}/${nParsed} = ${(contractViolationRate * 100).toFixed(1)}% > ${(CONTRACT_VIOLATION_MAX * 100).toFixed(0)}%（x_test 与 primary 自相矛盾）`);
  }

  return {
    tested: true, n, nRun: rows.filter((r) => !r.transportFailure).length, nParsed,
    axisExact, exact, unknown, secondaryExact, nSecondary,
    nContractViolation, contractViolationRate,
    pass: failures.length === 0, failures,
  };
}

/** 结论行。**「未测」必须与「未达标」「达标」三者长得不一样**（AGENTS.md §2.4.2）。 */
export function verdictLine(s, { blind = false, model = '?' } = {}) {
  const tag = blind ? '盲测(隐藏子类名)' : '常规(含子类名)';
  if (!s.tested) {
    return `⚠ 未测 · ${tag} · model=${model} · ${s.n} 条样本里一条都没跑成：${s.failures[0] ?? '原因未知'}`;
  }
  const head = s.pass ? '✅ 达标' : '❌ 未达标';
  const sec = s.secondaryExact === null ? 'n/a' : `${(s.secondaryExact * 100).toFixed(2)}%（${s.nSecondary} 条）`;
  return [
    `${head} · ${tag} · model=${model}`,
    `axis_exact = ${s.exact}/${s.nParsed} = ${(s.axisExact * 100).toFixed(2)}%（阈值 ≥${THRESHOLDS.axisExact * 100}%）`,
    `unknown = ${s.unknown}/${s.nParsed} = ${((s.unknown / s.nParsed) * 100).toFixed(2)}%（阈值 ≤${THRESHOLDS.unknownRate * 100}%）`,
    `secondary_exact = ${sec}`,
    `解析失败 = ${s.n - s.nParsed}/${s.n}`,
  ].join('\n');
}

/**
 * 复跑聚合：按 rule_id 汇总 N 次答案。
 *
 * 三档必须互斥且穷尽：
 *   stable_correct   N 次全是 gold
 *   stable_wrong     N 次全错，且每次答案完全相同（同一个错轴/同一个 UNKNOWN code）
 *   unstable         其余：至少出现两种答案（含「全错但错法不同」）
 *
 * 注意：stable_wrong 不是「全错」的同义词 —— 全错但每次错在不同轴，属于 unstable。
 */
export function aggregateRepeat(runs) {
  const validRuns = (runs || []).filter(Array.isArray);
  if (validRuns.length === 0) {
    return {
      tested: false, nRuns: 0, nRules: 0, nParsed: 0,
      stableCorrect: 0, stableWrong: 0, unstable: 0, stableUnknown: 0,
      stableCorrectRate: null, stableWrongRate: null, unstableRate: null,
      stableWrongDirections: {}, pass: false,
    };
  }
  const byRule = new Map();
  let nParsed = 0;
  for (const run of validRuns) {
    for (const row of run) {
      const rid = row?.rule_id;
      if (!rid) continue;
      if (row?.verdict) nParsed += 1;
      if (!byRule.has(rid)) byRule.set(rid, { gold: row.gold, answers: [] });
      byRule.get(rid).answers.push(answerKey(row));
    }
  }
  if (nParsed === 0) {
    return {
      tested: false, nRuns: validRuns.length, nRules: byRule.size, nParsed: 0,
      stableCorrect: 0, stableWrong: 0, unstable: 0, stableUnknown: 0,
      stableCorrectRate: null, stableWrongRate: null, unstableRate: null,
      stableWrongDirections: {}, pass: false,
    };
  }
  let stableCorrect = 0;
  let stableWrong = 0;
  let unstable = 0;
  let stableUnknown = 0;
  const stableWrongDirections = {};
  for (const { gold, answers } of byRule.values()) {
    // 少跑了一轮也按不稳定处理 —— 不把缺失当稳定。
    if (answers.length < validRuns.length) {
      unstable += 1;
      continue;
    }
    const unique = new Set(answers);
    const correctKey = `AXIS:${gold}`;
    if (unique.size === 1 && answers[0] === correctKey) {
      stableCorrect += 1;
    } else if (unique.size === 1) {
      stableWrong += 1;
      const answer = answers[0];
      const got = answer.startsWith('AXIS:') ? answer.slice(5)
        : answer.startsWith('UNKNOWN:') ? answer.slice(8)
          : answer;
      const dir = `${gold}→${got}`;
      stableWrongDirections[dir] = (stableWrongDirections[dir] ?? 0) + 1;
      if (answer.startsWith('UNKNOWN:')) stableUnknown += 1;
    } else {
      unstable += 1;
    }
  }
  const nRules = byRule.size;
  const rate = (n) => (nRules ? n / nRules : null);
  const stableCorrectRate = rate(stableCorrect);
  const stableWrongRate = rate(stableWrong);
  const unstableRate = rate(unstable);
  const pass = stableCorrectRate !== null
    && stableCorrectRate >= THRESHOLDS.axisExact
    && unstableRate <= UNSTABLE_MAX;
  return {
    tested: true, nRuns: validRuns.length, nRules, nParsed,
    stableCorrect, stableWrong, unstable, stableUnknown,
    stableCorrectRate, stableWrongRate, unstableRate,
    stableWrongDirections, pass,
  };
}

/** 单条答案的稳定键：轴 / UNKNOWN code / 解析失败 / 传输失败。 */
function answerKey(row) {
  if (!row) return 'MISSING';
  if (row.transportFailure) return 'TRANSPORT_FAIL';
  if (!row.verdict) return 'PARSE_FAIL';
  return row.verdict.primary
    ? `AXIS:${row.verdict.primary}`
    : `UNKNOWN:${row.verdict.unknown ?? '?'}`;
}

/**
 * 复跑结论行：四态。
 * 只要 unstable 超过门槛，即使 stable_correct ≥95% 也**不许**输出「达标」。
 */
export function verdictLineRepeat(a, { blind = false, model = '?' } = {}) {
  const tag = blind ? '盲测(隐藏子类名)' : '常规(含子类名)';
  if (!a.tested) {
    return `⚠ 未测 · ${tag} · model=${model} · 没有完整轮次`;
  }
  const pct = (x) => (x === null ? 'n/a' : `${(x * 100).toFixed(2)}%`);
  let head;
  if (a.unstableRate > UNSTABLE_MAX) {
    head = '⚠ 不稳定';
  } else if (a.pass) {
    head = '✅ 达标';
  } else {
    head = '❌ 未达标';
  }
  const dirs = Object.entries(a.stableWrongDirections)
    .sort((x, y) => y[1] - x[1])
    .map(([k, v]) => `${k} × ${v}`)
    .join('；') || '无';
  return [
    `${head} · ${tag} · model=${model} · repeat=${a.nRuns}`,
    `stable_correct = ${a.stableCorrect}/${a.nRules} = ${pct(a.stableCorrectRate)}（阈值 ≥${THRESHOLDS.axisExact * 100}%）`,
    `stable_wrong = ${a.stableWrong}/${a.nRules} = ${pct(a.stableWrongRate)}（方向：${dirs}）`,
    `unstable = ${a.unstable}/${a.nRules} = ${pct(a.unstableRate)}（阈值 ≤${(UNSTABLE_MAX * 100).toFixed(0)}%；超过时不得判达标）`,
    `stable_unknown = ${a.stableUnknown}/${a.nRules}`,
  ].join('\n');
}

/* ─────────────────────────────── 自证 ─────────────────────────────── */

function selftest() {
  const checks = [];
  const ok = (name, cond, detail = '') => checks.push({ name, pass: !!cond, detail });

  // ── 1 禁用字段：构造器读不到它们 ──
  // 做法：把禁用字段填成**极其显眼**的值，再看 prompt 里有没有。正反各一次。
  const poisoned = {
    rule_text: '规则正文 A', condition: '条件 A',
    primary_reviewed: 'ZZZ_FORBIDDEN', primary_initial: 'ZZZ_FORBIDDEN',
    quality_tag: ['ZZZ_FORBIDDEN'], policy_fragment: 'ZZZ_FORBIDDEN',
  };
  const msgNormal = buildUserMessage(poisoned, { blind: false });
  ok('禁用字段不进 prompt（含名）', !msgNormal.includes('ZZZ_FORBIDDEN') && !/primary_reviewed|policy_fragment|quality_tag/.test(msgNormal));
  const msgBlind = buildUserMessage(poisoned, { blind: true });
  ok('禁用字段不进 prompt（盲测）', !msgBlind.includes('ZZZ_FORBIDDEN'));

  // ── 2 盲测真的遮住了子类名，且**非盲测真的给了** ──
  // 两条必须成对：只断言「盲测里没有」的话，构造器恒返回空串也能过。
  const hinted = { rule_text: '规则正文 B', condition: '', subcategory_original: 'QIN_子类探针', category_original: 'QIN_一级探针', nature_raw: 'atomic' };
  ok('盲测遮住子类名', !buildUserMessage(hinted, { blind: true }).includes('QIN_子类探针'));
  ok('非盲测给出子类名（反向对照）', buildUserMessage(hinted, { blind: false }).includes('QIN_子类探针'));
  ok('盲测遮住一级分类', !buildUserMessage(hinted, { blind: true }).includes('QIN_一级探针'));

  // ── 3 解析：合法 / 围栏 / 垃圾 / 不合契约 ──
  const v1 = parseVerdict('{"primary":"FACT","secondary":null,"rule_nature":"disclosure","jurisdiction":"US","confidence":"high","reason":"按 CHN1","unknown":null}');
  ok('解析：合法 JSON', v1 && v1.primary === 'FACT' && v1.rule_nature === 'disclosure');
  const v2 = parseVerdict('```json\n{"primary":"CLAIM","unknown":null}\n```');
  ok('解析：围栏 JSON', v2 && v2.primary === 'CLAIM');
  const v3 = parseVerdict('{"primary":"NOT_AN_AXIS","unknown":null}');
  ok('解析：集合外 primary → null（不宽松收下）', v3 === null);
  ok('解析：纯文本 → null', parseVerdict('我觉得是 FACT') === null);
  ok('解析：空串 → null', parseVerdict('') === null);
  const v4 = parseVerdict('{"primary":null,"unknown":"U9","reason":"七轴均不命中"}');
  ok('解析：unknown 契约', v4 && v4.primary === null && v4.unknown === 'U9');
  const v5 = parseVerdict('{"primary":"FACT","unknown":"U9"}');
  ok('解析：同时给 primary 与 unknown → null（契约不允许）', v5 === null);

  // ── 3b x_test 契约（2026-10-20 加）──────────────────────────────
  // 正反成对：只验「矛盾形态会被抓到」的话，一个恒返回 violation 的实现也能过；
  // 所以每一种合规形态都必须配一条「不许被误报」的反向对照。
  const xt = (o) => parseVerdict(JSON.stringify(o));

  // 合规三态
  const okNA = xt({ x_test: 'n/a', x: null, primary: 'CHAN', unknown: null });
  ok('x_test：n/a 且非补充型 → 合规', okNA && okNA.contract_violation === null && okNA.x_test === 'n/a');
  const okFalse = xt({ x_test: 'false', x: '短期优先冷藏', primary: 'FACT', unknown: null });
  ok('x_test：false + FACT → 合规（反向对照，不许误报）', okFalse && okFalse.contract_violation === null);
  const okTrueD = xt({ x_test: 'true', x: '全程需有人守护', primary: 'DISC', unknown: null });
  ok('x_test：true + DISC → 合规（反向对照，不许误报）', okTrueD && okTrueD.contract_violation === null);
  const okTrueGap = xt({ x_test: 'true', x: '该姿势的优点', primary: null, unknown: 'U9' });
  ok('x_test：true + U9（规范缺口）→ 合规', okTrueGap && okTrueGap.contract_violation === null);

  // 违规三态 —— 每一条都必须真被抓到
  const badMissing = xt({ primary: 'FACT', unknown: null });
  ok('x_test：缺失 → 契约违规', badMissing && /缺失或取值非法/.test(badMissing.contract_violation || ''));
  const badFalseFact = xt({ x_test: 'false', x: 'X', primary: 'DISC', unknown: null });
  ok('x_test：false 但判 DISC → 契约违规', badFalseFact && /要求 FACT/.test(badFalseFact.contract_violation || ''));
  const badTrueFact = xt({ x_test: 'true', x: 'X', primary: 'FACT', unknown: null });
  ok('x_test：true 但判 FACT → 契约违规（FCT10 测试不成立）', badTrueFact && /去除测试不成立/.test(badTrueFact.contract_violation || ''));
  const badNoX = xt({ x_test: 'true', x: null, primary: 'DISC', unknown: null });
  ok('x_test：true 但 x 为空 → 契约违规', badNoX && /x 为空/.test(badNoX.contract_violation || ''));
  const badEnum = xt({ x_test: 'maybe', x: 'X', primary: 'FACT', unknown: null });
  ok('x_test：取值不在封闭集合 → 契约违规', badEnum && /缺失或取值非法/.test(badEnum.contract_violation || ''));

  // 计分必须把契约违规与答错分开（否则真因被掩盖）
  const sc0 = score([
    { gold: 'FACT', verdict: { primary: 'FACT', contract_violation: null } },
    { gold: 'DISC', verdict: { primary: 'FACT', contract_violation: 'x_test=true 但 primary=FACT' } },
  ]);
  ok('计分：契约违规单列，不计入分母', sc0.nParsed === 2 && sc0.nContractViolation === 1 && sc0.exact === 1);

  // ── 4 计分 ──
  const rows = [
    { gold: 'FACT', verdict: { primary: 'FACT', secondary: null } },
    { gold: 'CLAIM', verdict: { primary: null, unknown: 'U9' } },
    { gold: 'DISC', verdict: { primary: 'FACT', secondary: null } },
    { gold: 'CHAN', verdict: null, transportFailure: true },
  ];
  const s = score(rows);
  ok('计分：分母只算解析成功（3 不是 4）', s.nParsed === 3);
  ok('计分：exact=1', s.exact === 1);
  ok('计分：unknown=1', s.unknown === 1);
  ok('计分：未达标时 pass=false', s.pass === false);

  // 空输入必须落「未测」，不是 0%
  const s0 = score([]);
  ok('计分：空输入 → tested=false（未测，不是 0%）', s0.tested === false && s0.axisExact === null);
  const s1 = score([{ gold: 'FACT', verdict: null, transportFailure: true }]);
  ok('计分：全失败 → tested=false', s1.tested === false);

  // 反向对照：全对必须 pass
  const good = score(AXES.map((a) => ({ gold: a, verdict: { primary: a, secondary: null } })));
  ok('计分：全对 → pass=true（反向对照）', good.pass === true && Math.abs(good.axisExact - 1) < 1e-9);

  // 结论行的三种形态必须互不相同
  const lPass = verdictLine(good);
  const lFail = verdictLine(s);
  const lUntested = verdictLine(s0);
  ok('结论行三态互异', new Set([lPass.slice(0, 3), lFail.slice(0, 3), lUntested.slice(0, 3)]).size === 3);
  ok('未测文案里不许出现「达标」', !lUntested.includes('达标') && lUntested.startsWith('⚠ 未测'));

  // ── 5 白名单：构造器源码不许出现禁用字段名 ──
  // 形状同 AGENTS.md §2.4「名字出现过 ≠ 拦得住」，所以这里比的是**取值**不是名字（上面 1 已做），
  // 这一条只是补充：构造器源码里不该出现对禁用字段的引用。
  const src = buildUserMessage.toString();
  ok('构造器源码不引用禁用字段', !FORBIDDEN_INPUT_FIELDS.some((f) => src.includes(f)));

  // ── 6 复跑稳定性分档（正反例成对） ──
  const row = (gold, primary, rid = 'r1') => ({
    rule_id: rid, gold,
    verdict: primary ? { primary, secondary: null } : null,
  });
  const five = (answers) => answers.map((a) => [row('FACT', a)]);
  const aCorrect = aggregateRepeat(five(['FACT', 'FACT', 'FACT', 'FACT', 'FACT']));
  ok('复跑：5 次全对 → stable_correct',
     aCorrect.stableCorrect === 1 && aCorrect.stableWrong === 0 && aCorrect.unstable === 0,
     JSON.stringify(aCorrect));
  const aMixed = aggregateRepeat(five(['FACT', 'FACT', 'FACT', 'DISC', 'CLAIM']));
  ok('复跑：3 对 2 错 → unstable',
     aMixed.stableCorrect === 0 && aMixed.stableWrong === 0 && aMixed.unstable === 1,
     JSON.stringify(aMixed));
  const aWrongSame = aggregateRepeat(five(['DISC', 'DISC', 'DISC', 'DISC', 'DISC']));
  ok('复跑：5 次全错且同答案 → stable_wrong + 方向',
     aWrongSame.stableWrong === 1 && aWrongSame.stableWrongDirections['FACT→DISC'] === 1,
     JSON.stringify(aWrongSame));
  const aWrongDiff = aggregateRepeat(five(['DISC', 'CLAIM', 'SCENE', 'BRAND', 'CHAN']));
  ok('复跑：5 次全错但错法不同 → unstable（不是 stable_wrong）',
     aWrongDiff.stableWrong === 0 && aWrongDiff.unstable === 1,
     JSON.stringify(aWrongDiff));
  const aEmpty = aggregateRepeat([]);
  ok('复跑：空轮次 → tested=false（未测，不是 0%）', aEmpty.tested === false, '');

  // 100 条：97 条 5 次全对，3 条每次翻转 → stable_correct 97% ≥95%，unstable 3% >2%。
  const bigRuns = Array.from({ length: 5 }, (_, ri) =>
    Array.from({ length: 100 }, (_, i) => {
      const rid = `r${i}`;
      if (i < 97) return row('FACT', 'FACT', rid);
      return row('FACT', ri % 2 === 0 ? 'DISC' : 'CLAIM', rid);
    }));
  const aHighButWobbly = aggregateRepeat(bigRuns);
  const lWobbly = verdictLineRepeat(aHighButWobbly);
  ok('结论：unstable 超阈值时即使 stable_correct ≥95% 也不得判达标',
     aHighButWobbly.stableCorrectRate >= THRESHOLDS.axisExact
     && aHighButWobbly.unstableRate > UNSTABLE_MAX
     && lWobbly.startsWith('⚠ 不稳定')
     && !lWobbly.split('\n').some((line) => line.startsWith('✅ 达标')),
     lWobbly);

  const failed = checks.filter((c) => !c.pass);
  for (const c of checks) console.log(`${c.pass ? '✓' : '✗'} ${c.name}${c.pass ? '' : ` —— ${c.detail}`}`);
  console.log(`\n${failed.length === 0 ? '✅' : '❌'} ${checks.length - failed.length}/${checks.length} 项通过`);
  return failed.length === 0 ? 0 : 1;
}

/* ─────────────────────────────── 主流程 ─────────────────────────────── */

function parseArgs(argv) {
  const out = { sample: DEFAULT_SAMPLE, blind: false, limit: 0, concurrency: 4, repeat: 1, outPath: null, dryRun: false, selftest: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--selftest') out.selftest = true;
    else if (a === '--blind') out.blind = true;
    else if (a === '--dry-run') out.dryRun = true;
    else if (a === '--sample') out.sample = argv[++i];
    else if (a === '--limit') out.limit = Number(argv[++i]);
    else if (a === '--concurrency') out.concurrency = Number(argv[++i]);
    else if (a === '--repeat') out.repeat = Number(argv[++i]);
    else if (a === '--out') out.outPath = argv[++i];
    else if (a === '--help' || a === '-h') out.help = true;
    else { console.error(`未知参数：${a}`); process.exit(2); }
  }
  return out;
}

/** 跑一轮：每轮都是一次完整、无状态的 items 遍历。 */
async function runRound(items, args, llm, label = '') {
  const rows = new Array(items.length);
  let cursor = 0;

  async function worker() {
    while (true) {
      const idx = cursor++;
      if (idx >= items.length) return;
      const rule = items[idx];
      const userMsg = buildUserMessage(rule, { blind: args.blind });
      const r = await llm.chat(
        [{ role: 'system', content: SYSTEM_PROMPT }, { role: 'user', content: userMsg }],
        { maxTokens: 4000, temperature: 0, jsonMode: true },
      );
      const goldSecondary = rule.gold_secondary ?? null;
      if (!r.ok) {
        rows[idx] = { rule_id: rule.rule_id, gold: rule.gold, goldSecondary, verdict: null, error: r.error, transportFailure: true };
        process.stderr.write(`· ${label}${idx + 1}/${items.length} ${rule.rule_id} 传输失败：${r.error}\n`);
        continue;
      }
      const raw = r.message?.content ?? '';
      const verdict = parseVerdict(raw);
      rows[idx] = {
        rule_id: rule.rule_id, gold: rule.gold, goldSecondary, verdict,
        raw: verdict ? undefined : raw.slice(0, 300),
        finishReason: r.finishReason,
      };
      process.stderr.write(`· ${label}${idx + 1}/${items.length} ${rule.rule_id} gold=${rule.gold} got=${verdict?.primary ?? verdict?.unknown ?? 'PARSE_FAIL'}\n`);
    }
  }

  await Promise.all(Array.from(
    { length: Math.max(1, Math.min(args.concurrency, items.length)) }, worker));
  return rows;
}

/** 原子写：先写临时文件再 rename，进程被杀不会留下半个 JSON。 */
function writeJsonAtomic(p, obj) {
  const tmp = `${p}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2));
  fs.renameSync(tmp, p);
}

/**
 * 复跑主流程。每完成一轮就落盘，第 3 轮挂了前 3 轮仍在文件里。
 * 续跑只接受 sample/blind/repeat/rule_ids 完全一致的旧文件。
 */
async function runRepeat(items, args, llm) {
  const n = Math.floor(args.repeat);
  if (!Number.isFinite(n) || n < 2) {
    console.error(`⚠ 未测 · --repeat 必须是 ≥2 的整数，收到 ${args.repeat}`);
    return 2;
  }
  const outPath = args.outPath
    ?? `${args.sample.replace(/\.json$/i, '')}.repeat${n}.json`;
  const ruleIds = items.map((r) => r.rule_id);
  let runs = [];
  let priorCost = null;
  if (fs.existsSync(outPath)) {
    try {
      const old = JSON.parse(fs.readFileSync(outPath, 'utf8'));
      const same = old.sample === args.sample && old.blind === args.blind
        && old.repeat === n
        && JSON.stringify(old.rule_ids) === JSON.stringify(ruleIds);
      if (same && Array.isArray(old.runs)) {
        runs = old.runs;
        priorCost = old.cost ?? null;
        console.log(`↻ 续跑：已有 ${runs.length}/${n} 轮，从第 ${runs.length + 1} 轮开始（${outPath}）`);
      }
    } catch {
      // 坏文件不阻塞新跑；下一轮写完会覆盖。
    }
  }
  const initialRuns = runs.length;

  const t0 = Date.now();
  const runningCost = (elapsed) => {
    const stats = llm.stats ?? {};
    return {
      elapsedSeconds: Number(((priorCost?.elapsedSeconds ?? 0) + elapsed).toFixed(1)),
      calls: (priorCost?.calls ?? 0) + (stats.calls ?? 0),
      promptTokens: (priorCost?.promptTokens ?? 0) + (stats.promptTokens ?? 0),
      completionTokens: (priorCost?.completionTokens ?? 0) + (stats.completionTokens ?? 0),
    };
  };
  for (let round = runs.length; round < n; round++) {
    console.log(`\n=== repeat ${round + 1}/${n} ===`);
    const rows = await runRound(items, args, llm, `[${round + 1}/${n}] `);
    runs.push(rows);
    writeJsonAtomic(outPath, {
      schema: 'llm-rule-axis-repeat/v1',
      sample: args.sample, blind: args.blind, repeat: n,
      rule_ids: ruleIds, completedRuns: runs.length, complete: false,
      updatedAt: new Date().toISOString(),
      cost: runningCost((Date.now() - t0) / 1000), runs,
    });
    console.log(`  ↳ 已落盘 ${runs.length}/${n} 轮到 ${outPath}`);
  }

  const elapsed = ((Date.now() - t0) / 1000);
  const agg = aggregateRepeat(runs);
  console.log(`\n${verdictLineRepeat(agg, { blind: args.blind, model: llm.config?.llm?.model ?? '?' })}`);

  const stats = llm.stats ?? {};
  const cost = runningCost(elapsed);
  const newRuns = runs.length - initialRuns;
  const perRunSec = newRuns ? elapsed / newRuns : null;
  const newPrompt = stats.promptTokens ?? 0;
  const newCompletion = stats.completionTokens ?? 0;
  const perRunPrompt = newRuns ? newPrompt / newRuns : null;
  const perRunCompletion = newRuns ? newCompletion / newRuns : null;
  console.log(`本次耗时 ${elapsed.toFixed(1)}s · calls=${stats.calls ?? 0} retries=${stats.retries ?? 0} failures=${stats.failures ?? 0}`);
  console.log(`累计成本：耗时 ${cost.elapsedSeconds}s · calls=${cost.calls} · prompt=${cost.promptTokens} completion=${cost.completionTokens}`);
  if (perRunSec !== null) {
    console.log(`本次单轮：${perRunSec.toFixed(1)}s · prompt≈${Math.round(perRunPrompt)} · completion≈${Math.round(perRunCompletion)}`);
    console.log(`外推：N=5 ≈ ${(perRunSec * 5 / 60).toFixed(1)} 分钟 / prompt≈${Math.round(perRunPrompt * 5)}；`
      + `N=50 ≈ ${(perRunSec * 50 / 60).toFixed(1)} 分钟 / prompt≈${Math.round(perRunPrompt * 50)}`);
  } else {
    console.log('本次无新调用（全部轮次来自续跑文件），沿用累计成本。');
  }

  writeJsonAtomic(outPath, {
    schema: 'llm-rule-axis-repeat/v1',
    sample: args.sample, blind: args.blind, repeat: n,
    rule_ids: ruleIds, completedRuns: runs.length, complete: true,
    updatedAt: new Date().toISOString(), aggregate: agg,
    cost,
    runs,
  });
  console.log(`\n明细已写入 ${outPath}（complete=true）`);

  if (!agg.tested) return 2;
  return agg.pass ? 0 : 1;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('*/')[0]);
    return 0;
  }
  if (args.selftest) return selftest();

  let sample;
  try {
    sample = JSON.parse(fs.readFileSync(args.sample, 'utf8'));
  } catch (e) {
    console.error(`⚠ 未测 · 读不出样本（${args.sample}）：${e.code ?? e.message}`);
    return 2;
  }
  if (!Array.isArray(sample) || sample.length === 0) {
    console.error(`⚠ 未测 · 样本为空或不是数组（${args.sample}）`);
    return 2;
  }
  const items = args.limit > 0 ? sample.slice(0, args.limit) : sample;

  if (args.dryRun) {
    console.log(`〔dry-run〕${items.length} 条，不发请求。首条 prompt：\n--- system ---\n${SYSTEM_PROMPT}\n--- user ---\n${buildUserMessage(items[0], { blind: args.blind })}\n--- end ---`);
    return 2;   // 没测就是没测（AGENTS.md §2.4.2）
  }

  // 延迟 import：--selftest 与 --dry-run 不该因为找不到凭据而崩
  let llm;
  try {
    llm = await import('./agent/llm.mjs');
  } catch (e) {
    console.error(`⚠ 未测 · 模型调用层加载失败：${e.message}`);
    return 2;
  }

  if (args.repeat > 1) {
    return await runRepeat(items, args, llm);
  }

  const t0 = Date.now();
  const rows = await runRound(items, args, llm);
  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  const s = score(rows);
  console.log(`\n${verdictLine(s, { blind: args.blind, model: llm.config?.llm?.model ?? '?' })}`);
  console.log(`耗时 ${elapsed}s · 用量 calls=${llm.stats.calls} retries=${llm.stats.retries} failures=${llm.stats.failures}`);

  // 逐条明细，供人工复核（`reason` 必须指得出判定条件，否则无法复核）
  for (const r of rows) {
    const v = r.verdict;
    console.log(`  ${r.rule_id}  gold=${r.gold}  got=${v ? (v.primary ?? v.unknown) : 'PARSE_FAIL'}  ${v?.confidence ?? ''}  ${v?.reason ?? r.error ?? ''}`);
  }

  if (args.outPath) {
    fs.writeFileSync(args.outPath, JSON.stringify({ blind: args.blind, sample: args.sample, summary: s, rows }, null, 2));
    console.log(`\n明细已写入 ${args.outPath}`);
  }

  if (!s.tested) return 2;
  return s.pass ? 0 : 1;
}

main().then((code) => process.exit(code)).catch((e) => {
  console.error(`⚠ 未测 · 意外异常：${e?.stack ?? e}`);
  process.exit(2);
});
