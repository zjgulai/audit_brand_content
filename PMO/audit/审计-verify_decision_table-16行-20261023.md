# 审计：`tools/verify_decision_table.py` 覆盖的那 16 行验收

> 日期：2026-10-23 · 产出：`audit-multi-content-f3`
> **只审计，不改脚本、不改表格**（按 05 的约束 a）。
> 审计对象：验收表行 `18, 25, 27, 28, 29, 30, 31, 32, 33, 38, 39, 40, 42, 45, 46, 47`
> 与 `tools/verify_decision_table.py`（`--controls` 之外的主检）。

## 方法（以及刻意不用什么）

**不拿 `criteria` 编号去源码里 grep**。05 的第一版就是这么做的，报出 94 行「一个编号都找不到」——
它量的是「编号有没有出现」，不是「行为有没有被验」。本审计逐行读**表格原文要什么**，
再去脚本里找**做那件事的断言**（断言名 + 行号）。

三分类：
- **行为覆盖**：脚本里有对应断言，且测的是该行要的行为；
- **部分覆盖**：验了一半，或验的是相邻但不等价的东西；
- **未覆盖**：脚本里没有对应物。

---

## 一、16 行逐行结论

| 行 | 表格要什么（要点） | 脚本里的对应物 | 结论 |
|---|---|---|---|
| **18** | `detected_by∈{P0..P3}` 与 `severity∈{L0..L5}` 两套刻度；24 种组合全接受且只按 L 算；禁 P→L 查表；`confirmed+L0→ERROR(I4)`；`candidate+L0` 接受但不计严重度；排序不把 L0 当最小；P0 规则只含正则/关键词；语义样本 `detected_by≠P0` | `C4`（L0 confirmed → ERROR + I4，:259）。**其余没有**：无 detected_by 取值域断言、无 24 组合、无 P→L 扫描、无 P0 仅正则的扫描、无语义样本 | **部分覆盖** |
| **25** | 仅 candidate（含 L4/L5）→ REVIEW 且标「有疑似」；confirmed L1/L2 + 多 candidate L4/L5 不得 BLOCK；去掉 candidate 不得更重；仅 semantic candidate → REVIEW；全部驳回后不更强 | `C1`（candidate L5 单独 → REVIEW，:253）、`C2`（candidate 不贡献 max_sev，:254）、`C3`（partial 干净 → REVIEW）、`B7`（L4 先于 candidate）。缺：L1/L2 + 多 candidate 的组合、semantic-candidate 专门样本、驳回后重跑的方向性 | **部分覆盖** |
| **27** | 状态计算入口唯一；改映射结论随变；**按输入域穷举**全部合法组合与参考实现逐格对拍（E01-E14 一次性 golden）；无 null/未定义分支、链号∈1-15；每条链一个命中样本、多条件同时成立取最小链号；同快照重复跑恒定；静态确认只有一处判定逻辑 | `A01-A15`（15 链逐条命中）、`B1-B7`（顺序裁决）、`J1`（除白名单外无模块写 state/layer）、`G1/G2`（不 import 第二实现）、`H3a-c`（**3 行**独立期望表）、`H3d`（常量实现必红）、`H3e`（chain 字段）。缺：**穷举网格**、**同输入重复跑的确定性断言**、E01-E14 全量 golden（只对拍了 3 行） | **部分覆盖** |
| **28** | 1×L4/L5 + 2×L1/L2 → BLOCK，且群消息直接显示高危那条（不被数量阈值吞）；数量 1→10→100 严重度不降；只改数量标签不变、呈现条目变化；仅 candidate L5 → 非 BLOCK | `C1`（仅 candidate L5 → REVIEW，:253）。缺：**数量不降级**（1→10→100）、**呈现与数量分离**（群消息是 `report_render`，本脚本不碰）、高危单条直显 | **部分覆盖** |
| **29** | 组合规则共现升级：场景名词 + 消除性动词 → 命中且严重度上调；单要素不上调；组合规则未开启不上调 | **无**。本脚本只有 `decision_table.decide()`，不加载组合规则/规则引擎 | **未覆盖** |
| **30** | 判定函数输入 schema + 域外值被拒；coverage 派生六边界；空族记「未做·无控制点」；干净内容 → partial/REVIEW；补空族后可转 full；confirmed/candidate/rejected 组合 | `H1`（坏输入 → ERROR/null）、`H2`（声明 max_sev 与 findings 不符 → ERROR）、`C3`（partial 干净 → REVIEW）、`K7/K8`（coverage missing / parse failed 优先）。缺：**coverage 六边界表**（在 `verify_coverage_composer`）、**空族语义**（在 `verify_pass_reachability`）——本脚本一条都没有 | **部分覆盖** |
| **31** | I1–I7 各一违反样本 → ERROR、`external_label=null`、回执含 I 编号、报告/群里无五标签、外层默认话术；反向对照四种正常组合仍需出结论；无「ERROR 映射成未审查+parse_error」旧路径 | `D1-D7`（每码：ERROR + `invariant_violation==code` + state/label 均 null + obligations 记录，:272-278）、`C4`（I4）。缺：**报告/群消息层面无标签**（`F3` 只断言 ERROR 的 release_status 不是标签值）、默认话术、旧路径扫描 | **行为覆盖**（核心）；报告层是缺口 |
| **32** | 7 组「高优先级 vs 低优先级」成对样本：rule_conflict→BLOCK、authority conflict→BLOCK、partial→BLOCK、partial→PASS、parse failed→rule_conflict、L5+partial+candidate、L2+ok vs parse partial | `B1-B7` 逐条对应（:232-247）：B1 coverage missing 先于 L4；B2 parse failed 先于 rule_conflict；B3 rule_conflict 先于 L4；B4 authority conflict 先于 L4；B5 L4 先于 partial；B6 partial 先于 PASS；B7 L4 先于 candidate/partial/待自决；另有 `A11/A12/A13/A14` 作反向对照 | **行为覆盖** |
| **33** | PO-1/2/3/5/6：BLOCK+candidate→pending_candidate（处理方 DP2+DP3）；BLOCK+partial→partial_coverage（投放侧）；依据缺失→evidence_gap 且**逐条列 id 与状态**；四类触发在**报告与回执**里同组义务；无义务时字段是空数组 | `E1`（pending_candidate）、`E2`（evidence_gap）、`E3`（空数组不省略）、`E4`（不重复）、`B5b`（partial_coverage）。缺：**处理方（DP2+DP3 / 投放侧）**、**逐条 id 与状态**、**报告与回执同组**（报告层不在本脚本） | **部分覆盖** |
| **38** | 零命中三类样本（模态未跑 / 跑完干净 / 覆盖声明不全）；UNASSESSED 与 CLEAN-CANDIDATE 可区分且无第三种出口；缺模态零命中 → 未审查 + 空白清单列未跑项与原因；干净 → DP1、待放行、无自动发布路径 | `A01`（missing→未审查）、`A11`（partial→REVIEW）、`A15`（全清→PASS/DP1）、`K7/K8`。缺：**UNASSESSED vs CLEAN-CANDIDATE 的区分**（无此对象）、**空白清单**（报告层）、**无自动发布路径** | **部分覆盖** |
| **39** | 输出集合 ⊆ 五标签且单一值；非法输入走 ERROR；构造 UNASSESSED/ALLOW 负样本被 schema 拒；**五档各一个见证**（链 7/4-13/1-3/14/15）；第六个标签即红 | `F2`（五标签都可达，:311）、`A01-A15`（每链命中，含 7/1/2/3/14/15）、`F1/F1b`（release_status=待放行、external_label==state）、`H1`（非法输入→ERROR）。缺：`state=UNASSESSED/ALLOW` 的 schema 负样本——判定表不接收 `state` 入参，该负样本在 finding schema 层，不在本脚本 | **行为覆盖**（schema 负样本属另一层） |
| **40** | PASS 五条件逐条：① 覆盖四项缺失/未跑非空/齐全；② confirmed L1/L2 与 L4/L5 各自不 PASS 且落对档；③ 仅 candidate→REVIEW；**仅 rejected/superseded→可 PASS**；④ coverage missing/parse failed→未审查、UNASSESSED>0 禁 PASS；⑤ authority missing/expired/conflict 不 PASS；五种缺条件逐一比对实际标签 | `A15`（全清 PASS）、`A11`（partial）、`A01`（missing）、`A13`（candidate→REVIEW）、`A07`（L4→BLOCK）、`A14`（L2→待自决）、`A06/A08/A10`（依据缺失/过期）、`K1`（未知桶→REVIEW）、`C1`。缺：**仅 rejected/superseded 的样本**（全脚本没有 `superseded`/`rejected` 字样）、`UNASSESSED 计数>0` 的显式断言（K1 是相邻但不等价） | **部分覆盖** |
| **42** | 扫报告模板/群消息模板/指标定义/验收表本身：出现「P0 高危」「P0 严重」等把 P 当严重度即红；喂坏样本证明会红；「P0 层/正则层」不误报 | **无**。本脚本没有任何 P 代号措辞扫描；`detected_by` 只作为 finding 字段出现 | **未覆盖** |
| **45** | E01-E14 逐格 golden 对拍（一次性、不进 CI）；人工静态确认只有一处「输入→标签」逻辑；结论与代码位置留档 | `H3a-c`（只对拍 3 行：链 7/15/1）、`J1`（唯一写 state 的模块）、`G1/G2`。缺：**E01-E14 全量逐格**、代码位置留档 | **部分覆盖** |
| **46** | 扫全文列出 §3.3.8.1 之外所有出现五标签的表格行/段落，逐条确认是否带链号；实现只有一处判定入口；登记「指错/未指」条目 | `J1`（实现侧：除白名单外无模块写 state/layer/external_label，含反向对照 J5-J7）。缺：**文档侧扫描**（哪些段落提到五标签却没引 §3.3.8.1） | **部分覆盖** |
| **47** | I1–I7 违反样本：`run_state=ERROR`、`state=null`、`external_label=null`、回执 `invariant_violation=<I 编号>`、报告中不出现五标签；反向对照：合法输入 → OK + 有标签 + `invariant_violation=null` | `D1-D7`（四件事全断言，:272-278）、`F3`（ERROR 的 release_status 不是标签值）。缺：**报告文本层不出现五标签**（render 层）、**合法输入下 `invariant_violation` 必须为 null** 的显式断言 | **行为覆盖**（核心）；两处缺口 |

---

## 二、结论

**16 行里，真正行为覆盖的 4 行**：`31, 32, 39, 47`
**部分覆盖 10 行**：`18, 25, 27, 28, 30, 33, 38, 40, 45, 46`
**未覆盖 2 行**：`29, 42`

### 按 05 的约束 (b)：哪些行的 passed 是假的

- **#29（组合规则共现升级）**、**#42（P 代号不得表达严重度）**：脚本里**没有任何对应物**，
  它们现在的 `passed` 是**映射带来的**，应回退到 `untested`。
- 另外 10 行是「部分覆盖」：**不建议直接回退**，但它们的 `passed` 只说明「部分行为被验过」，
  不等于整行通过。尤其：
  - **#28** 的核心「数量不降级（1→10→100）」完全没有执行点；
  - **#40** 的「仅 rejected/superseded 可 PASS」没有样本；
  - **#27/#45** 的「穷举网格 / E01-E14 全量 golden」只对拍了 3 行。

### 一个更大的读数

这 16 行由**同一条命令**支撑。本次审计发现 2 行完全未覆盖 + 10 行部分覆盖——
也就是说：**这条命令绿一次，会让 2 行假绿、10 行「只验了一部分」被读成整行通过。**
单点风险的具体形状在这里，不在「脚本写错了」。

---

## 三、复现方式（第二个人怎么复核）

```bash
# 1) 取行原文
python3 - <<'PY'
import re
rows={18,25,27,28,29,30,31,32,33,38,39,40,42,45,46,47}
for l in open('PMO/audit/验收表-v3-覆盖全部判据-20261017.md',encoding='utf-8'):
    m=re.match(r'^\|\s*\**(\d+)\**\s*\|', l)
    if m and int(m.group(1)) in rows: print(l[:300])
PY
# 2) 看脚本有哪些断言
grep -n 'T("\|chk("' tools/verify_decision_table.py
# 3) 抽查缺口（应为空）
grep -n "superseded\|rejected" tools/verify_decision_table.py
grep -n "P0 高危\|P0 严重" tools/verify_decision_table.py
```
