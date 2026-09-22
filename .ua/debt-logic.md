# 逻辑债务审计 · audit_multi_content

> 只读审计。本次运行**没有修改、删除或新建仓库内的任何源文件**；唯一写入的产物是本文件。
> 参照系：`AGENTS.md` §2.4–§2.7 定义的「逻辑债务」四种变体。
> 审计时间：本次会话。工作树 `git rev-parse --short HEAD` = `243c6bf`。
> 完整复现命令见 §附录。

**先给结论**：本项目把「常量定义了没人用」治好了（原案那三个常量里两个真接上了），
但**同一个病换了一个更难看的形状活着**——
`MAX_SECTIONS` 被 import、被 re-export、被写进一张叫 `ENFORCED` 的台账、被自证断言点名，
**唯独没有任何一行代码在拦它**；而那条自证断言恰好就是「它有没有执行点」的执行点。

---

## 〇 · 断言层实跑读数（先交底：绿/红/未测分开）

每条都用 `cmd > /dev/null 2>&1; rc=$?` 取的真值（不经管道），末行为逐字抄录。

| # | 命令 | 退出码 | 末行 | 定性 |
|---|---|---:|---|---|
| 1 | `python3 tools/verify_engine_contract.py` | **0** | `验收 176/176  全绿` | 绿 |
| 2 | `node tools/verify_cards.mjs` | **0** | `通过 232 项 · 不通过 0 项` | 绿（但 J1 不会红，见 3-1） |
| 3 | `python3 tools/verify_pending.py` | **0** | `✅ 退 0：结构全过、没有到期未收；最近一个到期日 2026-10-02` | 绿 |
| 4 | `python3 tools/verify_prd_baseline.py` | **1** | `❌ 23 项中 2 项失败` | **真红**（L3 测到了，上游确实改了版） |
| 5 | `node tools/agent/prd_baseline.mjs --selftest` | **0** | `✅ 38 项全过（含「该闭嘴时闭嘴」与「该说时必说」两侧）` | 绿（但样本缺一个形状，见 3-2） |
| 6 | `python3 tools/verify_kb.py` | **0** | `✅ G1 + G3 全部通过` | 绿 |
| 7 | `python3 tools/verify_shouheng_ops.py` | **2** | `⚠ 1 项未测 —— 这不是通过（退 2，与 §2.4.2 同口径）` | **未测**（`ps` 被拒 → E1 落未测）。这是**正确**行为 |
| 8 | `python3 tools/verify_landing.py` | **0** | `通过 16 · 失败 0 · 跳过 0` | 绿 |
| 9 | `python3 tools/verify_external.py` | **0** | `✅ 全部条目在该来源快照中**逐字**命中（无形态差、无空位差）` | 绿（**但这个绿在零网络时也会出现，见 4-1**） |
| 10 | `python3 tools/verify_vocab_lark.py` | **0** | `结论：✅ 飞书与本地逐词一致（回读值，非写入返回码）` | 绿（需要网络；断网时会落成 **1**，见 4-2） |
| 11 | `python3 tools/lark_people.py --controls` | **0** | `✅ 全部 23 项通过` | 绿 |

第 4 条的原始读数（供复核）：

```
★★ 上游改版了：美国市场内容治理项目-一页纸计划书.md
   索引指纹 d78fdef6d7f2b61ec5d9bfd0c40758915841cd5ae91b63c8329ffcd3714b9460
   现场指纹 8211abc09a731dc151e40ce6686142f9be8c377b202b753f1c03fd423aafabd2
```

**合计：9 绿 / 1 真红 / 1 未测。未测那条没有被报成绿，这一点是对的。**

⚠️ 但第 4 条的「真红」要补一句限定：今天它红是因为**上游真的改了版**（L3 测到了）。
同一个脚本在**凭据失效**时也退 1，而那时它应该说「未测」—— 见 §4-6，
那一格的后果比这一格严重得多。

---

## 一 · 常量声明了、没有任何执行点

### 【1-1】★ `MAX_SECTIONS = 3` 至今没有任何一行代码在拦它 —— §2.4 那三个常量只修好了两个

- **证据（定义）**：`tools/reply-cards/cards.mjs:74`
  `export const MAX_SECTIONS = 3;`（上一行 :73 的注释写着「卡片正文里允许出现的段落数上限，防复读」）
- **证据（全部引用点，一共 4 处，没有一处是判定）**：

  | 位置 | 是什么 |
  |---|---|
  | `tools/reply-cards/envelope.mjs:28` | import 绑定：`BUILDERS, VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS,` |
  | `tools/reply-cards/envelope.mjs:387` | 对象字面量：`export const ENFORCED = { VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS, ... }` |
  | `tools/reply-cards/registry.mjs:16` | import 绑定 |
  | `tools/reply-cards/registry.mjs:499` | re-export 列表 |

- **复现**：`grep -rn "MAX_SECTIONS" tools/reply-cards/ tools/verify_cards.mjs`
  → 只有上面 4 行 + 3 处散文（`envelope.mjs:16`、`verify_cards.mjs:294` 的注释，
  `verify_cards.mjs:297` 的断言名列表）。
- **同文件对照（证明另两个是真执行的）**：`VERDICT_MAX` 在 `envelope.mjs:217/221/224` 真比较
  （`if (d.verdict && len(d.verdict) > VERDICT_MAX)`…），`BOUNDARY_MAX` 在
  `envelope.mjs:235/238/241` 真比较。**同一个 import 块里，两个在拦、一个不在拦。**
- **补充证据（连概念都不存在）**：`grep -rn "section" tools/reply-cards/*.mjs` → **零命中**。
  也就是说 `MAX_SECTIONS` 约束的是一个代码里根本没有的结构。
  （最接近的是 `evidence` 卡的 `groups`，`cards.mjs:268-269` 遍历它，**没有任何长度上限**。）
- **影响**：本项目四处文档同时声称「三个上限现在有唯一执行点」，那句是假的：
  - `tools/reply-cards/envelope.mjs:16-19`：「…三个常量定义完之后，整个仓库没有任何代码引用它们…**这一层就是它们唯一的执行点**」
  - `tools/reply-cards/registry.mjs:497-499`：「这三个上限以前只定义、不导出、不引用…**envelope.mjs 是它们现在唯一的执行点**」
  - `tools/reply-cards/contract.md:293-295`：同一句话
  - `PMO/守衡-回复卡片模版与语域规程.md:146`
  模型写 5 段、10 段正文，今天照发。
- **建议动作**：二选一 ——（a）删掉常量并同步删掉那四段声称（承认这条约束不存在）；
  （b）在 `envelope.enforceLimits` 里按段数真做一次搬迁（超出段落进折叠区，一个字符不丢），
  并给 `verify_cards` 加一条**喂 5 段输入必须看到搬迁记录**的用例。

### 【1-2】三个 Python 模块级常量零引用

机械读数（AST 遍历全仓 659 个 `.py`，统计定义体之外的 `Name`/`Attribute`/字符串常量出现次数；
命令见附录 A）：

| 常量 | 位置 | 引用数 | 复现读数 |
|---|---|---:|---|
| `VERDICTS` | `base/change_detect.py:74` | **0** | `grep -rn "VERDICTS" --include=*.py --include=*.mjs .` → 只命中定义行 |
| `RULE_TABLE_KEY` | `research/governance/skeleton/build_rules.py:38` | **0** | 同文件 :76 实际用的是 `AD_TABLE_KEY` |
| `TEXT_FIELDS` | `research/governance/skeleton/attribute_misses.py:25` | **0** | 同文件 :50 用的是 `WIDE_FIELDS` |

- **`VERDICTS`（`base/change_detect.py:74`）** 是「三值结论的枚举完整性守卫」——
  `VERDICTS = (V_SAME, V_NEW_NO_CLAIM, V_NEW_CLAIM)`，三个成员单独都在用，**只有这句汇总没人读**。
  即「三值结论到底有几个」这件事没有消费者：将来加第四个值，`VERDICTS` 不会跟着变，也没有东西会红。
  与 §2.4 原案（`VERDICT_MAX` 等）**完全同形**。
- **`RULE_TABLE_KEY`（`build_rules.py:38`）** = `"品线内容边界规则库"`，零引用。
  这个文件靠 `find_table(tables, needle)`（:41-45）按表名找表并**在命中不唯一时硬失败**，
  但那条「规则表叫什么」的真相只写在 `AD_TABLE_KEY` 那一半上；规则表名这个常量是死的。
- **`TEXT_FIELDS`（`attribute_misses.py:25`）** = `["Primary Text", "Headline"]`，
  与 `base/text_stage.py:98` 的 `AD_TEXT_FIELDS = ("Primary Text", "Headline")` **逐字相同** ——
  见 §6-5（同一决定的第二份副本）。
- **影响**：三个都是「读代码才看得见」的那一类，不会产出假数据；但它们让
  「有没有人用这个常量」这个问题的答案是「没有」，而文档/注释会让人以为有。
- **建议动作**：删掉，或接上一个真消费者（`VERDICTS` 最自然的消费者是
  `base/verify_base.py` 里一条「三值结论集合必须与枚举恒等」的断言）。

### 【1-3】`IDENTITY`（`tools/agent/persona.mjs:14`）零引用 —— 对外身份写死在代码里且无人读

- **证据**：`persona.mjs:14-19`
  ```js
  export const IDENTITY = {
    name: '守衡', role: '面向飞书群的智能体', owner: 'lute', businessContact: '李倩怡',
  };
  ```
  `grep -rn "\bIDENTITY\b" --include=*.mjs --include=*.js tools/ base/` → 只有定义行。
  `tools/agent/agent.mjs:15` 只 import `buildSystemPrompt`。
- **影响**：**业务对接人「李倩怡」这个名字改了不会有任何东西红。** 而她是全项目里
  出现频率最高的外部对象（§2.4.3 整节、`PMO/待收清单-v1.json`、BOUNDARY 表都在说她）。
  这不是假数据，但它是一份「看着像唯一真相、其实没人读」的身份登记。
- **建议动作**：要么让 `buildSystemPrompt` 真的从 `IDENTITY` 取值（并在提示词里体现），
  要么删掉并改成注释。

### 【1-4】`ENFORCED`（`envelope.mjs:387`）零消费者 —— 「谁读了哪些常量」这份台账自己没人读

- **证据**：`envelope.mjs:386-387`
  ```js
  /** 供 verify 与 CLI 用：哪些常量真的被读了 */
  export const ENFORCED = { VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS, KINDS: Object.keys(BUILDERS), validateCard };
  ```
  `grep -rn "ENFORCED" tools/ base/ research/ agent-skills/ PMO/` → **零命中**。
- **影响**：这份对象的存在本身就是「§2.4 的修法」的一部分 —— 把「哪些常量真的被读了」
  变成可读的数据。但没有任何检查器读它：`verify_cards.mjs:297` 走的是
  **正则扫源码文本**（见 3-1），而不是读这份台账。所以台账既没被读，也读不出真相
  （`MAX_SECTIONS` 在里面，而它没被执行）。
- **建议动作**：删掉 `ENFORCED`，把 J1 改成「喂进去一个超限输入，必须在**返回值**里看到搬迁记录」
  —— 判据必须是行为，不是名字。

### 【1-5】`validateCard` 的 warnings 在生产路径上**算完就丢**

- **证据（生产）**：`cards.mjs:318` `const W = (p, m) => warnings.push({ path: p, msg: m });`
  → 收集；`cards.mjs:392` `const v = validateCard(c);` → `cards.mjs:393-396` **只看 `v.errors`**，
  `throw` 或 `return c`，`v.warnings` 既不返回也不记录。
- **证据（唯一消费者）**：`tools/reply-cards/cli.mjs:113-115`
  `if (v.warnings.length) { console.log(...) }` —— 只有开发者手动跑 CLI 才看得见。
- **复现**：`grep -rn "\.warnings" tools/` → 只命中 `cli.mjs`。
- **影响**：`cards.mjs` 里**仅有的两条数值上限**因此不在生产路径上：
  - `cards.mjs:360` `if (el.columns?.length > 4) W(..., '手机上会挤；建议 ≤3')`
  - `cards.mjs:373` `if (el.rows?.length > 30) W(..., '群消息里过长；建议拆卡或折叠')`
  一张 4 栏或 40 行的卡会被 `build()` 正常建出并**发进群**。
- **建议动作**：warnings 要么升级成 errors（真拦），要么进 `envelope.mjs` 的 `moved` 记录
  并写进 ws_daemon 的日志行（至少可归因）。今天它是「算了没人看的假精度」。

### 【1-6】单引用常量逐个查过：都是真执行点（记下来以免误报）

`MAX_IMAGE_BYTES`（`base/media.py:100` → 真比较于 `:293`）、`GITIGNORE`
（`base/verify_base.py:75` → 真读于 `:233`）、`REACH_BINS`（`severity.py:64` → 真遍历于 `:76`）、
`ROUTING_FROM_AD`（`contract.py:236` → 真遍历于 `:434`）、`AD_TEXT_FIELDS`
（`text_stage.py:98` → 真判据于 `:117`）、`CARRIER_CORRECTED`（`judge_adapter.py:114` → `:151`）、
`ARTIFACTS`/`CODE_FILES`（`engine_manifest.py:50/85` → `:160/:183`）、
`RETRYABLE_STATUS`（`llm.mjs:16` → `:73`）、`JUDGE_PY`（`tools.mjs:285` → `:332`）、
`PENDING_SCRIPT`（`prd_baseline.mjs:58` → `:301`）、`MAX_TEXT_LEN`（`feishu.mjs:140` → `:143`）、
`FOLD_FIELD`/`FALLBACK_SLOT`/`PUBLIC_FIELDS`（`envelope.mjs:129/144/180` → 真判据）、
`MAX_LOG_BYTES`（`ws_daemon.mjs:292` → `:298`）、`truncate.mjs:22/25/28/31` → 真判据。
**这些不是债务。**

> **方法学提醒（重要）**：纯「数引用次数」的启发式**抓不到** 1-1 那种债。
> `MAX_SECTIONS` 有 4 处引用，计数看起来比上面那些安全，实际是唯一一条真债。
> 判据必须是「这个常量有没有出现在一个能改变行为的表达式里」。

---

## 二 · 文档写了上限、代码里找不到执行点

### 【2-1】AGENTS.md 自己给同一个读数写了两个数，其中 `18` 复现不出来

- **证据**：`AGENTS.md:41` 写「**23 项**离线反向对照」；`AGENTS.md:319`（§2.4.1 表格第 4 行）
  写「`--controls` 的 **18 项**离线反向对照」。
- **复现**：`python3 tools/lark_people.py --controls` → 退出 **0**，末行
  `✅ 全部 23 项通过`；`grep -c "lambda:" tools/lark_people.py` → **23**。
- **影响**：违反本文件 §2.2 第 1 条「文档里的数字要算出来，不能写进去」——
  而且是**在宪法文件自己身上**。§2.4.1 那一行是记那次真实事故的地方，
  数字错了会让读的人以为对照项变少了（即以为覆盖退化）。
- **建议动作**：改 `AGENTS.md:319` 的 18 → 23；并把「项数」这句改成带命令的句子
  （`python3 tools/lark_people.py --controls | tail -1`），按 §2.2 第 1 条的规矩办。

### 【2-2】★ AGENTS.md:568 指的执行点 `ws_daemon.mjs:229` 指错了行，而且没人管

- **证据**：`AGENTS.md:568`
  `| kill -TERM | ws_daemon.mjs:229 捕获 → shutdown() → **process.exit(0)** |`
- **实测真实位置**（`grep -n "shutdown\|process.exit(0)\|SIGTERM\|SIGINT" tools/ws_daemon.mjs`）：
  ```
  248: async function shutdown(sig) {
  255:   process.exit(0);
  257: process.on('SIGINT',  () => shutdown('Ctrl-C'));
  258: process.on('SIGTERM', () => shutdown('SIGTERM'));
  ```
  而 `sed -n '229p' tools/ws_daemon.mjs` 输出的是 `  },` —— 那是 `card.action.trigger`
  处理器的结尾。**指的是一个完全无关的括号。**
- **关键点**：`grep -n "229" tools/verify_shouheng_ops.py` → **空**。
  没有任何断言在看这个行号。
- **影响**：这正是 §2.4 那句话（「必须能指出是哪一行代码在拦它」）在**它自己身上**失效。
  行为没变（`exit(0)` 仍在），但「指得出对象」这件事丢了，
  而 §2.7 那一整节的推理都建立在这条指认上。
- **建议动作**：改成 `ws_daemon.mjs:255`（并给 §2.7 那张表加一条断言：
  引用的行号必须真的落在 `process.exit(0)` 那一行上）。

### 【2-3】contract.md 说 `column_set` 三栏，代码只在 >4 栏时给一条**不阻断**的提醒

- **文档**：`tools/reply-cards/contract.md:107`「`markdown · markdown · column_set(3栏) · collapsible(收起) · hr · markdown`」；
  `:118`、`:142` 同样是「3栏」；`:138`「**三栏一次说完**，不分段解释」。
- **代码**：`tools/reply-cards/cards.mjs:360`
  `if (el.columns?.length > 4) W(\`${q}.columns\`, \`${el.columns.length} 栏，手机上会挤；建议 ≤3\`);`
  —— 阈值是 **4 不是 3**，动作是 `W(...)` 进 warnings，而 warnings 在生产路径被丢弃（见 1-5）。
- **影响**：「≤3 栏」在今天是一句注释：4 栏的卡会被建出并发出，5 栏才会在 CLI 里看到一句提醒。
- **建议动作**：把阈值对齐到 3 并升成 `E(...)`（真拦），或把 contract.md 的「3栏」改成
  「实测 3 栏最好看，4 栏起手机上会挤（不阻断）」。

### 【2-4】contract.md 自己的「三条硬约束是被执行的」表里没有 `MAX_SECTIONS` 那一行

- **证据**：`tools/reply-cards/contract.md:284-288` 的表**只有两行**
  （`结论（verdict）≤60 字符`、`边界（boundary）≤90 字符`），
  而紧跟着 `:293-295` 的引文说「`VERDICT_MAX` / `BOUNDARY_MAX` / `MAX_SECTIONS`
  三个常量…`envelope.mjs` 是它们现在唯一的执行点」。
- **影响**：文档内部自相矛盾，而且矛盾的方向刚好**把缺口藏起来**：
  只读那张表的人会以为上限一共两条，都执行了。
  同理 `PMO/守衡-回复卡片模版与语域规程.md:89-93` 的「三条硬约束」里第 3 条是
  「内部记录只进折叠区」，不是段数 —— `MAX_SECTIONS` 在这份规程里**一次都没出现过**。
- **建议动作**：与 1-1 一起收口：要么补上第三行并真执行，要么把 `MAX_SECTIONS` 从文档删干净。

### 【2-5】judge.py:218 的「L5 档从未被使用」是一个没有执行点的断言式陈述

- **证据**：`research/governance/skeleton/judge.py:218`
  ```python
  "**L5 档从未被使用**：规则库现有严重等级只有 L0/L1/L2/L4，没有一条规则是 L5。"
  ```
- **实测（今天是真的）**：`rules-v1.json` 里 26 条规则的 severity 分布 =
  `{'L4': 11, 'L2': 13, 'L1': 1, 'L0': 1}`；`severity.py:44` 有 `"L5": "Very High"` 映射。
- **缺口**：`grep -n "L5" tools/verify_engine_contract.py` → 只命中 `:508` 一句无关的话。
  **没有任何断言盯着这句话。**
- **影响**：这句话出现在**每一次判定回执的边界声明里**（`judge.py:192-200` 的 `unknowns`
  会被渲染进 `render()`，`:845-847` 那段）。规则库一旦加一条 L5，
  这句话在每一条对外回执里变成假话，而不会有东西红。这是 §2.4 的一个新变体：
  **不是常量没人用，是一句「已知事实」写死在会对外输出的字符串里。**
- **建议动作**：加一条断言 `set(severity of rules) ∩ {'L5'} == ∅ ⇔ 文案里出现「L5 档从未被使用」`
  （两边互为反面，同 §2.4.3 的 C2/C3 手法）。

### 【2-6】★ 「内部记录只进折叠区」这条硬约束，在**纯文本路径上没有执行点**

- **文档**：`PMO/守衡-回复卡片模版与语域规程.md:93` 第 3 条硬约束；
  `agent-skills/守衡语域/SKILL.md:89` 第 7 行「**不是改写，是不许写。** 内部详情只进折叠区」；
  `SKILL.md:69`「**判据**：回复里出现 `tool_calls`、`call_xxx`、连续三次以上同名工具、
  或任何栈帧，**即违规**」。
- **代码（卡片路径有执行点）**：`envelope.mjs:186-205` `scrubInternal()`，由
  `enforceLimits` 在 `:270-273` 调用。
- **代码（纯文本路径**没有**执行点）**：`envelope.mjs:300-302`
  ```js
  if (!blk) {
    return { mode: 'text', text: raw, reason: null, moved: [], lint: lintCopy(raw), dropped: false };
  }
  ```
  —— 只调了 `lintCopy`（**报告**），没有 `scrubInternal`（**动作**）。
  而 `ws_daemon.mjs:101` 把 lint 结果只写一行日志，正文照发：
  `for (const h of shaped.lint) log(...)`。
- **实测（内存里跑，不落盘、不改文件）**：
  ```bash
  node --input-type=module -e "
  import { toCardOrText, leaksInternalMark } from './tools/reply-cards/envelope.mjs';
  const fault='我查了几轮还是没能得出可靠结论。我试过 list_files、list_files、list_files、list_files、list_files，返回 tool_calls=[] call_abc1234567890 finishReason=stop';
  const r=toCardOrText(fault);
  console.log(r.mode, leaksInternalMark(r.text), r.lint.map(h=>h.id+'x'+h.count).join(','));"
  ```
  读数：
  ```
  mode = text | dropped = false | reason = null
  泄漏标记仍在正文? -> true
  lint 命中 -> internalLeakx4
  ```
  **判据抓到了 4 次，动作一次都没有。**
- **为什么这条最严重**：2026-09-17 那条真事故（连列 27 次工具名的 434 字故障输出）
  **正是纯文本**（`PMO/守衡-回复卡片模版与语域规程.md:24`）。今天同样的输入，
  `internalLeak` 会命中 4 次、写 4 行日志、然后把原文原样发进群。
- **第三处缺口（检出条件本身也被缩小了）**：`SKILL.md:89` 写的检出条件是
  「连续同名工具 ≥3 次 / `tool_call_id` / `call_xxx` / 栈帧」，
  而真正在执行的 `scrubInternal` 正则（`envelope.mjs:200`）只认
  `/(tool_calls|tool_call_id|finishReason|reasoning_tokens|call_[0-9a-zA-Z]{10,})/` ——
  **「连续同名工具 ≥3 次」与「栈帧」不在执行点里**。
- **断言为什么没拦住**：`verify_cards.mjs` 的 J2 有 13 个 `leakCases`，
  其中「纯文本」那条喂的是 `'就是一句话，没有卡片。'`（**干净的**纯文本）。
  **没有任何一条用例喂「含内部标记的纯文本」**。
- **建议动作**：把 `scrubInternal` 提到 `toCardOrText` 的最外层（对 `mode:'text'` 也跑一次；
  纯文本没有折叠区，那就必须降级成「我这次没能把回答组织好」而不是原样发），
  并把 J2 的用例表补上「含 `tool_calls` 的纯文本」这一条。

---

## 三 · 不会红的断言（假精度）

### 【3-1】★ `verify_cards.mjs` 的 J1 是**源码文本存在性测试**，此刻正在它本该抓的缺陷上变绿

- **证据**：`tools/verify_cards.mjs:296-301`
  ```js
  const envSrc = fs.readFileSync(path.join(CARDS_DIR, 'envelope.mjs'), 'utf8');
  for (const k of ['VERDICT_MAX', 'BOUNDARY_MAX', 'MAX_SECTIONS']) {
    if (!new RegExp(`\\b${k}\\b`).test(envSrc)) no(`J1 ${k} 有执行点`, `${k} 在 envelope.mjs 里没被引用，上限又变回注释了`);
    else ok(`J1 ${k} 在 envelope.mjs 里被使用`);
  }
  ```
- **为什么它恒真**：判据是「这个名字在 `envelope.mjs` 的**文本**里出现过」。
  `envelope.mjs:28` 的 import 行、或 `:387` 的 `ENFORCED` 字面量，
  **任意一条**就能满足它 —— 而这两处都不改变任何行为。
- **实测反证（这是活的，不是推理）**：`MAX_SECTIONS` **确认没有任何执行点**（见 1-1），
  而 `node tools/verify_cards.mjs` → 退出 **0**、`通过 232 项 · 不通过 0 项`、**J1 三条全绿**。
- **影响**：§2.4 结尾写着「`node tools/verify_cards.mjs` 的 J1 段会断言这一点」——
  也就是说，**这条规矩的执行点本身不会红**。一个检查器在它被造出来要抓的那件事上恒绿，
  比没有检查器更糟（§2.1.1 的原话：会让人开始不看报告）。
- **建议动作**：J1 改成**行为断言**：构造一个 `verdict` 200 字 / `boundary` 300 字 /
  5 段的输入，调 `enforceLimits`，断言返回的 `moved` 非空**且每一项都有落点**
  （`to !== null`），并断言 `MAX_SECTIONS` 真的截到了段数。名字出现不算数。

### 【3-2】★ prd_baseline 的两个状态机把「退 1（红）但明细为空」静默记成绿

- **证据（基线状态机）**：`tools/agent/prd_baseline.mjs:127 / 147 / 170`
  ```js
  127:  if (code === 1 && now.drifted.length) { ... 说 ... }
  147:  if (code === 2) { ... 说 ... }
  170:  return { state: { ...st, lastState: 'ok', saidDriftFp: null }, say: null, why: '一直是绿的，不刷屏' };
  ```
  退 1 且 `drifted` 为空时，**穿过 127、穿过 147，落到 170** → 沉默 + `lastState:'ok'`。
- **证据（待收状态机同形）**：`:338 / :364 / :386`
  `if (code === 1 && (now.overdue ?? []).length)` … `:386 return { state: { ...st, p_lastState: 'ok' }, say: null, ... }`
- **实测（内存里调纯函数，不落盘）**：
  ```bash
  node --input-type=module -e "
  import { enter, enterPending } from './tools/agent/prd_baseline.mjs';
  const D='2026-09-21';
  console.log(JSON.stringify(enter({lastState:'ok'}, {code:1, day:D, drifted:[], untested:[]})));
  console.log(JSON.stringify(enterPending({p_lastState:'ok'}, {code:1, day:D, overdue:[]})));"
  ```
  读数：
  ```
  enter        code=1 drifted=[]  -> {"say":null,"why":"一直是绿的，不刷屏","lastState":"ok"}
  enterPending code=1 overdue=[]  -> {"say":null,"why":"没有到期未收，不刷屏","p_lastState":"ok"}
  ```
- **影响（两层）**：
  1. **告警永久沉默**，而且状态被写成 `ok` —— 于是将来真的从红恢复时，
     `:163`/`:379` 的「恢复」分支也不会触发（`prev.lastState` 已经是 `'ok'`）。
     一次红被彻底吞掉，群里什么都没看到。
  2. **它是纯函数，退 1 的那一半没有断言。** 38 项反向对照里**没有一项**喂
     `{code:1, drifted:[]}`（所有红样本都走 `drift(fp)`，drifted 非空）。
     基线那条靠**调用点**打补丁（`:281-283` 造一个占位 drift 条目），
     **待收那条连补丁都没有**（`:403-408` 只取 `data?.overdue ?? []`）。
- **建议动作**：把「退 1 必须说」这条判据移进 `enter`/`enterPending` 内部
  （`code === 1` 就必然 `say`，明细为空时用兜底文案），别留在调用点；
  并给 `--selftest` 补上 `{code:1, drifted:[]}` 与 `{code:1, overdue:[]}` 两条用例。

### 【3-3】★ `verify_pending.py` 的退 1 可以由**结构违规**触发，而结构违规在 daemon 侧没有任何消费者

- **证据（服务端）**：`tools/verify_pending.py:275`
  `code = 1 if (struct or od) else 0` —— 退 1 有两个来源：结构违规 **或** 到期未收。
- **证据（它自己的反向对照就在喂这个形状）**：`verify_pending.py:437`
  `lambda: judge([cp(p03, 状态="大概吧")], T, fake)["code"] == 1` —— 纯结构违规、`od` 为空。
  这条用例只断言「该红时红」，**没有人断言这个红会走到群里**。
- **证据（客户端零消费者）**：`grep -rn "struct_errors" tools/agent/ tools/ws_daemon.mjs` → **空**。
  `tools/agent/prd_baseline.mjs:403-408` 只取 `overdue` 与 `reason`，`struct_errors` 被丢掉。
- **合起来是一条可判定的链**：清单里某条「承诺」丢了上游原话指针 →
  `verify_pending.py` 退 1（JSON 里 `overdue: []`、`struct_errors: [...]`）→
  `runPendingChecker` 接受 code 1（`:317` 只要求 `[0,1,2].includes(raw) && data`）→
  `runCheckPending` 组出 `overdue: []` → `enterPending` 落到 `:386`
  → `{say: null, p_lastState: 'ok'}`。**清单被改坏 = 群里永远听不到。**
- **影响**：C2/C3 是 §2.4.3 整节最看重的两条断言（「承诺必须指得出原话」「我方问题不许
  写成对方承诺」）。它们红了之后，**唯一的输出是一行控制台字**，
  而那行字只出现在手动跑的时候。
- **建议动作**：`runCheckPending` 里加一条与基线对称的补丁
  （`code === 1 && overdue.length === 0` → 用 `struct_errors` 组一条「清单结构有问题」的 say），
  并在 `--selftest` 里断言这条文案真的会产出。

### 【3-4】`llm.mjs:73` 有一个恒真的合取项 + 一个写了两遍的谓词

- **证据**：`tools/agent/llm.mjs:73`
  ```js
  if (!RETRYABLE_STATUS.has(res.status) && attempt >= 0 && !RETRYABLE_STATUS.has(res.status)) {
  ```
  循环在 `:58` `for (let attempt = 0; attempt <= 3; attempt++)` → `attempt >= 0` **恒真**；
  同一个 `!RETRYABLE_STATUS.has(res.status)` 写了**两次**。
- **影响**：读起来像三重判据，实际只有一重。这类「看着像读过」的假精度是 §2.1.1 点名的形状。
- **建议动作**：删掉 `attempt >= 0` 与重复谓词（行为零变化）。

### 【3-5】`verify_external.py` 的「今日抓取」读数**在线与离线两次运行给出同一组数** —— 它不会动

- **证据**：`tools/verify_external.py:335-340`（打印）与 `:355-360`（结论行）
  都从 `hit[2]`（`'visible'` / `'embedded'` / `'pin:…'`）统计。
  而 `--offline` 分支（`:267-275`）只是把快照来源从网络换成**缓存文件**，
  匹配结果的**形状完全相同一个计数**。
- **实测对照**：
  - 联网跑（本次第 9 条）：`命中 62（今日抓取：可见正文 38 / 仅内嵌数据块 18；仓内钉住证据 6）`
  - 离线跑：`python3 tools/verify_external.py --offline` → 同样
    `命中 62（今日抓取：可见正文 38 / 仅内嵌数据块 18；仓内钉住证据 6）`
- **影响**：这一块读数是**恒真的假精度**（§2.7 原话：那块读数「必须会动」，否则证伪开关等于没有）。
  详见 §4-1 —— 同一件事的后果是「零网络运行照样报 ✅ 退 0」。
- **建议动作**：把 `meta[sid]` 的 `http=` 取值（`cached` vs `200`）算进结论行，
  例如「今日抓取 N 份 / 读缓存 M 份」，并让 `--offline` 下的结论行显式说
  「本次未联网，读的是缓存」。

### 【3-6】★ `verify_depad.py`：`stat` 调用失败 ⇒ 每个文件都跳过 ⇒ 打印「被填充 0 个」并退 0

> **这是 §2.2 第 5 条（`timeout` 不在时 rc=127 与「扫完了没命中」长得一模一样）的复刻版**，
> 只不过主角从 `timeout` 换成了 `stat`。

- **证据（调用处没有 `check=True`）**：`tools/verify_depad.py:98-101`
  ```python
  r = subprocess.run(["stat", "-f", "%z\t%N", *chunk],
                     capture_output=True, text=True, timeout=120)
  ```
  —— **没有 `check=True`**。所以 `stat` **进程存在但非零退出**（返回空 stdout）时
  **不抛异常**，于是 `:103-106` 的解析循环一行都解析不出来 → `stat_sizes` 返回一个
  **空字典 `{}`**（而不是 `None`）。
- **证据（空字典被当成「取不到就不判」）**：`tools/verify_depad.py:118-122`
  ```python
  seen = stat_sizes(targets)
  if seen is None:
      return None, None, len(targets)     # ← 只有「抛异常」才走这里（会退 2）
  ...
      s = seen.get(p)
      if s is None:
          continue                       # /N 在部分平台不可靠，取不到就不判
  ```
  → 6490 个目标**全部 `continue`** → `padded = []` → 主流程打印
  「扫描 N 个文本文件 · 被填充 0 个」并 **`return 0`**。
- **子代理实测读数**（内存 patch `subprocess.run` 使其返回 rc=1 + 空输出，未动盘）：
  `scan() -> padded=[] other=[] n=6486` → 「被填充 0 个」→ **`return 0`**。
- **影响**：这个检查器的**全部价值**就是「有没有文件被填充成 `read` 打不开」，
  而它最坏的情况是**环境取不到读数时报告「一个都没有」**。
  按 §2.2 第 5 条的原文：「规矩：**靠外部命令取的读数，取不到时必须说「未测」——
  不许空着，也不许当成 0。**」
- **可分辨性**：同文件 `:101-102` 的 `except` 分支**做对了**
  （`print("⚠️ stat 调用失败…不当作通过"); return None` → `:162 return 2`）。
  也就是说：**抛异常 → 正确退 2；非零退出 → 假绿退 0。** 两条路只差一个 `check=True`。
- **建议动作**：`subprocess.run(..., check=True)`（或显式判 `r.returncode != 0` → 走
  「未测」分支）；并补一条反向对照：喂一个 rc≠0 的假 stat，断言**退出码是 2 而不是 0**。

### 【3-7】`verify_feishu_index.py` 的 M5：断言的靶子一没，自己就变绿

- **证据**：`tools/verify_feishu_index.py:322-329`（§2.6 红线的执行点）
  ```python
  _ff = next((n for n in _ast.walk(_ast.parse(fs))
              if isinstance(n, _ast.FunctionDef) and n.name == "fetch_file"), None)
  _calls = [getattr(c.func, "id", getattr(c.func, "attr", ""))
            for c in _ast.walk(_ff) if isinstance(c, _ast.Call)] if _ff else ["<未找到 fetch_file>"]
  ck("M", "M5 fetch_file 不做任何网络调用（不下载、也不探测）",
     all(c not in HTTP_HELPERS for c in _calls), f"调用了：{_calls}")
  ```
  `_ff is None` 时 `_calls = ["<未找到 fetch_file>"]` —— 一个**保证不在 `HTTP_HELPERS` 里的字符串**，
  于是 `all(...)` **恒真** → M5 判 ✅。
- **影响**：M5 是 `AGENTS.md` §2.6 那条红线（飞书内容禁止下载）的四条执行点之一
  （M1 AST 扫全仓 / M2 喂坏样本 / M3 产物不许有二进制 / **M5 `fetch_file` 一次网络都不许有**）。
  `fetch_file` 被删掉或改名，**红线最该响的那一条会变绿**。
  子代理内存复现：喂一份没有 `fetch_file` 的源码 → **rc=0、`✅ 34 项全过`**。
- **建议动作**：`_ff is None` 必须直接 `no(...)`（「靶子不存在」不是「没违反」）。

### 【3-8】`verify_feishu_index.py` 的 E9：`stat` 取不到 ⇒ 判据静默跳过 ⇒ 恒绿

- **证据**：`tools/verify_feishu_index.py:216-220`
  ```python
  try:
      return int(_sp.run(["stat", "-f", "%z", p], capture_output=True,
                         text=True, timeout=5).stdout.strip())
  except Exception:
      return -1
  ```
  → `:226-227` `real, seen = os.path.getsize(p), _stat_size(p)` / `if seen > 0 and seen != real:`
  —— `seen = -1` 不满足 `> 0`，于是**该文件不参与判定**。
- **影响**：E9（「生成物未被环境填充」）在 `stat` 不可用时**恒绿**，
  而它恰好是 `AGENTS.md` §2.1 那条最贵的教训（+4096 填充）的执行点。
  与 3-6 是同一个形状（取不到 → 当成没问题），**两处独立发生**。
- **建议动作**：`_stat_size` 返回 `None` 而不是 `-1`，并在有 `None` 时把 E9 落成
  「未测」（`--json` 里能看出来），而不是 ✅。

### 【3-9】`verify_cards.mjs` 两处「靶子没了就通过」

- **L2（`:440-444`）**：`replyCardBody = feishuSrc.slice(indexOf('export async function replyCard'), indexOf('export async function sendTyping'))`
  —— `replyCard` 一旦改名/被删，`indexOf` 返回 `-1`，`slice(-1, …)` 得**空串**，
  于是 `/sendMarkdown|sendCard|message\.create/.test("")` 为 false → 走 `ok(...)`，
  打印「L2 feishu.replyCard 只尝试一次，兜底只有 daemon 一处」✅。
  **「函数不存在」被判成「它只尝试一次」。**
- **H（`:276-281`）**：`const r = spawnSync('git', ['check-ignore','-q', ...]); if (r.status === 0) no(...); else ok(...)`
  —— git 不可用时 `r.status` 是 **`null`**（不是 0），落 `else` → ✅「可入库」。
  与 §2.2 第 5 条同形：**外部命令不在，读数静默退化成正面的那一侧。**
- **影响**：L2 是 §2.5「发送兜底只能有一处」的执行点；H 是 §2.3「自有 skill 必须进
  `agent-skills/` 而不是 `skills/`」的执行点。两条都是「检查器在它该红的时候会绿」。
- **建议动作**：两处都加「靶子在不在」的前置判据（`indexOf >= 0`；`r.error`/`r.status === null`
  → 直接 `no(...)`）。

### 【3-10】`verify_shouheng_ops.py:227` 的 B3 是恒真断言 —— 它从不读闸门源码

- **证据**：`tools/verify_shouheng_ops.py:227`
  ```python
  check("B3", not scan_bypass("find tools -newer ref"), "闸门不再用「改过的文件都算生效」那种粗读法")
  ```
  而 `scan_bypass` 的模式表在 `:94-99`：
  ```python
  BYPASS = [
      (r"launchctl\s+kickstart", "直接 kickstart"),
      (r"launchctl\s+(bootout|unload|stop)\b", "把守衡卸下/停掉"),
      (r"pkill\s+-f\s+[^\n]*ws_daemon", "pkill 守护进程"),
      (r"\bkill\b[^\n]*ws_daemon", "kill 守护进程"),
  ]
  ```
  `scan_bypass` 扫的是**绕过闸门直接操作守护进程**的写法，
  而 B3 喂进去的是**另一个模式**（`find tools -newer`，§2.7 记的那个「粗读法」）。
  四个正则一个都匹配不到 → `not scan_bypass(...)` **恒为 True**。
- **关键点**：B3 **从不读 `restart_shouheng.sh` 的源码** —— 它的输入是一个**字面量字符串**。
  所以「闸门不再用粗读法」这件事，**没有任何东西在拦**（§2.7 那段「造这个闸门时我自己又犯了一次
  同一个病」的修复，自证里对应的那一条是空的）。
- **正确写法就在同文件隔壁**：B1/B2/B4/B5 都是 `run_gate("--check", "--since=…")` 拿**真实输出**
  做断言（那四条是好的）。B3 是唯一一条不读现场的。
- **建议动作**：B3 改成读 `tools/restart_shouheng.sh` 的源码并断言其中不出现
  `-newer`（同时给一条反向对照：塞一行 `find tools -newer` 进去必须红）。

### 【3-11】`verify_shouheng_ops.py` 的 `--controls`/常量类断言之外，还有两处读数为「声明」而非「实测」

- `base/verify_base.py:327-331` `n = r.stdout.count("✓"); nneg = r.stdout.count("必红")`
  —— 这两个数**只被打印、从不被断言**：模块自证打印「0 项（含 0 条必红）」也照样过。
- `tools/verify_feishu_index.py:160-168` 的 C2 第一个循环（`:161-164`）**每个分支体都是 `pass`**，
  `v` 算完就丢 —— 标题写「md 与 json 的关键数字一致」，实际只比了 `core_extent_ok` 一个数。
- 这两条属于「算了没人用 / 标题比判据大」，与 1-5 同类，**单独列出以免与真断言混在一起看**。

---

## 四 · 未测被报成通过（`2 ≠ 0` 这条规矩的存活情况）

### 【4-1】★★ `python3 tools/verify_external.py --offline`：**一次网络都没发，退 0，末行 ✅**，而汇总行还在说「今日抓取」

- **复现**：
  ```bash
  python3 tools/verify_external.py --offline > /tmp/ext.txt 2>&1; rc=$?; echo "EXIT=$rc"; sed -n '4p;23p;34p' /tmp/ext.txt
  ```
- **逐字读数**：
  ```
  EXIT=0
  OK S1   http=cached text=12991    条目=5   offline
  逐条核对：命中 62（今日抓取：可见正文 38 / 仅内嵌数据块 18；仓内钉住证据 6）  失配 0  不可复核 0  —— 共 62 条
  ✅ 全部条目在该来源快照中**逐字**命中（无形态差、无空位差）
  ```
  （来源表 17 行**全部**是 `http=cached … offline`。）
- **和 §2.4.2 记的那次事故是同一个形状**：AGENTS.md 原文——
  「这个脚本第一次运行时犯的错，比它修的问题更值得记：它自己打印了
  `✅ 16 项全过（含 L3：上游与指纹一致）`—— 而那一轮是 `--offline`，**一次网络都没发**。」
  **同一个形状活在同一个仓库的另一个检查器里**，而且这个检查器今天在跑、今天会给绿。
- **附带的假陈述**：`--offline` 下汇总行仍写「**今日抓取**：可见正文 38」——
  这是一句在离线运行时**确定错误**的话（今天什么都没抓）。
  这正是 §2.4.1 的自检句「这句话比我的输入大吗？」：输入是「我读了缓存」，
  说出去的是「我今日抓取了 38 篇可见正文」。
- **为什么没有东西红**：`:384` `ok = not miss and not unver and not pun and not wsq`；
  `:390` `return 0 if ok else 1` —— **退出码 2 不可达**（见 4-2），
  而且 `unver` 只覆盖「既无快照、又无仓内钉住证据」的条目，离线时钉住证据照样算命中。
- **建议动作**：① 结论行必须区分「今日抓取」与「读缓存/钉住件」的条数；
  ② `--offline` 或「今日抓取 = 0」时退 **2**（未测），不是 0；
  ③ 给 `verify_external` 加一条反向对照：喂一个「全部来源都没抓到」的假样本，
  结论行必须不许出现 ✅（同 prd_baseline `verdict()` 的做法）。

### 【4-2】退出码 2（未测）在 7 个检查器里不可达；其中 3 个有真实的未测条件却落成「红」

- **机械读数**（正则扫 `sys.exit(` / `return [012]` / `process.exit(` / `SystemExit(`；
  命令见附录 B，注意 `lark_people.py` 的 2 是经 `WORST` 字典算出来的，正则扫不到 —— 见 4-3）：

  | 文件 | 退出码 2 可达？ | 决定行 |
  |---|---|---|
  | `tools/verify_engine_contract.py` | ❌ | `:2388 return 0 if ok == n else 1` |
  | `tools/verify_external.py` | ❌ | `:390 return 0 if ok else 1` |
  | `tools/verify_kb.py` | ❌ | `:646 return 1 if c.failed else 0` |
  | `tools/verify_vocab_lark.py` | ❌ | `:184 return 0 if report["ok"] else 1`（+ `:58`） |
  | `tools/verify_skill.py` | ❌ | `:103/:105` |
  | `tools/lark_find.py` | ❌ | `:48/:55…` |
  | `tools/verify_depad.py` | ✅ | `:162 return 2` |
  | `tools/verify_feishu_index.py` | ✅ | `:66 return 2` |
  | `tools/verify_landing.py` | ✅ | `:64 return 2` |
  | `tools/verify_pending.py` | ✅ | `:483 return 2` |
  | `tools/verify_prd_baseline.py` | ✅ | `:189 return 2` |
  | `tools/verify_shouheng_ops.py` | ✅ | `:73 / :79 return 2` |
  | `base/verify_base.py` | ✅ | `:523 return 2` |
  | `node tools/verify_cards.mjs` | ❌ | 只有 `:558 process.exit(1)` 与隐式 0 |

- **可分性判断（诚实区分）**：
  - **纯本地文件检查没有 2 路径不算缺陷**：`verify_kb.py`、`verify_engine_contract.py`、
    `verify_cards.mjs`、`verify_skill.py` 只读仓内文件，没有真实的「未测」条件；
    文件缺失会 traceback（退出 1 = 红），不是假绿。**不报为缺陷。**
  - **真的有未测条件、却落成「红」的有 3 处**（按 §2.4.2 第 2 条，未测必须与通过与红
    **都**长得不一样）：
    1. `tools/verify_vocab_lark.py:58`
       `raise SystemExit(f"❌ 读 {tid} 失败：{json.dumps(r, …)[:300]}")`
       → `SystemExit(str)` 的退出码是 **1**。**断网/凭据失效时这个检查器报「红」。**
       而它上一次运行是绿的（需要网络），说明网络是通的 —— 但它没有「未测」这一档。
    2. `tools/lark_people.py:126` `raise SystemExit(f"❌ 取 token 失败：…")` → 退出 **1**。
    3. `tools/lark_find.py:48` `raise SystemExit(f"取 token 失败：{r}")` → 退出 **1**。
- **建议动作**：这三处改成 `return 2` + 文案里出现「未测」（照 `verify_prd_baseline.py:189`
  的写法）；这不改变它们今天的绿，只改变它们断网那天说的话。

### 【4-3】`lark_people.py` 把项目的退出码约定**反着用**：2 = 有依据的否定结论，1 = 未测

- **证据**：`tools/lark_people.py:695`
  `WORST = {"found": 0, "candidate": 3, "not_found": 2, "unverifiable": 1, "error": 1}`
  `:726` `print(f"❌ 本应用读得到的通道里都没有 {q}（退出码 2）\n")`
  `:688` 字典不可信时 `return 1`
- **全项目其余地方的约定**：`2 = 未测`（§2.4.2 第 2 条、§2.7；`verify_prd_baseline.py:189`、
  `verify_shouheng_ops.py:73/79`、`verify_pending.py:483`、`prd_baseline.mjs:123`
  「不认识的退出码一律折成 2 = 未测」）。
- **影响（具体）**：`prd_baseline.mjs:123` 的逻辑是
  `const code = [0,1,2].includes(now.code) ? now.code : 2;` 且 `:147 if (code === 2) → 报未测`。
  谁把 `lark_people.py` 接进这条链路，就会把**一个有充分依据的「本应用看不见她」报成
  「这次没测」**；反过来，它的 1（字典不可信 = 真的没测成）会被当成红。
- **建议动作**：`lark_people.py` 的输出码改成项目口径
  （未测 = 2，否定结论 = 0 或一个不复用 2 的码），或在文件显著位置声明这是**局部约定**、
  并给出一条断言禁止把它接进 `prd_baseline` 那套折码逻辑。

### 【4-4】`verify_shouheng_ops.py` 今天退 2 是**正确**行为，记下来以免被当成缺口

- **读数**：退出 **2**，末行 `⚠ 1 项未测 —— 这不是通过（退 2，与 §2.4.2 同口径）`，
  明细行 `⚠ E1  跑不了 ps（PermissionError: …Operation not permitted: 'ps'）→ 进程是否在跑【未测】，
  不等于「没在跑」。下面的 E2/E3 用日志给旁证`。
- **意义**：它证明本项目**会**把未测与绿分开 —— 所以 4-1/4-2 不是「全都不会」，
  是**选择性缺失**：§2.1 那张表里写了「退 2」的检查器做到了，没写的没做到。

### 【4-5】§2.4.2 的修法只落在了一半：判据层做到了，触发者层没有

- **判据层（做到了）**：`tools/verify_prd_baseline.py:187/189/191` 三态分明
  （`return 1, "❌ … 项失败"` / `return 2, "⚠️ 已测 … 全过，但 L3 **未测**…"` /
  `return 0, "✅ … 全过（含 L3：上游与指纹一致）"`）。
- **触发者层（没做到）**：`tools/agent/prd_baseline.mjs` 的 `enter`/`enterPending`
  **没有对应的「结论行不许撒谎」断言**。38 项对照里，关于「不许把没测说成没问题」的
  只有第 6/7/8 项（针对 `enter` 的 `say` 文案），而**没有任何一项**喂
  `{code:1, drifted:[]}`（见 3-2）。
- **影响**：§2.4.2 的原话是「修法不是改那句话，是把结论行拆成纯函数（`verdict(...)`），
  让 `--controls` 能**直接断言这句话本身不许撒谎**」。这句话在
  `verify_prd_baseline.py` 兑现了，在 `prd_baseline.mjs` **只兑现了「说」的那一半，
  没兑现「退 1 但明细空」这一半**。
- **建议动作**：见 3-2。

### 【4-6】★★★ 凭据失效 → 守衡在群里对上游说「**你的 PRD 改版了**」—— 一句说给外人听的假话

> **这是本次审计最严重的一条。** 它不是「未测被报成通过」，是**未测被报成一条对外的事实断言**。

- **链条（四跳，每一跳都有行号，合起来是确定的）**：

  **第 1 跳 · 站在未测上又加了一条失败**
  `tools/verify_prd_baseline.py:306-311`
  ```python
  tok, err = tenant_token()
  if tok is None:
      untested = [d.get("file") for d in docs]          # ← 已经认定「未测」
      add("L3", "C1 取 tenant_access_token", False, err)   # ← 同时又记了一条 FAIL（:310）
  ```
  （`:302-304` 的注释说明这一段的纪律是「失败/跳过 = 未测，不是通过」——
  但它只对 `--offline` 那条分支做到了，**取 token 失败这条分支没做到**。）

  **第 2 跳 · `verdict()` 先看 FAIL，看不见「未测」**
  `tools/verify_prd_baseline.py:186-189`
  ```python
  if n_fail:
      return 1, f"❌ {n_pass + n_fail} 项中 {n_fail} 项失败"     # ← 先命中这一条
  if untested:
      return 2, (f"⚠️  已测 {n_pass} 项全过，但 L3 **未测**…")   # ← 到不了
  ```
  → 退出 **1**，**末行完全不提「未测」**。
  这直接违背该文件自己的 docstring（`:180-185` 整段在讲「未测必须与通过长得不一样」）
  和 `AGENTS.md` §2.1 表格里这句：「**L3 未测时退 2，不是 0**」。

  **第 3 跳 · 触发者把「退 1 但抠不到指纹」补成一个占位漂移**
  `tools/agent/prd_baseline.mjs:281-283`
  ```js
  if (code === 1 && !now.drifted.length) {
    now.drifted = [{ file: '（输出里没抠到具体文件，见 PMO/logs）', old: '', now: '' }];
  }
  ```

  **第 4 跳 · 状态机于是说「上游改版了」**
  `tools/agent/prd_baseline.mjs:127-144`（`code === 1 && drifted.length` → 组 `say`）

- **实测（逐字复刻第 3 跳的逻辑 + 调真 `enter()`；纯内存、不落盘）**：
  ```bash
  node --input-type=module -e "
  import { enter, parseDrift } from './tools/agent/prd_baseline.mjs';
  const out='❌ 17 项中 1 项失败'; const code=1;      // ← 凭据失效时 verify_prd_baseline.py 的真实输出形状
  let drifted = code === 1 ? parseDrift(out) : [];
  if (code === 1 && !drifted.length) drifted = [{ file: '（输出里没抠到具体文件，见 PMO/logs）', old: '', now: '' }];
  console.log(enter({ lastState: 'ok' }, { code, day: '2026-09-22', drifted, untested: [] }).say);"
  ```
  读数 —— **这就是群里会收到的原文**：
  ```
  ⚠️ **上游 PRD 改版了** —— 我手上那份基线已经过期。
  · **（输出里没抠到具体文件，见 PMO/logs）**
    旧指纹 `…` → 新指纹 `…`
  我读到的还是旧版，**而且不会自己察觉**。请给我一分钟重拉一次基线并记新指纹；
  在那之前，凡是引用这份 PRD 的判断都按旧版算。
  ```
- **为什么这是最严重的一条（按 §2.4.2 第 3 条判）**：
  §2.4.2 明写「**对外说过的话优先** —— 因为对方会照着它安排自己的事；
  内部的一句注释烂尾只是烂尾，对外的一句承诺烂尾是**别人按它做了决定**」。
  这一条是同一个方向的更坏版本：**不是承诺烂尾，是对外说了一句假话**。
  上游（李倩怡）会照着这句话去查自己的文档、去解释为什么改版 —— 而文档根本没改，
  改的是我们本机的凭据。而且**指纹那一行是空的**（`old: '', now: ''` 被
  `String(d.old).slice(0,16)` 渲染成 `…`），
  一眼看过去像是「指纹读不到」而不是「我根本没读到上游」。
- **可复现的触发条件**：`~/.dsh/credentials/shouheng-lark.json` 过期／改名／
  飞书把 app secret 轮换掉 —— **任何一次凭据失效都会让群里收到这句话**。
- **建议动作（三处都要改，缺一处这条链还是通的）**：
  1. `verify_prd_baseline.py:310` 改成 `add(...)` 不进 FAIL 表（或 `verdict()` 把
     `n_fail` 与 `untested` 的优先序改成 `if untested and not n_fail_other_than_cred: return 2`）；
     最低成本是给这条 FAIL 项加一个 `kind='untested'` 标记，`verdict()` 分开数。
  2. `prd_baseline.mjs:281-283` 的占位文案不许说「改版了」——
     抠不到指纹时应当说「检查退了 1，但我没读到具体是哪一份 / 哪两个指纹，见 PMO/logs」，
     并且**不许**用「上游改版了」这个标题。
  3. 给 `--selftest` 补一条用例：`{code:1, drifted:[]}` 的 `say` **不许包含「改版」二字**。

### 【4-7】`verify_kb.py:538/541/543` 里的 `_d8` **没有定义** —— 那条分支一走到就 `NameError`

- **证据**：`grep -n "_d8" tools/verify_kb.py` → **只有 538 / 541 / 543 三处引用，零处赋值**。
  ```python
  535:            _gap8 = reg.get("KB-GAP-8")
  536:            c.add("F3", "外部标准库条目引用完整",
  537:                  bool(_d8),                    # ← NameError
  538:                  (f"⏭️ 制品 `外部标准库-v1.json` 未建立，但已在登记表里记为 "
  ...
  543:                  skipped=bool(_d8))
  ```
  （上面的行号按 `sed` 读数；三处 `_d8` 分别是判据、文案条件、`skipped` 标记 ——
  显然是想写 `_gap8`，写成了 `_d8`。）
- **可达性**：这条分支的条件是 `_ext is None`，即
  `research/kb/外部标准库-v1.json` **不存在**（`:530-533`
  `_ext = json.load(...) if os.path.exists(_extp) else None`）。
  而这段代码的注释（`:532-534`）**明说这个分支是故意支持的**：
  「制品不在时**不能直接红到底**…这里的纪律是「红可以变成 SKIP，但前提是这个空缺已经被登记成缺口」」。
- **影响**：制品一旦不存在（或被误删、或在别人的工作树上还没生成），
  这段会抛 `NameError`：`✓` 整段 E/F 组从报告里消失，而报出来的是一个
  与真实原因无关的错。子代理的实测（内存 patch，未动盘）是
  `❌ KB-CHK-1 … 导入 kb_query 失败：name '_d8' is not defined`。
  **今天制品存在，所以没触发** —— 本报告不把它算作已发生的故障，只算作一条**一碰就炸的死代码**。
- **为什么它值得单列**：这正是本项目反复记录的那个形状 ——
  **「写的分支没被执行过」和「写了且正确」在报告上长得一样**（§2.4.1「没红过的断言不算验证过它」）。
- **建议动作**：`_d8` → `_gap8`；并补一条反向对照（临时把 `_extp` 指到不存在的路径，
  断言这条分支给出 SKIP 而不是 traceback）—— 用 `monkeypatch` 在内存里做，别动盘。

### 【4-8】`base/verify_base.py`：`--no-selftests` 跳过整个 A 面，却照打「**各模块自证通过**」并退 0

- **证据（跳过）**：`base/verify_base.py:295-297`
  ```python
  if not run:
      print("  （跳过：--no-selftests）")
      return []
  ```
  由 `:491 faces = [("A 各模块自证", lambda: face_A(not a.no_selftests)), ...]` 驱动。
- **证据（结论行）**：`base/verify_base.py:519-526`
  ```python
  if allbad:
      print("✗ 基座自证未通过：%d 项" % len(allbad)); ...; return 2
  print("✓ 基座自证全绿：各模块自证通过 · L1 自足性通过 · 分级与 .gitignore 一致 · 无未登记产物")
  return 0
  ```
- **实测**：`python3 base/verify_base.py --no-selftests > /tmp/vb.txt 2>&1; rc=$?`
  → **EXIT=0**，末行 `✓ 基座自证全绿：各模块自证通过 · L1 自足性通过 · 分级与 .gitignore 一致 · 无未登记产物`，
  而第 6 行是 `（跳过：--no-selftests）`。
- **影响**：**「跳过了整个 A 面」和「A 面全过」在结论行上长得一模一样**（§2.4.2 第 2 条要治的正是这个）。
  A 面（`base/*.py` 五个模块的自证）恰是 `base/` 这一层的全部证据。
- **附带**：这个文件把**红定为退 2**（`:523 return 2`），与本项目
  「2 = 未测」的约定**恰好相反**（见 4-9）。
- **建议动作**：`face_A` 被跳过时结论行必须显式降级
  （「⚠️ A 面未跑 —— 本次结论不覆盖各模块自证」），且**不许出现「全绿」二字**；
  退出码按「未跑 = 未测」处理。

### 【4-9】退出码 `2` 在本项目里至少有**三种**互相冲突的含义

把本次所有读数并起来看，同一个数字 `2` 指三件不同的事：

| 出处 | `2` 的含义 | `1` 的含义 |
|---|---|---|
| `verify_prd_baseline.py:189`、`verify_shouheng_ops.py:73/79`、`verify_pending.py:483`、`verify_depad.py:162`、`verify_landing.py:64`、`verify_feishu_index.py:66`、`prd_baseline.mjs:123` | **未测**（项目口径） | 红 |
| `base/verify_base.py:523` | **红**（自证未通过） | 不适用（未测不用 1） |
| `tools/lark_people.py:695/726` | **一个有充分依据的否定结论**（查无此人） | **未测**（字典不可信，`:688`） |

- **影响**：`2 ≠ 0` 这条规矩是 §2.4.2 的核心，全项目都按「2 = 未测」写别的逻辑
  （最典型是 `prd_baseline.mjs:121-123`「不认识的退出码一律折成 2 = 未测」）。
  同一个仓里有三个模块用同一个数字表达三件不同的事，
  意味着**任何把这三个模块的输出接进同一套判据的链路都会读反**：
  接 `lark_people` → 「看不见她」被报成「这次没测」；
  接 `verify_base` → 「红」被报成「未测」。
- **建议动作**：定一个全仓退出码表（0 通过 / 1 红 / 2 未测 / 3 拒绝或否定结论），
  写进 `AGENTS.md` §2.1 的表头，并给它一条执行点：
  `verify_shouheng_ops.py` 已经有一个「全仓 AST 扫某类调用」的先例（C1、M1），
  照那个手法加一条「凡 `verify_*.py` / `base/verify_*.py` 顶层 `sys.exit` 常量必须是 {0,1,2}」的扫描。

### 【4-10】`verify_kb.py` 全文没有 2 路径，而它有 SKIP 这一档 —— **SKIP 与 0 混同**

- **证据**：`tools/verify_kb.py:646 return 1 if c.failed else 0` —— 只看 `failed`，
  **不看 `skipped`**。
- **它自己知道 SKIP 不是通过**：报告里会打印
  「⚠️ 无失败，但有 1 项跳过 —— 尚未完整通过」，但**退出码仍是 0**。
- **影响**：这是 4-2 那张表里「纯本地检查没有 2 路径不算缺陷」那个判断的**例外**：
  `verify_kb.py` 有 SKIP 这一档（制品缺失时按 §4-7 那条设计就是要 SKIP 的），
  所以它有真实的「未测」条件，却没有对应的退出码。
  → 「有跳过」在 CI / 守护进程眼里与「全过」无法区分。
- **建议动作**：`return 2 if c.skipped else (1 if c.failed else 0)`，
  并把「跳过不算通过」这句话兑现到退出码上。

### 【4-11】★★ `tools/verify_shouheng_ops.py:181` 会**真的调闸门带 `--yes`** —— 守衡下线时，跑这个自证等于一次真重启

> **这条是安全发现，不只是逻辑债。** `AGENTS.md` §2.1 的表把
> `python3 tools/verify_shouheng_ops.py` 列为「守衡自己还活着吗」的**自证入口**，
> 也就是说**文档要求人去跑它**。

- **证据**：`tools/verify_shouheng_ops.py:181`
  ```python
  rc, out = run_gate("--yes")
  check("A6", rc == 3 and "why" in out, f"--yes 不给理由 → 退出码 {rc}（应 3，重启必须留痕）")
  ```
  它想验的是「`--yes` 没带 `--why` 必须被拒」。而闸门的行为是（`tools/restart_shouheng.sh`）：
  - 守衡**在跑**：`:230-233` 「`--yes` 必须配 `--why`」→ `exit 3` ✅ 断言成立，**安全**。
  - 守衡**没在跑**：`:219-221` 走的是**另一条分支** —— `MODE="rescue"`，
    这一支**不要求 `--why`**，直接落到 `:241 launchctl kickstart -k "$DOMAIN/$LABEL"`。
    → **A6 期望的 3 会变成一次真实的重启**（并且会写账本、把 A3/A4「拒绝时没动进程/没记账」顶红）。
- **本次我做了什么（如实交代）**：我按任务要求跑了这条自证两次。
  **没有发生重启**，可核的两条读数：
  1. A1–A6 全 ✅，其中 **A6 通过**（`rc == 3`）→ 说明闸门走的是「在跑 + 无 `--why`」那条拒绝分支；
  2. 账本 `PMO/logs/restart-ledger.jsonl` 的 **mtime 仍是 `Sep 21 19:34`**，
     末两行是 `2026-09-21T10:04:35Z` 与 `2026-09-21T11:34:05Z`（`pid_after=79861`）——
     **没有新行**。也就是说这次没有产生任何重启记录。
  另外：`pgrep` 的「守衡在不在跑」这个读数本身有个自匹配陷阱 ——
  `pgrep -fl "ws_daemon.mjs"` 会**匹配到我自己的命令行**（因为我的命令里就有这个串），
  必须写成 `pat='ws_dae''mon'; pgrep -fl "$pat"` 才可信。
  这正好是 §2.2 第 5/7 条那个「读数看起来没问题、其实读的是别的东西」的形状。
- **影响**：这条链把「一个只读自证」变成了**在特定状态下有副作用的东西** ——
  而它的危险方向恰好是最需要它的时刻（守衡下线时人才会去跑它）。
  §2.7 的例外（「它没在跑的时候不必问，直接救活」）本身是对的，
  但**这条自证不该是触发者**：它不是「救活」，它只是想验一句拒绝文案。
- **建议动作（粗粒度）**：
  1. A6 换成**不触发副作用**的验法：给闸门加一个 `--dry-run-yes`（或让 `run_gate` 支持注入
     `SHOUHENG_GATE_DRYRUN=1`），断言「`--yes` 无 `--why` 时**报错文案**里含 why 字样，
     且**退出码非 0**」；
  2. 自证开头加一条：若守衡没在跑，**A 段整体落「未测」并跳过 A6**，绝不调带 `--yes` 的闸门；
  3. `AGENTS.md` §2.1 那一行补一句「跑它会调一次闸门（正常情况下只被拒）」，
     让人知道自己在按什么。

---

## 五 · 状态文件与并发

### 【5-1】★ 两份状态文件里，基线那份**至今仍含 `p_*` 键** —— §2.4.3 那个修复没有做完

- **证据（现场读数）**：`cat PMO/shouheng-state/prd-baseline-watch.json`
  ```json
  { "lastRunAt": "...", "lastDay": "2026-09-22", "lastCode": 0, "lastState": "ok", "saidDriftFp": null,
    "p_lastRunAt": "2026-09-21T10:09:35.338Z", "p_lastDay": "2026-09-21", "p_lastCode": 0,
    "p_rawCode": 0, "p_lastState": "ok",
    "saidUntestedDay": "2026-09-22", "lastChatId": "oc_3eadfdb47618327d41f9be9d07786258" }
  ```
  而正确的那份 `cat PMO/shouheng-state/prd-pending-watch.json` 里 `p_lastDay` = `"2026-09-22"`。
  **同一个键在两个文件里取两个不同的值（09-21 / 09-22），其中一个永远是旧快照。**
- **成因（可指认）**：`tools/ws_daemon.mjs:187`
  `if (chatId) saveState({ ...loadState(), lastChatId: chatId });`
  —— `saveState` 的**默认目标就是基线那份**（`prd_baseline.mjs:89` 定义 `STATE_FILE()`、
  `:100` `export function saveState(s, file = STATE_FILE())`）。
  于是「待收」这条链路在写「基线」那份文件，并且靠 `{ ...loadState() }`
  把陈旧的 `p_*` 一路原样带下去。同形调用还有 `ws_daemon.mjs:158`、
  `prd_baseline.mjs:236`（`resolveChat`）。
- **影响**：
  1. 「**每个检查各自一份状态文件**、一个文件同时只有一个写者」这句话对基线那份**不成立**：
     写者有 `prd_baseline.mjs:285`（基线检查）、`:236`（resolveChat）、
     `ws_daemon.mjs:158`（基线 watch 入口）、`:187`（**待收 watch 入口**）四处；
     而单飞锁 `baselineInFlight`（`:257-263`）只护住 `:285` 那一处。
  2. 任何按 `p_*` 找状态的读者，会在两份文件之间取到不同答案（今天无害，因为
     `ws_daemon.mjs:281` 读的是 `loadPendingState()`；但这是一颗定时炸弹）。
- **建议动作**：`ws_daemon.mjs:158/187` 的 `lastChatId` 记账**另起一个小文件**
  （或至少显式传 `STATE_FILE()` 的目标，并让待收那条写自己那份）；
  顺手从 `prd-baseline-watch.json` 里清掉 5 个 `p_*` 键。

### 【5-2】基线状态的写回仍是「读 → 跑子进程（最长 90 秒）→ 整体写回」，窗口内的写会被旧快照抹掉

- **证据**：`tools/agent/prd_baseline.mjs:267` `const prev = loadState();`
  → `:273` `const { code, out, note } = await run({});`（`runChecker` 默认 `timeoutMs = 90_000`，`:176`）
  → `:285` `saveState(state);`，而 `state` 由 `enter(prev, now)` 生成、`prev` 是 90 秒前的快照。
- **窗口内的写者**：`prd_baseline.mjs:236`、`ws_daemon.mjs:158`、`:187`（都写 `lastChatId`）。
  它们不在 `prev` 里 → 被 `:285` 覆盖。
- **严重度（如实标注）**：**比 §2.4.3 那次低** —— 丢的是 `lastChatId`（后果是
  `resolveChat()` 每次回落到 `im.chat.list` 接口），不是 `saidDriftFp` / `saidUntestedDay`
  那类「说了就闭嘴」的去重键。但**形状完全相同**：read → 慢操作 → write。
- **为什么 38 项对照抓不到**：那些用例全是「一次调用纯函数」的形状
  （`enter` / `enterPending` / 注入 `run` 的 `checkNow`/`checkPending`），
  **没有一项跨 `saveState` 的时间窗**。§2.4.3 的原话就是：「那些用例全是一次调用的形状，
  而这是个两次调用之间的时序问题。」
- **建议动作**：`saveState` 改成「只写自己那部分键的合并写」
  （读-改-写压在同一 tick 里，或引入版本号 + 重试），或者给 `lastChatId` 单开文件（与 5-1 同解）。

### 【5-3】`saveState` 非原子，且**写入失败完全静默** —— 与 `flushSeen` 的错误策略相反

- **证据（静默的那一半）**：`tools/agent/prd_baseline.mjs:100-104`
  ```js
  export function saveState(s, file = STATE_FILE()) {
    ensureDir(stateDir());
    try { fs.writeFileSync(file, JSON.stringify(s, null, 2)); }
    catch { /* 状态写不进去不该让守衡崩 —— 顶多下次多说一句 */ }
  }
  ```
  —— 直接覆盖写（**无 temp+rename**），失败不留任何读数、不计数、不告警。
- **证据（会说话的那一半，同一个进程里）**：`tools/agent/agent.mjs:46-65`
  `flushSeen()`：失败 `console.warn` 并 `seenFlushFailed++`，恢复时再报一次，
  且注释明写「重要：失败时不能清 seenDirty」。**同一份守护进程里两种相反的错误策略。**
- **影响链（可推演，如实标注为推演而非实测）**：
  state 写不进去 → `lastRunAt` 永不更新 → `prd_baseline.mjs:268-270` 的
  `COOLDOWN_MS`（`:61` = 30 分钟）**永远按旧值比较** → 群里每来一条含飞书文档链接的消息
  （`ws_daemon.mjs:69` `void baselineWatch('link', chatId)`）就 spawn 一次最长 90 秒的 python；
  同时 `saidDriftFp` 落不了盘 → 同一条漂移告警**反复发**。
  **三处「静默失败」串成一条重试风暴路径，而链路上每一环都没有读数。**
- **建议动作**：`saveState` 加 temp+rename，并把失败升级成与 `flushSeen` 同级的读数
  （首次 warn、恢复再报一次），最低成本是复用 `agent.mjs` 那套计数。

### 【5-4】单飞锁是**进程内变量**，而权威的第二个调用者来自 CLI

- **证据**：`tools/agent/prd_baseline.mjs:257-258` `let baselineInFlight = null; let pendingInFlight = null;`
  `:260-264` `checkNow` / `:390-394` `checkPending` 用它做单飞。
- **缺口**：`tools/agent/prd_baseline.mjs:571`
  `const r = await checkNow({ reason: 'manual', force: true, run: … })` ——
  手动跑 `node tools/agent/prd_baseline.mjs --check` 是**第二个进程**，
  它绕过这两把锁，读同一份状态、90 秒后整体写回，与守护进程互相覆盖。
- **影响**：§2.4.3 的「一个文件同时只能有一个写者」在**同进程内**成立，
  在**跨进程**时不成立；而这条链路的文档（`PMO/守衡-链路打通确认.md` 类）
  正是鼓励人工 `--check` 的。
- **建议动作**：锁落到文件层（`O_EXCL` 建锁 + 陈旧锁超时），或至少在 CLI 侧检测
  「守护进程刚刚写过」并拒绝（不如前者干净）。

---

## 六 · 重复的决策点（§2.5 那一类）

### 【6-1】★ 形态决策不在 §2.5 指定的那一行：`replyTo` 只收结果，真正选型在 `onMessage`

- **规矩**：`AGENTS.md` §2.5「「这条回复是卡片还是纯文本」这个判断**只允许**在
  `tools/ws_daemon.mjs` 的 `replyTo` 里做。」
- **代码**：
  - `tools/ws_daemon.mjs:99`（在 `onMessage` 里）`const shaped = toCardOrText(result.reply);`
  - `tools/ws_daemon.mjs:106` `const sent = await replyTo(chatId, msg.message_id, shaped.text, shaped.card ?? null);`
  - `tools/ws_daemon.mjs:126-138` `replyTo(...)` —— 只按「给没给卡」分支，
    **没有任何选型逻辑**。
  - 而 `ws_daemon.mjs:95-96` 的注释自己写着：「形态决策：模型给的是一段话，这里才决定它变成卡还是文本。
    **决策本身在 `reply-cards/envelope.mjs` 里**」—— 与本文件 §2.5 的说法直接冲突。
- **断言为什么没拦住**：`tools/verify_cards.mjs`
  - `:433` L3 `if (!/toCardOrText\(result\.reply\)/.test(daemon)) no(...)`
    —— 断言的正是「在 daemon 里调用了它」（当前形状），
  - `:436` L3 `if (!/shaped\.card \?\? null/.test(daemon)) no(...)` —— 断言卡片被传进 `replyTo`，
  - `:460-464` L5 只断言 `agent.mjs` 里没有卡片逻辑（`/reply-cards|toCardOrText|\[\[card:/`）。
  **没有任何一条断言在拦「决策点必须是 `replyTo`」。**
- **影响**：§2.5 想要防的是「内核按 A 想、发送层按 B 发」。今天 daemon 内部本身就有两处
  决定形态的地方（`envelope.mjs` 定 `mode`，`replyTo` 定降级链），
  而 `envelope.mjs` 是**内核侧的公共模块**（`persona.mjs:12` 也 import 它）。
  改 envelope 的选型逻辑会同时影响提示词侧和生产侧。
- **建议动作**：把 `toCardOrText(...)` 的调用移进 `replyTo`（`replyTo` 接收原始
  `result.reply`，自己过信封），并把 L3/L5 的断言改成
  「`onMessage` 里不许出现 `toCardOrText`/`shaped.card`」。

### 【6-2】`tools/reply-cards/index.mjs:52-66` 的 `replyCard()` 自带兜底 —— 正是 §2.5 第二条禁止的形状

- **证据**：`tools/reply-cards/index.mjs:60-65`
  ```js
  } catch (e) {
    const d = e?.response?.data;
    return { ...(await sendCard(chatId, kind, data)),
             mode: `reply-card-failed→fallback`,
             error: d ? `reply code=${d.code}` : String(e?.message ?? e) };
  }
  ```
  —— 失败时**新发一条**（`sendCard`），不是同一条引用里的文本。
  而 `tools/agent/feishu.mjs:222-228` 的注释明说这一层存在的理由就是**不**复用它：
  「为什么单独一个函数、不复用 `replyCard`（`reply-cards/index.mjs` 里那个）：
  那个版本失败时自己会去 `sendCard` 兜底…两处兜底叠加的后果是同一个回答在群里出现两次。」
- **实测（今天是零消费者）**：`grep -rn "reply-cards/index.mjs" tools/` → 只有
  `tools/agent/persona.mjs:12`（取 `menuForPrompt, REGISTRY`）；
  `sendCard` 只被 `tools/reply-cards/cli.mjs:132/177` 用。
- **影响**：今天**不会**重复投递（好消息），但库里留着一份「会重复投递」的实现，
  且它与 `feishu.replyCard` 同名同形。§2.5 的规矩是「发送兜底只能有一处」，
  今天实际上有 **3 处**：`index.mjs:39-44`（卡→文本新发）、
  `index.mjs:62`（reply 失败→sendCard 新发）、
  `ws_daemon.mjs:126-138`（卡→replyMarkdown→sendMarkdown）。
- **建议动作**：删掉 `index.mjs` 的 `replyCard`（零消费者），
  或把它改成「只尝试一次、失败如实返回」并加一条与 L2 同形的断言。

### 【6-3】三段截断/搬运各自独立，而且其中一条兜底**绕开了切块**

- **三层（阈值互不知道）**：
  - `tools/agent/truncate.mjs:31` `const DEFAULT_MAX_CHARS = 3000;`（砍 + 加可见标记，`:97-116`）
  - `tools/reply-cards/envelope.mjs:217/235` `VERDICT_MAX=60` / `BOUNDARY_MAX=90`（搬，不砍）
  - `tools/agent/feishu.mjs:140` `const MAX_TEXT_LEN = 8000;`（切块补发，`chunkText`，`:143-153`）
- **真正的重复在这里**：
  - `tools/agent/feishu.mjs:203-204` `replyMarkdown` **自己**做了一次
    「只发第一块 + `sendMarkdown` 补发其余」；
  - 而 `tools/reply-cards/index.mjs:40-43` 的纯文本兜底**完全绕开 `chunkText`**：
    ```js
    const r2 = await client.im.message.create({ ... data: { receive_id: chatId, msg_type: 'text',
      content: JSON.stringify({ text: renderText(card, why) }) } });
    ```
    直接把整段 `renderText(card, why)` 当**一条**消息发。
- **影响**：同一段超长文本，走 `replyMarkdown` 会被切块，走 `sendCard` 的降级分支会因
  单条超限被服务端拒（`chunkText` 的 8000 上限在这条路上不存在）→ 返回 `ok:false`
  → 上层再兜一次。「几个字算超长」这件事今天有三份答案。
- **建议动作**：`index.mjs` 的纯文本兜底改成走 `feishu.sendMarkdown`（它自带切块），
  别自己 `message.create`。

### 【6-4】字段数上限有第二份实现，而且是内联字面量

- **文档**：`tools/reply-cards/contract.md:105`「`fields`（≤4 个）」、
  `:181`「`fields`（≤3 个）」
- **代码**：`tools/reply-cards/envelope.mjs:252`
  `const cap = { 'query-answer': 4, 'receipt': 3, 'data-table': 6 }[kind] ?? 6;`
- **影响**：① 这里的 `4` / `3` **不从 `cards.mjs` 取**（与 `VERDICT_MAX` 那种「唯一执行点」
  完全不同的做法），改 contract 不会改代码、改代码不会改 contract；
  ② `data-table: 6` 与 `?? 6` 的默认值在 `contract.md` 里**找不到对应声明**。
- **建议动作**：把这张 cap 表提到 `cards.mjs` 并像 `VERDICT_MAX` 一样 export，
  或至少在 contract.md 的「上限」表里补上三行。

### 【6-5】`TEXT_FIELDS` 与 `AD_TEXT_FIELDS`：「什么算广告正文」这一决定的两份副本

- `research/governance/skeleton/attribute_misses.py:25` `TEXT_FIELDS = ["Primary Text", "Headline"]`（**零引用**）
- `base/text_stage.py:98` `AD_TEXT_FIELDS = ("Primary Text", "Headline")`（真判据，`:117`）
- **影响**：两份逐字相同的列表；前者是死代码（见 1-2），后者是真判据。
  将来加一个字段（例如 `Description`）只会改一处，而读代码的人看到两处会以为要同步改。
- **建议动作**：删掉 `attribute_misses.py:25`。

---

## 七 · 比输入大的否定结论（§2.4.1 的「这句话比我的输入大吗？」）

### 【7-1】`lark_people.py` 的三通道阳性对照是**真的、而且在否定路径上** —— 记下来以免被再修一次

- **证据**：`tools/lark_people.py:299-345` `verify_resolver(people, stat, anchor, min_people, chat_anchor, owner_anchor)`
  - 通道一（人员字典）：`:308-317` 空字典 / 规模 `<MIN_PEOPLE`（`:72` = 20）/ 锚点（`余玉珊`
    `ou_dd3f9a2e79d23eecaf7c963659d6149a`，`:69`）必须按已知 open_id 命中；
  - 通道二（群成员）：`:319-334` `群通道错误` / `群数 == 0` / `群成员 == 0` 任一即拒绝作证，
    且锚点 `刘华丽`（`:80`）必须命中；
  - 通道三（资源索引 owner）：`:336-345` 同形。
- **它在否定路径上**：`:670` `ok, why = verify_resolver(people, stat)`；
  `:396` `return {"status": "unverifiable", "why": why}     # ★ 不返回 not_found`。
- **反向对照实测**：`python3 tools/lark_people.py --controls` → 退出 **0**、
  `✅ 全部 23 项通过`；其中「通道活着 → 真没有的人仍判 not_found（不许把所有人洗成可送达）」
  与「通道死掉 → 同一个人必须变成 unverifiable，不能是 not_found」正是一对
  （`lark_people.py:604-609`）。
- **结论**：§2.4.1 第 4 行那个事故的修复是**真实有效的**，不是装饰。

### 【7-2】但「通道有几条」是写死的三条，没有恒等式在卡它

- **证据**：`lark_people.py:69`（`ANCHOR`）、`:80`（`CHAT_ANCHOR`）、`:337` 之后的
  `OWNER_ANCHOR` 是三个硬编码常量；`verify_resolver` 的签名（`:299-300`）把这几个锚点
  当参数收，**没有任何地方声明「本应用共有 N 条可达人员的通道」并用
  「分项之和 = 总数」去卡它**。
- **对照本项目已有的模板**：`verify_feishu_index.py` 的 `E1`/`A1`（分档之和 = 候选数）、
  `A3`（成功+失败 = 总数）、`B3b`（两个独立来源必须恒等）—— §2.4.1 第 2 条推荐的正是这个手法。
- **影响**：**新增一条通道不会让任何读数动**。第 4 行那个事故的教训是「一条通道活着，
  不给另一条通道作证」；今天做到了「三条各自作证」，
  但没做到「通道数本身是个被断言的量」—— 也就是说，**漏掉第四条通道仍然不会被发现**。
- **说明（诚实标注）**：这是一条**结构性观察**，不是已发生的事故。
- **建议动作**：把通道清单改成数据（一个列表 + 每条的「活着」判据），
  并加一条恒等式断言：`已作证通道数 == 通道清单长度`，少于即 `unverifiable`。

### 【7-3】BOUNDARY 的权限读数已改成带日期的重测读数、且两个方向分开 —— 也是修好的

- **证据**：`tools/lark_people.py:526-527`
  「★ 关于「`im/v1/chats` → 仅 1 个群 3 人，**不含此人**」那句（旧版 BOUNDARY 里的）：
  那个「不含此人」当时**没有任何代码去查过**，是一句凭空的限定语。」
  以及 `:53`「—— ★ 绝不在这种状态下说「查无此人」。**1 比 2 更坏，不许被 2 盖住。**」
- **结论**：§2.4.1 表格第 4/5 行的两处修复都能在代码里指到，不是文档话术。

### 【7-4】`base/media.py`：附件那句措辞**不在这个文件里**；但它有两处自己的「比输入大」

- **先澄清（避免误报）**：`base/media.py` 处理的是**公开网页上的图**，
  全文 `grep` 飞书/附件/下载/红线 **0 命中**。§2.6 的「策略边界 ≠ 能力边界」措辞在
  `tools/feishu_index.py:1348-1350`、`:1400-1402`、`:1733-1736`（那几处**写对了**，
  见 7-5 末段），**不在这里**。
- **缺陷 A（策略句吞掉了能力缺口）**：
  - `base/media.py:275-277` 对 `vector_format` 给了 `$why`：「**记为「不走 OCR」而不是「取不到」**，两者的分母不同。」
  - `base/media.py:279-281` 对 `unsupported_format` **没有 `$why`**，只有 `reason` 字段；
  - `:430` 把两者合并成一个 `skipped`；
  - `:458-460` 用**一句话**描述两者：
    「跳过的 %d 张（**SVG 矢量等**）单列，不进分母 —— 它们不是「取不到」，是「不走这条路」。」
  → 那个「**等**」把 `unsupported_format` 吞进去了：**一个能力缺口被用策略句描述了**。
  （`grep -rn '"reason"' tools/` → `reason` 只有那两个生产者，**没有任何消费者**。）
- **缺陷 B（冻结的否定结论，没有阳性对照）**：`base/media.py:728-730`
  「**手上一个视频文件都没有。** 实测：全仓 `*.mp4` / `*.mov` / `*.webm` 命中 0 个；92 个落地页的 HTML 里也没有 `<video>` 引用。」
  —— 这是一段**冻结的字符串**，没有任何代码重跑那个 glob；
  而「92 个落地页」这个输入只覆盖**抓取成功的子集**（`:763-766` 有说明但没在这句话旁边重复）。
  自证 `[6]`（`:1032-1038`）只检查字典结构 → **没有任何东西能证明「有视频时它找得到」**。
- **缺陷 C（算了不用的门）**：`:267` docstring 写「**遵守 robots**」，
  但 `:283-285`
  ```python
  rb = F.load_robots(dom, robots_cache, pacer)
  if not rb["obj"].allowed(path):
      pass          # ← 判完了，丢了
  ```
  紧接着 `:286-289` 直接 `F.http_get(url)`。
  **robots 的真执行点在 `tools/lp_fetch.py:270-272`**（`if not rb["obj"].allowed(path): out["tier_raw"]="robots_disallowed"; return out`）。
  → 「遵守 robots」这件事有**两处**，其中 `media.py` 这一处是装饰。
- **建议动作**：A 给 `unsupported_format` 也补 `$why`（并把那句「等」拆成两句）；
  B 把那句话改成带复现命令的读数，或让报告现场重算；C 补上 `continue/return`（或删掉那三行）。

### 【7-5】★ `tools/feishu_index.py`：一个接口失败会被渲染成一句**肯定的事实断言**

- **缺陷 A（通道失败 ≡ 真的不在任何群）**：`tools/feishu_index.py:1276-1283`
  ```python
  if doc["chats"]: ... 
  else:
      A("**0 个。** 守衡当前不在任何群里 —— 这不是「群不存在」，是「它不在里面」。")
  ```
  而 `discover_chats` 在接口报错时返回 `[], [], f"code={...}"`（`:357-358`）。
  `cerr` **被采到了**（`:850`）、**被存了**（`:1047` `"chat_err": cerr`），
  但 `render_md` 里 **`chat_err` 一个读者都没有**
  （`grep -n "chat_err" tools/feishu_index.py` → 只有 `:1047` 那一处写入）。
- **为什么比一般的静默更坏**：这句话不是「我没读到」，是一句**主动加强的断言** ——
  「**这不是「群不存在」，是「它不在里面」**」。接口 5xx 的那一刻，输出与
  「守衡真的不在任何群」**逐字相同**。
- **缺陷 B（0 条外链，可能来自被截断的窗口）**：`:1297`
  `A("**0 条。** 群消息里没有出现外链，核心层正文里也没有。")`
  两个来源（`:864-867` 群消息、`:925-926` 核心层正文）；
  翻页上限 `msg_pages=20`（`:367`），顶到上限这件事**记了**（`:396-397`
  `c_out["truncated"] = not reached_end`、`messages_read`），但**零消费者** ——
  `render_md` 在 `:1280` 用 `doc["messages"]` 重算了一遍。
  → 「0 条」可以从一个**被截断的、且没说自己是截断的**窗口里打出来。
- **缺陷 C（零通道下的绝对否定）**：`:658`
  `return {"ok": False, "err": f"该形态没有对应的只读内容接口：{ty}"}`
  —— 这是 `fetch_extent`（`:647-656`）在枚举完 `bitable/docx/sheet/slides/file/mindnote`
  之后的 **catch-all**：**一次探测都没做**，就断言「该形态没有只读内容接口」。
  （对照：紧邻的 `:657` mindnote 那条**是对的** —— 它把读数写进了文案
  「（`/mindnote/v1` 为 http_404）」。）
- **已修好的部分（模型级，值得抄）**：`:1348-1350`「附件内容 **按红线不取**…
  所以是**不做**，不是读不到」；`:1400-1402`「**无需申请、无需找 owner**：这是策略不是缺口」；
  `:1403`「（试过 4 个路径，全是 http_404 —— **接口不存在，不是权限不足**）」；
  `:1733-1736`「未抽的**不是失败**：附件=按红线不取、幻灯片/思维笔记=接口不存在」。
  这四处**正是 §2.6 要的写法**。
- **没有断言在拦 A/B**：最近的一条是 `tools/verify_feishu_index.py:182`
  `ck("D", "D3 消息的 chat_id 都能对到群清单", msg_ids <= chat_ids, …)`
  —— 两个集合都空时**空集包含恒真**，绿。B1（`:98`）只覆盖「0 张表」那一类，
  E3（`:191`）只管 `readable_untested == 0`。
- **建议动作**：`render_md` 里把 `chat_err/werr/derr` 与 `truncated` 读出来：
  有错误时那句话必须改成「**没读到群清单**（code=…）」，不许写「守衡当前不在任何群里」；
  `:658` 的 catch-all 要么补一次探测、要么把文案降级成「本工具没有为这个形态实现读取」。

### 【7-6】`lark_people.py` 的残留缺口：通道① 没有**基于读数**的自证（一条通道给另一条作证）

- **证据**：`tools/lark_people.py:287`
  ```python
  stat = {"底座": len(APPS), "数据表": tabs_n, "记录": rec_n, "群数": ..., "群成员": ..., ...}
  ```
  —— `"底座": len(APPS)` 是**按构造恒定的 8**（`APPS` 是写死的底座清单），
  **这个读数不可能变成 0**，所以「底座数」这一项永远不可能触发拒绝。
- **`:262-263` 承诺了计数却没有计数**：
  ```python
  if tabs.get("code") != 0:
      continue        # 单个底座不可读不致命，但要计数
  ```
  注释说「要计数」，**一行计数代码都没有**（`grep` 无对应累加）。
- **`verify_resolver` 对①②③不对等**：通道②（`:322-329` + 锚点 `:330-334`）与
  通道③（`:337-344` + `:345-349`）各有**通道专属的统计量 + 专属锚点**；
  而通道①（`:312-317`）**只用合并后字典里的锚点** ——
  也就是说：只要锚点 `余玉珊` 从**群通道或 owner 通道**进来，
  「人员字段那条通道自证活着」就算过了，**哪怕 `数据表=0 / 记录=0`**。
- **为什么这正是 §2.4.1 第 4 行那个形状**：那一行的原话是「**一条通道活着，
  不给另一条通道作证**」。①-⑤ 五个修好的点（`:392-396` 的门、②③ 的专属锚点）
  都是真的；**通道① 这一格没被覆盖**，而 `--controls` 第 :580-581 条
  （「群通道统计整个缺失 → 拒绝作证」）的 fixture **仍然传了 `底座/数据表/记录`** ——
  所以那条对照**只证了②**，正好绕开这个缺口。
- **说明（诚实标注）**：这是一条**结构性缺口**，子代理明确标注「今天没有触发」
  （当前制品读数 `数据表=41 / 记录=5222`，通道① 是活的）。
- **建议动作**：给通道①加一条与②③同形的读数门
  （`数据表 > 0 and 记录 > 0` 才算活着），并把 `--controls` 里那条 fixture
  改成**只缺通道①**的版本（现在那条缺的是②）。

### 【7-7】★★ 已经发出去的**过期绝对否定**：`route_landing_findings.py:121` 每次运行都把它重新写进交付物

- **证据（那句话）**：`tools/route_landing_findings.py:121`
  ```
  "而本应用**没有按姓名找人的能力**（8 条通道逐条实测，见 tools/lark_people.py）。"
  ```
- **证据（它进了交付物，而且是每次运行重新生成的）**：
  `route_landing_findings.py:33-39` 的常量把 `SITES = …/site-owners.csv` 读进来、
  写出 `OUT_JSON = research/landing/整改路由.json`；
  `grep -rln "没有按姓名找人的能力"` → **4 个文件**：
  `tools/route_landing_findings.py`、`research/landing/整改路由.json`（**产物**）、
  `research/governance/skeleton/_data/site-owners.csv`（10 行逐行都有）、
  `research/governance/skeleton/legal-decisions-v1.json`。
- **为什么它现在是错的（这一条是好消息里的坏消息）**：
  那句话的论据是「**唯一能同时拿到 姓名+邮箱+open_id 的通道是人员字段**，
  字典 **35 人**（8 底座 / **5042 条记录**）」。
  而它自己点名的那个文件 `_data/lark-visible-people.csv` 的元信息行（现读数）是：
  ```
  harvested_at=2026-09-21T07:37:05Z, 底座=8, 数据表=41, 记录=5222, 群=1, 群成员=3,
  索引owner=22, 索引已换名=19, 人数=58,
  口径=**3 条通道的并集**：① bitable 人员形状的值 …；② 机器人所在群的成员 …；③ … owner …
  ```
  → **引用的那份文件，逐项都与论据不符**：58 人（不是 35）、41 表（不是 8）、
  5222 条（不是 5042）、**3 条通道**（不是「唯一一条」）。
  也就是说：**它的引用指向了推翻它自己的那份读数**，
  而它那句「8 条通道逐条实测」也与工具现在的三通道口径对不上。
- **没有断言在看它**：`grep -rn "没有按姓名找人的能力" tools/verify_*.py tools/verify_*.mjs`
  → **空**。
- **影响**：按 §2.4.1 的自检句 —— 输入是「我查了我采的那条通道」，
  说出去的是「**本应用没有按姓名找人的能力**」+「8 条通道逐条实测」。
  **这句话比输入大**，而且它已经**写在交付物里、每次运行重新生成**。
  按 §2.4.3 第 3 条「对外说过的话优先」，这一条的优先级高于本报告里大多数纯代码缺陷。
- **建议动作**：把那句改成「**在那 3 条通道的并集（58 人）里都没有她**」这种**带口径与读数**的说法，
  并把日期与读数从 CSV 元信息行现场取（不要手抄）；
  或者干脆只留「按 D23 决定留空，不是待办」这半句 —— 那一半是对的。

---

## 八 · 引擎自身的语义（含**未接线守卫词的真实数字**）

### 【8-1】★★★ 守卫词实测：**声明 85 条，真正能产生降级效果的 46 条，剩 39 条（45.9%）对判定零影响**

- **复现命令**（Python heredoc，不落盘）：
  ```bash
  cd research/governance/skeleton && python3 - <<'PYEOF'
  import json, sys
  from pathlib import Path
  sys.path.insert(0, '.')
  import vocab as V
  G = json.loads(Path('context-guards-v1.json').read_text())
  words = G['words']
  Vv = V.load_vocab()
  all_down = set().union(*Vv.down_bands.values())
  act  = [w for w in words if w.get('status') == 'active']
  un   = [w for w in words if w.get('status') != 'active']
  reach = [w for w in act if w['word'].strip().lower() in all_down]
  print('声明', len(words), '| 装载', len(Vv.guards), '| 可达', len(reach), '| 未接线', len(un))
  PYEOF
  ```
- **逐字读数**：
  ```
  声明 85 | 装载 46 | 可达 46 | 未接线 39
  ```
  与文件自报的 `stats = {"guards": 85, "wired": 46, "not_wired": 39}` **一致**（这一点是好的）。
- **判据（哪一行在排掉那 39 条）**：`research/governance/skeleton/vocab.py:115`
  ```python
  V.guards = [w for w in gd.get("words", []) if w.get("status") == "active"]
  ```
  —— 只有 `status == "active"` 的词才进 `V.guards`，才可能进 `down_bands`（`:137-141`）。
  39 条的 `status` 全是 `pending`（`Counter({'pending': 39})`）。
- **另外两个计数（防止把话说过头）**：
  - 46 条 active 词**全部**落进了某条规则的降级带（**0 条死接线**）——
    即 `band_target` 逐词落点（D9）没有把任何 active 词误送到放行带。
  - 39 条未接线词**全部**带 `wire_gap`（0 条为空），`status_note` 是同一条字符串
    「待法务定性：现网登记了，骨架未收录 —— 删除，或补一条规则」。
    **所以 G5 要求的「逐条给出成因」在数据层是满足的。**
- **影响面（集中在这两条规则）**：39 条未接线词挂在且只挂在 **2 条规则**上——
  | 规则 | 未接线词数 | 该规则是否还有生效守卫 |
  |---|---:|---|
  | `T1.1.medical-cure` | 29 | 是 |
  | `T1.2.medical-prevent` | 10 | 是 |
  （26 条规则里没有任何一条是「只有未接线守卫」的，所以**不是「完全无防护」**，如实标注。）
- **它们会被报出来，但只报不改判**：`judge.py:144`
  `_UNWIRED = [w for w in doc.get("words", []) if w.get("status") != "active"]`
  → `:148-167 near_miss_guards()` → `:649 "unwired_guard_near_miss": near_miss_guards(text, h.rule_key)`
  → `:839-843` 渲染成一行 `⚠ 未接线守卫 'x'（status=…，若接线效果为 …）`。
  **落点（band）与处置（disposition）完全不受影响。**
- **为什么这 39 条不是「不重要」**：`ADR/ADR-0014-未接线守卫词的归属.md` §二 已经查清语义 ——
  旧系统的 `豁免词` 语义是**放行**，所以「未接线」= **从「放行」回归到「满档 `auto_reject`」**，
  而 `ADR-0009 §八` 曾把这句读成「未接线期间它们的降级效果与现网一致（即：不生效）」。
  ADR-0014 原话：「**括号里的那句是错的，而且方向反了。**」
  → **39 个词的未接线是一个已知的回归，今天仍然在**（本节的数字就是它的当前读数）。
- **建议动作**：（粗粒度）① 把「未接线词数」从**说明文字**升级成**门**（见 8-3）；
  ② 这 39 条要么接线、要么从表里删掉 —— 挂着不动是最坏的第三种状态，
  因为它让「语境守卫」这个机制的覆盖率看起来是 100%（表里有 85 条），实际是 54.1%。

### 【8-2】`context-guards-v1.json` 的 G5 声明了「退出码 2」，**没有任何代码实现它，也没有人读那张不变量表**

- **证据（声明）**：`research/governance/skeleton/context-guards-v1.json:28`
  ```
  "G5 wiring      ｜ wired=false 的守卫不计入失败，但必须逐条给出 wire_gap 成因（退出码 2）"
  ```
- **证据（零消费者）**：`grep -rn '"invariants"' tools/ research/governance/skeleton/*.py`
  → 只命中两个**生产者**：`build_context_guards.py:268`、`build_whitelist.py:134`。
  **没有任何读者。**
- **证据（退出码只有 0/1）**：`tools/verify_engine_contract.py:2388`
  `return 0 if ok == n else 1` —— 全文没有 `return 2`（见 4-2）。
- **影响**：这是一条**写在数据文件里的承诺，判据和触发者都不存在**（§2.4.2 的第三个变体，
  只是这次「承诺」写在 JSON 而不是文档里）。
  「未接线守卫 → 退 2」如果真实现了，今天 `verify_engine_contract.py` 就该退 2 ——
  而它退 **0**、报 `验收 176/176  全绿`。
- **建议动作**：要么在 `verify_engine_contract.py` 里实现 G5（未接线数 > 0 且成因不全 → 退 2），
  要么把 G5 那句里的「（退出码 2）」删掉，别留在不变量表里当装饰。

### 【8-3】唯一盯着未接线数量的断言是一道**只许不变大**的天花板，且硬编码的是今天的值

- **证据**：`tools/verify_engine_contract.py:2165-2170`
  ```python
  _N_UNWIRED = 39
  ...
  and len(_unwired) <= _N_UNWIRED,
  ```
- **行为**：数量涨到 40 → 红（好）；数量降到 20 → **仍然绿**
  （`_relax_u`（`:2166`）只在说明文字里提示「本门转红是故意的：请把阈值收紧到当前值再提交」，`:2175-2176`）。
- **缺口**：**没有任何断言要求它降下来**，也没有断言在拦「比值变坏」的另一种方式 ——
  例如把一条 active 词改成 `pending`（未接线 39 → 40 会红，但如果同时删掉另一条
  pending 词，总数不变、比值实际变坏，仍然绿）。
- **建议动作**：把判据从「绝对数 ≤ 39」改成「`active / 总声明数` 不得下降且必须 ≥ 某个口径」，
  或者更直接：把 G5 实现成「39 条必须在 `$decision_queue` 里有 open 的认领，
  且**认领数不许减少**」（`V45d` 今天只做了一半，见 `:2152-2155` 的 `_gap`/`_stale`）。

### 【8-4】ADR-0006「两段式」是真的两段，但四条硬规则里有两条**没有执行点**

- **结论：两段式在代码里是成立的**（这一条是好的）：
  - 第一段 = `score.py:417-420`（`for r in self.rules_for(product_line): ms, how = find_matches(text, r)` / `if not ms: continue`）→ `matcher.py:170-202`
  - 第二段 = `score.py:427 band_hits(...)` + `score.py:447-451`（把落点**改写**到 `h.disposition`）；
    核对（逐字校验）在 `matcher.py:158-163`
  - 结构性证据：带扫描**以第一段产出 ≥1 个 Match 为前提**，第二段只能
    **改写** `disposition`，**不能凭自己造出一个 Hit**。造正对照读数：
    `FDA approved wearable breast pump` → 命中、`band.kind=None`、`auto_reject`；
    `Our pump does not treat any disease` → 同一条规则、`band.kind='downgrade'`、`auto_reject → manual_review`。
- **缺陷（ADR-0006 硬规则 2「核验失败则该候选**作废并转人工**，禁止静默丢弃」没有实现）**：
  - `research/governance/skeleton/matcher.py:165-166`
    ```python
    if not out:
        out.append(Match(kw_for_log, via, "", None, None, reason=why))
    ```
    这个「造不出一条命中流水」的分支**不可达** —— 调用方是 `matcher.py:183`
    `if spans: out.extend(_locate(...))`：只有 `spans` 非空才调 `_locate`，
    而 `_locate` 对每个 span **恰好 append 一个 Match**，所以 `out` 永不为空。
    → 它要报的那句原因（`matcher.py:185`）**永远不会被打印**。
  - 定位失败时实现是 `matcher.py:100-104` **静默跳过**那次出现 —— 候选就这么没了，
    **全仓没有「作废 → 转人工」这条路**。
  - 实测：291 条记录 × 26 条规则 = **442 次命中，442 次定位成功，0 次未定位**
    （子代理 heredoc 读数）。也就是说 `Match.position.located=False`
    （`matcher.py:136-139`）与 **V2b**（`verify_engine_contract.py:143-146`）**从未被触发过**。
  - 硬规则 1（候选不带处置）也没有：候选一出生就带 disposition（`score.py:430
    disposition=r["disposition"]`），没有独立的「候选」对象，只有
    `disposition_declared` 与 `disposition_rewritten` 这一对（`judge.py:622-623`）。
- **断言**：挡「第二段自己造命中」的只有 **V9c**（`verify_engine_contract.py:274-276`，
  用的是 `FDA cleared` = **放行带**那个例子）；**降级带没有对应的反例**。
  另外 `grep -rln "ADR-0006" tools/ research/governance/skeleton/ base/` → **0 个文件**：
  **没有一条断言引用 ADR-0006**。
- **建议动作**：要么把 `matcher.py:100-104` 的静默跳过改成「记一条作废并进 `unknowns`」，
  要么把硬规则 2 从 ADR-0006 里删掉（今天它是 §2.4 意义上的注释）；
  并给降级带补一条与 V9c 对称的反例。

### 【8-5】★★ G5 的「退出码 2」**其实实现了** —— 在 `lint_context_guards.py:169`，而**没有任何东西在跑它**

> 这一条比「没实现」更值得记：**判据和触发者都写好了，只是它们在不同的文件里，而没人把两头接上。**

- **判据（真的存在）**：`research/governance/skeleton/lint_context_guards.py`
  - `:84-88` 计算 G5；`:157-161` 分「结构项」与「政策项 G5」；`:165-170`
    ```python
    structural = [f for f in fails if f != "G5"]
    ...
    if "G5" in fails:
        return 2
    ```
  - `:14` 的 docstring 逐字写着 G5 的语义：「wired=false 的守卫不计入失败，但每条必须给出 wire_gap 成因」。
- **零触发者**：全仓引用它的只有**文档和一句打印**：
  | 位置 | 是什么 |
  |---|---|
  | `research/governance/skeleton/迁移手册-机器词表.md:108` | 「`python3 lint_context_guards.py` # exit 2 = G5 的 39 词接线缺口」 |
  | `research/governance/引擎产品化-接口盘点.md:101` | 接口盘点表里的一行 |
  | `ADR/ADR-0009-语境守卫独立成表.md:149` | 五项不变量机检的执行点登记 |
  | `research/governance/skeleton/migrate_misrouted_guards.py:282` | `print("下一步：python3 lint_whitelist.py && python3 lint_context_guards.py")` |
  **`tools/verify_engine_contract.py` 不调它，`ws_daemon.mjs` 不调它，没有任何 verifier 调它。**
- **合起来的事实**：`context-guards-v1.json:28` 那条 G5 承诺的
  「退出码 2」**有一个真实执行点，但它在一个没人跑的文件里**；
  而唯一被 `AGENTS.md` §2.1 登记为入口的那个检查器
  （`verify_engine_contract.py`）**没有 2 路径**（`:2388`，见 4-2）。
  → 这正是 §2.4.2 那张两层表（**判据 / 触发者**）的教科书案例：
  **两层都有，只是不在同一条链路上。**
- **建议动作**：二选一 ——（a）把 `lint_context_guards.py` 接进
  `verify_engine_contract.py` 或 `verify_shouheng_ops.py`（并在 §2.1 表里登记）；
  （b）把 `context-guards-v1.json:28` 那句里的「（退出码 2）」删掉，
  改成「（机检见 `lint_context_guards.py`，当前未接入任何自证）」。

### 【8-6】`disposition-layers-v1.json:313` 还在说 Q7「未决」，而唯一真相源说它已经答了

- **证据（指针文件）**：`research/governance/skeleton/disposition-layers-v1.json:313`
  ```json
  "$open_question": "legal-decisions-v1.json · $decision_queue · Q7（未决）",
  ```
- **证据（唯一真相源）**：`legal-decisions-v1.json` 的 `$decision_queue` 里 Q7 是
  ```json
  {"id":"Q7","status":"answered","answered_at":"2026-09-16","answered_by":"Owner",
   "record":"legal-decisions-v1.json · D13"}
  ```
  同一个 JSON 块里还写着 `"$decision": "D13 · Owner 2026-09-16（回答 Q7）"` ——
  **同一个文件内部自相矛盾**。
- **没有消费者**：`grep -rn '\$open_question"' --include=*.py tools/ research/` → **空**。
  （对照：另一个键 `$open_questions_for_legal` **有**消费者，被 V30d
  `verify_engine_contract.py:1048-1052` 与 V16b `:483-486` 检查。）
- **影响**：本项目的规矩是「未决/预留事项的唯一书写位置是 `$decision_queue`；
  `disposition-layers-v1.json` **只放指针**」（D12 / V30）。一个**过期的状态词**
  写在指针里，等于在第二个位置又写了一份状态 —— 而 V30d 的判据是**按键名**的
  （它只查 `$open_questions_for_legal` 与 `$decision_queue_ids` 两个键名），
  所以这个键**从判据下面漏过去了**。
- **建议动作**：删掉 `$open_question` 这个键（指针只需指 id，状态去真相源读）；
  或把 V30d 从「按键名」改成「按形状」（子代理实测：全文 0 个 question-shaped 键，
  `options/recommended/default_if_unanswered/status` 一个都没有 —— 这种形状扫描比键名扫描强）。

### 【8-7】ADR-0007 的过滤是「默认true 可选退出」，而只有整仓混淆矩阵**间接**拦得住

- **过滤代码**：`research/governance/skeleton/score.py:221-224`
  ```python
  self.all_rules = [dict(r) for r in rules_doc["rules"] if r.get("enabled", True)]
  self.rules = [r for r in self.all_rules if not r.get("is_modifier")]
  self.modifiers = [... is_modifier]; self.disabled = [... not r.get("enabled", True)]
  ```
- **缺口**：`r.get("enabled", True)` 是**默认启用**。子代理做的内存反向对照
  （`copy.deepcopy(doc)`，**未动盘**）：删掉 `T6.3.reimbursement` 的 `enabled:false` →
  FP 7→29、precision 0.9703→0.8876、catch_all 159→155 → **V13**
  （`verify_engine_contract.py:388-391`，基准在 `:64-65`）变红。
  → **拦得住，但拦它的是整仓混淆矩阵，不是任何一条关于这个字段的断言**
  （`grep -n "停用\|disabled\|enabled" tools/verify_engine_contract.py` → **0 命中**）。
  字段改名/挪位的后果只有「恰好把语料算歪了」才会被发现。
- **附带不一致**：`vocab.py:108-113` 用**全部 26 条规则**（含停用的 T6.3 与
  modifier T9）组装 `V.rules/targets/match/pass_bands/down_bands`，
  **没有应用 `enabled/is_modifier` 过滤**；今天无命中差异（实测：喂 T6.3 的关键词得 0 命中），
  所以是**潜在**不一致，而 `assert_channels` 的 W1/G1/OV* 与 `judge.py:194`
  都是跑在**未过滤**集合上的。
- **ADR-0007 条件 3（`判断方式=自动可检测`）没有执行点**：`evaluability` 只喂
  `confidence`（`judge.py:266-272`）与 ESC-002（`:394-421`），**从不做过滤**。
  今天 21 条 legacy 规则全是「自动可检测」，所以这个条件是**空转**的。
- **建议动作**：把 `enabled` 的语义钉一条断言（例如「每条 `enabled:false` 的规则
  必须能说出停用理由与日期」），或把默认值从 `True` 改成**必须显式声明**
  （缺字段即硬失败）—— 后者更符合本项目「不给默认值就没有隐式行为」的取向。

### 【8-8】「避免第二份实现」这条纪律：主匹配原语收干净了，**另外四份还活着**

- **收干净的那一半（值得记）**：`score.py:92-112` 已全部委托给 `matcher.py`
  （`_cjk`→`:93`、`_is_wordish`→`:97`、`_find_literal`→`:102`、`match_text`→`:107`、
  `find_matches`→`:112`），声明在 `score.py:34`「★ 匹配原语只此一份；本文件不再自己实现」，
  旧副本的去处记在 `matcher.py:7-16` 与 `score.py:659-662`。
- **仍然活着的重复**：
  1. **`judge.py:155` 是第二份子串匹配器**：`near_miss_guards` 里
     `if w["word"].strip().lower() in tl:`（`judge.py:148-163`）——
     **没有词首边界、没有前缀契约**，与 `matcher.py:83-106` 的 `find_literal_all`
     （边界规则在 `:91-95`）**语义不同**。它是 report-only（进不了判定），
     但它可能报出一个 `find_matches` **本来不会命中的**「near miss」。
  2. **W1 有四份实现**：`vocab.py:154-161`（`assert_channels`）、
     `tools/offline_replay.py:119-138`（`assert_disjoint`）、
     `research/governance/skeleton/lint_whitelist.py:151-159`、
     `research/governance/skeleton/lint_context_guards.py:60-63`（G1）。
     四者**不等价**（`vocab.py:156-157` 跳过隔离词、`offline_replay.py:115-116` 只装 active）。
     `matcher.py:23-25` 自己点了其中两份；而 **V14a–V14c**
     （`verify_engine_contract.py:398-432`）**只 AST 检查 `score.py` 与 `judge.py`**
     —— 四份实现一份都没被 V14 覆盖。
  3. **`tools/offline_replay.py:208-213 match()`** 是「什么算命中」的**第三个定义**
     （`any(len(w) >= minlen and w in low ...)`），而 ADR-0006 / ADR-0007 对外发布的
     那几个数（precision 0.9703 等）**正是它算出来的**；
     引擎自己**从不读** observed/现网词表
     （`grep -rn "rules_raw\|observed_vocab" research/governance/skeleton/*.py`
     → 只有 `build_rules.py` 在**写**它）。
  4. **`matcher.py:44 lower_offsets_align()` 零消费者**（`grep -rn "lower_offsets_align" --include=*.py .` → 只有它自己的定义行），
     而**同一条判据被内联了两次**：`matcher.py:84` 与 `matcher.py:177`
     （两处都是 `exact = len(tl) == len(text)`）。
     → 三份同一判据，其中一份是死的。与 §1-2 同类，但这是它自己点名的「第二份实现」纪律的内部违反。
- **建议动作**：① 删 `lower_offsets_align` 或把它真正用起来（两处内联改成调用）；
  ② `judge.py:155` 改成调 `matcher`（哪怕只是 `find_literal_all`）；
  ③ W1 收成一份（其余三处改成 import），并把 V14 的 AST 扫描范围扩到全仓。

### 【8-9】ADR-0009 写的守卫词数是 **89**，实际是 **85** —— 而迁移手册记着 89→85 这件事

- **证据**：`ADR/ADR-0009-语境守卫独立成表.md:106`「共 89 词 = 46 + 39 + 4」、
  `:186`「飞书表 89 词」；而 `context-guards-v1.json` 的实际读数是
  **85 = 46 + 39**（`words` 长度 85，`stats.guards = 85`，`g3_violations = 0`），
  本报告 §8-1 是独立复现的同一个数。
- **迁移记录**：`research/governance/skeleton/迁移手册-机器词表.md:165`
  「白名单 26→30 词、**守卫表 89→85 词**、`lint_context_guards.py` 的 G3 违反 4→0」。
  → 那 4 个 G3 词已迁去白名单，**ADR-0009 没跟上**。
- **影响**：ADR 是决策记录，标题级的数字错 4 个会让读的人以为守卫表还有 4 条待裁定
  （实际上 0 条），并且与「85/46/39」这三个在 `judge.py:283-285` 每次判定都会回读的读数对不上。
  这正是 §2.2 第 1 条「文档里的数字要算出来，不能写进去」。
- **建议动作**：`ADR-0009:106/186` 的 89 改成 85（并注明 4 个 G3 词已迁走、日期），
  或者把这两处改成「见 `context-guards-v1.json` 的 `stats`」。

### 【8-10】附带：`L3` 也从未被使用，而那句话**只说了 L5**

- `judge.py:218-219` 只声明了 L5 未被使用（见 2-5）。
  子代理独立复现：规则库 severity 分布 `{L4:11, L2:13, L1:1, L0:1}`（26 条），
  `escalation` 的唯一目标是 `"to_severity": "L4"`，
  291 条语料跑完的分布是 `{L0:159, L4:95, L2:34, L1:3}` —— **L5 = 0，L3 = 0**。
  `rules-v1.json` 里唯一的字面量 `L3` 出现在一句 `$severity_note` 里（解释为什么选了 L4）。
- **影响**：边界声明里那句「只有 L0/L1/L2/L4」是**对的**（所以不算说错），
  但**同一个缺口（L3 也从未产生）没有被报出来** —— 而 §2.4.1 要求的是
  「读任何数据都要问：如果这个口径是错的，什么会红」。今天 L3 这一格既没有断言、也没有说明。
- **建议动作**：把那句话改成从 `severity.py` 的映射表**现算**未使用的档位
  （`set(SEVERITY_TO_IMPACT) - set(实际出现过的)`），这样 L3 会自动出现在声明里，
  而且加一条 L5 规则时那句话会**自己变对**（不需要人来改文档）。

---

## 九 · 守护进程的错误处理

### 【9-1】`process.exit(0)` 仍在（行为没变），但文档指的行号漂了

- **证据**：`tools/ws_daemon.mjs:248` `async function shutdown(sig) {`
  → `:255` `process.exit(0);`
  → `:257` `process.on('SIGINT',  () => shutdown('Ctrl-C'));`
  → `:258` `process.on('SIGTERM', () => shutdown('SIGTERM'));`
- **文档**：`AGENTS.md:568` 写 `ws_daemon.mjs:229` 捕获（见 2-2，229 行是 `},`）。
- **唯一缓解仍是**：`tools/verify_shouheng_ops.py` 的 C1（全仓不许有人绕过闸门动守护进程）
  与 D1–D7（`KeepAlive.SuccessfulExit` 必须仍是 `false`）+ `tools/restart_shouheng.sh` 闸门。
  **restart 闸门确实是唯一缓解** —— 代码里没有任何别的东西阻止「`kill -TERM` 之后永久静默」。
- **建议动作**：把 `shutdown()` 的退出码改成非 0（例如 143 = 128+15），
  这样 launchd 的 `KeepAlive{SuccessfulExit:false}` 会把它拉起来；
  或者把 `AGENTS.md:568` 的行号校正过来（见 2-2）。

### 【9-2】★ `uncaughtException` / `unhandledRejection` **只记日志、不退出** —— 进程带着未知状态继续对外服务

- **证据**：`tools/ws_daemon.mjs:259-260`
  ```js
  process.on('unhandledRejection', (e) => log('⚠ unhandledRejection:', e?.stack ?? e?.message ?? e));
  process.on('uncaughtException',  (e) => log('⚠ uncaughtException:',  e?.stack ?? e?.message ?? e));
  ```
- **影响**：Node 默认行为是崩（退出码非 0 → launchd 拉起，§2.7 实测「exit 1 → 9 秒内运行 5 次」）。
  这里被吞掉之后：**进程继续活着、继续回话、launchd 永远不会重启它**，
  而「我刚刚处于未定义状态」这件事唯一的痕迹是一行 stdout。
  对比：真正被计数的只有 `counters.failed`（`ws_daemon.mjs:45`），
  而它只在 `:76`（内核异常）、`:108`（发送失败）递增 —— **两条异常钩子都不进计数器**。
  这与 §2.7 那条「`exit 0` → 不拉起」是同一个后果面：**看起来一切正常，实际已经不可信。**
- **建议动作**：给这两条钩子加计数器并升级（连续 N 次 → 走 `safeSend` 在群里自报）；
  或者让 `uncaughtException` 真的退出（交给 launchd 重启），
  这与 §2.7「救活不必问」的例外是一致的。

### 【9-3】消息事件不丢、不静默 —— 这一条是**好的**

- `ws_daemon.mjs:51` `dumpRaw('im.message.receive_v1', data)`（原始事件落盘）、
  `:60-62` 「★ 收到消息 / type / 原文」三行日志、`:64` `--dump-only` 显式分支、
  `:75-79` 内核异常有兜底回复（带错误信息）、`:83-86` `!result.reply` 时**带 reason** 记一行。
- **意义**：§2.7 最怕的「重启窗口吃消息、事后补不回来」在**进程活着**时是有痕迹的
  （`PMO/logs/ws_events.jsonl`）。这一条记下来以免被误报成缺口。

### 【9-4】`card.action.trigger` 只记日志 —— 而「模版假装能交互」这件事的警告被丢掉了

- **证据**：`ws_daemon.mjs:224-229`
  ```js
  'card.action.trigger': async (d) => {
    counters.events++; dumpRaw('card.action.trigger', d);
    log(`★ 卡片交互 ${JSON.stringify(d).slice(0, 400)}`);
    // 卡片交互的回调应答需要返回 toast，这里先只记录；
    // 等真正做出交互卡片的业务场景时再接（不预先写没有调用方的代码）。
  },
  ```
- **问题的另一半**：`cards.mjs:374-376` **已经**把这件事写成一条 warning
  （`W(\`${q}\`, '按钮回调在 ws_daemon 里只记日志、未接住（诚实声明，别让模版假装能交互）')`），
  但 warnings 在生产路径被丢弃（见 1-5）→ **只有开发者在 CLI 里跑 `validate` 才看得见**。
  于是「卡片上有按钮、按钮按下去什么都不发生」这件事，从群里看不出来。
- **状态**：`PMO/守衡-回复卡片模版与语域规程.md` §六 已把「按钮回调 ❌ 未接住」列为未做项，
  所以**这不是隐瞒，是已知未做**；但那条自我警告不在生产路径上。
- **建议动作**：把这条 warning 移到 `envelope` 的 `moved`/日志里（或直接在
  `cards.mjs` 里禁止在无 callbacks 的情况下放按钮）。

### 【9-5】重试风暴路径

- 主路径见 §5-3（`saveState` 静默失败 → 冷却失效 → 每条带文档链接的消息 spawn 一次 90 秒子进程）。
- **独立的一条**：`ws_daemon.mjs:69`
  `if (LARK_DOC_RE.test(preview)) void baselineWatch('link', chatId);`
  —— 抑制完全依赖 `prd_baseline` 内部的 30 分钟冷却（`:61 COOLDOWN_MS`）
  与**状态落盘成功**；daemon 侧没有第二道限流。
- **建议动作**：daemon 侧加一个**只存在内存里**的最小间隔（不需要落盘，重启后失效也无害），
  把「状态盘坏了 → 风暴」这条链断掉。

---

## 附录 · 复现命令

**A · Python 常量引用计数（AST，全仓 659 个 `.py`）**
```bash
cd /Users/lute/Project/audit_multi_content && python3 - <<'PYEOF'
import ast, os, re
from collections import defaultdict
EXCL = {'.git','node_modules','.venv-r4','.pylibs','.tools','.vendor','skills',
        'skills-inventory','dsh-browser-ext','x-recovery','.ua','kb2agent-research'}
files=[]
for dp,dns,fns in os.walk('.'):
    if any(p in EXCL for p in dp.split(os.sep)): dns[:]=[]; continue
    files += [os.path.normpath(os.path.join(dp,f)) for f in fns if f.endswith('.py')]
trees={}; occ=defaultdict(list)
for f in files:
    try: trees[f]=ast.parse(open(f,encoding='utf-8',errors='replace').read())
    except SyntaxError: pass
for f,t in trees.items():
    for n in ast.walk(t):
        if isinstance(n,ast.Name): occ[n.id].append((f,n.lineno))
        elif isinstance(n,ast.Attribute): occ[n.attr].append((f,n.lineno))
        elif isinstance(n,ast.Constant) and isinstance(n.value,str) \
             and re.fullmatch(r'[A-Z][A-Z0-9_]{1,}', n.value or ''): occ[n.value].append((f,n.lineno))
print('scanned', len(trees))
for f,t in trees.items():
    for node in t.body:
        tg = [x.id for x in node.targets if isinstance(x,ast.Name)] if isinstance(node,ast.Assign) \
             else ([node.target.id] if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) else [])
        for name in tg:
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,}', name): continue
            uses=[u for u in occ[name] if not (u[0]==f and node.lineno<=u[1]<=node.end_lineno)]
            if len(uses)<=1: print(f'refs={len(uses)}  {name:24s} {f}:{node.lineno}  {uses[:4]}')
PYEOF
```
（同一手法用在 `.mjs` 上是正则扫 `^(?:export )?(?:const|let|var) [A-Z][A-Z0-9_]* =`；
**注意这个方法抓不到 1-1**，判据见 §1-6 末尾的方法学提醒。）

**B · 退出码 2 可达性**
```bash
for f in tools/verify_*.py base/verify_base.py tools/lark_people.py tools/lark_find.py; do
  printf "%-40s " "$f"
  grep -cE '(sys\.exit|return|process\.exit|SystemExit)\(?\s*2\b' "$f"
done
```

**C · 守卫词 85 / 46 / 39**（见 §8-1 的 heredoc）

**D · 三条行为反证（都不落盘、不改文件）**
```bash
# D1 J1 恒绿：MAX_SECTIONS 零执行点，而 verify_cards 退 0 且 J1 全绿
grep -rn "MAX_SECTIONS" tools/reply-cards/ ; node tools/verify_cards.mjs >/dev/null 2>&1; echo "rc=$?"

# D2 内部记录在纯文本路径上不被拦（判据命中、动作没有）
node --input-type=module -e "
import { toCardOrText, leaksInternalMark } from './tools/reply-cards/envelope.mjs';
const fault='我查了几轮还是没能得出可靠结论。我试过 list_files、list_files、list_files、list_files、list_files，返回 tool_calls=[] call_abc1234567890 finishReason=stop';
const r=toCardOrText(fault);
console.log(r.mode, leaksInternalMark(r.text), r.lint.map(h=>h.id+'x'+h.count).join(','));"

# D3 「退 1 但明细为空」被静默记成绿
node --input-type=module -e "
import { enter, enterPending } from './tools/agent/prd_baseline.mjs';
const D='2026-09-21';
console.log(JSON.stringify(enter({lastState:'ok'}, {code:1, day:D, drifted:[], untested:[]})));
console.log(JSON.stringify(enterPending({p_lastState:'ok'}, {code:1, day:D, overdue:[]})));"

# D4 零网络运行照样报 ✅ 退 0（且「今日抓取」读数与联网时一模一样）
python3 tools/verify_external.py --offline > /tmp/ext.txt 2>&1; echo "rc=$?"; sed -n '23p;34p' /tmp/ext.txt
```

---

## 附注 · 覆盖范围、方法、未完成项与如实交代

### 覆盖范围
- §1–§6、§9 的每一条都是**本次会话直接读代码 + 实跑**得到的，每条都带 `file:line` 与可复现命令。
- §7、§8 里标了「子代理复核」来源的条目（7-5/7-6/7-7、8-4/8-5/8-6/8-7/8-8/8-9/8-10），
  **报告人对每条的关键行都自己复读过一次**（`sed`/`grep` 读数已列在各条里）。
  凡子代理报出而报告人**未能独立复核**的，都在该条里显式标注为「子代理读数」。
- 7-1/7-3 是对**已修复项**的确认（写下来是为了防止被重复「修」一次）；
  7-2/7-6 是结构性缺口，**今天没有触发**。

### 方法（一条必须记住的教训）
**纯「数引用次数」的启发式抓不到 §1-1。** `MAX_SECTIONS` 有 4 处引用，
在引用计数上比一堆真执行点还「安全」，实际是本次唯一一条真常量债。
判据必须是：**这个常量有没有出现在一个能改变行为的表达式里**。
同一课在 §3 里又出现一次：`verify_cards` 的 J1 正是用「名字出现过」当判据。

### 边界与未完成项
- **未执行**（按要求）：`bash tools/restart_shouheng.sh --yes`、`python3 tools/verify_skill.py`。
- **未复现**（如实标注）：`matcher.py:160-163`（「偏移校验失败」）是否**严格**不可达
  —— 需要一个大小写折叠的边角案例（`re.I` 匹配 `ſ`/`s` 而 `.lower()` 不匹配），未复现；
  §5-3 那条重试风暴链是**代码推演**（`saveState` 静默失败 → 冷却失效），**未在运行时制造**。
- **未跑**：`verify_engine_contract.py --only V30`（子代理 3 未运行该脚本，其 V 号结论来自源码复读 + 独立重算）。
- **未判定**：除 `tools/agent/prd_baseline.mjs` 与 `tools/ws_daemon.mjs` 之外的退出码消费方
  （CI、人工脚本）没有人在本次范围内，未作结论。

### 关于本次运行自身的如实交代
1. **我在守衡在跑的时候跑了 `tools/verify_shouheng_ops.py`（两次）**。
   该自证在 `:181` 会调 `run_gate("--yes")`（见 §4-11）。
   **没有发生重启**，两条可核读数：(a) A1–A6 全 ✅，其中 **A6 通过（`rc == 3`）**，
   说明闸门走的是「在跑 + 无 `--why`」那条**拒绝**分支；
   (b) `PMO/logs/restart-ledger.jsonl` 的 mtime 仍是 `Sep 21 19:34`，**没有新增行**。
   **但这条风险是真的**：若当时它没在跑，闸门会走 `MODE="rescue"` 并真的
   `launchctl kickstart -k`（`restart_shouheng.sh:241`）。
2. `python3 tools/verify_external.py --offline` 是**唯一一个被我跑过的、会写盘的入口**
   的离线模式 —— `--offline` 分支（`verify_external.py:267-275`）**不写任何快照文件**，
   而 `os.makedirs(SNAPDIR, exist_ok=True)` 在目录已存在时是空操作（已先核实目录存在）。
   默认（联网）模式会写 `research/kb/_evidence/外部标准库/*.txt`，**我没有跑默认模式**。
3. 其余所有命令都是只读的（`sed`/`grep`/`python3` heredoc 不落盘、
   `node --input-type=module -e` 内存调用纯函数）。
4. 唯一在守衡上产生的**痕迹**：`grep`/`pgrep` 这类读数，以及两次自证运行本身的日志写入
   （日志由 launchd 重定向，属于该进程自身行为，不是我改的文件）。
   **仓库内没有任何源文件被创建、修改或删除**；本文件是本次审计唯一的写入产物。
