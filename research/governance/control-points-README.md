# 控制点主表与路由表 · 使用说明（**U2 未闭**）

> ⚠️ **先读这一句：本表的「结构」已闭合，「点位内容」未闭。**
>
> | 部分 | 状态 |
> |---|---|
> | 九字段结构、首批 20 个真码 + 4 个品牌草案码（B01–B04，`status=draft`）、唯一归属规则、两表集合恒等 | ✅ **已闭合**（T0-01） |
> | **场景 / 权利 / 渠道三族的点位内容** | ⛔ **未定（U2）** —— 待**产品 + 法务签署**；品牌族已有 B01–B04 草案（draft，规则 `enabled=false`） |
>
> **在签署之前，任何文档不得声称「U2 已关闭」，也不得把这 20 个码当成完整的控制点体系。**
> 空族以 `empty_families` 为准（**今天是 3：场景 / 权利 / 渠道**），不要写死数字；品牌族的 4 个草案点尚未启用。

## 文件

| 文件 | 字段数 | 内容 |
|---|---:|---|
| `control-points-v1.json` | 9 | 20 个控制点，字段见 Playbook §5.3.1；**它同时是码分配登记表** |
| `routing-v1.json` | 6 | 每个 `control_code` 的 `owner` / `layer` / `due` / `escalation` / `appeal` |
| `control-points-history.json` | — | 每次族/码变更的 who / why / evidence / version + 快照 |

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

**验收对应**：`L6-1…L6-6`（验收表第 79 项）、`L3-1`（路由表无空洞）；C-70/74/76 由
`tools/verify_control_points.py` 的 `H-*` / `C74-*` / `C76-*` 断言。

## 变更纪律（C-70 / C-74 / C-76）

1. **主表即码分配登记表。** 一个 `control_code` 只能属于一个 `family`；跨族拆分必须显式写
   `families`（或 `family_split`）并提供 `family_split_approval`（who / why / evidence），
   否则 `C76-2` / `C76-3` 红。
2. **任何族/码变更都必须：**
   - 升 `table_version`；
   - 在 `control-points-history.json` 追加一条 entry（`version` / `at` / `who` / `why` /
     `evidence` / `codes` / `family_by_code`）；
   - 否则 `H-3/H-4/H-5` 红（最后一条历史必须与主表版本、码集合、族归属逐项一致）。
3. **新增控制点三条件**：必须有规则引用（`rules-v1.json` 的 `parent_rule`）、依据引用
   （`authority_ref` 非空）、版本号（`version` 非空）；且 `table_version` 的 `-vN` 必须递增。
   缺一分别报 `E_CP_RULE_MISSING` / `E_CP_AUTHORITY_MISSING` / `E_CP_VERSION_MISSING` /
   `E_TABLE_VERSION_NOT_INCREMENTED`。
4. 历史文件里 `who` 不允许空；初始基线若原始操作人未留痕，必须明说「待补录」，不能伪装成已签。

## 为什么 `empty_families` 写「无控制点」而不是 `not_applicable`

`not_applicable` 的意思是「这一族对我不适用」。但场景/权利/渠道**是适用的**，
只是**点位内容还没定**。写成 `not_applicable` 会让一个「待办」看起来像「已决定不做」——
那正是本项目台账 K-05（未做被报成已清）的同一个形状。
