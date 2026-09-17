# `base/` —— 基座

> 状态：**B0 全部完成 · B1 图片档完成**（B0.1 立版本 · B0.2 `ContentUnit` ·
> B0.3 `judge(unit)` · B0.4 权威源同步 · B0.5 基座自证 · B1 图片 OCR 与三个指标）。
> B0.1 见 `ADR/ADR-0013-基座接口冻结与仓库入库分级.md`。
>
> **一条命令自证整个基座**（全离线，退出码 0/2）：
>
> ```bash
> python3 base/verify_base.py
> ```
>
> 它自己会调三个模块的自证（41 + 26 + 20 项，含 17 条反向对照），再跑四条仓库治理检查。

## 为什么单开一个 `base/`

仓库原有两个顶层目录，各自有明确的语义：

| 目录 | 装什么 | 判据 |
|---|---|---|
| `research/` | 调研过程与结论。证据、报告、方法论文档 | 「这是一次调研的产物」 |
| `tools/` | 调研期的脚本。抓取、核对、体检、推送 | 「这是为了让某次调研跑起来而写的」 |
| **`base/`** | **产品化的契约层。会被 PRD 之后的装配层依赖** | **「这东西不能随便改，改了要有人知道」** |

ADR-0013 §一 D1 定的「五个面」里，①②③ 三面会返工。基座就是那三面的落点：

```
① 进   ContentUnit + 解析器          ← base/contract.py          （B0.2 ✅）
   ①b  图片 OCR → unit               ← base/media.py + ocr_vision.m（B1 ✅ 图片档）
② 判   judge(unit) → Verdict         ← base/judge_adapter.py      （B0.3 ✅）
③ 供   规则词表单向同步 + 版本        ← base/sync_rules.py         （B0.4 ✅）
⑤ 证   基座自证                       ← base/verify_base.py        （B0.5 ✅）
④ 出   处置五层 + 回执                ← 已建成，在 skeleton/（ADR-0012）
```

**`research/` 与 `tools/` 本轮不动。** 引擎代码（`research/governance/skeleton/`）也不动 ——
ADR-0013 D1 说的是「在引擎**前面**立一个统一信封」，不是「改引擎」。

---

## `ContentUnit` 是什么

一句话：**把任意形态的内容，变成同一种可判、可溯、可复现的东西。**

```python
from contract import from_text, validate
u = from_text("FDA approved wearable breast pump", product_line="吸奶器")
validate(u)          # → [] 表示通过
u["text"]            # → 判定输入
u["fingerprint"]     # → 两个指纹
```

### 字段

| 字段 | 答什么问题 | 备注 |
|---|---|---|
| `unit_id` | **这一次观测**是哪一次 | `cu` + 16 hex。**两份指纹都进** —— 原件变了就是新的一次观测 |
| `content_key` | **这两次看到的是不是同一个东西** | `ck` + 16 hex。**只吃正文指纹** —— 页面重渲染后它不变 |
| `fingerprint.raw_sha256` | 看的是**哪份原件** | 广告 = 整行记录的规范化 JSON；落载体 = 原始响应体 |
| `fingerprint.text_sha256` | **重跑能不能得到一样的数** | 恒等于 `sha256(text)`（H4 断言） |
| `text` | 判定输入本身 | 是归一化的**不动点**（H3 断言）。**不是审计记录** |
| `source.uri` | **实际被取的那个 target** | 不是逻辑页面键。见下面「一个 url_key ≠ 一个 unit」 |
| `source.raw_pointer` | 原件在哪 | 可空。指不到时 `raw_verified=false`，**不假装验证过** |
| `normalization` | 正文经过哪一档归一化 | 具名档位 + 步骤。改档位 = 改所有指纹 |
| `composition` | 正文由哪些字段按什么口径拼成 | 含 `parts` 边界，**逐字可核** |
| `textification` | 非文本形态怎么变成文字、覆盖到哪 | 图片/视频必填 `covers` 与 `does_not_cover` |
| `text` / `has_text` | 有没有可判文本 | `has_text` 是**路由输入**（D5），不是判定输入 |
| `routing` | 按什么查得到收件人 | 键必须是 `judge()` 真的接受的形参名（H14） |
| `context` | 盘子有多大 | 花费/展示/点击/广告组。**不进判定，也不做路由键** |
| `reference_verdict` | 人工当时判了什么 | **只作对照**。进 `judge()` 就是拿答案评自己的卷子 |

### 不变量（`validate()` 执行，H1–H14）

```
H1  contract_version 已知
H2  text 是 str
H3  text 是归一化的不动点：normalize(text) == text
H4  text_sha256 == sha256(text)，text_chars == len(text)
H5  has_text == bool(text.strip())
H6  两个指纹都是 64 位小写十六进制
H7  unit_id / content_key 可复算
H8  source.kind 在取值域内，source.uri 非空
H9  normalization.profile/steps 与登记表一致
H10 composition 已登记；parts 有序、不重叠、在界内
H11 逐字可核：text[start:end] 的 sha256 == parts[i].value_sha256
H12 parts 之间恰好是 separator，首尾无多余字符
H13 reference_verdict 是 dict 或 None
H14 routing 的键 ⊆ judge() 的形参名（在 to_judge_kwargs() 里查）
```

**H11 是这套里最有用的一条。** 它让「拼装没吃掉、也没掺入任何字符」在**不持有原件**时也能验 ——
每个 part 带着自己那段的 `value_sha256`，所以一个 unit 离开它的来源之后仍然自证（ADR-0008 §四）。

---

## 三件在写它的过程中被实测逼出来的事

### 一、「广告文本怎么拼」全仓有四个口径，而它们**不一致**

| 位置 | 口径 | 空字段 |
|---|---|---|
| `skeleton/score.py:484` `rec_text()` | `" | ".join` | 过滤 |
| `tools/offline_replay.py:63` `text_of()` | `"\n".join` | 过滤 |
| `tools/verify_engine_contract.py:1427` | `PT + "\n" + HL` | **不过滤**，`.strip()` |
| `tools/lp_consistency.py:106` | `" | ".join` | 过滤 |

在 291 条真实语料上量两种口径（`" | "` vs `"\n"`）：

```
文本不同          232 / 291      ← 只有 59 条 PLA 空文案两边一致
判定不同            0 / 291
命中规则集不同      0 / 291
命中条数不同        0 / 291
命中位置不同       12 / 291      ← 差恰好 2 个字符（" | " 比 "\n" 长 2）
```

**今天它不改变任何一条判定，它改变位置。** 而位置是契约字段（ADR-0012 决策 5），
且 §3.1 写过「宁可少报位置，不可错报位置 —— 一个错位置比没有位置更坏，**它看起来是对的**」。

更硬的一条：**规则文件里有 10 条 pattern 把 `|` 写进了排除类**（`[^.!?|]*`）：

```
T2.1.1.milk-supply       295\s?mmhg[^.!?|]*(more milk|better|faster)
T2.1.2.pain-relief       (say )?goodbye to [^.!?|]*pain\w*
T3.2.expert-endorsement  \brecommended by [^.!?|]*(doctor|expert|pediatrician|ob-?gyn)
T2.2.mimic-claim         (auto|automatic|smart)[^.!?|]*(detect|find|identif|recogniz)\w*[^.!?|]*(rhythm|pattern|let-?down|pace)
…… 共 10 条
```

无论作者本意如何，它的**实际作用**是在 `|` 处截断跨字段匹配。换成 `"\n"` 拼串后这 10 道屏障**全部失效** ——
逐条 pattern 构造验证，有 **11 组**跨字段伪命中会因此成立：

```
PT="Hospital"  HL="Grade Suction"   →  T3.3.institution-grade 命中 "Hospital\nGrade"
PT="FDA"       HL="approved …"      →  T6.1.regulatory-status 命中 "FDA\napproved"
PT="zero"      HL="risk pumping"    →  T5.1.safety-claim      命中 "zero\nrisk"
PT="doctor"    HL="recommended …"   →  T3.2.expert-endorsement 命中 "doctor\nrecommended"
PT="3x"        HL="faster than …"   →  T2.3.sourced-data       命中 "3x\nfaster"
…… 共 11 组
```

**本语料上这 11 组一次都没发生**（291 条实测 0 处）。所以这是**潜伏**缺陷，不是现行缺陷 —— 这个区别必须说清。

**处置**：`" | "` 定为唯一规范口径（`fields-pipe-v1`），并把 `parts` 的**字段边界**记进 unit。
另一条口径（`fields-newline-v1`）在 `COMPOSITION_REGISTRY` 里**登记但未采用**，状态
`documented-not-canonical` —— 登记的用途是让「换口径位置会差 2 字符」这件事**可被复算**，而不是消失。

> **★ Owner 已裁定：A（2026-09-17）。** 这是本层唯一一处「选另一条也能自圆其说」的地方，裁定记录见 `ADR/ADR-0013` §8.4：
> 第三个选项是 **不做拼串** —— 把 `Primary Text` 与 `Headline` 作为两个 part 分别判定再做聚合。
> 它最干净（跨字段伪命中在结构上不可能），但会改动判定语义与聚合规则，代价远大于前两条。
> 在 PRD 到来、复核界面需要按位置高亮原文之前，前两条的差别不会显现。
> **推论**：装配层若要按 `position` 高亮原文，本须先定案 —— **现已定案**，
> 所以 `fields-pipe-v1` 是唯一规范口径，`fields-newline-v1` 只在登记表里以
> `documented-not-canonical` 留档，用途是让「换口径位置差 2 字符」可被复算。
> `--selftest` 有一条反向对照守着它（改 `separator` 必红）。

### 二、双指纹不是设计偏好，是**实测出来的必需品**

联网复取 4 个页面、每个取两次（间隔 20 秒；只读、遵守 robots、复用批次 C 的节流）：

```
页面                                                     raw_sha256   text_sha256
au.momcozy.com/pages/brand-new-wellness-1-warm-massage…    变           同
ca.momcozy.com/blogs/breastfeeding/how-much-milk-to-pump   变           同
de.momcozy.com/collections/electric-breast-pump            变           同
es.momcozy.com/collections/electric-breast-pump            变           同

→ raw 变 4/4，正文变 0/4
```

其中 de 站那个页面连**字节数**都变了（1074085 → 1072914），正文仍**逐字节相同**。

**这就是两个指纹不能合并的实测依据**：原件在变，正文没变。
合并成一个数之后，这件事再也观测不到 —— 要么把「页面没改」误报成「改了」（只留 raw），
要么答不了「当时到底看的是哪一份」（只留 text）。

原始证据：`research/landing/_evidence/refetch-20260917T080011Z/复取实测.json`（L2）。

### 三、一个「不崩、不报错」的静默缺陷，在第一版里真的发生了

`from_landing_page()` 第一版对商品 JSON 写的是 `extract_rec["structured"].get("text")` ——
而 `lp_extract.analyze_structured()` **根本不产出 `text` 这个键**（它给的是 `title` / `description_text`）。

后果：**44 个商品 JSON 全部拿到空正文、全部 `has_text=False`**，
也就是全部被路由去 DP0「没有可判文本」—— 而它们 44/44 有标题、17/44 有描述。

这正是本项目最怕的失效形态：**不崩、不报错，只是安静地把「取了 44 个 JSON」
记成「44 条没什么可看的」。** 覆盖 44 个 URL 的工作量看起来完成了，实际一条都没进判定。

**处置**：修正为按 `fields-pipe-v1` 拼 `title` + `description_text`（与广告文案同一口径，
同样受 `[^.!?|]` 那道屏障保护），并**加了一条专门守这个形态的断言**：

```
[9] 有提取内容却产出空正文的落载体：0 / 136
```

该断言已做**反向对照**：把 bug 放回去，它报 **44 / 44** —— 这条断言挡得住。

---

## `judge(unit)` —— 适配层（B0.3）

一句话：**`ContentUnit` → 一份判定，且这份判定知道自己在什么边界内成立。**

```python
from judge_adapter import judge_unit
r = judge_unit(unit)                    # 引擎一行没改
r["verdict"]["disposition"]
r["boundary_statement"]["unknowns"]     # 已按载体订正
```

### 为什么这不是「一层薄封装」

因为 `judge()` 的边界声明里有一句话，在 `ContentUnit` 出现之后**变成了假话**。

`skeleton/judge.py:220` 写死着一句（同一句话还以机器可读形式出现在
`boundary_statement.not_covered_carriers` 里）：

> **未覆盖的载体**：本判定只看文本。图片、视频、**落地页正文**、A+ 详情页均不在输入内。
> 批次 C 已产出落地页正文的获取能力，但**尚未接入本引擎**。

在一个 `landing_page` unit 进判定时，**它逐字是假的** —— 那份判定的输入就是落地页正文。
而 `judge.py` 自己（`_layer_note()` 的注释）已经立过这条原则：

> ★ 一句写死的免责声明迟早会变成假话。

**「边界声明说错了边界」比没有边界声明更坏**：一份声称「落地页不在输入内」的判定，
会让读的人以为这次审查根本没看落地页 —— 于是要么重复劳动，要么据此做出错误的覆盖结论。

订正的方向只有一条能走：**在适配层订正**（改 `judge.py` 是改引擎，且 161 项验收盯着它）。
订正动作本身进 `boundary_statement.$corrections`，**留痕，不静默改写**。

实测对照（`python3 base/judge_adapter.py --boundary-report`）：

| | 内容 |
|---|---|
| 订正前的 `unknowns[4]` | 「…落地页正文…**尚未接入本引擎**」← 对落地页 unit 是假的 |
| 订正后 | 「**载体：落地页正文——已接入，但只覆盖到文字那一层。**…**不含画面语义**，也抓不到 JS 运行时渲染出来的内容」 |
| `not_covered_carriers` | `['图片','视频','落地页正文','A+ 详情页']` → `['图片','视频','A+ 详情页']` |

**订正按载体分，不按「有没有文本」分。** 对一条广告文案，引擎那句仍然为真，**不动它** ——
只为落地页 / 商品 JSON 改写。这一条被写成断言守着。

### 回执：`judge()` 的回执答不了「哪份原件」

引擎回执只存 `input_sha256`（= 正文指纹）。这对广告够用（正文就是原件），对落地页不够 ——
同一段正文可以来自无数份 HTML（实测 raw 变 4/4 而正文变 0/4）。

适配层的回执在引擎那份之上加一个 `unit` 块：
`raw_sha256` / `text_sha256` / `kind` / `uri` / 归一化档位 / 组装口径 / 文本化边界。
**仍然不含原文与片段** —— ADR-0008 决策 2 与 ADR-0012 §3.3 那条约束没有被绕过。

**一个实现取舍值得记下**：回执的 `obligations` 块（D6/D10 出口声明）由 `judge()` 内部从分层表
生成，本层**不重写** —— 重写等于把一份**法务所有**的契约字段抄成第二份实现，两份迟早不一致。
做法是让 `judge()` 照常生成完整回执（只是写到临时路径），本层补上 `unit` 块后
再经**生产闸门**（`append_receipt`，含 origin 检查与前缀哈希链）落到真账本。

### 这一层的四条不变量

```
J1  unit 合法（contract.validate() 全过）—— 不拿坏信封去判定
J2  正文原样到达引擎：result["input"]["text_sha256"] == unit.fingerprint.text_sha256
    ★ 引擎自己也算了一遍 sha256；两个独立实现算出同一个数，证明正文没被中间层改写
J3  边界声明里不再声称本次的载体未被覆盖（且**只**对真的不成立的载体订正）
J4  边界声明新增本次输入的 covers / does_not_cover（ADR-0013 异议二）
J5  回执带 unit 块，且仍不含原文与片段
```

### 本层自己制造过一句假话（记下来）

第一版对「正文为空」只判了 `not has_text`，于是它对**那 59 条 PLA 广告**也说：

> ★★ **本条落 DP0 的原因与 PLA 那 59 条不同。**

—— 而它自己就是其中一条。**本层为了订正一句假话而写出的新句子，第一版就是假的。**
被本文件自己的断言抓到（[J3] 里「59 条 PLA 空文案不被告知『你与 PLA 那 59 条不同』」）。

修正后的判据按**载体**分：`landing_page` / `structured_json` / `image` / `video` 的空正文是
**取不到**；`free_text` 的空正文是**调用方给的就是空的**；`ad_text` 的空正文是**结构上没有**（PLA）。
三者都走 DP0，但性质与处置都不同 —— 而 DP0 那条通知如果只说「没有文本」，收件人无法行动。

---

## 「一个 url_key ≠ 一个 unit」

`抓取结果.json` 里：

```
92 个 url_key  →  133 个不同 target
                  其中 48 次抓取打的是 <页面>.js（Shopify 商品 JSON）
```

`ContentUnit` 因此以 **target** 为 `source.uri`，而不是 `url_key`。
把一个页面的 HTML 与它的 JSON 塞进同一个 unit，会让 `raw_sha256` 指着 A 而正文来自 B ——
**两个字段都写对了，合起来是错的。**

副产品：`92 + 44 = 136` 个观测折叠为 **133 个 `unit_id`**。少 3 个不是 bug ——
有 3 个 url_key（`collections/…/products/…` 形式）重定向到了同一个 target，
它们本来就该是同一个观测。这正是「一次观测 = 一个 id」的意义。

---

## 权威源与只读投影（B0.4）

ADR-0013 D2 的标题是「**飞书 Base 是规则与词表的唯一权威源，本地 JSON 是只读投影**」。
实测：**这句话对一半为真、对另一半为假。**

| 源 | 权威在谁 | 方向 | 「本地不得回写」靠什么 |
|---|---|---|---|
| 品线内容边界规则库（21 · 人写） | **飞书** | 飞书 → 本地 | **物理**：app 对主 Base 的写操作全部 `403 · code 91403` |
| 语境守卫词（85）· 白名单词（30） | **本地 JSON** | 本地 → 飞书 | **纪律**：两表在 app **自己拥有**的 Base 里，写权限完整 |

**两种保证不是同一个强度**：一条 `--apply` 就能改掉词表 Base —— 那边没有权限在拦，只有约定在拦。
所以 `base/sync_rules.py` 把 `authority` / `direction` / `enforcement` 定为**每源必填**，
并有一条断言守着「authority 与 direction 必须一致」—— 它守的正是 D2 标题句犯的错。

**旁证（可交叉验证）**：`tools/migrate_whitelist_to_lark.py` 本想把白名单表建在**主 Base** 里，
而实测主 Base 今天只有 4 张表、**没有白名单表**。三小时后写的迁移脚本记下了 403，改用 app 自有 Base。
**ADR-0009 的机制分离不是设计出来的，是被权限逼出来的。**

### 命令

```bash
python3 base/sync_rules.py --probe      # 只读：两库现状 + 本地漂移（联网，不发写请求）
python3 base/sync_rules.py --pull       # 拉快照到 L2（联网，唯一会写盘的联网命令）
python3 base/sync_rules.py --verify     # 离线：本地制品 vs 最近快照
python3 base/sync_rules.py --selftest   # 离线自证
```

### 冲突语义：同一个「不一致」，两个方向上含义相反

| | 本地多出来 | 权威/飞书多出来 |
|---|---|---|
| `pull`（飞书权威） | **✗ 本地成了第二个源**（D2 明令禁止） | ⚠ 待同步 |
| `push`（本地权威） | ⚠ 待发布 | **✗ 有人手改了发布面** —— 下一次推送会**静默覆盖**它 |

删除（任一方向）一律报出，绝不静默丢弃。
`push` 那一格是本模块存在的核心理由：**手改飞书的那个人不会知道自己的改动会被覆盖。**

### 规则链上夹着一份 L1 人工文档，而它才是被读的那个

```
PRD/内容治理需求文档.md ──build_rules.py──> rules_raw.json ──手工──> rules-v1.json
        ↑ 12 列（超集）                                        ↑ 引擎真正读的
_evidence/rulelib-live.json（真正的飞书拉取，9 列）
        └──> build_context_guards.py（只用于推导机注字段）
```

**`build_rules.py` 从不读飞书，它读 PRD。** 实测两者今天的关系（21 条 × 共有 8 列）：**0 处差异**，
但 PRD 是飞书的**超集**（多 4 列）。⇒ **有人在飞书改了规则而 PRD 不变 ⇒ 引擎用的是 PRD ⇒ 改动静默不生效。**
今天没有任何东西在守这件事 —— `--verify` 就是那个东西。

### 跑 `--probe` 撞出的两个自己的错（记下来）

1. **报告写「✓ 条目集合一致」，而它是假的。** 广告文案明细：飞书 291 条 vs 本地 289 条 ——
   两侧各有 2 条记录 `外部广告ID` 为空，被**一起**从分母里剔掉了。
   本仓吃过同形的教训（「把读不到的 10 条剔出分母后，『收集了 15 条』看起来像成功」）。
   已改为报告必须写出**分母是多少、少的那些是谁**。
2. **`--verify` 文案说「未通过」而退出码说 0。** 调用方看退出码、人看文案，
   **两边都会以为自己是对的**。已改为同一判据派生两样东西。

那 2 条无标识记录的真身：飞书 `recvuNu8mWXyYp` / `recvuNE6m1MyjQ` 有 `文案语种` 与 `父记录`，
但没有 `外部广告ID`；投影到本地后变成两条全空行 —— **既进不了判定，也追不到是哪条广告**。

---

## B1 · 图片进管道

```bash
bash base/build_ocr.sh                  # 编译 OCR（源码在 L1，二进制落 .tools/bin/）
python3 base/media.py --collect 6       # 联网：抽样下载 + OCR
python3 base/media.py --report          # 三个指标
python3 base/media.py --selftest        # 离线自证
```

### OCR 通道：本机编译链是坏的，绕法已固化

| 路 | 结果 |
|---|---|
| `swiftc` | ✗ SDK 由 Swift 6.4 构建、CLT 里是 6.3.3 |
| 默认 SDK `MacOSX27.0` | ✗ `tapi error ... unknown architecture arm64e.x1-macos` |
| **ObjC + clang + `-isysroot MacOSX15.4.sdk`** | ✅ 直连系统 `Vision.framework` |

**零第三方依赖。** `build_ocr.sh` 按「能用」顺序试 5 个 SDK，不写死一个。

### 三个数字（59 张图 / 6 个页面）

| 指标 | 值 | 口径 |
|---|---|---|
| 内容获取成功率 | **100.0%** | 59/59 位图。**SVG 单列不进分母** |
| 识别完整度 | **64.4%** | 38/59 有 OCR 文本；alt 为空的 29 张里 **15 张有文本** |
| 处理耗时（ms） | 下载 p50 **529** · OCR p50 **169** · 端到端 p50 **3573** | 含进程启动 p50 233，差值即子进程开销 |

**⚠ 抽样偏差**：样本取自已成功抓取的页面，**100% 部分是构造出来的**。这一条不写，
那个数会被当成能力。

### ★ 我的核心假设没被证实

**假设**：alt 是商品名目录（中位 17 字符），声明画在图里 —— OCR 应读到 alt 没有的声明。
**实测：`alt 非空而 OCR 读到新声明 = 0 / 30`。**

原因比假设有用 —— **声明词表是英文的，图片文字不是**：抽到的 es/de 站读出的是
`~70% indico un reflejo de bajada de la leche mas temprano*`、`Masaje sincronizado ... mas rapido y eficaz`。
且图片里的表述是**视觉化**的（对比图、`50avs Battery Life`），不是词表能枚举的词。

**换个与语言无关的问法：OCR 的实词，页面正文里有没有？**
覆盖率中位 **78%**，低覆盖（<50%）11 张 —— **而这 11 张多数是 OCR 噪声**：

```
momcooy | momor | treasl purp coetra          ← 花体 logo 被读错
R | 02:18 | 0-0.25 oz | 7 | + | LCR | Finish  ← 播放器与对比控件碎片
```

**把噪声当成「新发现」是这类测量的典型误读。** 真正的像素独占内容确实有
（`Images are for illustrative purposes only.` 这类免责声明、来源脚注），但很少，
**不足以支撑「OCR 是图片审查的主要通道」**。

⇒ **图片 OCR 的定位**：① 覆盖 alt 为空的图（15/29，这条是实的）
② 抓免责声明与来源脚注这类「小字」—— 而**不是**当作「图片已审」。

### ★★ 顺带抓到一个真缺陷：声明词表里两个词永远匹配不上

`lp_extract.CLAIM_PATTERNS["absolute"]` 末尾的 `\b` 让 **`100%` 与 `#1` 永不命中**
（`%`/`#` 是非单词字符，后跟空格时不存在单词边界）。

| | 修正前 | 修正后 |
|---|---|---|
| 21,424 条 alt 命中数 | 87 | **94** |
| 92 个页面正文里含 `100%`/`#1` 却抽不出 | **3** | 0 |
| **批次 C 一致性：至少一项声明未出现的广告数** | 33 | **35** |
| 未在落地页出现的声明计数 | 29 | **30** |

**这个缺陷一直在静默压掉跨载体不一致** —— 新增的正是
`{"广告中的表述": "#1", "落地页是否出现": false}`。一个广告说了 `#1`、落地页没有，
这正是批次 C 存在的全部理由，而它被一个 `\b` 挡住了。

**守卫**：`media.py --selftest` 新增**词形自洽检查 —— 6 类 30 个声明词，每个都必须命中自己。**
**这条守卫的缺席就是缺陷能活下来的原因。**

### 视频：49 条视频广告，0 个视频文件

| | |
|---|---|
| 视频广告 | **49** 条（其中 37 条带落地页） |
| 近 7 天费用 | **$5,110** |
| 视频文件 | **0** |

**准确说法**：这 49 条的**文案**已在覆盖内（在 427 个 unit 里）；
**素材本身 —— 画面、字幕、音轨 —— 一个字都没看过。**

**三个数字：没有。** 报 `cannot_measure`，不报 0、不留空。
拿到数字需要：① 素材文件 ② 转写通道（本机无 ffmpeg/whisper，外部服务须先过 ADR-0003）
③ 抽帧 ④ 人工标注真值。

---

## 基座自证（B0.5）

```bash
python3 base/verify_base.py            # 全绿 0 / 有红 2
python3 base/verify_base.py --no-selftests   # 只跑仓库治理四条，跳过三个模块自证
```

六个面：**A 五面自证 · B L1 自足性 · C 分级一致性 · D 产物完备性 · E 版本控制 · F 反向对照**。

### ★ 异议一那条检查：做不到全覆盖，而原因必须先说清

ADR-0013 异议一承诺 `verify_base.py` 必须查「L2 的每个关键产物都能在 L1 里找到
生成脚本 + 输入指纹」。**做不到 —— 因为 L2 不是一个性质，是五个。**

| 类 | 组数 | 那条判据 |
|---|---|---|
| `derived` 可复算 | 5 | **适用** |
| `addressed` 内容寻址 | 4 | 不适用（文件名即指纹，自证） |
| `primary` 本身是账本 | 3 | ★ **不适用，且必须写清为什么** |
| `runtime` 运行态 / `vendored` / `forbidden` | 19 | 不适用 |

**`primary` 是最该说清的一类。** §三 L2 把 `receipts.jsonl` 判为 L2，理由写的是
「**追加型账本**：只会增长，不需要 diff 与回滚」—— **不是**「可复算」。
回执记录的是「当时判了什么」，**L1 里没有第二份**，所以它不可复算、也不该被要求可复算。
`class` 是**必填**字段，正是为了让这件事不能含糊过去。

⇒ 异议一的措辞应收窄为「L2 里**以『可复算』为由**入库的每个产物」。
**D7 不必重议**：它排除 `records.json` 的理由正是「可复算」，而 `derived` 5 组已逐项查过。

### ★ `.gitignore` 自己的警告，已经应验过一次

`.gitignore` 头部写着「改动本文件 = 改动分级 = 需回到 ADR-0013 §三 同步」。
**B0.5 首跑就抓到它已经漂移**：`PMO/logs/` 与 `PMO/shouheng-state/` 两条规则
**在 §三 里一个字都没有**。已补录，并把「有出处」做成硬性要求（`adr_ref` 为空即红）。

这类漂移不会自己暴露：`.gitignore` 生效、git 状态正常、没有任何命令报错，
只是台账与制品各说各话。

### B0.5 里我自己犯的两个错（记下来）

1. **D 面误报 `要素提取.json`「未被覆盖」。** 真因是 `git ls-files` 对非 ASCII 路径
   做八进制转义，我 strip 引号后没解码。**这类错很危险：它看起来像发现了问题，
   其实只是两边用了不同的编码。** 修法：`git -c core.quotePath=false`。
2. **F 面的输出淹没 F 面的结果。** 反向对照调 B/C 两面，它们自己会打印。已静音子调用。

---

## 自证

```bash
python3 base/contract.py --selftest     # 30 项检查 + 11 条反向对照，必须全绿
python3 base/contract.py --stats        # 语料规模与指纹分布
python3 base/contract.py --from-text "文案…" --json
python3 base/contract.py --from-record GG-d1ff3cf1bb1d --json
python3 base/contract.py --from-url-key momcozy.com/products/… --json
```

```bash
python3 base/judge_adapter.py --selftest          # 427 个 unit 全部进判定
python3 base/judge_adapter.py --boundary-report   # 边界声明订正前后对照
```

当前结果：

```
✓ B0.2 自证全绿：291 条广告 + 136 个落载体 → 427 个合法 unit
✓ B0.3 自证全绿：427 个 unit 进判定，边界声明按载体订正，回执挂双指纹
```

九个面：语料面 / 归一化面 / 拼装面 / 指纹面 / 复取实测 / 留痕面 / 桥接面 /
反向对照 / schema 面 / 静默空正文面。

**十条反向对照**（改坏 unit 必须红）是这套自证的价值所在 ——
一条永远不会红的检查等于没有检查。它们各自盯一个不变量：

```
改一个字符            → H4        正文尾部塞空白        → H3
unit_id 手改          → H7        正文尾部塞可见字符    → H4 + H12
has_text 撒谎         → H5        separator 改掉        → H10
raw_sha256 写短       → H6        未知路由键            → H14
kind 越域             → H8        旧 bug 复现           → [9] 44/44 红
parts 起点挪 1        → H11
归一化档位不存在      → H9
```

---

## 这一层**不做**什么（说清，否则会被当成已解决）

1. **不判定。** 本层不产出任何合规结论。`to_judge_kwargs()` 只把 unit 翻译成 `judge()` 的实参，
   判定是 ADR-0005 的边界，属 `judge()`（B0.3）。
2. **不落库。** `unit["text"]` 是判定输入，不是审计记录。
   留痕用 `fingerprint_view()` —— 它把正文换成指纹，与 ADR-0012 §3.3 同一条规矩。
   **代价同那条决定**：光看这个视图无法还原当时判了什么，要复核必须同时持有原文。
3. **不抓取、不解析。** 落地页的字节来自批次 C（`lp_fetch.py` / `lp_extract.py`）；
   本层只把它们的产物收进同一个信封。
4. **图片 / 视频只有契约，没有实现。** `from_media()` 存在，但**必须由调用方给出正文与覆盖边界**，
   且刻意不提供默认值 —— 一个默认的 `covers` 会让「只做了 OCR」看起来像「图片已审」。
   OCR/ASR 是 **B1**。ADR-0013 异议二要求：B1 的图片/视频指标里必须写清
   「本数字只覆盖图内文字，不含画面语义」，并进 `boundary_statement.unknowns`。
5. **`raw_sha256` 不等于「原件已入库」。** 它是指纹；原件在 L2（内容寻址），或压根不在本仓。
   `raw_verified` 如实记录指纹是不是由落盘原件重算来的。
7. **适配层不改引擎。** `judge.py` 里那句过时的边界声明**仍然在源码里** —— 本层只在返回值上订正。
   真正的修法要等 ADR-0012 的验收脚本一起改，那时才能动那句话。在那之前，
   **凡是不经 `base/judge_adapter.py` 直接调 `judge()` 的路径，拿到的仍是那句假话。**
6. **规则与词表的权威源仍在飞书**（ADR-0013 D2）。本层不做同步，那是 B0.4。

---

## 与后续步骤的接口

| 期 | 依赖本层的什么 | 本层已备好 |
|---|---|---|
| ~~**B0.3** `judge(unit)`~~ | — | ✅ **已完成**（`judge_adapter.py`） |
| ~~**B0.4** 规则单向同步~~ | — | ✅ **已完成**（`sync_rules.py`；D2 拆为 D2a/D2b） |
| ~~**B0.5** `verify_base.py`~~ | — | ✅ **已完成**（含异议一承诺的 L1 自足性检查） |
| **B0.5** `verify_base.py` | `selftest()` 作为五个面之一被调用；另需补 ADR-0013 异议一承诺的 **L1 自足性检查** | ✅ `--selftest` 退出码 0/1 可直接编入 |
| **B1** 四形态管道 | `from_media()` 的 `covers` / `does_not_cover` 必填 | ✅ 契约在，实现在 B1 |
| **装配层（等 PRD）** | `position` 的一致性 | ✅ **已定案（A）**，`position` 可安全用于高亮 |
