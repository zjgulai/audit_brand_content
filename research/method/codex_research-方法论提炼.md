# codex_research × Kb2Agent 方法论提炼

> 对象：**仓库 A** `research/method/codex_research`｜**仓库 B** `research/method/Kb2Agent`
> 取证：结论均来自实际打开的文件；标注 `文件:行号` + 原文摘录。无出处处写「仓库中未见」。**未修改两仓库任何文件。**
> 实际读取：A 的 `README.md`/`METHODOLOGY.md`/`PLAN.md`/`AGENTS.md`/`design-qa.md`/`scripts/build-site.mjs`/`scripts/verify-artifact.mjs`/`scripts/site-template.html`/`data/build-manifest.json`/`.github/workflows/pages.yml`；B 的 `docs/architecture/adrs/`（README + 5 ADR）/`m1-a-design-audit.md`/`m1-a-product-contract.md`/`m1-a-schema-catalog.md`/`m1-a-test-blueprint.md`/`m1-a-execution-receipt.md`/`m1-b-cross-audit.md`/`m1-b-implementation-receipt.md`/`design-qa.md`/`qa-receipt.md`。**超出清单的两处补充取证**（为回答「G 门是什么」）：`knowledge-system/capability-map.json` 的 `scopeNote`、`docs/architecture/g6-a11-public-static-closeout-and-g7-roadmap.md` 的 G7 表格，正文已标注。

---

# 第一部分：codex_research（仓库 A）

## 1.1 它是什么

把 4,184 个 Codex 插件映射到 14 个全栈开发节点，交付**一个离线单文件网站** + **一份带缺口的证据账本**。

> `README.md:3`｜一个可离线打开的单页网站，把 4,184 个 Codex 插件及可取得证据的 Skill 映射到 `vibecoding_config` 的 M00–M13 全栈开发节点。
> `README.md:9`｜全量派生数据以 `gzip + Base64` 内嵌，并由现代浏览器原生 `DecompressionStream` 解压……不支持该 Web API 的旧浏览器会显示明确错误。

---

## 1.2 对象模型（问题 1）

### 四类对象

> `METHODOLOGY.md:5–10`｜本项目采用四类互不混淆的对象：
> - `M00–M13`：执行模块；每个插件和 Skill 必须且只能有一个主模块。
> - `A00–A13`：模块间持久交接的证据产物，不是额外的流程节点。
> - `G0–G6`：生命周期的人类决策门；工具只能补证据，不能自行通过。
> - `R0–R3`：风险与最低验证等级；真实外部动作仍需对象级、当次、未过期的授权。

**数量核对**（实跑解析脚本核对，非按文件名推测）：

| 类别 | 数量 | 依据 |
|---|---|---|
| `M00–M13` | **14** | `build-site.mjs:47–62` 的 `MODULES` 数组实有 14 个 `id: "Mxx"`；`verify-artifact.mjs:24` 硬断言 `data.modules.length !== 14` |
| `A00–A13` | **14** | 每个模块恰带一个 `artifact` 字段，实测 14 个：`A00 Context Pack` / `A01 Project Charter` / `A02 Opportunity Brief` / `A03 Problem Evidence` / `A04 Product Strategy` / `A05 Product Spec` / `A06 Prototype Evidence` / `A07 Architecture & Tickets` / `A08 Implementation Report` / `A09 Quality Evidence` / `A10 Release Readiness` / `A11 Operations Learning` / `A12 Experiment Record` / `A13 Evolution Record` |
| `G0–G6` | **7** | 从 `MODULES[].gate` 提取的去重 G 令牌恰为 `G0,G1,G2,G3,G4,G5,G6`；`R3` 另行出现在 `M10/M11/M12` 的 gate 数组 |
| `R0–R3` | **4** | 仅由编号区间 + `METHODOLOGY.md:10` 推得；**R0/R1/R2 的逐条定义、`R3` 的含义展开在仓库中未见** |

「A 类不是流程节点」被重复固定了两次，是为防止后续改代码的人（或 Agent）混用编号：

> `METHODOLOGY.md:8`｜`A00–A13`：模块间持久交接的证据产物，**不是额外的流程节点**。
> `AGENTS.md:8`｜M00–M13 是模块，A00–A13 是交接产物，G0–G6 是生命周期的人类决策门；**不要复用 G 编号表示动作影响**。

### G 的语义边界：工具只能补证据

> `README.md:21`｜节点映射是研究模型的推断，不是插件作者的官方定位。**插件只能为 Gate 提供证据，不能替人通过 Gate**。`已安装`、`已认证`、`调用通过`和`生产可用`也是四种不同状态。

代码上的落实是「只挂证据贡献，不挂通过状态」，且**把 R 从这条通道剔除**：

```js
// build-site.mjs:207–209
function gatesFor(primaryModule) {
  return MODULE_BY_ID.get(primaryModule).gate.filter((item) => item.startsWith("G"));
}
```

> `site-template.html:1406`｜`detailBlock("Gate 贡献", (item.gateEvidence || []).join(", ") + "；只供证，不能代替人通过")`

### 为什么把「动作影响等级」从 G 里拆出来叫 `effectClass`

> `METHODOLOGY.md:12`｜`vibecoding_config` 的旧文档还把 G0–G6 用作动作影响等级。它与后来的生命周期 Gate **同名不同义**。本网站保留后者，并把动作影响单独命名为 `effectClass`，**避免混算**。

拆开的根本原因：两者是**正交的两根轴**——Gate 轴问「谁有权决定要不要做」（人），`effectClass` 轴问「工具一跑会碰到什么」。共用编号会产生「G3 到底是需要 G3 门批准，还是会写生产」的歧义。

`effectClass` 七档由 `inferEffect()` 推断，`writes` 是前置闸门，顺序即优先级：

```js
// build-site.mjs:180–187
if (writes && /(deploy|deployment|release|dns|firewall|kubernetes|terraform|hosting)/.test(text)) return "production";
if (/(secret management|manage secrets|...)/.test(text) && writes) return "secrets";
if (writes && /(git|github|gitlab|commit|pull request|merge request|branch)/.test(text)) return "git";
if (writes && /(mcp|app connector|if mcp tools|if skill and mcp|browser computer)/.test(text)) return "external";
if (writes && /(send|publish|delete|trade|order|payment|email|calendar|crm|task)/.test(text)) return "external";
if (writes && /(local cli|workspace|source code|file|terminal)/.test(text)) return "workspace";
if (writes) return "local-artifact";  // 否则 read-only
```

> `METHODOLOGY.md:66–70`｜七档为 `read-only`、`local-artifact`、`workspace`、`git`、`external`、`secrets`、`production`。它是根据说明和接口形态推断的**审计提示，不是正式权限清单**。

三个细节：① 所有非 `read-only` 分支都要求 `writes === true`（只读 git 查询不会被误标为 `git`）；② 顺序 `production→secrets→git→external→workspace→local-artifact`，越靠前越危险；③ 危险三档在 UI 上独立视觉：`site-template.html:1362` `(["production","secrets","external"].includes(item.effectClass) ? "danger" : "")`。

**最值得学的一点**：每一档都自带「怎么验证」，标签不是终点：

> `site-template.html:1233–1241`｜`"external": "先用预览或沙盒做最小操作，再回读外部系统确认结果"`／`"production": "先做 dry-run、回滚和监控；获得明确上线授权后再验证线上"`（$7$ 档各自一条）

---

## 1.3 「核心三件事」如何被强制执行（问题 2）

> `README.md:13–17`｜每个插件或 Skill 固定回答三件事：1. 能帮你做什么；2. 使用前要准备什么；3. 怎样确认真能用。
> `METHODOLOGY.md:31–33`｜① **能帮你做什么**：优先呈现插件独有动作与对象；不把目录声明升级为实测能力。② **使用前要准备什么**：安装状态、认证策略、能力形态与未知条件；不把 Skill 加载写成外部连接成功。③ **怎样确认真能用**：给出最小验证、可观察结果、未验证缺口与副作用边界。

**第三件事不是附加说明，而是三件事之一**——进了合同就必须有渲染出口，这是它能被强制执行的根本原因。

### 四层锁（生成器 / 校验器 / manifest / 模板）

| 层 | 机制 | 位置 |
|---|---|---|
| 数据层 | 每条记录必须有来源 description，否则 `validateData()` 抛错 | `build-site.mjs:445` `if (!item.description) errors.push("Missing source description for " + item.id);` |
| 产物层 | HTML 里必须存在 `function coreTexts(item)`，否则拒绝写出 | `build-site.mjs:468` `if (!html.includes("function coreTexts(item)")) htmlErrors.push("Runtime core-three generator is missing");` |
| 承诺层 | 写进 manifest 的 checks 块 | `build-manifest.json:126` `"coreThreePresent": true` |
| 独立复核层 | 校验器在**看不到生成过程**的条件下重新断言（description + coreTexts + 四个 UI 目标） | `verify-artifact.mjs:32/54/57` |

校验器侧的交付面断言（这是三件事真正的落地点）：

```js
// verify-artifact.mjs:54–58
for (const id of ["overview-metrics", "node-list", "node-panel", "search", "result-grid", "detail-dialog"]) {
  if (!html.includes('id="' + id + '"')) errors.push("Required UI target missing: " + id);
}
if (!html.includes("function coreTexts(item)")) errors.push("Runtime core-three generator missing");
```

### 内容的唯一生成口 `coreTexts(item)`

```js
// site-template.html:1244–1261（节选）
const does = FEATURED_COPY[item.name] || short(description, 280) || (isSkill ? "给 Agent 一套可重复执行的操作步骤。" : "帮助完成“" + PLAIN_TITLES[item.primaryModule] + "”这一步。");
...
if (item.authPolicy === "未说明") conditions.push("目录没把认证条件说完整，使用前要补查");
const proof = FEATURED_CHECKS[item.name] || ((isSkill ? "..." : (effectChecks[item.effectClass] || "...")) + "。这一步的成功标准是：" + module.done);
const unverified = isSkill ? ["Skill 实际触发","父插件认证","工具依赖","生产稳定性"] : ["认证状态","权限范围","代表性调用","生产稳定性"];
return { does, conditions: conditions.join("；") + "。", proof, unverified };
```

三个强制点：① `does` 不可能为空（人工文案 → 原文截断 → 通用句三级 fallback）；② `conditions` 至少推出一条安装/启用条件，且 `未说明` 有专属分支；③ **`proof` 的成功标准被绑到 `module.done`**——「怎样确认真能用」不是泛泛的「测一下」，而是「这一步的成功标准是：〈该节点的完成定义〉」。

**同一份数据、三处强制渲染**（节点候选行 `:1304`、目录卡片 `<dl class="core-three">` `:1365`、详情弹窗 `<div class="dialog-three">` `:1401`），且候选行把未验证清单直接拼进「依据」：`site-template.html:1298` `"依据：插件目录说明 + 本站节点归类。未验证：" + core.unverified.join("、") + "。"`

---

## 1.4 证据分层：四态怎么判定（问题 3）

> `METHODOLOGY.md:41–48`｜冻结插件快照只有 `skillCount`，没有 Skill 名称与逐条说明。当前 remote catalog 提供逐 Skill 元数据，但目录已有漂移。因此网站区分：
> - `frozen-exact`：当前目录中仍能找到冻结版本，Skill 元数据可与版本精确绑定；
> - `current-version-drift`：只有同名插件的新版本，当前 Skill 可供参考，**但不得冒充冻结版本**；
> - `local-bundle-exact`：本机缓存中存在精确版本的 `SKILL.md` front matter；
> - `historical-payload-missing`：冻结版本声明有 Skill，**但当前无法恢复逐条载荷**。
>
> Skill 记录以 `canonicalPluginId + releaseVersion + skillName` 为键。父插件的功能分与公共声量只作为上下文，不代表该 Skill 本身经过独立评分或获得相同采用量。

### 判定代码

```js
// build-site.mjs:352–377（节选）
let evidenceState = "historical-payload-missing";     // ① 默认落在最坏态
if (marketplace === "openai-curated-remote") {
  const frozenVersions = new Set((row.releaseRecords || []).map((release) => release.version));
  const exact = candidates.find((candidate) => candidate.release && frozenVersions.has(candidate.release.version));
  const selected = exact || candidates[0];
  if (selected && selected.release) {
    evidenceState = exact ? "frozen-exact" : "current-version-drift";   // ② 精确命中 vs 漂移
    ...
} else {
  const localSkills = localSkillsFor(row);
  if (localSkills.length) { evidenceState = "local-bundle-exact"; ... }  // ③ 本地精确 bundle
  else if (Number(row.skillCount || 0) === 0) evidenceState = "not-declared";  // ⑤ 文档外第五态
}
```

四步读法：① **默认值取最不可信**，只有证据到了才往上抬（不是「默认可信、出问题降级」）；② 按 `canonicalPluginId` 拆名，用冻结版本号集合匹配当前 catalog，命中即 `frozen-exact`，同名但版本不符即 `current-version-drift`；③ 非 remote 插件去本地缓存找精确版本 `SKILL.md`（`localSkillsFor`，`build-site.mjs:262–278`）；④ **`gap` 单独算**：只有 `current-version-drift`，或「声明有 Skill 但载荷丢失」才算缺口——`not-declared` 不算缺口（本来就没有）。

```js
// build-site.mjs:381
gap: evidenceState === "current-version-drift" || (evidenceState === "historical-payload-missing" && Number(row.skillCount || 0) > 0),
```

**文档/代码漂移**：`METHODOLOGY.md:44–46` 只列四态，代码里有第五态 `not-declared`（`build-site.mjs:376`），文档未提。

### 为什么需要四态而不是「有/没有」

因为「有」在三个不同事实层面被混用了：

| 问题 | 二态答案 | 四态答案 |
|---|---|---|
| 这版本有没有 Skill？ | 有 | `frozen-exact` |
| 你看到的说明是不是这版本的？ | 有 | `current-version-drift`（**不是**） |
| 你手上有没有这版本原文？ | 有 | `local-bundle-exact`（本机有、目录无） |
| 声明里有、但拿不到？ | **没有** ← 错 | `historical-payload-missing`（**声明为真、证据缺失**） |

`historical-payload-missing` 是关键：二态模型会把它退化成「没有 Skill」，即把「上游声明为真但我们拿不到」错写成「这东西不存在」——正是 `METHODOLOGY.md:37` 禁止的改写方向。

四态的下游后果：① **每态单独计数不合并**（`build-site.mjs:410–421` 的 `skillCoverage` 实测 `frozenExact: 5326 / localBundleExact: 13 / currentVersionDrift: 81 / pluginHistoricalMissing: 4 / pluginsWithGap: 16`，见 `build-manifest.json:16–27`）——合并成「共 5420 条」，那 81 条漂移和 16 条缺口就消失了；② 漂移态在 UI 上是警告色 `site-template.html:1359`；③ 中文标签直说漂移 `:1066` `"current-version-drift": "当前版本漂移"`；④ 详情页并列「observed / claimed」`:1397`；⑤ `evidenceLevel` 随证据态切换 `build-site.mjs:343` `versionState === "local-bundle-exact" ? "static-local-manifest" : "static-catalog-metadata"`。

**可迁移的一般形式**：任何「上游声明的数量」与「我们能取到的载荷」之间都有四种关系，二态必然丢掉「声明为真但证据缺失」和「证据存在但版本不符」——而这两种恰是审计里最该被看见的。

---

## 1.5 排序：三视角与权重（问题 4）

> `METHODOLOGY.md:52–58`｜保留三种可切换视角，不把它们伪装成一个"真排名"：**节点适配**（本项目 M00–M13 启发式适配度）、**功能潜力**（元数据经证据折扣后的全栈潜力，不是 runtime benchmark）、**公开声量代理**（GitHub 仓库或品牌域名的公开代理，**不是安装量、活跃用户或留存**）。
> "研究优先级"只用于发现候选：**节点适配 55%，功能潜力 35%，有可归因声量时最多 10%；缺失声量不会当成零**。页面始终并列展示原始分项和证据置信度。

### 权重与「缺失不当零」的实现

```js
// build-site.mjs:210–218
function weightedPriority(fit, functional, publicProxy, weights) {
  let numerator = fit * weights.fit + Number(functional || 0) * weights.functional;
  let denominator = weights.fit + weights.functional;
  if (publicProxy !== null && publicProxy !== undefined) {   // ← 缺失时不加分子，也不加分母
    numerator += Number(publicProxy) * weights.publicProxy;
    denominator += weights.publicProxy;
  }
  return round(numerator / denominator, 1);
}
```

插件用 `{ fit: 0.55, functional: 0.35, publicProxy: 0.1 }`（`:294`），Skill 用 `{ fit: 0.65, functional: 0.28, publicProxy: 0.07 }`（`:336`）——**后者在 `METHODOLOGY.md` 中未见，只存在于代码**。

缺失不当零的实质：把缺失当零 → 该项最高只能拿 `0.9×满分`，**「没数据」被惩罚成「数据差」**；现在的写法把权重重新归一化到 `fit+functional`，**既不奖励也不惩罚，但页面上仍并列显示分项**（`:1299`）；排序时空值转为 `-1`（`:1352`）排到最后，而不是当 0 分参与比较。

### `matchConfidence` 怎么算

```js
// build-site.mjs:150–165（节选）
const fitScore = round(clamp(34 + Math.min(43, top[1] * 2.15) + Math.min(15, gap * 1.8) + (topDirectHits ? 5 : 0), 0, 99), 1);
const oldReview = Boolean(entity.classNeedsReview || (parent && parent.classNeedsReview));
const versionAmbiguous = Boolean(entity.versionAmbiguous || (parent && parent.versionAmbiguous));
let matchConfidence = "medium";
if (!topDirectHits || gap < 1.25 || oldReview || versionAmbiguous || fitScore < 55) matchConfidence = "review";
else if (topDirectHits >= 2 && gap >= 3 && fitScore >= 72) matchConfidence = "high";
const secondaryModules = sorted.slice(1).filter((entry) => entry[1] >= Math.max(3, top[1] * 0.44)).slice(0, 3).map((entry) => entry[0]);
```

`fitScore` 四项：基线 `34` + 绝对命中 `min(43, top×2.15)`（**封顶**，防词表灌分）+ 领先优势 `min(15, gap×1.8)`（**封顶**）+ 存在词项级证据 `+5`；`clamp(…,0,99)`——**上限 99 不是 100**，没有一个分数可以满分。

`matchConfidence` **只有三条路径，但进 `review` 有五个触发条件**（`!topDirectHits` / `gap<1.25` / `oldReview` / `versionAmbiguous` / `fitScore<55`），而 `high` 需要三个条件**同时**满足（`>=2 / >=3 / >=72`）。这是**保守的不对称设计**：`review` 一条不满足即触发，`high` 三条全中才给。UI 上只有 `review` 是警告色（`:1065` `value === "high" ? "high" : value === "medium" ? "medium" : "需复核"`），匹配理由为空时强制显示 `:1392` `'<span class="badge warn">只有弱先验，需复核</span>'`。

### 排名之外的「编辑层」被显式分离

> `METHODOLOGY.md:60`｜工作台**不是第四种自动分数**。它在每个节点的完整排名上增加一层显式编辑选择……**原始 `moduleRank` 不被改写**；用户可一键回到该节点的完整目录复核。这个编辑层用于缩小候选，不代表作者背书、运行通过或生产可用。

代码保证：`moduleRank` 在全量上统一分配（`build-site.mjs:394–402`），编辑层只在渲染时把 3 个候选提到前面（`site-template.html:1314–1316`），**候选行显示的是原始名次**（`:1301` `' · #' + item.moduleRank`），并附可见说明（`:1328` `"结合站内排名、通用性和当前安装状态选出 3 个；原始排名仍在完整目录。"`）。**这是「推荐」最干净的写法：允许人为介入，但介入必须可见、可回退、不改写底层名次。**

---

## 1.6 校验清单：两个脚本逐条（问题 5）

### A. `build-site.mjs` 校验的不变量

| # | 不变量 | 位置 |
|---|---|---|
| A1 | `--snapshot` 与 `--catalog` 必填，否则 exit 2 | `:12–15` |
| A2 | 模板必须含 `__APP_DATA_GZIP_BASE64__` 占位符，否则抛错 | `:456` |
| A3 | 插件总数恰为 4,184 | `:440` |
| A4 | 插件 ID 全局唯一 | `:441` |
| A5 | Skill 证据 ID 全局唯一 | `:442` |
| A6 | 每条记录（插件+Skill）主模块必须是 14 个合法模块之一 | `:444` |
| A7 | 每条记录必须有来源 description | `:445` |
| A8 | 每条 Skill 的父插件必须存在 | `:446` |
| A9 | **不允许任何 `readyNow` 声明**（断言零） | `:447` |
| A10 | 精确 CSP 存在且在 `<style>`/`<script>` **之前** | `:463` |
| A11 | 无外链 `<script src>` | `:464` |
| A12 | 无外链 `<link rel=stylesheet>` | `:465` |
| A13 | 无 `http(s)` 的 `<img>/<source> src` | `:466` |
| A14 | 无本地绝对路径泄漏（`/Users/`、`file:///Users/`、`.codex/plugins/cache`） | `:467` |
| A15 | 运行期三件事生成函数必须存在 | `:468` |
| A16 | `<`、U+2028、U+2029 全部转义 | `:452` |

前九条在 `validateData()` 内（`:438–451`），失败即 `throw new Error("Data validation failed:…")`，**不写文件**。后七条在写盘前的 HTML 检查内。另有 manifest 落下的可外部复核事实：`artifactBytes`/`artifactSha256`/`embeddedData.{jsonBytes,gzipBytes,encodedBytes,sha256}`/`sourceCommits`/`sourceHashes`/`checks`（`:472–485`）。

### B. `verify-artifact.mjs` 校验的不变量（逐条）

| # | 不变量 | 位置 |
|---|---|---|
| B1 | 内嵌数据边界标记必须找得到 | `:12–19` |
| B2 | Base64 → gunzip → JSON.parse 必须成功 | `:21–22` |
| B3 | `meta.pluginCount === 4184` **且** `plugins.length === 4184`（双条件） | `:23` |
| B4 | 模块数恰为 14 | `:24` |
| B5 | `skills.length === meta.skillCoverage.evidenceRows`（自洽） | `:25` |
| B6 | 插件 ID 唯一 | `:26–27` |
| B7 | Skill 证据 ID 唯一 | `:28` |
| B8 | 每条记录主模块在模块表中 | `:31` |
| B9 | 每条记录有 description | `:32` |
| B10 | 每条 Skill 的父插件在插件 ID 集合中 | `:33` |
| B11 | `embeddedData.encoding === "gzip-base64"` | `:35` |
| B12–B15 | `jsonBytes` / `gzipBytes` / `encodedBytes` / `sha256` 四项与实测一致 | `:36–39` |
| B16 | 恰好一个内联 `<script>` 块 | `:43` |
| B17 | 内联 JS 能被 `new Function` 解析 | `:45–46` |
| B18 | 精确 CSP 存在且顺序在 `<style>`/`<script>` 之前 | `:50` |
| B19 | 无外部运行资源（script src / stylesheet link / http img） | `:51` |
| B20 | 无本地绝对路径泄漏 | `:52` |
| B21 | **无凭据样材料**（`gh[opusr]_…`、`github_pat_…`、`AKIA…`、`PRIVATE KEY`） | `:53` |
| B22 | 六个必需 UI 目标存在 | `:54–56` |
| B23 | 运行期三件事生成函数存在 | `:57` |
| B24 | 运行期 gzip 解码器存在（`new DecompressionStream("gzip")`） | `:58` |
| B25 | `manifest.artifactSha256 === sha256(html)` | `:61` |
| B26 | `manifest.artifactBytes === byteLength(html)` | `:62` |

### 两个脚本的分工与「为什么必须分开」

| 维度 | `build-site.mjs` | `verify-artifact.mjs` |
|---|---|---|
| 输入 | 冻结快照 + catalog + 本地缓存（三个绝对路径） | **只有两个文件**：`public/index.html`、`data/build-manifest.json` |
| 知道生成过程吗 | 知道（它就是生成者） | **不知道**（拿不到源数据） |
| 检查集 | 源侧（计数、ID 唯一、父关系、主模块、CSP、转义） | 交付侧（脚本块数、JS 语法、凭据、UI 目标、解码器、hash/byte） |
| 失败行为 | `throw` → 不写文件 | `process.exit(1)` → 打印全部错误 |

原文依据：

> `README.md:46`｜生成器会验证 canonical ID 唯一性、总数、单一主节点、技能父子关系、HTML CSP、压缩数据的大小与 SHA-256、内嵌数据一致性和敏感路径泄漏。
> `README.md:48`｜**生成后再运行独立 artifact 检查：**
> `METHODOLOGY.md:74–75`｜发布验证分开记录：本地 HTML 检查、Git commit、远端 push、Actions workflow、Pages deployment 与公开页面字节验证，**任何一项都不能替代下一项**。

拆开的一般理由（本题最值钱的一条）：① **生产者不能只用自己的断言证明自己**——生成器检查「我打算生成的东西」（意图），校验器检查「已经躺在磁盘上、即将发布的那些字节」（事实）；② **校验器的输入面必须更小**，因此**无法被源数据洗白**；③ **两者检查集合不重合**，只跑一个必漏另一半；④ 失败语义不同——生成器失败 = 不要生成，校验器失败 = 不要发布。`AGENTS.md:9` 把它变成不可跳过的流程：「变更分类规则后，必须重新运行数据不变量、ELI5 checker、桌面/手机浏览器和公开页面验证。」

### 顺带发现：一次诚实性修复的「数据层残留」

> `design-qa.md:15`｜P1：节点短句仍出现"独立证明它没有骗你"等生成式口号。已为 14 个节点重写自然语言标题、说明和三项任务。

但该口号**仍留在生成器的数据字段里**：`build-site.mjs:57` 的 M09 记录 `short: "独立证明它没有骗你"`。实测模板中 `.short` 出现 **0 次**——UI 用的是模板内 14 条 `PLAIN_SUBTITLES`（`site-template.html:1081–1084`）。即**这次修复只在渲染层完成，源数据层未清理**。两个校验脚本都不检查「数据字段里的话术」，`checks.coreThreePresent` 也不覆盖。启示：**诚实性规则若只在渲染层实施，就会在数据层留下会被未来新界面重新渲染出来的口号。**

---

## 1.7 诚实性写法：未知/未说明/未实测（问题 6）

### 三条原文规定

> `METHODOLOGY.md:37`｜**产品名、plugin ID、版本、数字、否定、条件、情态和完成状态保持不变。资料不足时显示"未知／未说明／未实测"，不改写成"没有／无需／安全"。**
> `AGENTS.md:7`｜不得把 publisher claim、安装状态、Skill 加载、认证、一次调用或生产可用性互相升级。
> `README.md:21`｜`已安装`、`已认证`、`调用通过`和`生产可用`也是四种不同状态。

第一句是**保真编辑器的操作定义**：列出七个「不许动」的语法范畴（产品名/ID/版本/数字/**否定**/**条件**/**情态**/完成状态），禁止的改写是 `未知·未说明·未实测 →✗→ 没有·无需·安全`。它的狠处在于**同时禁止两个方向**：把缺失说成负面结论（误杀）和把缺失说成安全（漏放）。

### 代码里的十处实现

1. **缺字段一律落「未说明」**：`build-site.mjs:297` `developer: row.developer || "未说明"`；`:301` `authPolicy: row.authPolicy || "未说明"`；`:290` `… || "当前目录没有提供可解释的能力说明。"`
2. **运行状态五档**：`build-site.mjs:200–206` `已安装并启用 / 已安装 / 默认关闭 / 目录标记不可用 / 可用未安装`。
3. **界面上「已安装」强制跟随「未实测」**：`site-template.html:1296` `item.installed ? "已安装 · 未实测" : "未安装"`。
4. **认证条件三路，`未说明` 有专属话术**：`:1253–1254`（非 NONE/未说明 →「账号和授权范围尚未实测」；未说明 →「目录没把认证条件说完整，使用前要补查」）。
5. **每条记录固定四项未验证清单**：`:1257–1259`（Skill：`Skill 实际触发/父插件认证/工具依赖/生产稳定性`；插件：`认证状态/权限范围/代表性调用/生产稳定性`）。
6. **未验证清单被拼进「依据」强制打印**：`:1298`。
7. **每个字段都有 fallback，且不同缺失原因给不同的词**：`:1383` `esc(value || "未说明")`；`:1405–1413`「匹配理由 → 弱先验」「运行阻断 → 静态来源未列出」「外部来源 → 无可用外链」「分类上下文 → 继承父插件/未说明」。**「未说明」是一个词，但缺失有五种原因**——这是很细但很重要的一手。
8. **统计口径不制造 Ready Now**：`build-site.mjs:429` `readyNowCount: plugins.filter((item) => item.readyNow).length`，配合 A9 断言恒为 0，并在收据中记录 `PLAN.md:62`「0 个 `Ready Now`」。
9. **两句具体的 fineprint**：`:1280`「排名来自静态资料，真实调用尚未验证。」；`:1417`「节点归类和排序是本站推断。插件作者的说明不等于实际测试结果；已安装、已登录、调用成功和生产可用也不是一回事。」
10. **不把机器生成的通用句冒充独有能力**：`METHODOLOGY.md:35`「不把机器生成的通用节点句冒充插件独有能力」，代码上由 `FEATURED_COPY`（人工撰写）优先于原文截断实现（`:1248`）。

---

# 第二部分：Kb2Agent（仓库 B）的工程纪律

## 2.1 工作单元的完整闭环（问题 7）

### 两条不同的链，先分清

- **控制链（人看）**：`design-audit → product-contract → schema-catalog → test-blueprint → execution-receipt → cross-audit → implementation-receipt`
- **数据链（机器跑）**：`m1-b-implementation-receipt.md` 的 mermaid——`6-format synthetic corpus → Structure-aware extractors → Candidate compiler → Immutable snapshot → SQLite FTS index → E2 deterministic agent → ActionPackage + Trace + Receipt → Lab + Evidence + Map + Cases + Build + Ops`

注意 M1-A 把「交付面」与「交叉审计」写在**同一份** `m1-a-execution-receipt.md` 里，而 M1-B 把它们**拆成两份**（`m1-b-cross-audit.md` + `m1-b-implementation-receipt.md`）。这说明**回执与审计在职责上可分**，M1-A 只是恰好合写。

### 七步的输入与输出

| 步 | 输入 | 输出（含原文证据） |
|---|---|---|
| ① `m1-a-design-audit.md` | 页面 Home/`/lab/`/`/lab/runs/amazon-ads-replay-001`；视口 1440/1280/960/768/390；本地 VitePress candidate；`LO-S synthetic` | 九维 PASS 表 + 交互回执 6 条 + 自动化回执 + 视觉判断。**关键字段是「禁止解释」**：`禁止解释：不证明 compiler、模型、API、live 或部署已实现` |
| ② `m1-a-product-contract.md` | 一句话价值、双产品线、主用户 A1/A2、旗舰任务、E2 边界 | 允许声明清单 / 禁止声明清单 / 非目标 / 退出条件 / **当前授权边界**。状态行：``状态：`local-candidate` · 证据上限：`L2 fixture/dry-run` · 实现范围：`P0–P2` `` |
| ③ `m1-a-schema-catalog.md` | L0–L6 分层意图 | 每层对象 + Schema 文件 + **进入下一层的必要条件**；关系端点白名单；Guide 适配映射表。结论句：`对象通过 Schema 不等于领域正确，不等于真实 Agent 已执行，也不等于产品验收` |
| ④ `m1-a-test-blueprint.md` | 产品合同 + Schema + UI 主路径 | 八层门禁矩阵（层/检查/**失败条件**）+ 正例清单 + **6 个固定负例** + 禁用短语静态扫描 + **写死的串行执行顺序** |
| ⑤ `m1-a-execution-receipt.md` | P0–P2 实施结果 + 本地 QA 结果 | 裁决字符串 + **实施边界表**（基线/分支/隔离/授权 + 四行「零」）+ 交付面 + QA 证据 + **七视角交叉审计表** + 下一门禁前置条件 |
| ⑥ `m1-b-cross-audit.md` | M1-B 的 P3–P6 实现与全部证据 | 七视角结论表（视角/结论/关键证据/遗留风险）+ P7/P8/P9 TODO + **「暂不进入」清单** |
| ⑦ `m1-b-implementation-receipt.md` | P3–P6 实现 | 状态与证据上限 + 交付结果表 + 确定性/停止条件 + 运行入口 + 安全与依赖审计 + **未授权与未完成清单** |

### 关键原文

> `m1-a-execution-receipt.md`｜`LOCALLY_VERIFIED_CANDIDATE / NOT_ACCEPTED / NOT_PUBLISHED` ……该裁决允许 Owner 与四角色审阅候选，**不构成 commit、发布、部署、真实模型调用、领域效果证明或产品验收**。
> `m1-a-test-blueprint.md`｜`| Negative | 固定负例必须失败 | 负例通过或失败原因不匹配 |`；`M1-A 的通过是本地候选回执，不是 commit、PR、发布或生产回执。`
> `m1-b-cross-audit.md`｜`没有发现把计划、静态 Demo 或本地测试冒充生产结果的情况。证据上限保持 L2-fixture-or-dry-run。`
> `m1-b-implementation-receipt.md`｜`validatePromotion({ apply: true })` 固定抛出 `CANONICAL_APPLY_DISABLED`。
> `m1-a-execution-receipt.md`｜4. Amazon Ads 领域 reviewer 与许可证决策可继续作为阻断项，**不得用工程测试替代**。

**「0 值清单」是回执的固定结构**（`m1-a-execution-receipt.md`）：`外部调用 0 provider calls / 0 platform calls`、`外部副作用 0 writes / 0 sends / 0 deploys`、`Git/发布 0 commit / 0 push / 0 package publication`。

### 为什么要有 cross-audit

① **实现者与审计者的证据集合不同**：七视角中的「产品合同/安全与权限/**部署准备**」根本不是实现者会主动去看的——实现者关心「跑通没有」，审计者关心「声明有没有越界」。② **它专抓一种失败——冒充**，其验收标准就是 ``没有发现把计划、静态 Demo 或本地测试冒充生产结果的情况``。③ **它给「有条件通过」留了唯一通道**：七视角里唯有 `安全与权限｜有条件通过｜external calls/effects/writes 均为 0；apply=true 硬阻断；静态公网面｜dev-only 依赖公告、experimental SQLite`——如果只有通过/不通过，「0 调用但依赖有公告」这个真实状态就无处安放。

### 为什么要有独立的 implementation-receipt

① **审的是「上一阶段」，记的是「这一阶段交付了什么」**——前者判决书，后者货物清单。② **回执必须独立回答「证据上限是什么」**：M1-A 是 `LOCALLY_VERIFIED_CANDIDATE / NOT_ACCEPTED / NOT_PUBLISHED`，M1-B 是 ``candidate-complete；证据上限：`L2-fixture-or-dry-run` ``。③ **回执是下一道门的输入，且门不自动开始**：

> `m1-a-execution-receipt.md`｜## 下一门禁　M1-B 不自动开始。进入前至少需要：1. Owner 确认或提出……修改意见。2. 明确是否单独授权 M1-B 本地 compiler/runner/export 实现。3. 保持 provider call、真实平台、canonical write、deploy、commit、push 与 publish 继续关闭。4. …**不得用工程测试替代**。
> `m1-b-cross-audit.md`｜**以上四组能力需要新的明确授权，不能由"同意下一门禁"推断获得。**

## 2.2 ADR 机制（同属工程纪律）

> `adrs/README.md`｜1. 新决策创建新 ADR，**不静默改写已接受 ADR 的结论**。2. 替代旧决策时填写 `supersedes`，旧 ADR 改为 `superseded` 但保留。3. 任何**提高权限、改变证据语言、开放公网输入或改变权威存储**的 ADR 必须由 Owner 重新确认。4. **ADR 接受仅代表设计决策，不代表实现、验收或生产状态。**

五份 ADR：`ADR-001 双账本独立成熟度（accepted-design）`、`ADR-002 Git-native 权威源 + SQLite 运行投影（accepted-design）`、`ADR-003 Replay-first 单 E2 Agent（accepted-design）`、`ADR-004 公网固定输入、无上传、无自由文本（accepted-design）`、`ADR-005 未选许可证前阻断公开发布（proposed-blocking）`。

三份最值得照抄的写法：

> `ADR-001`｜Guide 使用 `principle/solution/runnable/acceptance`；Reference 使用 `draft/replayable/live-candidate/accepted`。**两套账本只能通过显式引用关联，不允许互相继承等级。**
> `ADR-002`｜JSON/YAML/Markdown、稳定 ID、typed relations 和 immutable snapshot 是权威合同。SQLite FTS5…是**可重建运行投影，不是 canonical source**。／**重新评估触发器**：只有出现经测量的对象规模、并发、复杂图算法或恢复时间瓶颈，才评估专用图/向量存储。
> `ADR-003`｜无 provider key 也必须能复放固定 bundle。……**没有任何写工具、消息工具或 canonical promotion 工具。**
> `ADR-005`｜在 Owner 确认项目许可证前，Schema、fixture 和未来 Runner 只允许本地开发与审查，**禁止 package/container 公开发布**。（状态 `proposed-blocking`，blocker `LICENSE_DECISION_PENDING`，含关闭条件）

「**重新评估触发器**」这一节尤其值得搬：它把「以后可能换技术」变成有条件的决策，而不是悬而未决的犹豫。

（补充取证）`knowledge-system/capability-map.json` 的 `scopeNote`：`每项能力必须绑定证据引用与禁止声明；状态只能由门禁回执支撑，不得由页面完整或上线事实自动抬升。`

## 2.3 `design-qa.md` 与 `qa-receipt.md` 的区别（问题 8）

| 维度 | `design-qa.md` | `qa-receipt.md` |
|---|---|---|
| 标题 | MKD Guide Product **Design** QA | MKD Guide **本地验收回执** |
| 对象 | **视觉与交互** | **命令、门禁、数据契约、依赖、部署边界** |
| 判据 | 参考图对照（`reference-1440x1024.png` / `implementation-1440x1024-final.png` / `comparison-1440x1024-final.png`） | 命令实测与退出码：`最终门禁：npm run docs:qa`｜`退出状态：0` + **17 步串行门禁表** |
| 结构 | 对照证据 / 差异收敛记录 / 有意保留的差异 / 浏览器与无障碍回执 / G2.1–G2.4 增量审计 | 17 步门禁表 / G0–G1 专项 / G2.1–G2.4 专项 / 外链分类告警 / 依赖审计 / 范围声明 |
| 结尾 | `final result: passed（仅限本地暖白方案 B 的视觉与交互候选）` | `本回执证明本地 G0–P3……不证明 Git 交付、部署、生产完成、L4 回执真实性或自然人已经接受责任` |

### 差异的实质

**① 判据不同**：一个是「与参考图并排检查」，一个是「命令退出码 0 + 实测数字」。`qa-receipt.md` 的第 1 步就是硬数字：`baseline v4 一致：26 页、265 H2、352 个代码块、167 个 Markdown 链接、83 个唯一 Markdown 外链`。

**② 「视觉通过」与「内容成熟度」被明确切开**——这是最关键的一条，同一句话在三处增量审计里被重复了三遍：

> `design-qa.md`｜- 审计边界：**视觉通过不提高内容成熟度**；12 个 owner gap 与 3 条 L0 断言继续作为治理阻断项。
> `design-qa.md`｜- 视觉通过**只证明**工作台可读和可操作；71 个未迁移词面线索与学习效果验证继续作为内容阻断，**不因卡片可视化而升级**。
> `design-qa.md`｜- 视觉通过**只证明**验收条件可发现、可比较、可操作；三个契约仍为 `approval-blocked`，0/3 accepted。

**③ 设计评审主动拒绝把「好看」当成状态提升**：

> `design-qa.md`｜| P0 | 初版首页仍偏传统落地页，**目录证据状态存在被误读为"全站已验证"的风险** | 改为数据驱动 EvidenceHome；24 个无回执页面保持"待复核"，仅 2 个 fixture 显示"烟测通过" |
> `design-qa.md`｜第 3 稿中的绿色"是"和成批日期没有被照抄。实现只允许实际 evidence 驱动验证状态；没有 evidence 的页面显示"待复核"，**没有伪造复核日期**。该差异属于证据契约要求，不是视觉遗漏。

**④ 两份文件都登记「自我更正」**（最反直觉、最值得学）：

> `design-qa.md`｜2026-08-03 当前方案 B 以暖白背景为唯一主题，`appearance: false`。下文 2026-08-02 关于深色模式……的记录**仅是历史审计，不属于当前候选，也不得作为恢复深色背景的依据**。
> `qa-receipt.md`｜收尾只读检查发现 VitePress 1.6.4 的 `preview`……实际监听 `*.4173`；同一局域网地址可以访问。**此前"静态预览只绑定 127.0.0.1"的表述因此不成立。**
> `qa-receipt.md`｜第一次串行复跑在复用视觉审计静态预览时出现旧 HTML……导致 9 个浏览器用例失败。……**这是测试服务器生命周期问题，不是忽略的产品失败。**

**⑤ `qa-receipt.md` 用「不证明什么」收尾**：

> `qa-receipt.md`｜## 范围声明　- 未部署、未推送、未合并、未切流、未导入真实数据、未调用供应商生产服务。……本回执证明本地 G0–P3 内容、身份、契约、构建、设计与浏览器门禁通过，**不证明 Git 交付、部署、生产完成、L4 回执真实性或自然人已经接受责任**。

### 为什么必须分开记

① **失败后怎么办不同**：视觉失败 → 改样式（可快速迭代）；门禁失败 → 修实现（不能靠调样式蒙过去）。合在一份文件里，人会倾向于用改样式「关掉」一个门禁失败。② **证据不能互相替代**：好看不证明命令通过，命令通过不证明对人可用。③ **有效期不同**：视觉结论随设计稿失效（那条 2026-08-03 更正就是证据）；门禁数字随代码失效但**可复算**。④ **读者不同**。⑤ **最关键**：分开之后「视觉通过」才无法被当成熟度凭证——否则 `passed` 一个词会同时覆盖「好看」和「能上线」两种完全不同的含义。

顺带一条极硬的门禁与一条极诚实的写法：

> `qa-receipt.md`｜`authorized-live` 越级测试除要求 L4 回执外，**还要求四角色全部 `accepted`**；仅有角色占位不能成为在线授权。
> `qa-receipt.md`｜12/12 claim 均有四角色映射且职责分离；0 个 claim mapping gap。仓库没有具名接受事实，因此 12 个角色保持 `role-mapped`、0 个 `accepted`，页面显示"**4/4 角色已映射 · 0/4 已接受**"。

---

# 第三部分：两仓库的共同内核

## 3.1 不可妥协的规则（14 条，每条双仓出处）

两仓库之间**未见任何互相引用**——它们是两条独立演化的方法线，「共同内核」由本次对比得出，不是它们自己声明的。

1. **证据与声明必须分离**｜A `METHODOLOGY.md:9`「`G0–G6`：生命周期的人类决策门；**工具只能补证据，不能自行通过**。」／B `adrs/README.md`「ADR 接受仅代表设计决策，不代表实现、验收或生产状态。」
2. **状态之间不可互相升级**｜A `AGENTS.md:7`「不得把 publisher claim、安装状态、Skill 加载、认证、一次调用或生产可用性互相升级。」／B `ADR-001`「两套账本只能通过显式引用关联，**不允许互相继承等级**。」
3. **未知必须显式，且不得写成否定或安全**｜A `METHODOLOGY.md:37`「资料不足时显示"未知／未说明／未实测"，**不改写成"没有／无需／安全"**。」／B `m1-a-product-contract.md`「输入不足时只允许输出公式、区间、未知项和下一证据，**不允许伪造精确数值**。」
4. **工具与人的权限边界（默认无写能力）**｜A `METHODOLOGY.md:70`「写入、删除、发信、付费、发布、交易或生产动作仍需查看真实 tool schema、最小权限、预览或 dry-run、read-back 与明确授权。」／B `ADR-003`「**没有任何写工具、消息工具或 canonical promotion 工具**。」
5. **可重放 / 冻结真相源**｜A `README.md:25`「4,184 个 canonical plugin IDs，**冻结于 2026-09-16 01:29:11 +08:00**」+ `build-site.mjs:431` 记录 `sourceCommits`/`sourceHashes`／B `ADR-002`「**immutable snapshot 是权威合同**……SQLite 是可重建运行投影，不是 canonical source。」
6. **独立验收——生产者不能自证**｜A `README.md:48`「**生成后再运行独立 artifact 检查**」／B `m1-a-test-blueprint.md`「`| Negative | 固定负例必须失败 | 负例通过或失败原因不匹配 |`」+ `m1-b-cross-audit` 七视角。
7. **负例必须真的失败**｜A `build-site.mjs:449`「`throw new Error("Data validation failed:…")`」（**A 无固定负例集，只有断言失败即中止**）／B `m1-a-schema-catalog.md`「验证四个产品注册表、一个正例包、**六个固定负例**和跨对象不变量。」
8. **语言层面的诚实（禁用短语 / 保真改写）**｜A `METHODOLOGY.md:37`「**产品名、plugin ID、版本、数字、否定、条件、情态和完成状态保持不变。**」／B `m1-a-test-blueprint.md`「静态扫描阻止以下短语在 M1-A 页面无标签出现：`production-ready`、`已上线`、`真实客户验证`、`已验收`、`实时 Agent 已运行`。」
9. **授权逐项、当次、不可外推**｜A `METHODOLOGY.md:10`「真实外部动作仍需**对象级、当次、未过期**的授权。」／B `m1-b-cross-audit.md`「以上四组能力需要新的明确授权，**不能由"同意下一门禁"推断获得**。」
10. **回执绑定可复算摘要**｜A `build-manifest.json:5–14`（`artifactBytes`/`artifactSha256`/`embeddedData.{jsonBytes,gzipBytes,encodedBytes,sha256}`）／B `m1-b-implementation-receipt.md`「manifest hash 为 `sha256:cfa7d24c…4240`」+ `qa-receipt.md`「按合同、用途、主体、批准角色、决策和 **artifact SHA-256** 绑定」。
11. **变更后必须重跑全套门禁**｜A `AGENTS.md:9`「变更分类规则后，必须重新运行数据不变量、ELI5 checker、桌面/手机浏览器和公开页面验证。」／B `qa-receipt.md`「**最终又从头执行完整 `docs:qa`，没有忽略或降级该失败。**」
12. **失败不得降级、阈值不得放宽**｜A `PLAN.md:3` 预写完成标准「4,184 个插件身份不丢失；……每条记录有唯一主节点与"做什么／怎么用／怎么验"」／B `qa-receipt.md`「测得搜索交互代理 218ms，真实超过 200ms 门槛。**没有放宽阈值**」、`qa-receipt.md`「断言改为 URL 解码后核对语义锚点，**未放宽目标路径或交互标准**」。
13. **交付面分级 + 声明「不证明什么」**｜A `METHODOLOGY.md:74`「本地 HTML 检查、Git commit、远端 push、Actions workflow、Pages deployment 与公开页面字节验证，**任何一项都不能替代下一项**」／B `m1-b-cross-audit.md`「**明确区分 local、container、candidate cloud 与 production**」+ `qa-receipt.md` 的「范围声明」。
14. **角色「已映射」不等于「已接受」**｜A `site-template.html:1406`「Gate 贡献…**只供证，不能代替人通过**」／B `design-qa.md`「**不再把角色槽位伪装成具名 owner**」+ `qa-receipt.md`「仅有角色占位不能成为在线授权」。

## 3.2 哪些是「工程纪律」（可迁移到任何项目）

| # | 纪律 | 一句话操作化 |
|---|---|---|
| 1 | 生产者/验收者分离 | 生成脚本与校验脚本是两个程序；校验脚本的输入面只含交付字节 |
| 2 | 证据与状态分离 | 「观察到什么」与「因此处于什么状态」是两个字段，禁止自动推导 |
| 3 | 状态不可继承 | 上游通过不改变下游等级；父子/双账本之间只能显式引用 |
| 4 | 未知显式化 | 缺数据必须落一个词（未说明/未实测/未覆盖），**禁止落成 0、空串、false 或"安全"** |
| 5 | 四态而非二态 | 声明与载荷之间至少有：精确命中/版本漂移/本地精确/载荷缺失；另加「未声明」 |
| 6 | 逐项、当次、不可外推的授权 | 授权是一张白名单表；「同意下一步」≠「继承上一步权限」 |
| 7 | 默认无写能力 | 首版工具集只有 read/calculate/draft；写动作需单独且可被硬编码阻断的开关 |
| 8 | 冻结输入 + 摘要回执 | 每个交付物绑定输入 hash、产物 bytes、产物 sha256；receipt 可被第三方复算 |
| 9 | 负例必须真的失败 | 维护「预期必须报错」的 fixture 集；负例通过 = 门禁失效 |
| 10 | 语言层禁用词扫描 | 把「production-ready/已上线/已验收」做成静态扫描；允许的词必须带状态前缀 |
| 11 | 交付面分级 + 免责声明 | local/container/candidate-cloud/production 分开记；每份回执结尾写「不证明什么」 |
| 12 | 失败如实记录，阈值不放宽 | 失败写进文档并归类；修实现不修判据；调阈值必须单独说明理由 |
| 13 | 角色映射 ≠ 角色接受 | `role-mapped` 与 `accepted` 两个状态；占位角色不能授权任何事 |
| 14 | ADR 的「重新评估触发器」 | 每个技术决策配「什么条件下重新评估」，把悬而未决变成有条件决策 |

## 3.3 哪些是「该仓库特有」（不该照搬）

| 特有点 | 出处 | 为什么不该照搬 |
|---|---|---|
| M00–M13 十四节点及其内容 | `build-site.mjs:47–62`（含指向 `vibecoding_config@d0a611e` 具体行号的 `sourceUrl`） | 这是外部文档 `vibecoding_config` 的内容，照搬等于把别人的分类法当自己的领域模型 |
| `G0–G6` / `R0–R3` 编号体系 | `METHODOLOGY.md:9–10`；且 `:12` 已自陈与旧文档同名冲突 | 编号本身不带信息，且 B 的 `G0–G7` 是**另一套完全不同的门**；两仓 G 不可混用 |
| `effectClass` 七档 | `build-site.mjs:177–188` | 为「Codex 插件」的接口形态设计（MCP/App/CLI/Browser 标签参与判定），换领域必须重写判定规则 |
| 4184 / 5420 / 14 / 0 Ready Now 等硬编码 | `build-site.mjs:440`、`verify-artifact.mjs:23–24` | 是某次冻结快照的产物；新项目要断言自己的计数 |
| 单文件 HTML + CSP + gzip/Base64 + `DecompressionStream` | `README.md:9`、`METHODOLOGY.md:74` | 「离线单页」这个交付形态的约束；**思想**（无外部运行依赖、可离线验证）可迁移，**实现**不必 |
| 42 个手工精炼候选的编辑层 | `METHODOLOGY.md:60` | 42 是当时的人工投入量级；可迁移的是「编辑层可见、可回退、不改写原始名次」这个**结构** |
| L0–L6 对象链、Guide×Reference 双账本 | `m1-a-schema-catalog.md`、`ADR-001` | Kb2Agent 产品形态特有的分层，别的项目需要自定义层级 |
| `LO-S synthetic`、`CASE-AMZ-ACOS-SYNTHETIC` 等案例 | `m1-a-design-audit.md`、`m1-b-implementation-receipt.md` | 合成案例的**存在**是纪律，**具体案例**不可迁移 |
| 腾讯云 P8/P9 部署清单、Amazon Ads 领域 reviewer | `m1-b-cross-audit.md` | 强绑定该项目目标环境与领域 |
| `docs:qa` 的 17 步具体命令链 | `qa-receipt.md` | VitePress 项目特有；可迁移的是「串行门禁 + 从头重跑 + 退出码 0」这个**形式** |

**一处方法差异需要指出**：A **没有**「预期必须失败的 fixture 集」，只靠「断言不满足即抛错」（`build-site.mjs:438–451`）；B 两者都有（门禁矩阵 + 6 个固定负例 + 4 类失败注入）。**A 的做法无法证明门禁真的会拦**——若某条断言写错（如恒真），没有任何用例会发现。**迁移时应取 B 的形态。**

---

# 第四部分：对 Momcozy 营销内容合规审查项目的启示

## 4.0 先对齐事实（避免用方法论去解一个不存在的问题）

| 本项目已知事实 | 出处 |
|---|---|
| 21 条规则跑在 291 条真实记录上，**只能复现 13.8% 的人工判定**，且从不多报一条 | `research/governance/README.md:17,251` |
| `检查人` 填写率 **0/291** | 同上 `:17` |
| 291 条实际只有 **163 条不同素材**（1.7× 伪重复） | 同上 `:18` |
| **没有任何一列能承载人工复核结论**；`风险等级 × 处理状态` 完全对角（291/291）→ **判定从未被校准** | 同上 `:21` |
| 424 个检测关键词中**小语种词 0 个**，实际非英语文案占 28.2%；8 条规则无正则（含 H03/H04 两条红线） | 同上 `:21` |
| 未命中 → 显示「合规·绿」，「没覆盖」与「确认合规」**在数据模型里是同一个值** | `research/governance/规范-审核规则库完整设计.md` §5.1 |
| 委托方**没有强制卡点**（「目前无法强制卡死『审查完才能上线』的系统节点」） | 同上 §5.2.1 |
| PRD「子页面1 内容审查Agent-知识库」**无权限**，「本目录全部结论仅基于子页面2，拿到权限后须重跑」 | `research/governance/README.md:374` |
| 已有 9 个只读工具的对话 Agent「守衡」+ 19 项离线测试 | `PMO/守衡-架构说明.md` |

**这意味着**：项目当前最缺的不是「更多规则」，而是**判定状态的可观测性**——两个仓库的方法论恰好是围绕这件事长出来的，所以下面的映射不是硬套。

## 4.1 codex_research 的哪些做法可直接用于管理「需求/任务/证据」

**① 四态证据分层 → 直接映射到我们的四处证据缺口。** 关键是学 A 的默认值：`let evidenceState = "historical-payload-missing"`（`build-site.mjs:355`）——**默认取最坏态**。映射：`frozen-exact`=表内当前版本且导出 hash 一致（**当前仓库中未见该 hash 的记录机制，需新建**）；`current-version-drift`=手里有导出但表已改（导出时间 < 表最后修改时间）；`local-bundle-exact`=本地精确副本（如 `errorbook/errorbook.csv` 143×25）；`historical-payload-missing`=**PRD 子页面1 无权限**（`:374`）。**为什么这条最值钱**：现在「本目录全部结论仅基于子页面2」在人类阅读时是清楚的，但机器读一张表时它会退化成「有 52 条改写建议」——**权限缺口消失了**。落地：每条记录加 `evidence_state` + `evidence_version` 两字段，默认最坏态。

**② 「核心三件事」→ 每条规则、每条改写建议的固定三问。**

| A 的三问 | 我们的三问 | 对应的现有缺口 |
|---|---|---|
| 能帮你做什么 | 这条规则**能判什么**（覆盖的表述形态、语种、平台、品类） | 小语种覆盖 0%、8 条无正则 |
| 使用前要准备什么 | 判这条**需要哪些输入**（文案、投放地区、产品线、是否有 clearance） | `适用产品` 字段写死（规则库设计 §3.6） |
| 怎样确认真能用 | **最小验证**：用哪条已知正例/反例能确认它工作 | 判定从未被校准 |

强制方式照抄 A 的四层锁：数据层（缺字段校验失败）→ 产物层（生成的需求库必须含三问字段）→ 承诺层（manifest `checks.coreThreePresent: true`）→ 独立校验层。

**③ `effectClass` → 把「三级审查」与「动作影响」拆成两根正交轴。这是我认为最直接的映射。**

| 轴 | 内容 | 谁决定 |
|---|---|---|
| 审查深度轴（三级） | L1 机检 → L2 规则复核 → L3 终审 | 人按内容风险决定 |
| 动作影响轴（`effectClass`） | `read-only` 只判不改／`local-artifact` 产出改写草稿／`workspace` 写本地错题本／`external` 回写飞书·发通知·建工单 | 权限系统按动作决定 |

**为什么必须拆**：业务方原话是「无法强制卡死审查完才能上线」。若「三级审查」同时表示「判多深」和「能做什么动作」，一次「L3 通过」很容易被读成「可以自动回写飞书」。拆开后可以精确地说：**L3 通过只授权 `local-artifact`，`external` 仍需当次授权。** 每档自带验证动作可本地化（照抄 `site-template.html:1233–1241` 的形态）：`read-only` → 用一条已知答案的文案试读并与人工判定逐项对照；`external` → 先用预览/沙盒写一条记录再回读，并确认有回滚路径；`production` → 当前不授权。

**④ 三视角排序 + 缺失不当零 → 规则优先级排序。** 映射：节点适配 55% → **规则适配度**（这条在 291 条里能判多少、误报多少，我们已有实测数据）；功能潜力 35% → **可执行化潜力**（能否写成确定性检测器）；公开声量代理 ≤10% → **平台/法域声量代理**（三巨头 strike 模型、DSA/Ofcom 执法案例出现频次）。**「缺失不当零」在这里的具体含义**：`README.md:379` 记 `G10 | 加拿大（SOR/98-282）监管定性未调研 | Momcozy 有 14 条广告在跑，是真实空白`——这条**不能因为「没有声量数据」被排到最后**，应按 55/35 重新归一化，而不是按 0.9 倍打折。并照抄 A 的不对称双阈值：**只要「无正则」或「无正负例」或「无归属语种」，就直接进 `review`**，而不是等综合分低才进。

**⑤ 生成器 + 独立校验器双脚本 → `build-requirements.mjs` + `verify-requirements.mjs`。这是我们最该先照抄的具体结构。** 校验器只接收两个参数（学 `verify-artifact.mjs` 的 `process.argv[2]/[3]`），必须检查生成器**检查不到的三类**：完整性（`artifactSha256`/`artifactBytes`）、安全性（无凭据——2026-09-17 之前我们仓库里就有 `PMO/腾讯云-周健-SecretKey.csv`，现已按 ADR-0013 · D8 移出至 `~/.dsh/credentials/`；本地路径泄漏检测仍是**真实需求**）、存在性（学 `if (!html.includes("function coreTexts(item)"))` → 我们的 `if (!item.canJudge) errors.push(...)`）。**并且要断言「唯一实体数」而不只是「行数」**：291 条实际只有 163 条不同素材，所以除 `records.length !== 291` 外还应断言 `uniqueAssets(records).length !== 163`。**这里必须如实说明：A 只断言行数，没有断言去重后唯一实体数；这一条是从我们的缺口反推的改进，不是 A 的现成做法。**

**⑥ 诚实性写法 → 直接用在「未命中 ≠ 合规」上。** A 的禁则（`METHODOLOGY.md:37`「不改写成"没有／无需／安全"」）与我们已独立推导出的原则是同一条，可互相加固：

> `规范-审核规则库完整设计.md` §5.1｜**[判断] 这是整份设计里最重要的一句话。** 现状是：**规则没命中就是「合规·绿」**。｜`| 没有任何规则覆盖这个情形 | **合规·绿** ← 错 | **L0 未覆盖** |`

A 的增量价值在于给出了**实现层的话术库**（每个缺失原因配不同的词：`未说明`/`继承父插件`/`静态来源未列出`/`无可用外链`/`弱先验`）。我们现在的 `coverage_state ∈ {covered, uncovered, partially_covered}`（同文件 §5.5.1）只解决「规则覆盖」这一层，**还缺「为什么未覆盖」的话术**——可直接借鉴 A 的五种缺失词。另外 A 的 `runtimeState` 五档（`已安装并启用/已安装/默认关闭/目录标记不可用/可用未安装`）与我们 §5.2.1 推出的「检测器异常必须独立通道」是同一思想：**把「不能工作」与「工作结果为否」分开。**

**⑦ ADR 的「重新评估触发器」→ 我们的每一步决策。** 例：决定「用飞书多维表格作为规则库权威源」时，写明触发器「只有当规则数 > N 或需要跨表关系校验时，才评估迁到本地 YAML + 投影」——与我们「建本地需求知识库」的方向一致。

## 4.2 Kb2Agent 的 G 门 + receipt 机制，在本项目对应成什么

### 先明确 G 门在 B 里的实际形态

G 门不是一张「G0–G7 定义表」，而是**一串带编号、需逐项授权的门禁单元**：`m1-a-product-contract.md`「本轮只授权本地 P0–P2。`provider-call`、`deploy`、`canonical-write`、`external-send`、`commit`、`push` 和 `package-publish` 均需要新的明确授权。」；`m1-b-cross-audit.md`「下一门禁建议：M1-C Candidate Deployment Readiness」；`m1-a-execution-receipt.md`「M1-B 不自动开始。」（补充取证：`g6-a11-public-static-closeout-and-g7-roadmap.md` 把 G7 拆成 `G7-A1 provider-readiness contracts → A2 bounded shadow canary → A3 replay vs provider evaluation → A4 authenticated internal Agent candidate → A5 public product candidate`，并注明 `G7-A1 state: recommended-not-authorized`）。

**所以 G 门的本质是：每个门 = 一个可交付的增量 + 一张授权白名单 + 一份回执 + 一个不自动开始的下游。** （**仓库 B 中未见 G0–G7 的完整语义定义表**；上述描述基于实际编号使用与 G7 分阶段表。）

### 建议的 8 道门

| 门 | 名称 | 交付增量 | 授权白名单 | 回执要证明什么 | 下游 |
|---|---|---|---|---|---|
| G0 | 需求冻结门 | 一页纸 product-contract：四类知识库的定义、291/21/52/39 的口径与时间点、允许/禁止声明 | 只读本地文件 | 四张表的行数、**唯一实体数**、导出色与 hash、已知缺口清单（含子页面1 无权限） | G1 |
| G1 | 证据与样本门 | 正负样本抽取规则 + 错题本 132 条 A 类的人工复判结论 | 读飞书表，**不可回写** | 复判覆盖率、`检查人` 从 0/291 到 N/291、一致性 α | G2 |
| G2 | 规则契约门 | 21 条规则 → 机器可判 Schema（`coverage_state` 与 `severity` 正交 + 兜底规则 `CATCH-ALL-01`） | 本地 | 每条规则有三问字段、≥1 正例 + ≥1 反例；**负例必须失败** | G3 |
| G3 | 审查流水线门 | 三级审查本地实现（守衡侧只读工具） | 本地，**零外部调用** | 固定样本集跑通；FP/FN 第一次可算；`effectClass` 只到 `local-artifact` | G4 |
| G4 | 校准门 | 第一次真正的精度/召回度量（含 IAB Tech Lab `evaluation.py` 的 Balanced Accuracy） | 本地 | 有一个可与行业基准对比的数字；区分 `covered`/`uncovered`/`ERROR` 三通道 | G5 |
| G5 | 领域验收门 | 四角色具名 + 逐条规则接受回执 | 本地，**禁止任何外部写入** | `4/4 角色已映射 · x/4 已接受`；未接受的一律不得进入下一门 | G6 |
| G6 | 回写门 | 审查结果回写飞书 + 通知 | 仅飞书 API，**逐条、当次、可撤销**；先 dry-run + read-back | 回写前后 diff、可回滚路径、零误写 | G7 |
| G7 | 在线前哨门 | shadow：Agent 判定与人工判定并行，不产生任何外部动作 | 只读 | 一段时间内的一致性；**不覆盖人工基线**（学 `ADR-003`「live 只作为……限频对比，不覆盖 Replay 基线」） | 生产 |

### 四角色映射（照抄 B 的写法）

| B 的角色 | 我们的角色 | 现状 |
|---|---|---|
| 内容维护 | 规则库 owner（业务方，管 21 条规则内容） | 待具名 |
| 证据复核 | 合规/法务（能否引用 510(k)、RCT、平台政策） | 待具名 |
| 测试维护 | 工程（守住 291/163、错题本、评测脚本） | 待具名 |
| 最终批准 | 品牌/合规负责人 | 待具名 |

**初始状态就该写成 `4/4 角色已映射 · 0/4 已接受`，而不是「已设四角色」。**

### receipt 机制应产出什么

| Receipt | 对应 B 的哪份 | 字段级内容 |
|---|---|---|
| **RunReceipt**（每次跑批） | `ActionPackage + Trace + Receipt` | 输入快照 hash、规则版本号、模型/prompt 版本、逐条判定、证据 locator、`coverage_state`、ERROR 通道标记、成本/耗时、**零外部副作用声明** |
| **ChangeReceipt**（每次规则改动） | `m1-b-implementation-receipt.md` | 改前/改后规则、影响内容数、正负例回归结果、谁批准、何时生效 |
| **GateReceipt**（每道门） | `m1-a-execution-receipt.md` | 裁决字符串 + 授权白名单快照 + **零动作清单** + 下一门禁前置条件 |
| **DesignReceipt**（每轮界面改动） | `design-qa.md` | 差异收敛记录 + **固定的「视觉通过不提高内容成熟度」收尾句** |
| **QaReceipt**（每次全量门禁） | `qa-receipt.md` | 串行命令表 + 实测数字 + 退出码 + 失败与自我更正记录 + **「不证明什么」** |

## 4.3 如果要「照搬」，第一步应该先定什么

### 结论：先定**一页纸的 product-contract**，而不是先建目录、先写 Schema、先选技术栈。

三个理由（三处落点一致）：

① **B 把它放在 P0，且是全部工作的第一件交付物**：`m1-a-product-contract.md`「本文冻结 MKD · Knowledge to Agent 的首版产品合同。它约束本地候选实现，不证明 Reference runtime、真实 Amazon Ads 效果或生产部署已经完成。」它一份文件里同时定义：一句话价值、双产品线、主用户、旗舰任务、执行边界（允许/禁止）、输出合同、允许/禁止声明、非目标、退出条件、当前授权边界。

② **A 的第一步是「冻结真相源」，不是「建模」**，而且**在建任何模型之前先解掉编号同名冲突**：

> `PLAN.md:5–10`｜Phase 1 — 冻结真相源　- [x] 固定 `vibecoding_config` commit 并审计 M00–M13、A00–A13、G0–G6、R0–R3。……- [x] **识别旧版 G0–G6 与生命周期 Gate 的同名冲突。**

我们项目正有同类风险：**「三级审查」在业务语境指「判多深」，在权限语境可能被读成「能做什么」**——这正是 `effectClass` 被拆出来的理由。

③ **我们最贵的未解问题只有 product-contract 能关掉**：`规范-审核规则库完整设计.md` §5.2.1「委托方**没有强制卡点**……后果是**业务绕过审核流程** —— 这比漏放更危险。」「没有卡点」不是技术问题，是**授权与责任边界问题**，product-contract 的「当前授权边界」小节就是回答它的地方。

### 建议的第一份文件骨架（抄 B 的 10 节结构）

```markdown
# Momcozy 营销内容合规审查 Agent · 产品合同
> 状态：local-candidate · 证据上限：L1-规则命中 · 实现范围：P0-P1

## 一句话价值
（把四类知识库编译为有来源、有覆盖状态、可校准的审查证据链，
  再由受控 Agent 产出可复核、可回滚、不回写业务的审查建议。）
## 双账本（学 ADR-001，不允许互相继承等级）
| 账本 | 用户任务 | 权威资产 | 当前最大声明 |
| 规则账本 | 判定某条文案在某辖区/平台是否违规 | 21 条规则 + 释义层 + 兜底规则 | 具备本地可校验的规则合同 |
| 证据账本 | 证明某条判定有依据 | 510(k)/RCT/平台政策逐字 + locator | 具备本地证据台账 |
## 四类知识库的定义（是合同，不是清单）
文案 291 条（**唯一素材 163 条**）/ 规则 21 条 / 改写建议 52 条 / 正负样本 39 条
——每条必须带 evidence_state 与 effectClass。
## 主用户
A1 内容审核员：默认视图要能判断「为什么判违规 / 依据在哪 / 哪些未覆盖」
A2 合规法务：展开视图要能查证据 locator、规则版本、判定一致性
## 旗舰任务
固定一条合成文案（含已发生的假阴性「秒杀」），回答：应判成什么、依据哪一条、规则没覆盖时怎么记。
## 执行边界（允许 / 禁止）
允许：读冻结快照、确定性检测、生成待人工复核的建议、产出 Receipt
禁止：修改飞书表、发送通知、自动发布、接受自由文本/任意 URL（学 ADR-004）
## 输出合同
每条判定必须含：事实/推断/未覆盖分栏、证据 locator、coverage_state、
severity（uncovered 时必须为 NULL）、规则版本号、下一步动作。
## 允许声明 / 禁止声明（最重要的一节）
允许：「规则合同机器可读」「固定正负样本可在本地校验」「291 条的覆盖缺口已量化」
禁止：「审查系统已可上线」「判定已被校准」「九条红线已全部可自动检测」
     「三级审查已打通」「Agent 已回写业务系统」
## 非目标
多租户、账号计费、自动回写、模型微调、全量替换人工审核
## 退出条件
P0：四张表冻结 + 缺口清单 + product-contract + ADR 0001-0005
P1：规则 Schema + 兜底规则 + 固定负例 + 本地跑通 163 条唯一素材
P2：第一次校准数字（Balanced Accuracy）+ 四角色具名
## 当前授权边界
本轮只授权本地只读 + 本地产物。
feishu-write / external-send / deploy / auto-publish / agent-live 均需新的明确授权。
```

### 配套的三个动作（顺序不能换）

1. **冻结真相源 + 写缺口清单**（学 A 的 Phase 1）：固定 291/21/52/39 的导出色、hash、时间点，并逐条登记已知缺口——`PRD 子页面1 无权限`、`检查人 0/291`、`8 条无正则`、`小语种 0 个`、`291 条实为 163 条`。**缺口清单是资产，不是待办。**
2. **写 5 份 ADR**（学 B 的 `adrs/README.md`）：`ADR-001 规则账本与证据账本独立成熟度`、`ADR-002 飞书多维表格为权威源 + 本地 JSON 为可重建投影`、`ADR-003 审查 Agent 首版 replay-first、零写工具`、`ADR-004 输入面收敛：只接受白名单字段，禁止自由文本与任意 URL`、`ADR-005 未取得 PRD 子页面1 权限前，禁止把缺口写成「已覆盖」`（**阻断型 ADR**，学 ADR-005 的 `proposed-blocking` 形态）。
3. **建两个脚本的地基**（学 A）：`build-requirements.mjs` + `verify-requirements.mjs`，先只断言四件事——行数、**唯一实体数**、hash、缺口字段非空。**在系统还没建起来之前就把「生成」与「验收」分成两个程序**，这是最便宜、收益最大的一步。

## 4.4 三个最容易做错的地方

1. **不要把「三级审查流程」当成 `effectClass` 用。** 三级说「判多深」，`effectClass` 说「能碰什么」；混用的直接后果是「L3 通过 → 自动回写飞书」这种越权。
2. **不要在需求库里只记「有 291 条」。** 291 条实际只有 163 条唯一素材（`research/governance/README.md:18`），只记 291 会系统性高估样本量、低估伪重复。
3. **不要把「未命中」实现成默认合规。** 这是我们已经独立识别的最大风险（规则库设计 §5.1），也是 A 的 `METHODOLOGY.md:37` 在另一领域的同一句话——**在数据模型层就必须有第三个值**，不能靠 UI 提示。

---

# 附录 A：「仓库中未见」清单

| 问题 | 未见项 |
|---|---|
| Q1 | **R0/R1/R2 的逐条定义、`R3` 的含义展开**在仓库 A 中未见；`A00–A13` 的**内容定义**也未见（只有名称），逐条语义应在上游 `vibecoding_config` |
| Q3 | `METHODOLOGY.md:44–46` 只列四态，代码中另有第五态 `not-declared`（`build-site.mjs:376`），文档未提 |
| Q4 | Skill 的排序权重 `{fit: 0.65, functional: 0.28, publicProxy: 0.07}` 在 `METHODOLOGY.md` 中未见，只在代码里；`functionalScore`/`publicProxyScore` 的**上游计算过程**亦未见（来自未随仓库分发的 `plugin-research-snapshot.json`，见 `README.md:35–44`） |
| Q5 | 仓库 A 中**未见固定负例 fixture 集**（只有「不满足即抛错」的不变量断言） |
| Q7 | 仓库 B 中**未见 G0–G7 的完整语义定义表**；本报告的 G 门描述基于实际编号使用与（补充取证）G7 分阶段表 |
| Q7 | `m1-a-execution-receipt.md` 与 `m1-a-design-audit.md` 之间的**直接引用关系未见**（两份并列，互不引用） |
| 全部 | 两个仓库之间**未见任何互相引用**；「共同内核」由本次对比得出，不是它们自己声明的 |

# 附录 B：按问题编号的答案索引

| 问题 | 章节 |
|---|---|
| Q1 对象模型 | §1.2 |
| Q2 核心三件事的强制执行 | §1.3 |
| Q3 四态证据分层 | §1.4 |
| Q4 排序与 matchConfidence | §1.5 |
| Q5 校验清单 + 双脚本分离 | §1.6 |
| Q6 诚实性写法 | §1.7 |
| Q7 工作单元完整闭环 | §2.1（§2.2 ADR 机制） |
| Q8 design-qa vs qa-receipt | §2.3 |
| Q9 共同不可妥协规则 | §3.1（14 条，双仓出处） |
| Q10 工程纪律 vs 仓库特有 | §3.2 / §3.3 |
| Q11 对 Momcozy 的启示 | §4.1 / §4.2 / §4.3 / §4.4 |
