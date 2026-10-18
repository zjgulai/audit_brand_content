# 控制点主表与路由表 · 使用说明（**U2 未闭**）

> ⚠️ **先读这一句：本表的「结构」已闭合，「点位内容」未闭。**
>
> | 部分 | 状态 |
> |---|---|
> | 九字段结构、20 个真码、唯一归属规则、两表集合恒等 | ✅ **已闭合**（T0-01） |
> | **场景 / 权利 / 渠道三族的点位内容** | ⛔ **未定（U2）** —— 待**产品 + 法务签署** |
>
> **在签署之前，任何文档不得声称「U2 已关闭」，也不得把这 20 个码当成完整的控制点体系。**
> 当前覆盖是 4/7 族，权利控制与渠道控制两族**一个控制点都没有**。

## 文件

| 文件 | 字段数 | 内容 |
|---|---:|---|
| `control-points-v1.json` | 9 | 20 个控制点，字段见 Playbook §5.3.1 |
| `routing-v1.json` | 4 | 每个 `control_code` 的 `owner` / `due` / `escalation` / `appeal` |

**两表分开、各自独立版本**（`table_version` / `routing_version`）——
这是 A-3 的裁定：控制点是**判定信息**（判什么），路由是**组织信息**（谁负责），
两者审批人与变更频率不同，塞在一张表里会互相拖累。

## 数据从哪来

`research/governance/skeleton/rules-v1.json`：26 条规则、21 个不同 `parent_rule`
（20 个真码 + `安全词`）。按 Playbook §5.3.2，`安全词` **不是码**、不入表。

**没有重新编号**：`control_code` 沿用规则库里已有的 `parent_rule`，因为旧码一经分配永不复用。

## 两个已知缺口（**不要当成已解决**）

### 1. `family` 的取值是判断，不是数据

盘上**没有**任何一份原始材料直接给出这 20 个码属于哪个控制族。
现在的归属是**按 `topic_label` 的语义推的**，依据写进了 JSON 的 `family_assignment_note`。

若产品/法务认为某条归错族：**改 `family` 字段并升 `table_version`，不要改 `control_code`。**

### 2. `U02` 缺依据

`L6-4` 要求每个控制点都指得出 `authority_ref`。规则库里 **19/20 有 `external_ref`，U02 没有**。

当前处置：标 `status = deprecated` 并记进 `known_gaps`。
**这不等于解决** —— 要么补依据，要么正式退役该码，需要产品 + 法务定。

## 怎么用

```bash
python3 -c "
import json
cp=json.load(open('research/governance/control-points-v1.json'))
rt=json.load(open('research/governance/routing-v1.json'))
a={c['control_code'] for c in cp['control_points']}
b={r['control_code'] for r in rt['routes']}
print('主表', len(a), '路由', len(b), '集合恒等:', a==b)
print('空族:', [f['family'] for f in cp['empty_families']])
"
```

**验收对应**：`L6-1…L6-6`（验收表第 79 项）、`L3-1`（路由表无空洞）。

## 为什么 `empty_families` 写「无控制点」而不是 `not_applicable`

`not_applicable` 的意思是「这一族对我不适用」。但场景/权利/渠道**是适用的**，
只是**点位内容还没定**。写成 `not_applicable` 会让一个「待办」看起来像「已决定不做」——
那正是本项目台账 K-05（未做被报成已清）的同一个形状。
