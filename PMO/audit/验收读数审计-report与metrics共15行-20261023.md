# 验收读数深度审计：`verify_report_render.mjs`（9 行）与 `verify_metrics_read_model.py`（6 行）逐行行为核查（2026-10-23）

> **任务性质**：按 `audit-multi-content-05` 指令，对本会话名下「一条命令支撑多行 passed」的两支核心验证器（共 15 行验收项）做**行为级而非编号字面量级**的逐行拆解审计。
> **三条硬约束**：
> 1. **(a) 只审计，不改脚本、不改验收表、不改 `verifier_map.json`**；
> 2. **(b) 凡未覆盖或仅部分覆盖而缺失关键行为判据的行，明写「`#NN` 应回退到 `untested`（或判为部分覆盖缺口）」**，绝不为了保住 `passed=121` 的读数而把半截断言说成全覆盖；
> 3. **(c) 每行给出「表格原文逐句拆解 + 脚本里对应断言名与 `文件:行号` + 具体缺什么」**，并专项核查 `#80–#84` 与今天 `#129`（`InlineMetricSummary.tsx` / `check_no_metrics_dashboard.mjs`）的前后端口径一致性。

---

## 一、总表：15 行验收项的三分类真实读数

| 验收器 | 宣称覆盖行数 | **行为覆盖（全覆盖）** | **部分覆盖（有对应物但缺一半）** | **未覆盖（0 对应断言 / 放在错的脚本）** | 审计结论摘要 |
|---|---:|---:|---:|---:|---|
| **`tools/verify_report_render.mjs`** | **9 行**（`#37, #57, #58, #60, #61, #62, #63, #66, #67`） | **2 行**（`#58, #63`） | **5 行**（`#37, #57, #60, #61, #67`） | **2 行**（**`#62` 完全未覆盖**、**`#66` 核心多 finding 优先级未覆盖**） | **9 行里只有 2 行真正全覆盖！`<br>`#62`（M4 并行义务短标记）在 `report_render.mjs:318-342` 的 `renderMessage()` 里甚至连 `obligations` 字段都没读，100% 假绿，必须回退 `untested`！`<br>`#66` 只造了 1 条 finding，从未测「1 个 L4/L5 + 2 个 L1/L2 不被数量吞掉」。** |
| **`tools/verify_metrics_read_model.py`** | **6 行**（`#9, #80, #81, #82, #83, #84`） | **1 行**（`#80`） | **4 行**（`#81, #82, #83, #84`） | **1 行**（**`#9` 完全不在该脚本**） | **`#9`（`failure_kind` 四类计数且报告全列）在 `verify_metrics_read_model.py` 里 0 断言（只测了一个 `fetch_error_count == 2`），纯粹是绑错了脚本，必须回退或改绑！`<br>`#81–#84` 共同缺失「跨两个自然月窗口过滤（`MetricsReadModel` 把 `window` 当装饰字符串原样返回，根本没按时间过滤 `cases`！）」與「首次测量后记录基线并做趋势比较」。** |
| **合计** | **15 行** | **3 行（20%）** | **9 行（60%）** | **3 行（20%）** | **15 条 `passed` 中，至少 3 条（`#9, #62, #66`）应立即回退 `untested`，9 条存在明确的行为级缺口（连同被测模块 `report_render.mjs` 与 `metrics_read_model.py` 自身的实现缺口）。** |

---

## 二、第一支：`tools/verify_report_render.mjs`（搭配 `tools/audit/report_render.mjs`）逐行审计（9 行）

### 1. `#37` · 视频五项覆盖声明与关键帧读数（`V1 / V2 / V4 / V5`）
* **分类判定**：**部分覆盖（验了 40%，缺 60%）**
* **验收表原文要求的 4 件事 vs 脚本实际验了什么**：
  1. **V1（五项覆盖键与第一阶段枚举承诺）**：
     - 表格要求：「断言 `covers` 中字幕、内嵌文字、关键帧、音轨、完整画面语义五个键都存在且**值属于约定枚举**；**逐一删除每个键构造五个负样本**，断言提交被拒；**断言按第一阶段承诺音轨为未覆盖、完整画面语义为部分覆盖**。」
     - 脚本已验：`verify_report_render.mjs:299, 306-309`（`C9` 验了五键存在；`R5` **只删了 `音轨` 1 个键**，没逐一删 5 个键）。
     - **脚本未验（且 `report_render.mjs:150-155` 未实现）**：
       - **未校验枚举值**！在 `video.covers` 里写 `{ 字幕: "随便写", 音轨: "yes", 完整画面语义: "full" }`，`validateSnapshot` 照样算通过！
       - **未断言第一阶段承诺**（`音轨 === "no"`、`完整画面语义 === "partial"`）。
  2. **V2（三数交叉核对：`frames ≈ duration / interval ± 1`）**：
     - 表格要求：「解析报告断言抽了几帧、视频总时长、抽帧间隔三个数都存在且单位明确；**与回执里的总帧数、抽帧间隔以及视频元数据的总时长交叉核对，帧数约等于总时长除以间隔，允许边界差 1**；缺任一数即判红。」
     - 脚本已验：`verify_report_render.mjs:301-303, 310-315`（验了三个数是 number 且删除 `frames` 会红）。
     - **脚本未验（且 `report_render.mjs:156-160` 未实现）**：**完全没有校验 `Math.abs(frames - duration_seconds / interval_seconds) <= 1`**！传 `{ frames: 999, duration_seconds: 60, interval_seconds: 2 }` 照样绿！也没跟 `receipt` 交叉核对。
  3. **V5（回执中存在抽帧间隔与总帧数且与 `frame_no` 对拍）**：
     - 表格要求：「断言回执中存在抽帧间隔与总帧数两个字段且数值与实际抽帧一致；删除任一字段的回执断言 schema 校验失败；用这两个字段与 `frame_no` 复算互相对拍。」
     - **脚本完全未验（0 断言）**：`baseSnapshot().receipt`（`:85-91`）里根本没有 `frames` / `interval_seconds` 字段，也没做 `frame_no` 复算对拍。
  4. **V4（「视频已审」短语守卫）**：
     - 表格要求：「生成一条只写『视频已审』的报告或群消息，断言文案检查器报红；生成一条带齐五项覆盖声明的文案，断言通过；检查器按『出现该短语即要求同一句或同一段含五项』实现。」
     - 脚本已验：`verify_report_render.mjs:299-303, 316-322`（`R5 消息说「视频已审」但无五项 → 红`）。

---

### 2. `#57` · Markdown 渲染必跑、时点、输入输出（`SEC-4.3.1-1 / SEC-4.3.1-2 / SEC-4.3.1-3`）
* **分类判定**：**部分覆盖（验了渲染器纯函数输入与只读性，缺完整流程时点顺序与篡改敏感性）**
* **验收表原文要求的 3 件事 vs 脚本实际验了什么**：
  1. **时点顺序与必跑（`SEC-4.3.1-1`）**：
     - 表格要求：「跑一次完整流程，检查步骤/回执顺序：状态确定事件早于 md 生成，md 生成早于群消息/报告输出；断言 md 中已是最终状态而非空状态；把渲染步骤跳过时流程必须报错。」
     - **脚本未验**：`verify_report_render.mjs` 只直接调 `R.renderReport(baseSnapshot())` 单测渲染函数，没有测「状态确定 → md 生成 → 群消息输出」的流水线时序与跳过报错。
  2. **只接受冻结 IR 输入 + 幂等性 + 篡改 IR 随动（`SEC-4.3.1-2`）**：
     - 脚本已验：`verify_report_render.mjs:337-349`（`C10 塞 store → 违规依赖`、`C10 渲染器不写盘/不联网`、`C10 渲染不改输入`）。
     - **脚本漏验的一半**：「同一 IR 重渲染两次结果一致；篡改 IR 中的状态或 finding 后重渲染，md 必须随之变化」—— 脚本没有显式写 `renderReport(s).markdown === renderReport(s).markdown` 与篡改前后 diff 断言。
  3. **产物扩展名 `.md` 与 Markdown 解析（`SEC-4.3.1-3`）**：
     - 脚本已验：返回 `r0.markdown` 字符串并按 `## ` 解析各区块（`:105-111, 136`）。

---

### 3. `#58` · md 六区块逐字、字段齐全、空块写「无」
* **分类判定**：**行为覆盖（全覆盖，微瑕仅在枚举负样本）**
* **对应脚本断言与行号**：
  - 六个标题逐字且各出现恰好 1 次：`verify_report_render.mjs:135-141`（`C0 区块标题逐字且恰好一次`）
  - 同义替换坏样本（`## 问题列表`）：`verify_report_render.mjs:142-143`（`C0/F2 不许同义替换标题`）
  - 六区块必带字段逐字核对（含 `放行状态：待放行`）：`verify_report_render.mjs:154-170`（`C1/F2 ## 结论..## 执行回执 字段逐字齐全`）
  - 空内容最小样本不省略区块且写「无」：`verify_report_render.mjs:171-189`（`C2/F1 空内容不省略区块 & 空内容写「无」`）
  - 反查 IR 指纹与版本：`verify_report_render.mjs:145-151`（`R1 报告带 source_ir_version + 64 位 IR 指纹`）及 `:186, 232` 每条 finding 输出 `finding_id` 与 `control_code`（`:361-373` `C12/C13`）。

---

### 4. `#60` · 群消息骨架与五档必带字段
* **分类判定**：**部分覆盖（验了五档正向骨架，缺 4 个反向对照 + 发现 1 处严重行为缺陷）**
* **对应脚本断言与行号**：
  - 五档开头 `【标签】` + 单行 + 末尾报告链接 + 关键字段：`verify_report_render.mjs:191-215`（`C3 五标签消息：BLOCK/REVIEW/未审查/待自决/PASS → 一句 + 报告链接`）。
* **缺失的反向对照与潜伏的代码缺陷**：
  1. **★ 潜伏的真 bug（被这次审计抓出！）**：
     - 验收表要求：「REVIEW 消息……用**原因为空的坏样本做反向对照**」「待自决消息……用**待决事项为空的坏样本做反向对照**」「PASS 消息……把该句换成『未发现问题』或**删掉即判红**」。
     - 看 `tools/audit/report_render.mjs:331-340`：
       ```js
       } else if (state === "REVIEW") {
         detail = ir.decision.review_reason || "需要人看";
       } else if (state === "未审查") {
         const u = asArray(snapshot.unassessed)[0];
         detail = u ? `${u.part}：${reasonText(u.reason)}` : "未审原因未提供";
       } else if (state === "待自决") {
         detail = ir.decision.self_decide || "请提交人确认是否修改";
       }
       ```
     - **铁证**：当 `review_reason` 为空时，`renderMessage` 居然静默兜底成了空泛的 `"需要人看"` 并返回 `ok: true`！这**正面违反**了验收表 `#60` 原文写的「**不是空泛的『请人工看一下』；用原因为空的坏样本做反向对照**」！同理，`BLOCK` 无 finding 时兜底成 `"最严重命中缺失"` 仍返回 `ok: true`；`待自决` 缺 `self_decide` 时兜底成 `"请提交人确认是否修改"` 仍返回 `ok: true`！
  2. 脚本 `C3` 只跑了 5 个正样本，**0 个缺字段坏样本反向对照**。

---

### 5. `#61` · 每档恰好一句、机器生成、其余进报告（`M1 / M2 / M3`）
* **分类判定**：**部分覆盖（验了单行无换行和纯函数确定性，未验「0 句 / 2 句坏样本被拒」）**
* **对应脚本断言与行号**：
  - 单行无换行、`【标签】` + 报告链接：`verify_report_render.mjs:208-213`（`!text.includes("\n")`）
  - 模板纯函数生成（无 LLM 调用）：`report_render.mjs:318-363`
* **具体缺什么**：
  - 表格要求：「按约定的句子边界切分消息正文，断言【标签】与报告链接之间恰有 1 个句子；**构造 0 句和 2 句的坏样本做反向对照，检测必须变红**。」
  - 现状：如果往 `ir.decision.review_reason` 里塞两句话 `"第一句原因。第二句原因。"`，`renderMessage` 会原样拼出含 2 个句子的群消息并返回 `ok: true`！脚本没有句子边界切分器，也没有 0 句 / 2 句的反向对照。

---

### 6. `#62` · 并行义务短标记（`M4`）
* **分类判定**：**未覆盖（0% 覆盖 —— `#62` 应立即回退到 `untested`！）**
* **验收表原文要求**：
  > 「构造『`BLOCK + has_candidate=true`』样本，断言消息在关键句后出现对应并行义务标记（如『`· 另有 1 条疑似待确认`』）且数量/类别正确；构造无并行义务样本，断言不出现该标记（反向对照）。」
* **盘上代码铁证**：
  - 查 `tools/audit/report_render.mjs:318-343` 的 `renderMessage(snapshot)`：
    ```js
    let text = `【${state}】${detail} · 报告：${snapshot.report_url || "无"}`;
    ```
  - **`renderMessage` 整个函数里根本没有读取 `ir.decision.obligations`，也没有统计 `status === "candidate"` 的 finding 数量！**
  - 在 `verify_report_render.mjs:54` 的 `baseSnapshot()` 里，虽然写了 `obligations: ["partial_coverage"]`，但 `renderMessage(baseSnapshot())` 产出的群消息里**一个字都没提并行义务**！`verify_report_render.mjs` 里也**没有任何一行断言检查群消息里的并行义务短标记**。
  - **结论**：`#62` 是一条**100% 零实现、零断言的假绿**，必须回退到 `untested`（并在后续修票中补齐 `renderMessage` 的 `M4` 并行义务短标记逻辑与正反例）。

---

### 7. `#63` · 去 AI 味七条按等级执行
* **分类判定**：**行为覆盖（全覆盖）**
* **对应脚本断言与行号**：
  - 七条规则（4 条 `block`：`chatbotResidue / conclusionTail / hedgeStack / internalLeak`；3 条 `warn`：`padding / ruleOfThree / connectorStack`）逐条喂坏样本验证等级：`verify_report_render.mjs:236-257`（`C6`）；
  - 报告正文只拦 `chatbotResidue` 与 `internalLeak`，不拦 `padding`：`verify_report_render.mjs:258-260`（`C6 padding 不适用于报告正文`）；
  - 四条阻断级在 `renderReport` 与 `renderMessage` 中真正拦截（`ok === false && blocked === true`）：`verify_report_render.mjs:262-278`（`C7`）；
  - 警告级照发且记录 `warnings`（不许也被拦）：`verify_report_render.mjs:280-286`（`C8`）；
  - 干净样本不误报：`verify_report_render.mjs:136, 208`（`C0`、`C3`）。
  - （注：底层 `tools/reply-cards/registry.mjs` 的 2 层 hedge 不触发等边界亦在 `verify_cards.mjs` 中有成对验证）。

---

### 8. `#66` · 群里不刷屏、L4/L5 不被数量吞掉（`L4-1 / SEC-8-8`）
* **分类判定**：**未覆盖（脚本只测了单条 finding，未测多条不同严重度 finding 排序 —— `#66` 应回退到 `untested` 或补齐多条样本断言）**
* **验收表原文要求**：
  > 「用 L 刻度构造『**1 个 confirmed L4/L5 + 2 个 L1/L2**』的样本（不用 P），跑输出，断言群里消息直接显示那条 L4/L5 的严重度、控制点、逐字原文、位置，而不是只出分类汇总；若只出汇总或最严重条被数量盖掉即红。再构造多条同质 finding，断言群消息仍按 M1 只有一句、不逐条刷屏。」
* **盘上代码实况**：
  - 虽然 `tools/audit/report_render.mjs:310-316` 写了 `worstFinding(findings)` 函数（按 `confirmed` 优先 + `SEVERITY_RANK` 降序取第 0 条），
  - **但是在 `tools/verify_report_render.mjs` 里，`baseSnapshot().ir.findings`（`:38-50`）从头到尾只有 `1` 条 finding（`f-1`）！**
  - 整个 `verify_report_render.mjs` **一次都没有构造过 ≥2 条 finding 的样本**！如果把 `worstFinding()` 改成直接返回 `findings[0]`（把 2 条 `L1/L2` 放在数组前面、1 条 `L4` 放在数组末尾），`verify_report_render.mjs` **今天照样 100% 全绿**！
  - 因此，`verify_report_render.mjs` **完全没有验证 `#66` 要求的行为**。

---

### 9. `#67` · 未审两层输出与不冒充已审（`丁 / SEC-8-5`）
* **分类判定**：**部分覆盖（验了 `PASS + partial` 被拒与基础 `未审查` 消息，缺三类未审样本词表禁令与 `UNASSESSED vs CLEAN-CANDIDATE` 对照）**
* **脚本已验**：
  - `verify_report_render.mjs:195`（`C3 未审查` 群消息带 `无能力`）；
  - `verify_report_render.mjs:324-334`（`L1-6 PASS + coverage=partial → 报告/消息均拒绝`）。
* **脚本未验（缺口）**：
  1. 未分别构造 `parse_status=failed`、`coverage missing`、`unsupported` 三类未审样本并做禁用词表断言（断言生成文案中不出现 `已审 / 已通过 / 没问题 / PASS`）；
  2. 未构造一条 `UNASSESSED` 与一条 `CLEAN-CANDIDATE` 样本跑报告并断言两者的标签、原因说明、覆盖证明不同。

---

## 三、第二支：`tools/verify_metrics_read_model.py`（搭配 `base/metrics_read_model.py`）逐行审计（6 行）

### 1. `#9` · `failure_kind` 四类分别计数且报告全列（`L1-7 / L1-8 / SEC-8-10`）
* **分类判定**：**未覆盖（绑错了验证器！`#9` 在 `verify_metrics_read_model.py` 中未覆盖，应回退或改绑）**
* **验收表原文要求**：
  > 「造 `empty` 2 条、`parse_error` 3 条、`fetch_error` 1 条、`unsupported` 1 条的样本跑统计与报告；断言 **`empty=2` 与其余 `failed` 合计=4 分别可见且可核对**，而不是只有一个失败总数。再跑一次全部成功的正常运行，断言 **`fetch_error`、`parse_error`、`empty`、`unsupported` 四个键都存在且值为 0**，缺任一键或写成空白即红。」
* **盘上铁证**：
  - `base/metrics_read_model.py:167-169` 在 `_uncovered` 里**只算了 `clean_candidate_count`、`error_count`、`fetch_error_count` 三个字段**，**根本没有统计 `empty`、`parse_error`、`unsupported`！**
  - `tools/verify_metrics_read_model.py` 全文搜 `parse_error` 只有第 85 行造夹具出现 1 次（作为 `unassessed` 的背景属性），搜 `unsupported` **0 次**，搜 `empty=0` **0 次**！
  - （注：反倒是 `tools/verify_report_render.mjs:217-226` 的 `C4` 测了报告里的 `fetch_error=0 parse_error=0 empty=0 unsupported=0`，但也只测了全 0 和 `unsupported=1`，没测「`empty=2` 与其余 `failed` 合计=4 分别可见」）。
  - **结论**：把 `#9` 绑在 `verify_metrics_read_model.py` 上是**彻底的错绑**，`#9` 必须回退到 `untested`（或补齐专门的 `failure_kind` 聚合与报告对拍断言）。

---

### 2. `#80` · 四指标七要素、未测、n/样本不足（`L5-1 / L5-2 / L5-5 / SEC-8-20`）
* **分类判定**：**行为覆盖（全覆盖）**
* **对应脚本断言与行号**：
  - 四指标七要素（`numerator / denominator / window / sampling_layer / min_n / status / target`）齐全：`verify_metrics_read_model.py:134-145`（`A1`, `A2`, `A2b`, `A2c`, `A2d`）；
  - 断开数据源（抛异常 / 返回 `None` / 坏结构 / 空 `window`）输出精确等于 `"未测"` 且分子分母与 `ratio` 均为 `None`（非 `0` / `N/A`）：`verify_metrics_read_model.py:173-187`（`B1–B4`）；
  - `n < 30`（`n=10`）跑召回率与推翻率显示 `"样本不足"` 且 `ratio is None`、`n == 10`；`n >= 30`（`n=40 / 48`）比率与 `n` 同时出现：`verify_metrics_read_model.py:146-171, 188-204`（`A3, A5, A8, C1–C3`）；
  - 加上今天 `#129` 的 `web/scripts/check_no_metrics_dashboard.mjs:230-265`（`C3` 逐一删掉七要素任一字段共 7 轮断言标为 `不可用`），`#80` 的正反向判据均已闭环。

---

### 3. `#81` · 高危召回率定义与读数（`SEC-6-R1-1 … R1-7`）
* **分类判定**：**部分覆盖（验了分子/分母基础公式、缺层未测、样本不足与待基线，但漏了 4 项关键行为，含 2 处 `MetricsReadModel` 实现盲区！）**
* **脚本已验**：
  - 40 条人工 L4 中 32 条机器 L4、8 条机器 L2 → `32/40 = 0.8`（`A3`，`:146-149`）；
  - `sampled_layers` 缺一层 → `status="未测"` 且 `ratio=None`（`D1`，`:206-210`）；
  - 样本不足与断开数据源 → `"样本不足"` / `"未测"`（`B1–B4`, `C1`）；
  - 首次测量前 `target=None, target_status="待基线"` 且源码无数字字面量（`A2c`, `F1–F2`）。
* **脚本未验（且暴露出 `base/metrics_read_model.py` 的 2 个真盲区）**：
  1. **★ 盲区一：混入 `BLOCK` 层样本时，代码没有过滤掉 `state == "BLOCK"`！**
     - 验收表 `#81` 原文要求：「**构造一条 BLOCK 层样本混入，断言它不进入召回率抽检集（BLOCK 是阳性类，走 §6.1 ② 的全量复核，不进召回采样）**」；「断言 PASS / 待自决 / REVIEW / 未审查 各有一份独立抽样清单与条目；任一层缺失、或把两层及以上混成一个池，即红。」
     - 看 `base/metrics_read_model.py:120-124`：
       ```python
       human_pos = [c for c in cases if c.get("human_max_sev") in HIGH_SEV]
       numerator = sum(1 for c in human_pos if c.get("machine_max_sev") in HIGH_SEV)
       denominator = len(human_pos)
       sampled = set(cov.get("sampled_layers") or [])
       ```
     - **铁证**：`_recall` 根本没有检查 `c.get("state") in RECALL_LAYERS`！如果在 `dataset()` 里有一条 `state="BLOCK", machine_max_sev="L4", human_max_sev="L4"` 的样本，`_recall` 会**直接把它算进召回率的分子和分母**！而且 `_recall` 只看了 `cov["sampled_layers"]` 这个声明数组里有没有四个名字，根本没检查 `cases` 里是不是真的四层都有抽样样本！
  2. **★ 盲区二：`window` 参数完全没参与过滤（跨月样本未实现、未测试）！**
     - 验收表 `#81/#82/#83/#84` 全部要求：「**构造跨两个自然月的样本，跑默认窗口计算，断言只统计当月；改窗口参数后断言参与计算的样本集合变化。**」
     - 看 `base/metrics_read_model.py:89-114`：`window` 只是原样传给 `self.load(window)` 并写回返回字典 `m["window"] = window`，`dataset()` 里的 `case` 甚至连 `created_at` / `month` 字段都没有，`verify_metrics_read_model.py` **一次都没用两个不同月份的 `window` 调过 `compute()`**！
  3. **边界值 `n=29` vs `n=30`**：脚本 `C1` 用的是 `n=10` 和 `n=40`，没测 `n=29`（样本不足）与 `n=30`（出比率）的紧邻边界。
  4. **首次测量后记录基线并与后续周期比较**：脚本只测了 `target=None`（待基线），未测「完成首次测量后基线读数被记录，后续周期与基线比较」。

---

### 4. `#82` · 高危误判率定义与读数（`SEC-6-R2-1 … R2-7`）
* **分类判定**：**部分覆盖（且发现「验收表原文」与「脚本/代码」在未复核条目分母口径上正面冲突！）**
* **脚本已验**：
  - 40 条已复核机器 L4 中 8 条人工降为 L2 → `8/40 = 0.2`（`A5`，`:153-156`）；
  - `block_review_complete=False`（`30/42`）→ `status="未测"`、`ratio=None`、`reviewed_coverage = 30/42`（`D2`，`:211-217`）。
* **缺失项与口径冲突**：
  1. **★ 验收表原文 vs 代码分母口径冲突**：
     - 验收表 `#82` 原文写：「样本集中加入系统 L4/L5 但无人工结论的条目，**断言分母包含它，且分母等于系统判 L4/L5 的总数**。」
     - 而 `base/metrics_read_model.py:23, 138-140` 与 `verify_metrics_read_model.py:75, 154` 写的是：「2 条机器 L4 未复核：**不得进误判分子/分母**（`reviewed = [c for c in machine_pos if c.get("review_completed") is True]`，`denominator = len(reviewed) = 40` 而不是 `42`）」。
     - 这两处对「未复核的机器 L4 条目进不进 `denominator`」定义相反，必须由编排会话裁定以哪一处为准（虽然未复核完时 `status="未测"` 不出 `ratio`，但 `denominator` 填 `40` 还是 `42` 直接矛盾）。
  2. 同样缺失**跨月样本窗口过滤**与**首次测量后基线比较**。

---

### 5. `#83` · 未覆盖占比定义与读数（`SEC-6-R3-1 … R3-7`）
* **分类判定**：**部分覆盖（核心分子分母与 `CLEAN-CANDIDATE` 排除已验，缺 `n=1` 边界、入口计数核对、跨月窗口与基线比较）**
* **脚本已验**：
  - 分子只算 `state == "未审查"` 且非 `ERROR` / 非 `fetch_error`（20 条），`CLEAN-CANDIDATE`（3 条）、`ERROR`（2 条）、`fetch_error`（2 条）计入分母（67 条）但不计入分子：`verify_metrics_read_model.py:157-165, 220-226`（`A6, A7, E1`）；
  - `n=0` 不出百分比：`verify_metrics_read_model.py:200-203`（`C3`）。
* **脚本未验（缺口）**：
  1. 未显式构造 `n=1`（分母为 1）的合成数据断言给出比率而非「样本不足」（虽然 `MIN_N_UNCOVERED = 1` 已定义，但 `verify_metrics_read_model.py` 未跑 `len(cases) == 1` 的用例）；
  2. 未验证「构造一条未被计入的条目，断言总数与入口计数不符即红」；
  3. 同样缺失**跨月样本窗口过滤**与**首次测量后基线比较**。

---

### 6. `#84` · 人工推翻率定义与读数（`SEC-6-R4-1 … R4-7`）
* **分类判定**：**部分覆盖（验了推翻率基础计算与申诉胜败进分母，缺「人工维持但理由不同不进分子」专项样本、`n=29/30` 紧邻边界、跨月窗口与基线比较）**
* **脚本已验**：
  - 分母为有机器结论且有人工结论的 48 条，无人工结论的 2 条 `unrev` 不进分母：`verify_metrics_read_model.py:166-169`（`A8`）；
  - 申诉胜（`won`）与败（`lost`）均计入分母：`verify_metrics_read_model.py:170-171, 227-235`（`A9, E2`）。
* **脚本未验（缺口）**：
  1. 验收表要求：「构造**人工与机器同结论、人工推翻、人工维持但理由不同**三类样本，断言分子只计结论不同的条数。」—— 脚本 `dataset()` 里没有 `reason_changed=True` 但 `machine_conclusion == human_conclusion` 的专项对照样本；
  2. `C2` 只测了 `n=10`，未测 `n=29` vs `n=30` 紧邻边界；
  3. 同样缺失**跨月样本窗口过滤**与**首次测量后基线比较**。

---

## 四、专项核查：`#80–#84`（`base/metrics_read_model.py`）与今天 `#129`（前端 `InlineMetricSummary.tsx`）口径对得上吗？

按 `05` 的提示，我把 `base/metrics_read_model.py` 的输出结构与今天新建的 `web/src/components/InlineMetricSummary.tsx` 及 `web/src/pages/{QueuePage,CaseDetailPage,ReportPage}.tsx` 逐行比对，结论是：**Schema 校验函数对得上，但存在 2 处真实断层**：

### 1. 对得上的部分（七要素 Schema 级）
* `InlineMetricSummary.tsx:18-26` 的 `SEVEN_METRIC_KEYS`（`numerator, denominator, window, sampling_layer, min_n, status, target`）与 `verify_metrics_read_model.py:39` 的 `SEVEN` 列表**逐字恒等**；
* `check_no_metrics_dashboard.mjs:205-225` 在 `C1` 中用子进程真调了 Python `MetricsReadModel` 的正常态、异常未测态（`raises=True`）和样本不足态（`n=10 < 30`），喂给前端 `validateMetric()` 全部通过。

### 2. 对不上的两处真断层（主动曝光）

#### 断层 A：前端 `validateMetricSevenElements` 在 `BLOCK 未复核完`（`D2`）或 `召回缺抽样层`（`D1`）时会忽略后端的 `ratio: None`（防呆依赖 `status === "未测"` 的判断顺序）
* 在 `base/metrics_read_model.py:124-130, 149-155` 中，当召回缺抽样层或 `block_review_complete != True` 时，后端依然填了数字型的 `numerator`（如 `8`）和 `denominator`（如 `40`），同时设 `status = "未测"`、`ratio = None`、`reviewed_coverage = 30/42`。
* 前端 `InlineMetricSummary.tsx:104` 幸好先判了 `if (status === "未测") return { displayValue: "未测" }`，所以没算出假百分比；**但是前端完全没有读取或展示 `reviewed_coverage`（已复核占比 `30/42`）**！而验收表 `#82` 与 `verify_metrics_read_model.py:13, 213` 明确要求「BLOCK 未全量复核 → 显示 `未测` + **已复核占比**」。前端 `InlineMetricSummary.tsx` 把 `reviewed_coverage` 丢了。

#### 断层 B：三张页面（`QueuePage / CaseDetailPage / ReportPage`）挂载的 `<InlineMetricSummary>` 目前传的是页面本地计数，**根本没有调用 `GET /metrics` 或 `validateMetricSevenElements()`！**
* 看 `web/src/pages/QueuePage.tsx:350-355`、`CaseDetailPage.tsx:419-424`、`ReportPage.tsx:148-153`：
  - `QueuePage` 传的是：`countsLabel="待办 X 条..."`、`trendLabel={null}`、`untestedLabel={queued.length > 0 ? "partial" : "未测"}`；
  - **三张页面里没有任何一处调用了 `validateMetricSevenElements()`，也没有消费后端的 `MetricsReadModel` 四指标输出！**
  - 也就是说：`validateMetricSevenElements()` 目前只被 `check_no_metrics_dashboard.mjs` 测试脚本调用，**在真实前端页面运行时是 dead export（0 个页面组件调用它）**！这正是 `AGENTS.md` §2.4「定义了却没有在业务链路里接通」的变体。

---

## 五、审计结论与处置建议（等待 `05` 派修票）

1. **应立即回退 `untested`（或判为未覆盖）的 3 行**：
   - **`#9`**（`failure_kind` 四类计数且报告全列）：绑在 `verify_metrics_read_model.py` 上纯属错绑，该脚本 0 断言覆盖 `empty / parse_error / unsupported` 四键全列；
   - **`#62`**（`M4` 并行义务短标记）：`report_render.mjs` 的 `renderMessage` 根本没读 `obligations` / `candidate`，`verify_report_render.mjs` 0 断言；
   - **`#66`**（群里不刷屏、`L4/L5` 不被 `L1/L2` 数量吞掉）：`verify_report_render.mjs` 全程只有 1 条 finding，从未测多 finding 严重度排序与不刷屏。
2. **需在下一张修票中补齐的 9 行部分覆盖缺口**：
   - **`report_render.mjs` & `verify_report_render.mjs`（`#37, #57, #60, #61, #67`）**：
     - `#37`：补 `V1` 五键枚举值校验 + 第一阶段承诺（`音轨=no, 完整画面语义=partial`）+ 5 个单删负样本；补 `V2` `frames ≈ duration / interval ± 1` 校验；补 `V5` 回执 `frames/interval` 与 `frame_no` 对拍；
     - `#57`：补同一 IR 两次渲染恒等、篡改 IR 随动、以及流水线时序/必跑断言；
     - `#60`：**修掉 `renderMessage` 在 `review_reason` / `self_decide` / `findings` 为空时静默兜底返回 `ok: true` 的真 bug**，补齐五档缺字段坏样本反向对照；
     - `#61`：补群消息句子边界切分（恰 1 句）及 0 句 / 2 句坏样本被拒断言；
     - `#67`：补三类未审样本禁用词表（禁现 `已审/已通过/没问题/PASS`）及 `UNASSESSED vs CLEAN-CANDIDATE` 报告差异断言。
   - **`metrics_read_model.py` & `verify_metrics_read_model.py`（`#81, #82, #83, #84`）+ `#129` 对齐**：
     - `#81`：**修掉 `_recall` 未过滤 `state == "BLOCK"` 及未按四层校验实际抽样条目的真 bug**；
     - `#81–#84` 共性：补齐 `window` 自然月过滤（跨月样本测试）、`n=29 vs n=30`（及 `#83` `n=1`）紧邻边界、首次测量后记录基线并做趋势对比；
     - `#82`：裁定并统一「未复核的机器 L4 条目是否计入 `denominator`」；
     - `#129`：在 `InlineMetricSummary` 中补齐 `reviewed_coverage`（BLOCK 已复核占比）展示，并在页面中真实接入 `validateMetricSevenElements`。

<!-- END OF DOCUMENT: acceptance-15rows-audit-ea-20261023 -->
