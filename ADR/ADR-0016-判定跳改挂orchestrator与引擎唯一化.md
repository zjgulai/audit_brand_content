# ADR-0016：判定那一跳改挂 orchestrator，且 rule_judge 为唯一判定引擎

- 状态：`accepted` —— **2026-10-25 委托方裁定**：由 `proposed` 推进为 `accepted`，
  **不另写一份方向相反的 ADR**。票清单 v2 原推荐的「B：保留双轨 + 版本标注」不作为反面决定，
  改记为本文件 **§5.4 的事实陈述**（现状是「合并尚未完成」，不是「双轨是设计」）。
  > 原状态行照留不删，逐字如下：`proposed`（§七 两项待 Owner 确认；§二/§三 是**已由委托方裁定**的两项，
  > 本条只把它们落成可执行口径与可指出的执行点）。
  > ★ 2026-10-25 核对发现：原句里的 **§七 应为 §九** —— 两道待确认的题在「§九、待 Owner 确认的问题」，
  > §七 是「口径陷阱」。原句按 ADR/README 规则 5（不因决策已定而删异议/原文）保留，此处只加注。
- 日期：2026-10-20（起草）· **2026-10-25（裁定 `accepted`，裁定人：委托方）**
- 编号属主：`audit-multi-content-4b`。**本条最初取号 ADR-0015，与
  `production-backend-assembly` 的同号 ADR 撞车；2026-10-20 本会话整份让号到 0016，
  对方那份 0015 一个字未动。事故与教训记在
  `PMO/implement/待办盘点与执行票-20261020.md` §二。**
- 决策者：委托方（§二 生产主链形态 / §三 判定引擎唯一化）· 开发者（口径细化、判据设计、边界代价核算）
- 依赖：ADR-0012（判定引擎产品化 · 处置分层）· ADR-0013（基座接口冻结）
- 触发：`PMO/audit/内容审核Agent-输入类型与工作流剖析-20261020.html` §2.2/§5.1/§5.2 的
  「设计主链与生产主链是两条不相交的链」，以及 §5.3 的 22 条契约裂缝。
  盘点全部待办后确认：这是唯一一个**元问题** —— 不定它，其余每条「接线待办」
  都是在给一条没人走的链继续接线。

> ★ 本 ADR 不复制剖析文档的内容：D-01…D-19 / W-01…W-16 / C-01…C-15 / U-01…U-08 的原文、
> 逐条证据与复现命令只在那一份 HTML 里。本文件只放**决策**与**它带来的票**。

---

## 一、问题：不是「缺功能」，是两条不相交的链

盘点六源（剖析 HTML / PRD / Playbook / 三份规格 / 代码现场 / 会话现场）之后，
待办有几十条，但它们几乎全部指向同一件事：

| | 设计主链 | 生产主链 |
|---|---|---|
| 入口 | `submission_router` → `normalizer` → `orchestrator` | `ws_daemon.mjs` → `agent.mjs` 模型工具循环 |
| 判定 | `rule_judge` + `semantic_judge` → `decision_table` | 模型**可以**调 `judge_copy`（25 个工具之一），**也可以不调** |
| 产物 | ContentUnit（双指纹 / parse_status）→ ReviewIR → 报告 | `judge.py` 的 verdict/receipt → 群里一句话 |
| 调用者 | `tools/smoke_end_to_end.py` §186、`tools/verify_orchestrator.py` §126 —— **只有测试** | 守衡守护进程，**真在跑** |

`base/orchestrator.py` 的 `Orchestrator` **在本仓非 vendored 代码里只有 3 处构造**，
全部在 `tools/verify_orchestrator.py:126,245` 与 `tools/smoke_end_to_end.py:186` ——
**`api/`、`base/`、`web/`、`tools/agent/` 里一处都没有。** 也就是说：
**对外承诺的五步 / 15 链 / 回执，不是线上实际跑的架构。**

> ★ **这一行的初稿写的是「全仓只有那两处构造」，是错的 —— 记在这里因为它是个典型陷阱。**
> `grep -rn "Orchestrator(" --include='*.py' .` 会命中 **4 处**，第 4 处是
> `research/repos/ad-review-agent/src/agents/review_agent.py:42` 的 `ReviewOrchestrator()`。
> 那是**挖来的第三方仓库快照**（`research/repos/` 整个目录被 gitignore，
> `git check-ignore` rc=0），与本仓的 `base/orchestrator.py` **没有任何关系**。
>
> 判据必须写成**限定范围**的：「`api/ base/ tools/ web/` 里有没有构造点」——
> 写成「全仓」就会把 vendored 仓库的**同名类**算进自己的口径里，
> 而那个数字看起来更「完整」。这与 AGENTS.md §2.4.1 是同一个形状：
> **读到了数、口径却比输入大。**

这条不先定，任何接线工作都可能白做 —— 因为在 A 方案下要接的点和在 B 方案下不是同一批。

## 二、决策一（委托方 2026-10-20 定）：群交互保留 LLM 循环，判定这一跳改挂 orchestrator

**不整体切 pipeline，也不维持现状。** 取中间那一刀：

```
ws_daemon.mjs onMessage
  └─ agent.mjs LLM 工具循环（保留：多轮追问 / 读文档 / 查状态 / 边界声明）
       └─ judge_copy  ← ★ 改造点：从「直接 execFile judge.py 返回 JSON」
                        改成「构造 ContentUnit → 调 Orchestrator → 返回五标签 + 回执」
```

**为什么选这条**：

- 群里多轮追问是本产品当前**唯一真实在用**的能力，切 pipeline 会把它弄丢，
  而这是最容易在「架构正确」的名义下付出的一次不可逆损失。
- `judge_copy` 已经是 25 个工具之一，改它不需要动 `agent.mjs` 的主循环结构。
  **改动面 = 一个工具 + 一个新入口，不是整条链重写。**
- `orchestrator` 的 `rule_judge` / `evidence` 本来就是**必须注入**的
  （`base/orchestrator.py:232-286` 的默认实现不含这两个），说明它的设计本来就预期
  「谁来判」是可换的 —— 这次只是把生产装配接上去。

**明确不做**（避免被读成「什么都保留了」）：

- 不因为保留了循环就承认「LLM 循环就是产品」。判定这一跳**必须**走 orchestrator，
  模型无权跳过。这一条要有执行点（见 §六 T2）。
- 不在这一步引入 `job_dispatcher` 的 worker 模型。第一阶段判定是同步的；
  异步化是后面的票，不是这张。

## 三、决策二（委托方 2026-10-20 定）：`rule_judge`（rules-v1.json）为唯一判定引擎

`skeleton/judge.py` 降级为**分析工具**（benchmark / 抽样 / 人工复核辅助），
不再参与生产判定。

**判据是硬的，不是偏好**：

| 需要的能力 | `rule_judge` | `skeleton/judge.py` |
|---|---|---|
| 产出 `control_code`（控制点覆盖四项之一） | ✅ | ❌ 无此字段 |
| 产出 `rule_key`（追到具体哪条检测规则） | ✅ `HIT_FIELDS` 已含 | ❌ |
| 下游 `decision_table` 吃得下 | ✅ | ❌ 输出 `disposition∈{auto_reject, manual_review, auto_pass_with_note, auto_pass, catch_all}` 不是五标签 |
| 与 `finding_store` 的 `ADMISSION_KEYS` 对齐 | ✅ `control_code/authority_ref/location` | ❌ 无 `authority_ref` |
| 输出的五标签 | 需一层映射（本 ADR §六 T3） | 需映射 + 需造 `control_code`，两件事 |

`skeleton/judge.py` 的输出是 `{boundary_statement, contract_version, hits, input,
receipt, suggestion, verdict, versions}`，**没有 `control_code`**。
没有它，`coverage_composer` 的「适用控制点」那一项填不出来 → coverage 恒 partial →
PASS 永远出不来（这一条当前**已经**成立，见 §五）。

**反过来说：换引擎不会让 coverage 变 full。** 见 §五 —— 那是 U2 的问题，不是引擎的问题。

### 3.1 `catch_all` 是这套映射里最危险的一格

`skeleton/judge.py` 的 disposition 取值域实测是
`{auto_reject: 11, manual_review: 13, auto_pass_with_note: 1, auto_pass: 1}`（26 条规则），
另有一个**不属于这四类**的 `catch_all`（`judge.py:729`）。代码自己写着它的含义：

> ★ catch_all 的含义是「**规则库没有覆盖它**」，**不是**「已检查且合规」。（`judge.py:831`）

映射到五标签时，它只能落 **未审查 / DP0**，绝不能因为 disposition 里带 `pass` 就落 PASS。
这一格是「没查到」与「查过没问题」长得一模一样的地方 —— 与 AGENTS.md §2.4.1 第 4 行
（否定结论的输入）是同一个形状。T3 的反向对照必须专门喂它。

### ★ 一个当场纠正：换引擎**不需要**重跑 65 条基准

我在提这一问时的推荐语里写了「65 条基准是在 skeleton 上跑的，需要重跑一次基线」。
**那句是错的**，写进 ADR 前核实后撤回了：

- 65 条基准验的是 **归轴**（一条规则该归 CHAN/RIGHT/…/CLAIM 哪一轴），读的是
  `rule_id` / `rule_text` / `condition` 与分类规范 §3。见
  `PMO/implement/基准复核-65条-循环第一轮-20261020.md` §一 —— 剥掉分类名、只读规范判。
- 检测层（`judge()` 产出 finding）与键级关联（rule_key ↔ rule_id）是**另外两层**。
  规范 §9.11 已把这三层分开写死，并记录了我自己两次被推翻的断言。

**把「归轴基准」说成「判定引擎的基线」正是 §9.11 禁止的那种混淆。**
所以：换引擎 **不触发** 65 条重跑。要不要为判定层单独建基线，是另一张票（T7），
不是这次换引擎的代价。

## 四、决策带来的连锁：三层关系必须重说一遍

规范 §9.11 已经钉死三层，本 ADR 不改它，只说明换引擎落在哪一层：

| 层 | 是什么 | 本 ADR 影响 |
|---|---|---|
| ① 归轴评测 | 规则 → 七轴，65 条基准测的就是这一层 | **不受影响**，不重跑 |
| ② 检测 | `judge()` 产出 findings（`control_code`/`rule_key`/`severity`/`quote`） | **换引擎 = 换这一层的实现** |
| ③ 键级关联 | `rule_key` ↔ `rule_id` 的映射 | **仍不存在**。36/638 桥接覆盖。不是本 ADR 修的 |

第 ③ 层不修，**不影响**判定跑通 —— 它是「这条 finding 对应规范里哪条规则」的追溯，
不是判定的前提。这一点必须说清楚，否则会被读成「映射没做所以判定不能上」。

## 五、代价与已知不解决的（写在这里，不写进票里假装能修）

### 5.1 换引擎**不会**让 PASS 变得可达

当前 `control-points-v1.json` 只有 20 个控制点，族分布 14/3/3，
**场景 / 权利 / 渠道 / 品牌 四族为空**（`empty_families`，理由均为「U2 点位内容未定，
待产品+法务签署」）。`base/coverage_composer.py:39-42` 自己明写：四空族计入 partial，
> ★ **2026-10-21 现状态**：品牌控制点 B01–B04 已以 `draft` 入表（规则 `enabled=false`），空族现为 **3（场景/权利/渠道）**。上一段保留 2026-10-20 的事实陈述，不篡改；当前值以 `control-points-v1.json` 的 `empty_families` 为准。
所以每一份内容都是 partial、**PASS 永远出不来**。

这是**产品能力缺口**，不是引擎选择问题。换谁当引擎都一样。
它只能由 U2（控制点主表内容，待产品+法务签）解决 —— 本 ADR **不试图**绕开它，
也不把「PASS 出不来」当成引擎的缺陷。

### 5.2 换引擎要付的迁移代价

`skeleton/judge.py` 现在同时被**生产**（`judge_copy`）和**分析**（基准/抽样）用。
本决定之后它只剩分析用途，但：

- `tools/agent/persona.mjs:114,122` 仍写着「每条结论必须能指到一条 `kb_search` 的命中」
  「judge_copy 会自己查知识库挂 `evidence_chain`」—— **而 `tools.mjs` 的 25 个工具里
  没有 `kb_search`**，`judge.py` 的输出也**没有** `evidence_chain`。
  这是 persona 与代码不一致，**不是本 ADR 造成的**，但改 `judge_copy` 时会撞上它。
  处理方式见 T4（不夹带修，单独一张票）。
- `tools/agent/kb_client.test.mjs` 当前直接崩（`TypeError` at :311，根因是
  `executeTool('kb_search')` 返回「未知工具」没有 `result` 字段）。
  这条在 T4 之前会一直是红的，**不要把 T2 的验收绑在它上面**。

### 5.3 明确不做的事

- **不**在这一步统一两套判定栈的**算法**。`rule_judge` 是 7 字段 P0 命中，
  `skeleton/judge.py` 是 score/vocab/severity；合并算法是独立课题，
  当前没有「合并后哪个对」的判据。
- **不**顺手改 `web-write-isolation` 的五项后端装配。那是他的范围，本 ADR 只登记依赖。

### 5.4 已知未完成：双轨仍然存在（**是现状，不是设计**）

> 这一节是 2026-10-25 裁定 `accepted` 时补写的。它的作用正好与标题相反：
> **它记录的是本 ADR 自己派下去的活还没做完**，不是给双轨找一个说法。
>
> ★ **读这一节时最容易犯的错**：「两条链路各自有回归读数，合并会引入未测风险」这句话
> 读起来像一条**决策理由**，于是下一跳就变成「所以双轨是设计好的」。
> **它不是。** 那句话在 §5.4.2 里被明确标注为**现状的成因描述**；
> 授权只在 §三 —— `rule_judge` 是唯一判定引擎。**把风险当理由，等于用代价否掉决策。**

#### 5.4.1 事实一：`judge_copy` 至今仍直接 `execFile judge.py`

这不是推测，是当前盘上的读数。**A15-T2 未做。**

```bash
$ grep -n "JUDGE_PY" tools/agent/tools.mjs
613:const JUDGE_PY = path.join(REPO_ROOT, 'research', 'governance', 'skeleton', 'judge.py');
702:      const args = [JUDGE_PY, '--text-file', tmp, '--json', '--brief', '--receipt',

$ grep -n "execFileP('python3', args" tools/agent/tools.mjs
708:      const { stdout } = await execFileP('python3', args, {
```

三条读数各自说明一件事：

| 读数 | 说明 |
|---|---|
| `JUDGE_PY` 指向 `research/governance/skeleton/judge.py` | 守衡调的是 **§三 已降级为分析工具** 的那个引擎，不是 `rule_judge` |
| `execFileP('python3', args)` 的目标是 `JUDGE_PY` | 是**子进程直调**，中间没有 `ContentUnit`、没有 `Orchestrator`、没有回执五步 |
| 全仓 `execFile.*judge\.py` 的**拦截面为 0** | §六 T2 要求的「调用点只允许出现在 `base/judge_entry.py` 以内」**没有任何代码在拦** —— 与 AGENTS.md §2.4「写进文档的约束必须能指出哪一行在拦它」同一条。取证见下（含正向对照） |

第三行要单独核一次，因为它才是「未完成」与「未完成且有护栏」的区别：

```bash
$ grep -rn "execFile.*judge\.py" tools/ base/ api/ web/ --include='*.mjs' --include='*.py'
（无输出，rc=1）
```

**这条「无输出」必须先证它不是恒真，否则它什么都说明不了。** 正向对照：

```bash
$ cat > /tmp/ctl-sample.mjs <<'EOF'
await execFileP('python3', ['research/governance/skeleton/judge.py', '--json']);
EOF
$ grep -rn "execFile.*judge\.py" /tmp/ctl-sample.mjs
/tmp/ctl-sample.mjs:1:await execFileP('python3', ['research/governance/skeleton/judge.py', '--json']);
（rc=0 —— 命中，说明扫描器活着）
```

两个读数合起来才是结论：**扫描器会命中（正对照 rc=0）+ 仓内零命中（rc=1）→ 全仓没有一行在拦这件事。**

> ⚠️ 这里的「零命中」**不能**直接推出「守衡没在直调 `judge.py`」——
> `tools.mjs` 那行的参数是**变量** `JUDGE_PY`，行内没有字面量 `judge.py`，所以这条 grep
> 按设计就扫不到它。两件事分开记：**调用确实存在**（上面第一条 grep 证明）
> 与**没有任何守卫**（这条 grep + 正对照证明）。
> 把两者混成「全仓 grep 零命中」就会得出相反的错误结论。
>
> ★ 写这一段时踩了一个坑，记下来因为它长得像通过：初稿写的是
> `grep -rn "execFile.*judge\\\\.py"`（四个反斜杠）。在单引号里它变成正则
> `execFile.*judge\\.py`（= 一个反斜杠 + 任意字符 + `py`），**在正样本上也不命中**（实测 rc=1）。
> 于是它恒真，而恒真的判据打印出来与「没找到违规」一模一样（AGENTS.md §2.4.4 同一个病）。
> **凡是写进文档的 grep，都要连同它的正向对照一起写。**

> ⚠️ 行号随时会漂（改一个函数就会整体移动）。
> **判据是 greps 的输出内容，不是行号。** 复现时带命令，不要当校对基准（AGENTS.md §2.2 第 1 条）。

#### 5.4.2 事实二：工作台侧走的是另一条链

| | 守衡（群） | 工作台 |
|---|---|---|
| 入口 | `ws_daemon.mjs` → `agent.mjs` 工具循环 → `judge_copy` | `api/production_app.py` → `base/submission_service.py` → `base/judge_entry.judge_unit` |
| 判定 | `research/governance/skeleton/judge.py`（**降级后的分析引擎**） | `base/judge_entry.py` → `Orchestrator` + `base/rule_judge.py` |
| 产出 | `judge.py` 的 `verdict.disposition`（`auto_pass` / `auto_reject` / …） | `decision_table` 的 `state`（`PASS`/`REVIEW`/`BLOCK`/`未审查`/`待自决`）+ `release_status` |
| 自证 | `tools/agent/judge_evidence_wiring.test.mjs` | `tools/verify_judge_entry.py` |

工作台侧那条链的 import 就是它自己说的：

```bash
$ grep -n "^from base.orchestrator\|^from base.rule_judge" base/judge_entry.py
23:from base.orchestrator import Orchestrator  # noqa: E402
24:from base.rule_judge import RuleJudge  # noqa: E402
```

**「两条链路各自有回归读数」这句话是事实**，两个读数当场都能跑出来：

```bash
$ python3 tools/verify_judge_entry.py | tail -1     # 工作台侧
✅ 12/12 全过

$ node tools/agent/judge_evidence_wiring.test.mjs | tail -2   # 守衡侧
✅ judge_evidence 接线自证 22/22 项通过
```

引用的两个文件数（口径写在命令里，别记数）：

```bash
$ grep -rl "judge_entry" tools/*.py | wc -l        # 工作台链的消费者
13
$ grep -rl "judge_copy" tools/agent/ | wc -l       # 守衡链的消费者
5
```

> ★ **这两句话的关系必须分清，否则下一个人会把它读成「双轨是设计」：**
>
> | 这是 | 不是 |
> |---|---|
> | **合并尚未完成的成因**：两条链各有自己的回归读数，任何一次合并都会让「原本绿的那一堆」变成未测 | **保留双轨的决定**：本 ADR 从未授权两条链并存 |
>
> 换句话说：「合并有代价」解释的是 **为什么 T2 到今天还没做**，
> 它**不构成「所以不做也行」的理由**。§三 的授权只有一条 ——
> `rule_judge` 是唯一判定引擎。**代价是决策的约束，不是决策的反面。**
> （这条如果读反了，就等于用 §五 的代价表把 §三 的决策撤销了，而没有任何一份 ADR 说过这样的话。）

#### 5.4.3 事实三：A15-T1…T7 七张票全部仍然有效

`accepted` **不取消任何一张票**。状态从 `proposed` 变 `accepted` 只意味着「方向定了」，
不意味着「活干完了」—— 这正是 `ADR/README.md` 规则 4 写的那句话。

```bash
$ grep -o "A15-T[0-9]" ADR/ADR-0016-判定跳改挂orchestrator与引擎唯一化.md | sort -u | wc -l
7
```

> ⚠️ 别用 `grep -c "^| \*\*A15-T"` 数：**下面这张状态表与 §六 的票表格式相同**，
> 它会被一起数进去（实测这条命令现在返回 `14`）。
> **一个把自己也数进去的计数，会随文档变长而变大。** 用 `sort -u` 数**票号去重**，
> 才不会把「同一张票写了两遍」当成两张票。

| 票 | 状态（2026-10-25 逐条核） | 判据 / 复现 |
|---|---|---|
| **A15-T1** `base/judge_entry.py` | ✅ **已落地** <br>`wc -l < base/judge_entry.py` → `197`<br>`python3 tools/verify_judge_entry.py` → `✅ 12/12 全过` | 存在 + 自证全绿 |
| **A15-T2** `judge_copy` 改调 T1 入口 | ❌ **未做**（见 §5.4.1） | `grep -n "JUDGE_PY" tools/agent/tools.mjs` 仍指向 `skeleton/judge.py` |
| **A15-T3** 五标签映射 | ⚠️ **工作台侧已落，守衡侧未落**<br>`base/judge_entry.py:146` 取 `result["decision"]["state"]`；守衡侧返回的仍是 `verdict.disposition` 的 `auto_pass/auto_reject/…` | 两侧返回字段的**取值域不同**，见 §5.5 |
| **A15-T4** persona 与代码对齐 | ⚠️ **半做**：`evidence_chain` 已真接线（`judge_evidence.mjs`，自证 22/22）；`kb_search` 仍未注册（`grep -c "register('kb_search'" tools/agent/tools.mjs` → `0`） | 工具名对齐只做了一半 |
| **A15-T5** 契约裂缝三条 | ⚠️ **修了两条，第三条仍在**：<br>· ✅ `content_unit_ref.kind` 已含 `ad_text`/`structured_json`（`base/content-unit-v1.schema.json:32`）<br>· ✅ `receipt.steps` 字段名已统一为 `input_summary`/`output_summary`/`duration_ms`（`base/orchestrator.py` 产出 ≡ `contracts/receipt-v1.schema.json`），并有反向对照 `tools/verify_contracts.py:354`「旧字段名 `input_digest`/`elapsed_ms` 必须拒绝」<br>· ❌ **`source_ir_version` 仍指向 ContentUnit**：实测 `judge_unit` 产出 `ir.source_ir_version = "content-unit-v1"`，而 `contracts/review-ir-v1.schema.json` 的 `source_ir_version.description` 逐字写着「**只指向 ReviewIR，不指向 ContentUnit** —— 这是 S-3 的核心裁定」 | 复现见本节末「T5 第三条的取证」 |
| **A15-T6** 四维落盘 | ❌ **未做**：`content_type`/`content_stage`/`entry_channel` 三个字段在 `base/content-unit-v1.schema.json` 的 `properties` 里**一个都没有** | `python3 -c "import json;s=json.load(open('base/content-unit-v1.schema.json'));print([k for k in ('content_type','content_stage','entry_channel') if k not in s['properties']])"` → `['content_type', 'content_stage', 'entry_channel']` |
| **A15-T7** 判定层基线 | ❌ **未做**：`PMO/implement/` 下没有判定层/检测层读数文档 | `ls PMO/implement/ \| grep -i "判定层\|检测层"` → 无输出，rc=1 |

> **怎么读上表**：✅ / ⚠️ / ❌ 标的是「这张票要的东西在不在盘上」，判据是右列那条命令**当天**的输出。
> **它不是验收** —— 「在盘上」与「够不够用、有没有反向对照」是两件事，
> 后者要跑各自的 `verify_*`，而本 ADR 没有为七张票逐张跑。
> 也就是说：右列命令的输出我可以背书；「够不够用」那一层**本表未测**。
> 引用时请重跑右列命令，不要抄我的结论（AGENTS.md §2.2 第 1 条）。

**T5 第三条的取证**（这一段单独放，因为它是我在写这一节时**才发现仍未修**的那一条）：

```bash
$ python3 - <<'EOF'
from base import contract as C
from base.judge_entry import judge_unit
u = C.from_text('测试', uri='inline:t5'); u['parse_status'] = 'ok'
r = judge_unit(u, clock=lambda: 1000.0)
print('source_ir_version =', r['ir'].get('source_ir_version'))
print('ir_version        =', r['ir'].get('ir_version'))
print('steps[0] keys     =', sorted(r['receipt']['steps'][0].keys()))
EOF
source_ir_version = content-unit-v1
ir_version        = review-ir-v1
steps[0] keys     = ['duration_ms', 'input_summary', 'name', 'output_summary']
```

第一行是缺陷，第二三行是已修好的对照：同一份回执里，`ir_version` 已经正确地是 `review-ir-v1`，
而 `source_ir_version` 还指着 `content-unit-v1`。**「已经改对了两个、剩下一个还是旧的」
是这里最危险的形状** —— 第三行全对会让人以为整块都改完了。

> 这一条与本文件 §七 表格第二行（#15）说的是同一件事的两个阶段：
> §七 记的是 2026-10-20 的现场（`input_summary`/`duration_ms` 对 `input_digest`/`elapsed_ms`），
> 那个已经修好了；`source_ir_version` 是在同一张票里、但**没跟着一起修完**的那一条。

### 5.5 「两条链路结论不同」什么时候允许 —— **当前：不允许**

这一节是**判据**，不是原则。拿它当一个检查项用：出现不一致时，按下表判定，不要凭印象。

#### 5.5.1 判据

| 情形 | 允许？ | 动作 |
|---|---|---|
| 同一段文本，两条链给出**相同**结论 | — | 正常。**但不构成证据说明双轨没问题** —— 一致可能只是这段文本恰好不触发差异 |
| 同一段文本，两条链给出**不同**结论 | **不允许** | **记为缺陷**，见 §5.5.3 |
| 一条链给出结论、另一条链**不可用**（引擎报错 / 未测） | 允许（但不是「一致」） | 必须在对外回复里说清是哪一侧、哪种不可用。**不许读成「另一侧也认为没问题」** |
| 两条链的结论**表述不同但语义等价**（如 `auto_pass` 与「未发现拦截理由」） | 允许 | 但必须能写出**一对一**的映射表；写不出来就是上一条 |

**根子是 §三 的授权，不是我的偏好**：`rule_judge` 是唯一判定引擎（委托方 2026-10-20 定，
2026-10-25 推进为 `accepted`）。所以「两条链路都算数」这个状态**在决策层面从来没有被授权过** ——
双轨存在的原因是 §5.4.2 说的「合并尚未完成」，不是「两个答案都对」。

> ★ 最常见的错读：把「两个引擎算法不同，没有『合并后哪个对』的判据」（§5.3 第一条）
> 读成「所以两个答案都可以」。**那句话说的事实是「合并这件事还没定口径」，
> 不是「两个口径都成立」。** 前者是待办，后者是授权 —— 而 §三 没有给过这个授权。

#### 5.5.2 当前差异是**真实存在**的，不是理论风险

2026-10-25 实测，同一段文案：

```bash
$ python3 - <<'EOF'
import json, subprocess, tempfile
text = '这款吸奶器静音模式很好用'
p = tempfile.mktemp(suffix='.txt'); open(p,'w').write(text)
o = subprocess.run(['python3','research/governance/skeleton/judge.py',
                    '--text-file', p, '--json', '--brief'], capture_output=True, text=True)
print('守衡侧 disposition =', json.loads(o.stdout)['verdict']['disposition'])

from base import contract as C
from base.judge_entry import judge_unit
u = C.from_text(text, uri='inline:probe'); u['parse_status'] = 'ok'
r = judge_unit(u, clock=lambda: 1000.0)
print('工作台侧 label =', r['label'], '| layer =', r['layer'])
EOF
守衡侧 disposition = auto_pass
工作台侧 label = REVIEW | layer = DP3
```

**两条链对同一句话给出了不同的结论**：守衡说「机器未发现拦截理由」（`auto_pass` → DP1 业务自审），
工作台说 REVIEW（DP3）。

这不是「谁算错了」。两边各自的自证都是绿的（§5.4.2 的两个读数），各自的逻辑在**自己的口径里**
都成立。它们不一致，是因为**它们回答的不是同一个问题**：

| | 守衡 `skeleton/judge.py` | 工作台 `rule_judge` + `decision_table` |
|---|---|---|
| 回答的问题 | 「规则库有没有命中拦截理由」 | 「这份内容能不能放行」 |
| 底数 | score/vocab/severity 打分 | 7 字段 P0 字面命中 + 控制点覆盖 |
| 无命中时 | `auto_pass`（**带有**「机器未发现拦截理由，不是判定通过」的对外话术） | `REVIEW` —— 覆盖不全就不许 PASS（`partial` 永不 PASS） |
| 对「静音模式」这类词的处置 | 命中 → 降级/放行带 | 命中 P0 → 走 `decision_table` 链序 |

所以**「方向相反」这个说法不准**，要改：不是两个引擎互相矛盾，
是**一个回答「有没有拦的理由」，一个回答「能不能放」**。这正是 AGENTS.md §2.4.1 那个形状 ——
**两个读数各自都对，合起来是两件事**。

> 但**这不是给它开脱**。对群里等结论的人来说，「未发现拦截理由」与「REVIEW」
> 是两个不同的处境，而他只看得到一条。**差异真实存在，且用户在意的正是差异本身。**
> 这就是 T2 必须做完的理由，不是可以商量的偏好。

#### 5.5.3 出现不一致时怎么办（可执行，不是口号）

在 T2 完成之前，凡是发现两处结论不一致：

1. **记为缺陷，不是记为「设计如此」。** 登记处用现有的事故/误答登记
   （`PMO/守衡-误答登记-*.md` / `PMO/audit/故障登记-*.md`），一条一个样本，
   **必须带那段文本原文与两侧的原始返回值**。
2. **不许在对外回复里出现「两个引擎都这么说」或「以其中之一为准」。** 后者尤其危险：
   在本 ADR 下，**权威侧是 `rule_judge`**，但守衡今天**根本没调它** ——
   所以「以 rule_judge 为准」这句话在守衡链上是一句**没有执行点的承诺**
   （AGENTS.md §2.4.2 同一个形状）。
3. **它不阻塞别的票，但它决定 T2 的优先级**：每一个这样的样本，
   都说明守衡正在对外给出一份与工作台不同的判定。样本越多，T2 越不该往后排。
4. **一致不算通过。** 上面 §5.5.1 第一行已经写了 —— 两条链对同一段文本给同一个答案，
   可能只是这段文本刚好不触发差异。**「没红过」不等于「不会红」**（AGENTS.md §2.4.1）。

**这条判据自身的执行点在哪**：目前**没有**。这是必须写明的 ——
§5.5 现在只是一份**人工判据**，没有任何代码在跑它。T7（判定层基线）做完之后，
它才会变成一个能自动比对的读数。**在那之前，谁读到一份不一致，谁就是执行点。**

## 六、口子（tickets）：每一张都必须指得出执行点

> 编号沿用本仓习惯：`A15-Tn`。每张票的「执行点」一栏若为空，**这张票就不许被记成做完了** ——
> 与 AGENTS.md §2.4 同一条规矩：写进文档的上限/约束，必须能指出哪一行代码在拦它。

| 票 | 做什么 | 范围（文件） | 执行点（判据在哪一行变红） | 依赖 |
|---|---|---|---|---|
| **A15-T1** | 新增 `base/judge_entry.py`：入参纯文本 → 构造 ContentUnit → 调 `Orchestrator`（注入 `rule_judge` + `evidence`）→ 返回 `{label, receipt, findings}` | 新文件（不碰 `api/`、`base/` 既有模块） | `tools/verify_judge_entry.py`（新建）：① 同一文本两次产出同 `unit_id`；② 五步各恰好一次且顺序逐字等于 `STEP_ORDER`；③ `release_status` 恒 `待放行`；④ **反向对照**：把 `rule_judge` 换成返回 `[]` 的桩 → 必须落 REVIEW/未审查，不许落 PASS | 无（可立刻开工） |
| **A15-T2** | 把 `tools/agent/tools.mjs:614-690` 的 `judge_copy` 改成调 T1 的入口；**不许**再直接 `execFile judge.py` | `tools/agent/tools.mjs`（单文件，614-690 段） | `node tools/verify_cards.mjs` 不红 **且** 新增断言：全仓 `execFile.*judge\.py` 的调用点只允许出现在 `base/judge_entry.py` 以内；喂一个「模型跳过判定」的工具轨迹 → 必须红 | T1 |
| **A15-T3** | 五标签映射：`rule_judge` 的 finding → `decision_table` 的 state 已有，但「群回复用哪个标签」需要一层收口 | `tools/agent/tools.mjs`（返回形状） | 断言：`judge_copy` 的返回值**必须**含五个标签之一，且 `release_status` 为 `待放行`；喂 `PASS` 且 coverage=partial → 必须红（这条已在 smoke R3 有先例） | T1 |
| **A15-T4** | 对齐 persona 与代码：`persona.mjs:114,122` 关于 `kb_search` / `evidence_chain` 的两句，要么补实现要么改文案 | `tools/agent/persona.mjs` | 断言：persona 里提到的每个工具名都在 `tools.mjs` 的 register 列表里；缺失即红。**这条与 T2 分开做**，不夹带 | 无 |
| **A15-T5** | 契约裂缝第一批（**只修会改行为的三条**）：`receipt.steps` 字段名、`review-ir.source_ir_version` 指向、`content_unit_ref.kind` 补 `ad_text`/`structured_json` | `base/orchestrator.py`、`contracts/review-ir-v1.schema.json`、`base/content-unit-v1.schema.json` | `tools/verify_contracts.py` 新增 B-6：**用 orchestrator 真实产出的回执**喂 `receipt-v1` schema（现在只喂手造 good_receipt）；喂旧字段名 → 必须红 | 无（与 T1 并行） |
| **A15-T6** | 四维落盘：`content_type` / `content_stage` / `entry_channel` 进 ContentUnit 与 Attempt | `base/content-unit-v1.schema.json`、`base/normalizer.py` | 断言：L1-0「四维每个取值都能产出 unit」**从产物复算**，不再只测 `submission_router` 的 accepted/rejected（当前 #1 就是这么绿的，见 §七） | 无 |
| **A15-T7** | 判定层基线：为 ②检测层单独建一套读数（**不是**重跑 65 条归轴基准） | `PMO/implement/` 新文档 + fixture | 判据：同一份 fixture 在两个引擎上跑，读数与差异逐条可列出。**未测就写未测** | T1、T2 |

**不开的票**（明确记下，防止被当成遗漏）：

- U2 控制点主表内容（产品+法务签）—— 不是工程票，本 ADR 只挂依赖。
- `web-write-isolation` 的五项后端装配 —— 他的范围，`feb8d57` 已登记未开工。
- `skill/` 37 个成员的安装与 NEEDS_INPUT 映射 —— 依赖产品口径，独立课题。
- 图片/视频通道 —— 属于输入层，与判定跳无关，不要夹进这一批。

## 七、口径陷阱：两条「绿但窄」的验收必须一起报

盘点时发现验收 runner 的 `mapped=110 / passed=110 / untested=26`（rc=**2**，不是 0）
里有两条是**命令退 0 但判据没逐字成立**的：

| 验收行 | 映射到 | 它实际证明的 | 它没证明的 |
|---|---|---|---|
| **#1**（甲 / L1-0 / SEC-8-1） | `verify_submission_router.py` | 各取值 accepted/rejected | **「每个维度都产出 ContentUnit」** —— 四维不落盘，结构上无法从产物复算（T6） |
| **#15**（SEC-3.3.3-1…6 / L2-7 / SEC-8-13） | `verify_contracts.py` | 手造 `good_receipt` 合 schema | **真实 orchestrator 的回执**合 schema —— 字段名是 `input_summary`/`duration_ms`，而 schema 要 `input_digest`/`elapsed_ms`（`base/orchestrator.py:155,308-311` vs `contracts/receipt-v1.schema.json`）（T5） |

所以 runner 的 110 passed 读作「**命令退 0**」，不读作「判据成立」。
这条本身就是 AGENTS.md §2.4.1 的同一个形状：**读通了接口，但口径读错，安静地产出假绿。**

> ★ **2026-10-25 现状更新（不改上表，只加注）**：上表 #15 那两对字段名，
> `receipt.steps` 那一对**已经修好**（`input_summary`/`duration_ms` 已是现行字段名，
> 并有反向对照拒绝旧名）；但**同一张票里的第三条 `source_ir_version` 仍未修** ——
> 实测仍指向 `content-unit-v1`。详见 §5.4.3 的「T5 第三条的取证」。
> **A15-T5 因此不能记成完成**：三条改完两条。上表的原始记载保留，
> 因为它是 2026-10-20 的现场读数，删掉就无处可查「当时差在哪」。

## 八、反向对照：这个 ADR 自己也要能被证伪

本 ADR 的核心断言是「判定这一跳将走 orchestrator」。如果将来没人能指出
「哪一行在拦模型跳过判定」，那它就退化成一句注释。所以：

- T1 / T2 / T3 各自带一条**喂坏样本必须红**的反向对照，写在票的执行点栏里。
- T5 的 B-6 是**用真实产出**喂 schema，不是再手造一份 —— 手造的那份正是今天假绿的成因。
- 若 T1 完成后 `smoke_end_to_end` 不再是唯一构造 `Orchestrator` 的地方，
  应当**新增**断言把「生产构造点」与「测试构造点」分开计数，而不是删掉 smoke。

## 九、待 Owner 确认的问题

> ★ **2026-10-25 之后这两问仍然开着**（状态推进为 `accepted` 没有回答它们）：
> 两问都是**实现口径**（T3 怎么映射、T4 补实现还是改文案），不是决策方向。
> `accepted` 定的是方向 —— **这两问不因它关闭，也不会因为它而变得不重要**。
> 按 `ADR/README.md` 规则 4：「ADR 被接受只代表设计决策已定，不代表已实现」。
> 谁在 T3/T4 上动手，谁就要先把这两问的答案要出来；**不要自己替它们定**。

1. **T3 的五标签映射口径**：`rule_judge` 的 finding 经 `decision_table` 得出的 state
   是否就是群里回复的标签，不再另做一层？当前 `decision_table` 已经产出五标签，
   但生产 `judge_copy` 今天返回的是 `skeleton/judge.py` 的 `disposition`。
   本 ADR 倾向「直接采用 decision_table 的 state，不再叠加映射」—— 需确认。
2. **T4 的方向**：`persona.mjs` 那两句（`kb_search` / `evidence_chain`）是
   **补实现**还是**改文案**？这取决于知识库（`~/.dsh/Momcozy知识库` 不存在）
   是否在近期计划内。本 ADR 不给推荐 —— 它是产品决策，不是工程决策。

## 十、异议留档

（按 `ADR/README.md` 规则 5：即使决策与建议相反，建议原文与依据也保留。）

- **关于「整体切 pipeline」的异议**：PRD v2.0 优化稿 §9.3（v1.2 无 §9.3；现行说明见该节）与 Playbook §2 要求五步 pipeline
  「每步恰好一次、无回边、无轮次」。§二 的决定让生产入口保留 LLM 循环，
  意味着这两条判据在**群交互路径**上不成立。辩护是：判定这一跳仍然恰好一次、
  仍然无回边；循环发生在**判定之外**（读文档、追问、查状态）。
  **这个辩护是否被验收接受，不由本 ADR 决定** —— 需在验收表里为 §2 的五步判据
  明确一条「适用范围」注记，否则 runner 会一直把它当成对整条生产路径的要求。
  这条注记我没写，因为它是验收口径的改动，属共享登记簿，需先与人对齐。

---

## 附：本 ADR 引用的现场读数（时点值，不是常量）

| 读数 | 值 | 复现 |
|---|---|---|
| `Orchestrator` 构造点 | **11 处，其中 1 处是生产**（`base/judge_entry.py:136`） | `grep -rn "Orchestrator(" --include='*.py' base api tools web` → 11 |
| ~~同上，别名口径~~ | ~~3 处，全在测试~~ **← 这个口径是错的，2026-10-26 更正** | `grep -rn "O\.Orchestrator(" …` → 3。**它靠 `O.` 别名把 `base/judge_entry.py:136` 的 `Orchestrator(` 筛掉了**，于是读起来像「连生产也没有」，与 §5.4.2 的事实（工作台确实在跑 orchestrator）直接冲突。★ 这正是本项目反复记的那个形状：**口径比输入大**。改口径时不要删旧读数，让它与被更正的原因并存 |
| 生产工具数 | 25 | `grep -c "^register(" tools/agent/tools.mjs` |
| 控制点 | 20 个，全部 `literal`，族 14/3/3，四族空 | `base/control_points.py` / `control-points-v1.json` |
| 验收 runner | mapped=110 / passed=110 / untested=26，**rc=2** | `python3 tools/verify_acceptance_run.py` |
| 契约 schema 数 | 4 份 + `base/content-unit-v1.schema.json` | `ls contracts/*.json` |

> 这些数字会漂移（AGENTS.md §2.2 第 1 条）。引用时请带上复现命令，不要当校对基准。
