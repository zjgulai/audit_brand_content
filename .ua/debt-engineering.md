# 工程债务诊断 · `audit_multi_content`

> 只读审计，未修改 / 删除 / 「修复」任何文件。
> 审计范围：`git ls-files` 的 464 个受版本控制文件（`skills/`、`.venv-r4/`、`.pylibs/`、`.vendor/`、`node_modules/`、`.ua/`、`research/repos/` 按约定不计入）。
> 判据来源：`AGENTS.md`（审计期间被上游改动过一次，改动点见 §7.4）。
> 全部读数为 **2026-09-22 12:1x–12:4x** 的现场读数；凡涉及变化的，都写明是「某时某刻的读数」。

---

## 零、项目自证入口实跑结果（先跑验收，再改 —— AGENTS.md §2.1）

复现方式（**逐条取真实退出码，不经管道**）：

```bash
cd /Users/lute/Project/audit_multi_content
python3 tools/verify_engine_contract.py      >/tmp/last.out 2>&1; echo "RC=$?"; tail -3 /tmp/last.out
# …… 其余九条同理
```

| # | 自证命令 | 实际退出码 | 最终结论行 | 实测 / 未测 |
|---|---|---|---|---|
| 1 | `python3 tools/verify_engine_contract.py` | **0** | `验收 176/176  全绿` | ✅ 实测（7s，全离线） |
| 2 | `python3 tools/verify_kb.py` | **0** | `✅ G1 + G3 全部通过` | ✅ 实测（1s） |
| 3 | `node tools/verify_cards.mjs` | **0** | `通过 232 项 · 不通过 0 项` | ✅ 实测（<1s） |
| 4 | `python3 tools/verify_feishu_index.py` | **0** | `✅ 34 项全过` | ✅ 实测（1s，全离线） |
| 5 | `python3 tools/lark_people.py --controls` | **0** | `✅ 全部 23 项通过` | ✅ 实测（<1s，离线反向对照） |
| 6 | `python3 tools/verify_prd_baseline.py` | **1 → 0** | 首跑 `❌ 23 项中 2 项失败`；**审计中途复跑为 `✅ 23 项全过`** | ✅ 实测（联网，需凭据） |
| 7 | `node tools/agent/prd_baseline.mjs --selftest` | **0** | `✅ 38 项全过（含「该闭嘴时闭嘴」与「该说时必说」两侧）` | ✅ 实测（<1s，离线） |
| 8 | `python3 tools/verify_pending.py` | **0** | `✅ 退 0：结构全过、没有到期未收；最近一个到期日 2026-10-02` | ✅ 实测（<1s） |
| 9 | `python3 tools/verify_depad.py` | **0** | `扫描 6475 个文本文件 · 被填充 0 个` | ✅ 实测（1s） |
| 10 | `python3 tools/verify_shouheng_ops.py` | **2** | `⚠ 1 项未测 —— 这不是通过（退 2，与 §2.4.2 同口径）` | ⚠ **部分未测**（见下） |
| ★ | `python3 base/verify_base.py`（`base/README.md` 的自证入口，AGENTS.md §2.1 表里没列） | **0** | `✓ 基座自证全绿` | ✅ 实测 |

**第 10 条必须说清楚**：它退 2 不是红，是**未测**。真因是 E1 读不到进程：

```
⚠ E1  跑不了 ps（PermissionError: [Errno 1] Operation not permitted: 'ps'）→ 进程是否在跑【未测】
✅ E2  日志里出现过启动横幅 18 次
✅ E3  日志 3 分钟前还在写（心跳每 5 分钟一次 → 没卡死）
```

这正是 `AGENTS.md §2.2` 第 7 条描述的形态，**且修复已生效**（旧版会抛 traceback 打死整个自证）。E2/E3 给了旁证，但**「它现在在不在跑」这个读数本次没有取得**，不许记成通过。

**第 6 条必须说清楚**：首跑是**真红**，不是抖动：

```
❌ [L3] C3 上游 sha256 = 索引指纹 · 美国市场内容治理项目-一页纸计划书.md
        索引 d78fdef6d7f2b61e… / 现场 8211abc09a731dc1…
❌ [L3] C4 上游字数 = chars · 美国市场内容治理项目-一页纸计划书.md   索引 2831 / 现场 2932
```

审计进行中，`PRD/feishu/` 被上游（本会话的父代理）按 `AGENTS.md §2.1` 新增的「落盘配方」重拉并 depad，复跑转绿。**这条自证的判据本身是活的、会红的** —— 这是本次审计里唯一一条在审计窗口内真的变过色的判据。

未跑：`python3 tools/verify_skill.py`（按指示不跑；它会把规程里每条 bash 真跑一遍）。它存在，见 §E-7.6——**它的验证对象不在版本控制里**。

---

## 一、重复 / 近似重复

### 复现命令

```bash
# 函数级重复：同名函数跨文件的体相似度
python3 - <<'PY'   # 完整脚本见 §1.1 说明
# 对 114 个受控 .py 做 AST 取函数体 → 按函数名分组 → difflib.SequenceMatcher 比体
PY
# 行级重复：6 行归一化窗口哈希
# 规模
git ls-files 'tools/*.py' | xargs wc -l | tail -1     # 19183  total
git ls-files | grep -E 'verify_[^/]*\.(py|mjs)$' | xargs wc -l | tail -1   # 7331 total
```

### 规模基线（实测）

| 族 | 文件数 | 总行数 |
|---|---|---|
| `tools/*.py` | 50 | 19,183 |
| `verify_*`（py+mjs 全域） | 12 | 7,331 |
| `kb_*.py` | 11 | 3,152 |
| `lp_*.py` | **5**（不是 6） | 2,274 |
| `tools/agent/*.mjs` | 8 | 2,445 |
| `tools/reply-cards/*.mjs` | 5 | 1,576 |
| `research/governance/_scratch/**` | 19 | 1,056 |
| 全仓 `.py`（已排除 `skills-inventory/`） | 114 | 约 36,000 |

> 口径更正：`lp_*.py` 是 **5** 个（`lp_consistency / lp_extract / lp_fetch / lp_metrics / lp_stability`），不是 6；`kb_*.py` 是 **11** 个，不是 12。复现：`git ls-files 'tools/lp_*.py' | wc -l` → `5`。

---

### 【E-1.1】全仓只有 **60** 条内部 `.py → .py` import 边；工具链基本是「一堆互不认识的独立脚本」

**证据**

```bash
# AST 扫 118 个 .py 的 import，只保留目标也是本仓 .py 的边
python3 /tmp/debtaudit/edges.py | head -1
# → === internal .py->.py import edges: 60 ===
```

`tools/` 里 50 个 Python 文件，互相 import 的只有 7 对：
`kb_analyze→load`、`kb_build→load`、`kb_classes→load`、`kb_evidence→load`、`kb_facts→load`、`kb_gaps→load`、`kb_index→load`、`kb_query→load`、`kb_materials_lark→kb_classes`、`kb_facts→kb_materials_lark`、`kb_gaps→kb_facts`、`live_snapshot→lark_find`、`lp_consistency→lp_extract`、`lp_stability→lp_extract`、`lp_stability→lp_fetch`。

`.ua/knowledge-graph.json` 独立佐证同一结论（它的 `imports` 边更少）：

```bash
python3 -c "
import json;d=json.load(open('.ua/knowledge-graph.json'))
print(sum(1 for e in d['edges'] if e['type']=='imports'))"
# → 57
```

**影响**：没有共享的 HTTP 客户端层、没有共享的 JSON 读写层、没有共享的 `main()` 骨架 —— 所以下面 E-1.2 / E-1.3 的复制粘贴不是偶然，是**结构性缺一层**。

**建议动作（粗粒度）**：在 `tools/` 下立一个被 import 的公共模块（飞书 HTTP + 凭据 + JSON 读写 + `main()` 骨架三件事），先只搬已证同形的部分，不为「统一风格」动逻辑。

---

### 【E-1.2】`call()` 在 4 个文件里**逐字节同形**，但超时与错误体上限**互相不一致**（60/60/30/25 · 400/400/400/500）

**证据** —— 四个文件的同一函数，行号可点：

| 文件:行 | `timeout=` | HTTP 错误体截断 |
|---|---|---|
| `tools/kb_materials_lark.py:49` | `timeout=60` | `[:400]` |
| `tools/migrate_kb_to_lark.py:45` | `timeout=60` | `[:400]` |
| `tools/migrate_vocab_to_lark.py:42` | `timeout=30` | `[:400]` |
| `tools/migrate_whitelist_to_lark.py:41` | `timeout=25` | `[:500]` |

复现：

```bash
cd /Users/lute/Project/audit_multi_content
for f in tools/kb_materials_lark.py:49 tools/migrate_kb_to_lark.py:45 \
         tools/migrate_vocab_to_lark.py:42 tools/migrate_whitelist_to_lark.py:41; do
  p=${f%:*}; l=${f#*:}
  echo "--- $p:$l"; sed -n "${l},$((l+13))p" "$p" | grep -E "timeout=|decode\(\)\[:"
done
```

函数名级读数：`n_files=6, sim=1.00`（其中 `tools/shouheng.py:81` 是**同名不同物**的类方法，`tools/verify_vocab_lark.py:31` 是 `call(url, token)` 两参数变体，两者不计入这一族）。

**影响**：这不是「不好看」。同一个飞书接口，从一个脚本调 60 秒超时、从另一个调 25 秒超时 —— **在慢网络上，同一个接口在 A 脚本成功、在 B 脚本失败**，而失败会被压成 `{"_err": ...}`（见 §6）。四个副本的每一个都是「改一处漏三处」的定点。

**建议动作**：抽一个飞书 HTTP 客户端，超时与错误体上限**作为显式参数**（各自调用点自己声明，不藏在函数默认值里）。

---

### 【E-1.3】`def main()` 出现在 **89 个文件**里，累计 9,903 行

**证据**

```bash
# 同名函数跨文件统计（AST + difflib），摘录：
#   n_files=89 total_lines= 9903 sim=0.35  def main()
#   n_files=11 total_lines=  167 sim=1.00  def check()      ← base/*.py 六份 + 5 处
#   n_files= 9 total_lines=   72 sim=0.21  def token()
#   n_files= 7 total_lines= 1004 sim=0.14  def selftest()   ← base/*.py 六份
#   n_files= 5 total_lines=   70 sim=0.42  def split_md_row()
#   n_files= 3 total_lines=   27 sim=1.00  def percentiles()
#   n_files= 3 total_lines=   21 sim=0.99  def get_token()
#   n_files= 3 total_lines=   54 sim=0.91  def ensure_table()
#   n_files= 4 total_lines=   64 sim=0.73  def _req()
#   n_files= 2 total_lines=   29 sim=1.00  def match()
#   n_files= 2 total_lines=   10 sim=1.00  def load_snapshot()
#   n_files= 2 total_lines=   20 sim=1.00  def grab()
#   n_files= 2 total_lines=   33 sim=0.97  def link_of()
#   n_files= 2 total_lines=   17 sim=0.83  def get()
```

逐条可点的 100% 相同副本：

- `def percentiles()` **sim=1.00**，三份：`base/media.py:404`、`base/text_stage.py:80`、`tools/lp_metrics.py:48`（3×9=27 行，两份纯冗余）
- `def match()` **sim=1.00**：`tools/heldout_test.py:91`、`tools/offline_replay.py:208`
- `def load_snapshot()` **sim=1.00**：`tools/heldout_test.py:47`、`tools/offline_replay.py:54`
- `def grab()` **sim=1.00**：`research/governance/audit_make_errorbook.py:60`、`research/governance/audit_rule_consistency.py:35`
- `def get_token()` **sim=0.99**：`tools/migrate_kb_to_lark.py:60`、`tools/migrate_vocab_to_lark.py:57`、`tools/migrate_whitelist_to_lark.py:56`
- `def ensure_table()` **sim=0.91**：`tools/kb_materials_lark.py:96`、`tools/migrate_kb_to_lark.py:182`、`tools/migrate_vocab_to_lark.py:151`
- `def check()` **sim=1.00，11 处**（`base/*.py` 六份：`change_detect.py:215` `contract.py:744` `judge_adapter.py:285` `media.py:944` `sync_rules.py:532` `text_stage.py:407`；另 `feishu_index.py:1644` `verify_engine_contract.py:43` `lp_stability.py:707` `engine_manifest.py:315` `audit_migration_fidelity.py:563`）
- `def selftest()` **7 份 / 1,004 行**：`base/change_detect.py:210` `contract.py:739` `judge_adapter.py:282` `media.py:941` `sync_rules.py:529` `text_stage.py:404` `lp_stability.py:698`

至少 9 个函数在 ≥2 个文件里**完全相同**（sim ≥ 0.99），合计 **约 250 行**是纯副本，没有任何共享模块。

**影响**：`percentiles()` 这种统计口径三份独立实现，任一份被改就产生「同一个指标两个口径」—— 本项目已为此出过三次事（`base/README.md` 自述「口径全仓有四个」）。

**建议动作**：把 sim ≥ 0.99 且语义单一的函数（`percentiles` / `match` / `load_snapshot` / `get_token` / `ensure_table` / `link_of` / `grab`）抽到一个共享模块，抽完在原位置保留同名 re-export，行为零变化。

---

### 【E-1.4】`probe_cards2.mjs` 有 19/91 行与 `probe_cards.mjs` 重复，且**共享硬编码群 ID**

**证据**

```bash
# 5 行归一化窗口哈希，跨文件出现的窗口数：
#   19  tools/probe_cards.mjs   (247 代码行)
#    6  tools/probe_cards2.mjs  (91 代码行)   ← 91 行里有 6 个 5 行块是抄来的
python3 /tmp/debtaudit/mjsdup2.py
```

重复块之一是整段头部：

```js
import fs from 'node:fs';
import path from 'node:path';
import { client } from './agent/feishu.mjs';
import { LOG_DIR, ensureDir } from './agent/config.mjs';
const CHAT_ID = process.env.PROBE_CHAT_ID || 'oc_49a7cfb2861cffa4365ca8491f398d32';
```

同一行群 ID 还出现在 `tools/probe_cards.mjs:27`、`tools/probe_cards2.mjs:20`、`tools/reply-cards/cli.mjs:31`、`tools/send_once.mjs:8`、`tools/test_agent.mjs:522` 与 `:636`（6 处，见 §5）。

**影响**：探针脚本是「往真群里发真消息」的东西。两份副本 + 6 处硬编码群 ID = 换群 / 换环境时要改 8 处，漏一处就把探针卡发到错误的群。

**建议动作**：`probe_cards2.mjs` 的独有部分（第二路候选写法）合并进 `probe_cards.mjs` 的 `--only=` 分派里；群 ID 收敛到 `tools/agent/config.mjs`。

---

### 【E-1.5】`.tools/cdp.mjs` 与 `.tools/cdp2.mjs` 共享 CDP 脚手架代码

**证据**：5 行重复窗口 3 处，最长一段：

```js
let target = list.find(t => t.type === 'page');
if (!target) { console.error('no page target'); process.exit(1); }
const ws = new WebSocket(target.webSocketDebuggerUrl);
let id = 0; const pending = new Map();
const send = (method, params={}) => new Promise((res, rej) => { const i = ++id; pending.set(i,{res,rej}); ws.send(JSON.stringify({id:i,method,params})); });
```

`tools/.tools/cdp.mjs` 39 行 / `cdp2.mjs` 30 行，`.tools/cdpeval.mjs` 13 行 —— 三个文件合计 82 行。

**影响**：低（调试工具，非运行时路径）。但它是「复制粘贴是默认工作方式」的又一个读数。

**建议动作**：低优先级；可合并为一个带 `--eval` 开关的文件。

---

### 【E-1.6】重复度是**被稀释过的假低**——按「块」量只有 1–3%，按「函数」量有 9 个完全同形的函数

**证据**：两种口径给出的读数**相差一个数量级**：

| 口径 | 读数 |
|---|---|
| 6 行归一化窗口的克隆行数 / 族总行数 | `kb_*` 84/2809 = **0.03**；`verify_*` 48/3869 = **0.01**；`lp_*` 24/2885 = **0.01** |
| 同名函数的体相似度 ≥0.99 的跨文件重复 | **9 个函数族，约 250 行纯副本** |

原因：`main()` 这种「同形但内容不同」的骨架占了大头，把行级 Jaccard 稀释到 0.2 以下（`J>=0.5` 的配对数是 **0**）。

**影响**：**只看「多少行是复制的」会得出「这个仓库几乎没有重复」的错误结论。** 真实债务在函数粒度：**同一个语义有两到三份独立实现**，而它们不共享任何东西。

**建议动作**：把「同形函数副本数」而不是「重复行占比」作为长期指标（现有 `.ua/duplication-check.cjs` 可扩展成常驻检查）。

---

## 二、孤儿 / 死脚本

### 复现命令

```bash
# 对每个 tools/ 下文件，统计「其它受控文件里是否出现过它的文件名」
python3 /tmp/debtaudit/orphan.py
# 并把它拆成「可执行引用」与「纯文档引用」两类
python3 /tmp/debtaudit/orphan2.py
```

### 【E-2.1】**确认并复现**：`tools/` 下 9 个文件被**任何**受控文件引用 **0 次**（连文档都没提）

**证据**（`exe=0 doc=0`，即零引用）：

| 文件 | 行数 | 是什么 |
|---|---|---|
| `tools/_ingest_batch10.py` | 457 | 一次性入库脚本（Q27–Q34 → D29–D36） |
| `tools/build_product_line_matrix.py` | 130 | 生成「品线确认表」CSV |
| `tools/probe_cards.mjs` | 286 | 飞书卡片能力探针 |
| `tools/probe_cards2.mjs` | 111 | 第二路探针 |
| `tools/probe_models.mjs` | 22 | DeepSeek 模型清单探测 |
| `tools/probe_tools.mjs` | 30 | function-calling 探测 |
| `tools/ws_handshake.mjs` | 40 | WebSocket 握手验证 |
| `tools/ws_raw_trace.mjs` | 134 | 长连接原始帧取证 |
| `tools/ws_watch.sh` | 54 | 实时盯日志 |

**关键的区分（不能一刀切）**：

- **`probe_models.mjs` / `probe_tools.mjs` / `ws_handshake.mjs` / `ws_raw_trace.mjs`** 是**诊断取证工具**：报告写完了、故障修了，工具留着。它们是**该留的**（下次同类故障直接用），但**当前没有任何东西在跑它们，也没有任何文档指向它们** —— 属于「留了但找不回来」。`ws_watch.sh` 的头注释自己写着用法，是好的一类，但一样零引用。
- **`probe_cards.mjs` / `probe_cards2.mjs`** 是**已被 `tools/reply-cards/contract.md` 取代的一次性探针**：`contract.md` 的自述是「实测出来的（`PMO/logs/card_probe.jsonl`）」。探针的**结论已固化成文档 + 登记表**，探针本体仍有复查价值（卡片 schema 会变），但 `card_probe.jsonl` 落在 `PMO/logs/`（`.gitignore:64` 忽略）—— **产物不入库，工具入库**。
- **`_ingest_batch10.py`** 是**已执行完的一次性迁移**（见 §3）。
- **`build_product_line_matrix.py`** 最可疑：它的 docstring 写着产物是「交给产品填」的 CSV，而 `research/governance/品线确认表.csv` **确实在库里** —— 说明它跑过。但它既无引用也无文档，改动 `product_lines` 时不会有人想起它。

**影响**：`build_product_line_matrix.py` 的现实风险最大 —— `product_lines` 是**收窄动作**，脚本自己的注释写着「写错一个值会让规则在所有品线上静默消失（漏报）」，而**这个脚本没有任何自证、也不在 `verify_engine_contract.py` 的覆盖里**。

**建议动作**：不要删诊断类探针（它们的价值就在故障时）；给 `tools/` 建一个「工具索引」文档（一行一个：什么时候用它、产物落哪），并把「零引用」做成常驻检查，**新出现的零引用要红，已在册的白名单放行**。

---

### 【E-2.2】另有 **9 个文件只有文档引用、没有任何代码路径会调它**

`exe=0, doc≥1`，按 doc 引用数排序（节选）：

| 文件 | doc 引用 | 引用长什么样 |
|---|---|---|
| `tools/_recon_legacy.py` | 9 | 只见于治理文档散文 |
| `tools/_migrate_ids_batch12.py` | 6 | `tools/_recon_legacy.py:20` 的 docstring 点名 |
| `tools/measure_cross_line_homographs.py` | 5 | 治理文档散文 |
| `tools/route_landing_findings.py` | 7 | 治理文档散文 |
| `tools/lark_probe.py` | 5 | 治理文档散文 |
| `tools/ws_test.mjs` | 3 | `PMO/守衡-飞书打通测试报告.md:258,277,294` |
| `tools/send_once.mjs` | 1 | `PMO/守衡-架构说明.md:22` |
| `tools/check_contact_scope.py` | 3 | `PMO/上游对接人表.md:172` 等 |
| `tools/kb_materials_data.py` | 3 | `tools/kb_classes.py:25`、`tools/kb_materials_lark.py:81`（docstring 里点名） |

**注意反例**：`tools/run_shouheng.sh` 在我的脚本里也落进「doc-only」，但**它是活的** —— 被 `tools/com.shouheng.lark.plist:16` 用绝对路径调用（我的分类器没认出 `<string>` 里的路径）。这说明「引用计数」这类扫描必须配人工复核，**不能直接当删除依据**。

**建议动作**：`send_once.mjs`（11 行）与 `ws_test.mjs` 属于「事故现场留证」，标注为**只读存档**；`kb_materials_data.py` 是**被依赖的数据模块**（`kb_classes.py:25` / `kb_materials_lark.py:81` docstring 里点名它是数据源），应把它从「疑似孤儿」名单里划掉并补上正式 import 关系。

---

### 【E-2.3】`tools/reply-cards/index.mjs:52` 的 `replyCard()` 是**没有任何调用者的第二套发送兜底** —— 正是 §2.5 要禁的那件事，只是它恰好没被用

**证据**

```bash
git grep -n "replyCard" -- . | grep -v verify_cards.mjs
# AGENTS.md:494                       ← 文档说「兜底只能有一处」
# tools/agent/feishu.mjs:222,229     ← 正确的那一个（只尝试一次）
# tools/reply-cards/index.mjs:52      ← 第二个（失败时自己 sendCard 兜底）
# tools/ws_daemon.mjs:128             ← 唯一的真实调用点，用的是上面那个

git grep -n "import.*reply-cards" -- '*.mjs' '*.js'
# tools/agent/persona.mjs:12: import { menuForPrompt, REGISTRY } from '../reply-cards/index.mjs';
# tools/ws_daemon.mjs:26,27:  from './reply-cards/envelope.mjs' / './reply-cards/registry.mjs'
# → index.mjs 的 replyCard 零消费者
```

`tools/reply-cards/index.mjs:52-73` 的实现：

```js
export async function replyCard(messageId, chatId, kind, data) {
  ...
  } catch (e) {
    return { ...(await sendCard(chatId, kind, data)), mode: `reply-card-failed→fallback`, ... };
  }
}
```

**影响**：`AGENTS.md §2.5`（「发送兜底只能有一处…两处叠加 = 同一个回答在群里出现两次」）由 `tools/verify_cards.mjs:432-444` 的 **L1/L2** 守着，而 L2 只检查 `agent/feishu.mjs` 的 `replyCard` 体里没有兜底调用 —— **它检查不到「另有一个同名导出函数在做兜底」**。今天它没被调用，所以不出事；**任何一次「复用它试试」的改动都会命中 §2.5 描述的重复投递**，而 L2 不会红。

**建议动作**：把 `reply-cards/index.mjs` 的 `replyCard` 改名成不被误用的名字（或在 L2 加一条「全仓 `replyCard` 只能有一处做尝试性发送」的断言）。

---

### 【E-2.4】知识图谱把 **8 个受控文件**完全漏掉

**证据**

```bash
python3 -c "
import json,subprocess
d=json.load(open('.ua/knowledge-graph.json'))
g={n['filePath'] for n in d['nodes'] if n.get('filePath')}
t=[f for f in subprocess.check_output(['git','ls-files'],text=True).split() if f not in g and not f.startswith('skills-inventory')]
print(len(t)); [print(' ',x) for x in sorted(t)]"
```

漏掉的 8 个：`dsh-browser-ext/assets/icons/{deepseek-256.png,deepseek.ico,icon16,icon32,icon48,icon128}`、`dsh-browser-ext/panel/assets/deepseek-256.png`、`tools/package-lock.json`。

**影响**：前 7 个是二进制图标（可理解）；**`tools/package-lock.json` 被漏是实质缺口** —— 它是整个 Node 侧唯一的可复现依据（见 §4），却没进图谱。

**建议动作**：图谱生成时把锁文件 / 清单文件明列为「必须入图」的文件类型。

---

## 三、入库的一次性脚本

### 复现命令

```bash
cd /Users/lute/Project/audit_multi_content
git ls-files 'tools/_*.py' | xargs ls -l | awk '{s+=$5; print $5, $9} END {print "TOTAL", s}'
git ls-files 'research/governance/_scratch/*' | xargs wc -l | sort -rn
du -sh research/governance/_scratch research/governance/annotations research/distill/scratch
```

### 【E-3.1】7 个 `tools/_*.py` 共 **114,034 字节**入库；其中 `_ingest_batch10.py` 单个 40,912 字节（最大）

**证据**

```
40912  tools/_ingest_batch10.py
16867  tools/_recon_legacy.py
16069  tools/_ingest_batch12.py
14313  tools/_migrate_ids_batch11.py
13193  tools/_migrate_ids_batch12.py
 8577  tools/_rc_d38.py
 4103  tools/_rc_d37.py
TOTAL  114034
```

**影响**：这 114 KB 是**一次性的**，但它们不是「死重」——`_rc_d37.py` / `_rc_d38.py` 是**反向对照脚本**，`AGENTS.md §2.4.1` 的原则是「一个新断言如果不能在某次真实事故里变红过，就不算验证过它」。这两个脚本正是**让断言红过**的证据生成器。删掉它们 = 删掉「这条断言验证过」的可复现依据。

**建议动作**：分类处置 —— `_ingest_*` / `_migrate_*` 归入只读存档（加「已执行，勿重跑」标记）；`_rc_*` **保留并升格**（它们做的是验收工作，不是迁移）。

---

### 【E-3.2】`_ingest_batch10.py` 与 `_ingest_batch12.py` 是**已执行完毕的历史动作**，不是可重跑工具

**证据**（docstring 自述）

- `tools/_ingest_batch10.py:5`：`用途：一次性的入库脚本。Q27–Q34 由 Owner 于 2026-09-17 逐条裁定（讨论稿 §九）`
- `tools/_ingest_batch10.py:9-11`：`· 8 条决定 D29–D36` / `· 8 条已答的题 Q27–Q34` / `· 1 条**新提出的未决项 Q35**`
- `tools/_ingest_batch12.py:4`：`_ingest_batch12.py —— 第十二批入库：Q36 裁定 → D38`
- `tools/_ingest_batch12.py:8`：`ADR-0013 的局部决策编号已由 tools/_migrate_ids_batch12.py 就地加 ADR13- 前缀（58 处 / 18 个号）`

**它们是不是地雷**：是。**重跑 `_ingest_batch10.py` 会把 D29–D36 / Q27–Q35 再写一遍**到 `research/governance/skeleton/legal-decisions-v1.json`（207 KB 的受控制品）。判据：这两个脚本里**没有幂等断言**（无「已存在则跳过」的读音），也没有写盘前 sha256 前置校验。

对比 —— **`_migrate_ids_batch12.py` 就是反例**，它做对了：

```
tools/_migrate_ids_batch11.py:27  python3 tools/_migrate_ids_batch11.py          # 只打印将改什么（不改盘）
tools/_migrate_ids_batch11.py:28  python3 tools/_migrate_ids_batch11.py --write  # 落盘
```

**默认不改盘、`--write` 才落盘** —— 这个模式应该成为所有一次性脚本的硬要求。

**影响**：一个误触 `python3 tools/_ingest_batch10.py` 的 agent 会静默改掉唯一台账。而台账的守卫（`verify_engine_contract.py` 的 V46b/V46e）比的是**结构与同代性**，重写同内容的重复条目**不一定红**。

**建议动作**：给 `_ingest_batch10.py` / `_ingest_batch12.py` 加 `--write` 门（照 `_migrate_ids_batch11.py:27-28` 的样子），或把它们移出可执行路径改名成 `*.py.archive`。

---

### 【E-3.3】`_rc_d37.py` / `_rc_d38.py` **会往真文件注入缺陷**，依赖「注入 → 跑判据 → 逐字节还原」的自律，且全族无 depad

**证据**

```
tools/_rc_d37.py:2   """_rc_d37.py —— D37 的反向对照：往**真文件**里注入缺陷，证明判据真的会红。
tools/_rc_d37.py:4-5  记 sha256 → 注入 → 跑真判据 → 断言它以**预期的那句话**报红 → 逐字节还原 → 复核 sha256
tools/_rc_d38.py:20  本脚本对**真文件**注入缺陷 → 跑**真判据** → 断言它以**预期那句话**报红 → 逐字节还原 → 复核 sha256
```

**这条与 `AGENTS.md §2.1` 直接冲突**：

> **两条规矩：① 反向对照只在内存里做**（`judge()` 那种纯函数就是为此拆的）；
> **② 非要动盘就用 shell 的 `cp` / `sed`，别用 Python；事后跑一次 `verify_depad.py`。**

`AGENTS.md §2.1` 的实测记录写得很清楚：用 Python 改真实数据（即使 sha256 完美复原）会让文件进**填充态**，`read` 工具再也打不开它 —— 抓它的是 `verify_depad.py`，不是那个新写的 verifier。

而 `_rc_d37.py:71` / `_rc_d38.py:45` 用的是 `subprocess.run(cmd, shell=True, ...)` + Python 侧的文件改写，**没有任何一处调用 `depad()`**：

```bash
git grep -n "depad" -- 'tools/_rc_*.py' ; echo "rc=$?"     # → rc=1，零命中
```

当前盘上是干净的（`verify_depad.py` 报「被填充 0 个 / 6486 个文件」），所以**这是潜伏地雷，不是现行缺陷** —— 这个区别必须说清。

**旁证 —— 同族的 `_recon_legacy.py` 是「只读 + 显式 `--write`」的正确写法**：

```
tools/_recon_legacy.py:12  所以本脚本**只读**，做一件事：把 `遗留#` 的 52 行摊平成「真实集合」
tools/_recon_legacy.py:278  > **只读产物**，由 `python3 tools/_recon_legacy.py --write` 生成，不要手改。
```

也就是说：**同一个批次里，两种写法并存** —— `_recon_legacy.py` 默认只读、`--write` 才落盘；`_rc_d37/d38.py` 直接改真文件。后者应该照前者改。

**影响**：今天无害；下一次有人重跑 `_rc_d37.py` / `_rc_d38.py` 时，可能把 `legal-decisions-v1.json`（207 KB）或 `ADR-0013`（128 KB）推进填充态。而这两个脚本的存在理由恰恰是「证明判据会红」，也就是**最可能被重跑的那一类**。

**建议动作**：这两个脚本收尾处加一步 `verify_depad.py --fix`（或在 `AGENTS.md §2.1` 的「落盘配方」里把它们列为必须跟跑的对象）。

---

### 【E-3.4】`research/governance/_scratch/` = **19 个文件 / 1,056 行 / 136 KB**，全部硬编码 `/Users/lute/…` 绝对路径

**证据**

```
19 files, 1056 lines total
1056 total
   215  step_platforms.py     88  fix_ftc.py      82  fix_g8.py
    77  fix_amazon.py         66  fix_eubpa.py    62  fix_113.py
    59  fix_inv2.py           49  fix_bpa.py      47  step_platforms_fixup.py
    43  fix_disclaimer.py     42  fix_enforce.py  38  fix_86.py
    36  fix_final.py          34  fix_prio.py     34  fix_inv.py
    32  fix_gaps.py           30  fix_g7.py       22  step_platforms_dedupe.py
     0  _err.txt
```

**17 处硬编码绝对路径**，`fix_*.py` 的第一行就是：

```bash
git grep -c "/Users/lute" -- 'research/governance/_scratch/*'
# research/governance/_scratch/R5-integration-scripts/fix_113.py:2
# research/governance/_scratch/R5-integration-scripts/fix_inv2.py:2
# 其余 15 个各 1 处
```

```
research/governance/_scratch/R5-integration-scripts/fix_113.py:5
  p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
```

**它们是什么**：**15 个** `fix_*.py`（+ 3 个 `step_platforms*.py` + `_err.txt` = 19）是对**同一份文件**（`research/governance/R5-category-and-competitors.md`，335 KB）的**连续字符串替换补丁**，用 `subs.append((old, new))` 的形式硬编码待替换文本。`step_platforms*.py`（3 个）是同一批的步骤脚本。复现：`git ls-files 'research/governance/_scratch/*fix_*.py' | wc -l` → `15`。

**是不是地雷**：**是，而且是本次审计里最脆的一族**。三条独立理由：

1. **不可重跑**：`fix_86.py` / `fix_inv2.py` 之类依赖「上一步已经改过」的前置状态；重复跑会二次替换或找不到模式。
2. **不可移植**：绝对路径写死，换机器直接 `FileNotFoundError`。
3. **无文档、无自证**：`fix_86.py` 只有一行注释（`# -*- coding: utf-8 -*-` 之后直接就是替换对），`fix_bpa.py` 有一行英文 docstring；**没有一个写明了它属于哪一批、跑完的验证是什么**。
4. **`_err.txt` 是 0 字节**：`research/governance/_scratch/R5-integration-scripts/_err.txt` 存在但空 —— 一个「本该记录错误但什么都没记」的产物。

**影响**：136 KB 的「改文档历史」以**不可复现、不可理解**的形态入库。它们现在**不再是活代码，也不再是证据** —— 卡在中间：既不能被跑（路径死、前置状态没了），也不能当历史读（没有日期、没有顺序说明）。

**建议动作**：把这一族整体降级为只读存档：加一份 `_scratch/README.md` 写清「这批补丁属于哪一轮、按什么顺序跑的、产物是哪个文件」，并去掉可执行位；不要试图把它们改成相对路径重跑（那份文档已经被改过了，重跑会破坏现状）。

---

### 【E-3.5】`research/governance/annotations/` = **19 个受控文件 / 504 KB**，混装「活脚本 + 中间产物 + 交付物」

**证据**（受控文件按大小）

```
217809  annotate.html                            ← 交互标注界面（交付物？）
 77749  pain-corpus-blind.json                   ← 盲评语料（中间产物）
 49553  pain-corpus-annotator-view.json
 29203  guide_reclass_v2.json
 24318  ANN-GUIDE-001-T1.4-T2.1.2.md             ← 规程文档
 12132  guide_reclass_v1.json                    ← v1 与 v2 并存
 11516  measure_alpha.py                         ← 脚本（Krippendorff α）
 10853  CONSULT-001-engorgement-permit.md
 10464  classify_with_guide.py                   ← 脚本
  8755  audit_permit_paths.py                    ← 脚本
  4354  annot_rater_A_notes.md
  4253  disambiguate_pump.py                     ← 脚本
  3509  annot_rater_B_notes.md
  1328  pump_sensitivity.json
  1219  annot_rater_C.tsv
  1209  annot_rater_B.tsv
  1209  annot_rater_A.tsv
   301  alpha_result.json
   236  pump_ambiguity.json
```

**观察**：

- `guide_reclass_v1.json` 与 `guide_reclass_v2.json` 并存（12 KB + 29 KB）—— **没有文档说明哪个是当前口径**，也没有断言。
- `pump_ambiguity.json`（236 B）与 `pump_sensitivity.json`（1,328 B）是同一次分析的两半，命名不表意。
- 4 个脚本（`measure_alpha.py` / `classify_with_guide.py` / `audit_permit_paths.py` / `disambiguate_pump.py`）**全部不在 §1 的 60 条 import 边里**，也全部不在 `AGENTS.md §2.1` 的自证表里 —— **没有人跑它们**。
- `alpha_result.json` 只有 301 字节，是标注者一致性系数 —— 这是一个**对外可引用**的结论级数字，但它**没有任何自证在守**（对比：`verify_kb.py` 的 E7 会守外部承诺到期）。

**影响**：标注一致性（α）如果被引用，就没有任何东西保证它还是用当前的 `annot_rater_*.tsv` 算出来的 —— 这是 `AGENTS.md §2.4.1` 的「假数据与真数据长得一样」形态。

**建议动作**：把这一族拆成「脚本（活）+ 产物（可复算）+ 交付物（只读）」三档，删掉 v1（或写明 v1 的留档理由），给 `alpha_result.json` 补一条可重算判据。

---

### 【E-3.6】`research/distill/scratch/` = 19 个 `_p*.md` / `_t*.md` 中间产物入库（108 KB）

**证据**

```bash
git ls-files 'research/distill/scratch/*'
# _p5.md _p10.md _p20.md _p30.md _p40.md _p50.md _p60.md
# _probe100.md _probe200.md _probe400.md
# _t1.md … _t9.md
du -sh research/distill/scratch    # 108K
```

命名全部是 `_` 前缀 + 无表意编号。`.gitignore` **没有**忽略这一目录。

**影响**：与 `.gitignore` 的分级原则（`L1 人写的 / L2 机器生成可复算 / L3 凭据`）冲突 —— 这批「探针输出」属于 L2，却进了 L1。

**建议动作**：确认它们是否可复算；可复算的移入 `**/_evidence/`（已登记的内容寻址目录）或加进 `.gitignore` 的 L2 段。

---

## 四、构建 / 依赖可复现性

### 复现命令

```bash
cd /Users/lute/Project/audit_multi_content
ls package.json pyproject.toml requirements.txt setup.py 2>&1   # 全部 No such file
python3 /tmp/debtaudit/deps2.py                                  # 真实第三方依赖面
ls .venv-r4/lib/python3.9/site-packages .pylibs
cat tools/package.json tools/agent/package.json
wc -l tools/package-lock.json
```

### 【E-4.1】**根目录确实没有任何清单** —— 确认

**证据**

```bash
ls /Users/lute/Project/audit_multi_content/{package.json,pyproject.toml,requirements.txt,setup.py,setup.cfg,Pipfile,environment.yml}
# 全部：No such file or directory
git ls-files | grep -E '^(package\.json|pyproject|requirements|setup\.)' ; echo "rc=$?"   # rc=1
```

仓库根只有 `README.md`（2 行）、`AGENTS.md`、`.gitignore`。

**影响**：新机器上「怎么装依赖」这件事，只能靠读 `AGENTS.md` 散文 + 猜。

**建议动作**：加一个根 `README`-级别的「环境自举」小节 + 一份 `requirements.txt`（哪怕只有注释说明「本仓 Python 侧零第三方依赖，见 E-4.2」）。

---

### 【E-4.2】**Python 侧的第三方依赖面是 —— 空的**（118 个文件里零第三方 import）

**证据**

```bash
python3 /tmp/debtaudit/deps2.py
# === NON-STDLIB, NON-LOCAL imports (the real 3rd-party surface) ===
#   math         <- 3 file(s)     ← 误报：3.9 的 distutils 枚举没收录它
#   unicodedata  <- 2 file(s)     ← 同上
#   zlib         <- 1 file(s)     ← 同上
#   brandkit     <- 1 file(s): ['skills-inventory/refs/brand-docx/scripts/cli.py']
```

扣除 3 个伪阳性（`math` / `unicodedata` / `zlib` 都是标准库）与 1 个第三方技能库自带的 `brandkit`（在 `skills-inventory/`，不在审计范围），**受控的 118 个 `.py` 里，第三方 import 数是 0**。

用的是 37 个标准库模块：`sys(110 文件) json(87) re(62) pathlib(62) os(48) urllib(45) argparse(45) collections(36) __future__(32) hashlib(31) …`

**这是本项目一个**真实的、可表扬的**工程事实** —— 飞书调用走 `urllib.request`，OCR 走 ObjC + 系统 `Vision.framework`（`base/build_ocr.sh`，按序试 5 个 SDK），没有 pip 依赖。

**但 `README.md` 只有 2 行，所以这条事实没有任何地方写着。**

**建议动作**：把「零第三方 Python 依赖」写进 README 并加一条自证（AST 扫全仓 `import`，出现非标准库即红）。

---

### 【E-4.3】`tools/package.json` **不是**未编辑的 `npm init` 存根 —— 它有一份被提交的锁文件

**口径更正**：`name: tools` / `description: ""` / `main: index.js` / `test` 退 1 —— 这四点**属实**（`tools/package.json:2,4,5,7`），并且 `index.js` **确实不存在**：

```bash
ls tools/index.js    # No such file or directory
```

**但是**，它同时有：

```jsonc
// tools/package.json:13-15
"dependencies": { "@larksuiteoapi/node-sdk": "^1.74.0" }
```

以及一份 **618 行的 `tools/package-lock.json`**（受控），精确钉住版本：

```jsonc
// tools/package-lock.json:15-18
"node_modules/@larksuiteoapi/node-sdk": {
  "version": "1.74.0",
  "resolved": "https://registry.npmjs.org/@larksuiteoapi/node-sdk/-/node-sdk-1.74.0.tgz",
  "integrity": "sha512-K2WoGy6x97u2kPPSFsu0v9X8CY+0q4OwO3rhXiOSRXYjGS7ovydFpEH07AS5VYcBnbQCoc5sGezo0IEGVViuoA==",
```

**Node 侧因此是可复现的**（`npm ci` 能复现 1.74.0）。

**但有两个缺口**：

1. **两份清单，一个锁**：`tools/agent/package.json`（`name: shouheng`, `main: ws_daemon.mjs`, 同样的 `@larksuiteoapi/node-sdk: ^1.74.0`）**没有自己的锁文件**，而 `tools/package-lock.json` 的 `name` 是 `tools`。`tools/agent/` 下的 8 个 `.mjs` 是守衡运行时的核心（`ws_daemon.mjs` → `agent/*.mjs`），依赖却挂在父目录的清单上。
2. **`tools/package.json` 的 `main: index.js` 指向不存在的文件**、`scripts.test` 是 `echo "Error: no test specified" && exit 1` —— **在 `npm test` 下会假红**。而 `tools/agent/package.json:9-12` 有真正的 `start` / `probe` 脚本。两份清单的成熟度不一致，没有任何文档说该用哪份。

**影响**：新机器上最容易踩的是「在 `tools/agent/` 里 `npm install`」→ 装上同版本但**没有锁定 integrity**，或「`npm test`」→ 得到退出码 1 而以为是真红。

**建议动作**：把 `tools/package.json` 的 `main` / `scripts.test` 删掉或改成真东西；让 `tools/agent/` 使用父级锁（写清在 README 里），或给它自己一份锁。

---

### 【E-4.4】`.venv-r4/`（13 MB）与 `.pylibs/`（61 MB）装着**没有任何受控代码 import 的包**

**证据**

```bash
ls .venv-r4/lib/python3.9/site-packages/   # pip packaging setuptools wheel pypdf typing_extensions
ls .pylibs | head                            # curl_cffi pymupdf fitz pypdf certifi cffi pycparser
du -sh .pylibs .venv-r4 .vendor              # 61M  13M  869M

# 全仓搜这些包名（含文档）：
git grep -niE "\bfitz\b|pymupdf|pypdf|curl_cffi" -- . | grep -v skills-inventory
# kb2agent-research/raw/_distill-legal.md:209     「本机无 pdftotext/PyPDF2/Quartz」
# kb2agent-research/raw/_sub_legal.md:22,477      同上
# research/governance/_shards/R8-W1-source-taxonomy.md:78,979   「pypdf 提取」← 一次性使用记录
# research/readmes/{omniguard,polysafe}.md:99     外部项目对照，非本仓
```

**结论**：`.pylibs/` 里的 `pymupdf` / `curl_cffi` / `cffi` **零消费者**；`pypdf` 只在 `research/governance/_shards/R8-W1-source-taxonomy.md:78` 上被记成「一次性用来抽 FTC 那份 53 页 PDF」的工具 —— 那份 PDF 在 `research/governance/_evidence/R8/`（被 `.gitignore:46` `**/_evidence/` 忽略）。

也就是说：**这三处依赖目录（合计 943 MB）对今天的仓库没有任何一行代码是必需的**，而 `.gitignore:33-35` 把它们的存在理由写成「依赖与构建产物，**可由清单重建**」——**没有清单**（§E-4.1）。

**影响**：`ADR-0013` 把它们记成「可由清单重建」（`ADR/ADR-0013-基座接口冻结与仓库入库分级.md:157`），但这个断言**不可执行**。今天删掉 `.pylibs/` 不会坏任何东西；明天有人为了让某个脚本跑起来往里装东西，仍然不会有清单记下来。

**建议动作**：要么为 `.pylibs/` 写一份清单（哪怕只有一行「历史遗留，当前无消费者，可删」），要么确认无消费者后连同 `.venv-r4/` 一起清掉。**先别急着删 `.vendor/`**（见 §E-4.5）。

---

### 【E-4.5】`dsh-browser-ext/panel/assets/index.js`（418 KB 压缩包）**入库但没有源码**，源码只存在于不可寻址的 vendored tarball 里

**证据**

```bash
head -c 200 dsh-browser-ext/panel/assets/index.js
# var Dm=Object.defineProperty;var $m=(e,t,s)=>t in e?Dm(e,t,{…})  ← 典型 Vite/Rollup 压缩产物

ls -R dsh-browser-ext/panel
# assets: deepseek-256.png  index.css  index.js
# index.html
# ← 没有 src/、没有 vite.config、没有 package.json

# 全仓搜这个 bundle 的构建配置：
git grep -ln "vite\|rollup\|esbuild\|webpack" -- dsh-browser-ext
# dsh-browser-ext/background.js          ← 只是 bundle 内部的字符串
# dsh-browser-ext/panel/assets/index.js  ← 同上

# 源码在哪：
ls .vendor/dsh-browser-main       # packages/  scripts/  pnpm-lock.yaml  pnpm-workspace.yaml …
shasum -a 256 .vendor/dsh-browser.tar.gz
# 5267d10b0f07420dcaf4bb13ca73d814d0e4902a691581fe5d85420dadf584ba
# 全仓搜这个 hash / 这个文件名：
git grep -n "dsh-browser.tar.gz\|dsh-browser-main" -- . ; echo "rc=$?"    # rc=1，零命中
```

`ADR/ADR-0013-…md:138` 明确把 `dsh-browser-ext/**` 划为 **L1（入历史、会被人改、改了要能回滚）**。

**影响**：L1 里躺着一份**改了也回滚不了、读也读不懂、重建也建不出来**的 418 KB 产物：
- 它是 `.vendor/dsh-browser-main` 的编译输出，而那个目录被 `.gitignore:35` 忽略；
- tarball 的 sha256（`5267d10b…`）**在仓库任何地方都没有记录**；
- 因此「把它改回去」这件事**今天不可执行**。

**建议动作**：把 `dsh-browser-ext/` 重新分级 —— 要么判为 L2（机器生成、入盘不入历史）并写清生成命令 + 上游 tarball 的 sha256；要么把最小源码集一起入库。**当前「入 L1 但不可重建」是最坏的组合。**

---

## 五、硬编码的机器相关状态

### 复现命令

```bash
cd /Users/lute/Project/audit_multi_content
git grep -o "/Users/lute" -- . | wc -l                     # 60
git grep -l "/Users/lute" -- . | wc -l                     # 47
git grep -oE "oc_[0-9a-f]{8,}" -- . | wc -l                # 101
git grep -coE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" -- '*.py' '*.mjs' '*.sh' | awk -F: '{s+=$2} END{print s}'   # 226
```

### 【E-5.1】全仓 **60 处 `/Users/lute/…`**，分布在 **47 个受控文件**里

**证据（按密度）**

| 文件 | 处数 | 性质 |
|---|---|---|
| `tools/com.shouheng.lark.plist` | **4** | **功能性** —— launchd 真读它 |
| `research/star-lists-audit-report.md` | 3 | 散文 |
| `AGENTS.md` | 3 | 散文（示例） |
| `research/distill/00-写作规范.md` | 3 | 散文 |
| 17 个 `research/governance/_scratch/R5-integration-scripts/fix_*.py` | 各 1–2 | **可执行且是路径主体** |
| `tools/probe_cards.mjs:172` | 1 | **卡片内容里的字面量** |
| `tools/feishu_index.py` | 1 | docstring |

**最坏的两处**（会真的断）：

```xml
<!-- tools/com.shouheng.lark.plist:15-16 -->
<string>/bin/bash</string>
<string>/Users/lute/Project/audit_multi_content/tools/run_shouheng.sh</string>
<!-- :22 -->  <string>/Users/lute/Project/audit_multi_content/tools</string>
<!-- :40,42 --> <string>/Users/lute/Project/audit_multi_content/PMO/logs/ws_daemon.log</string>
```

```python
# research/governance/_scratch/R5-integration-scripts/fix_113.py:5
p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
```

**影响（会坏成什么样，分开说）**：

- **plist 4 处**：这是 `launchd` 的 `ProgramArguments` / `WorkingDirectory` / `StandardOutPath`。换机器 / 换目录 → **守衡起不来，而且日志也写不到地方**。而 `verify_shouheng_ops.py` 的 **D1** 断言的是「仓库副本 ≡ 在跑的配置」—— **两边都是绝对路径，所以它照常全绿**。这是 `AGENTS.md §2.4.1` 的形态：判据读得到了，但读的不是「换机器还成立吗」这一问。
- **17 处 `_scratch`**：见 §E-3.4，换机器直接 `FileNotFoundError`。

**建议动作**：plist 用 `$HOME` 不可行（launchd 不展开），改为**占位符 + 安装脚本**（安装时 `sed` 出真路径），并让 D1 增加一条「仓库副本里不许出现绝对路径」的断言。

---

### 【E-5.2】同一个群 ID `oc_49a7cfb2861cffa4365ca8491f398d32` 硬编码在 **6 个可执行文件**里

**证据**

```
tools/probe_cards.mjs:27          const CHAT_ID = process.env.PROBE_CHAT_ID || 'oc_49a7cfb2…'
tools/probe_cards2.mjs:20         同上
tools/reply-cards/cli.mjs:31      const DEFAULT_CHAT = process.env.PROBE_CHAT_ID || 'oc_49a7cfb2…'
tools/send_once.mjs:8             receive_id: 'oc_49a7cfb2861cffa4365ca8491f398d32'   ← 无环境变量兜底
tools/test_agent.mjs:522          runtimeContext.chatId = 'oc_49a7cfb2…'            ← 无兜底
tools/test_agent.mjs:636          listRecentMessages('oc_49a7cfb2…', 5)             ← 无兜底
```

全仓 `oc_` 字面量共 **101 处**（含文档与探针日志引用）。

**影响**：其中 3 处有 `PROBE_CHAT_ID` 环境变量兜底（改进过的），**3 处没有**（`send_once.mjs:8`、`test_agent.mjs:522`、`test_agent.mjs:636`）。这是**会往真群里发消息**的代码路径 —— 换环境时那 3 处会把消息发到一个不属于当前环境的群。

**建议动作**：6 处统一收敛到 `tools/agent/config.mjs` 的一个常量（该文件已经是配置中心，`tools/agent/config.mjs:6-7` 就在管凭据路径）。

---

### 【E-5.3】凭据路径 `~/.dsh/credentials/shouheng-lark.json` 在 **16 个文件**里各写一遍

**证据**

```bash
git grep -n "shouheng-lark.json" -- '*.py' '*.mjs'
# base/sync_rules.py:92            CRED = Path(os.path.expanduser("~/.dsh/credentials/shouheng-lark.json"))
# tools/check_contact_scope.py:71  CRED = Path(os.path.expanduser(...))
# tools/feishu_index.py:97         CRED = os.path.expanduser(...)
# tools/kb_materials_lark.py:41    CRED = os.path.expanduser(...)
# tools/kb_snapshot.py:29          CRED = os.path.expanduser(...)
# tools/lark_find.py:24            CRED = os.path.expanduser(...)
# tools/lark_people.py:64          CRED = Path(os.path.expanduser(...))
# tools/lark_probe.py:21           CRED = os.path.expanduser(...)
# tools/migrate_kb_to_lark.py:34   CRED = os.path.expanduser(...)
# tools/migrate_vocab_to_lark.py:31
# tools/migrate_whitelist_to_lark.py:29
# tools/push_receipts.py:54
# tools/verify_prd_baseline.py:81  CRED = Path(os.path.expanduser(...))
# tools/verify_vocab_lark.py:26
# tools/agent/config.mjs:6         注释里写路径
# tools/ws_test.mjs:14             注释里写路径
```

**这条设计本身是对的**（`ADR-0013 · D8` 把凭据移出项目目录，`base/verify_base.py:187` 有断言守着），**没有硬编码任何密钥**（`git grep -niE "(app_secret|api_key|token)\s*=\s*['\"][A-Za-z0-9_-]{16,}" -- '*.py' '*.mjs' '*.js' '*.sh' '*.json'` → **0 命中**）。

**但 16 处独立字面量意味着**：改凭据位置要改 16 个文件；换一个飞书应用（换 app_id）要改 16 处。而 `tools/agent/config.mjs` **已经是** Node 侧的配置中心 —— Python 侧没有对应的东西。

**建议动作**：Python 侧立一个 `tools/_feishu_cred.py`（一个常量 + 一个 `token_of()`），16 处改为 import。

---

### 【E-5.4】`226` 个日期字面量在可执行代码里；大部分是历史注释，**少数是活读数且没有过期判据**

**证据**

```bash
git grep -cE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" -- '*.py' '*.mjs' '*.sh' | sort -t: -k2 -rn | head
# tools/verify_engine_contract.py:27    ← 全是「★ 2026-09-17 加 V11d」这类历史注释
# tools/lark_people.py:16               ← 见下
# tools/feishu_index.py:14
# tools/agent/prd_baseline.mjs:14
# tools/kb_gaps.py:11
# tools/verify_pending.py:8
```

**全仓代码里日期总数 226**。分两类：

- **历史注释（无害，且是资产）**：如 `tools/verify_engine_contract.py:463` `# ★ 这一条 2026-09-16 改过极性，原因值得留下：` —— 这类是「为什么这么写」的留档，应保留。
- **活读数（是债务）**：`tools/lark_people.py` 的 `BOUNDARY` 字符串（`:501`）里写着一整张 2026-09-21 的实测表，运行时会打印给用户看：

```
tools/lark_people.py:76   # 实测依据（2026-09-21）：GET im/v1/chats/oc_49a7cfb2…/members
tools/lark_people.py:506       索引里 22 个 owner 有 19 个能叫出名字（含李倩怡、钱撷羽）。2026-09-18 扩过权限。
tools/lark_people.py:525  BOUNDARY_STALE_NOTE = """…
```

这**正是 `AGENTS.md §2.4.1` 第 5 行要求的修法**（「BOUNDARY 改成**带日期的重测读数**」）—— 修得对。

**但缺一层**：没有任何东西断言这张表**还没过期**。对比 —— `verify_kb.py` 的 **E7** 会守「外部承诺未逾期」。这里的 09-21 读数在 10 月、11 月仍会被原样打印给人看，读起来完全正常。

**建议动作**：给 `BOUNDARY` 加一个「读数日期 + 有效期」字段，超过 N 天就在输出里显式标「以下读数采集于 X 天前，可能已变」。

---

### 【E-5.5】端口只用环境变量兜底，没有硬编码端口 —— 这一项是干净的

**证据**

```bash
git grep -nE ":(3000|4000|5000|8000|8080|9000|43120)" -- 'tools/*' 'base/*' ; echo "rc=$?"   # rc=1
.tools/cdp.mjs:6   const list = await (await fetch('http://127.0.0.1:' + (process.env.CDP_PORT||'9222') + '/json/list')).json();
```

`9222` 是 CDP 默认端口，有 `CDP_PORT` 环境变量覆盖。**没有发现不可覆盖的硬编码端口。**

**建议动作**：无需动作。（写在这里是为了说明这一项**查过了**，不是漏了。）

---

## 六、错误处理与失效形态

### 复现命令

```bash
cd /Users/lute/Project/audit_multi_content
git grep -nE "except[^:]*:\s*pass|except\s*:" -- 'tools/*.py' 'base/*.py'      # 单行形态
python3 /tmp/debtaudit/silent.py                                                # 多行形态（except 后换行接 pass/continue）
git grep -nF "|| true" -- '*.sh' '*.py' '*.mjs'
git grep -nF "2>/dev/null" -- '*.sh' '*.py' '*.mjs'
```

### 先说三个**没有**发现的（避免把「查过」当成「有问题」）

| 形态 | 实测 | 说明 |
|---|---|---|
| 裸 `except:` | **0 处** | `git grep -cE "except\s*:"` → 无命中 |
| `except …: pass`（单行） | **0 处** | 同上 |
| `|| true` | **1 处** | `tools/ws_watch.sh:46`（只为 `grep -c` 无命中时不报错，合理） |
| `2>/dev/null` | **11 处** | 集中在 `restart_shouheng.sh`(5) / `ws_watch.sh`(2) / `run_shouheng.sh`(1) / `build_ocr.sh`(1)，均有上下文说明 |
| 硬编码密钥 | **0 处** | 见 §E-5.3 |
| 未检查的 `subprocess.run` | **有，见 E-6.4** | — |

**`AGENTS.md §2.2` 第 5–7 条（`timeout` 不存在 / `$?` 在管道后 / `ps` 被拒）的形状**，逐条查过：

- **`timeout` 命令**：全仓 **0 处**调用外部 `timeout`；脚本里出现的 `timeout` 全是 Python `urllib` 的 `timeout=` 参数或 Node 的 `timeoutMs`。**这个坑已经被绕开了**（`base/media.py:144`、`tools/agent/prd_baseline.mjs:187`、`tools/agent/tools.mjs:275` 都用进程内超时）。
- **`$?` 在管道后**：`tools/` 下 4 个 `.sh` 里，`| head` / `| tail` 只出现在赋值里（`restart_shouheng.sh:62`、`run_shouheng.sh:34`、`ws_watch.sh:19`）或 `tail -f | grep` 的交互流里（`ws_watch.sh:53`），**没有一处把管道后的 `$?` 当判据**。
- **`ps` 被拒**：`tools/restart_shouheng.sh:154-155` 仍在用 `ps` 取 `lstart`/`etime`，但已按 §2.2 第 7 条改成「取不到就说未测」（`:260` 的 `grep -c` 兜底）；`verify_shouheng_ops.py:315` 的 E1 落「未测」。**已修**。

**结论：`AGENTS.md §2.2` 记录的三个坑，同一个形状在 `tools/`+`base/` 里已经找不到新的活样本了。** 下面三条是**不同形状**的。

---

### 【E-6.1】`feishu_index.py` 分页中途失败时**静默 `break`**，且「网络失败」与「顶到页数上限」被压成同一个 `truncated: true`

**证据**

```python
# tools/feishu_index.py:363-369（docstring，作者自己写了这条规矩）
    ⚠️ **翻页必须翻到 has_more=False，不能设一个「够用」的页数上限。**
    第一版设了 msg_pages=2，抓到 78 条就停；而第 1 页本身就返回了
    `has_more: true` —— 也就是说还有更早的消息没抓，脚本却什么都没说。
    这是典型的**静默截断**：读数字的人会以为「这个群一共就这么些」。
    现在默认翻到底（20 页 = 1000 条），并把是否顶到上限记进 `truncated`。

# :373-375  ← 真正的失败路径
            m = _get(url, tok)
            if m.get("code") != 0:
                break                        # ★ 不记账、不报错、不置标志

# :393-397
        # 顶到 tmppages 上限 = 还有更早的消息没读到。必须显式记账，不许沉默。
        for c_out in out:
            if c_out["chat_id"] == cid:
                c_out["messages_read"] = sum(1 for m in msgs if m["chat_id"] == cid)
                c_out["truncated"] = not reached_end
```

**三重问题**：

1. `:375` 的 `break` **不留任何痕迹** —— 没有 `err`、没有 warn、`return out, msgs, None`（`:399` 返回的第三位恒为 `None`）。
2. `:397` 的 `c_out["truncated"] = not reached_end` —— 网络失败时 `reached_end` 是 `False`，于是**网络失败被记成 `truncated: True`**，与「顶到 20 页上限」**完全同一个值**。两种完全不同的病共用一个字段。
3. **`truncated` 没有任何消费者**：

```bash
git grep -n "truncated" tools/feishu_index.py tools/verify_feishu_index.py
# tools/feishu_index.py:354,397,578,1227     ← 生产者
# （tools/verify_feishu_index.py 零命中）     ← 消费者：无
```

**影响**：这正是 `AGENTS.md §2.4.1` 那句「**空结果与我读错了必须在输出里长得不一样**」的反面 —— 这里是「**读失败**与「**读完了但有上限**」长得一样，而且没有断言。写这段代码的 docstring 明确说了「必须显式记账，不许沉默」—— **该记的那一种记了，另一种漏了**。

**建议动作**：`break` 前把失败原因记进该群的输出（如 `page_error`），`truncated` 拆成 `hit_page_cap` 与 `page_error` 两个字段，并让 `verify_feishu_index.py` 断言「`page_error` 必须为 0」。

---

### 【E-6.2】`except → pass/continue` 共 **20 处**，其中 `tools/` 有 5 处、`research/governance/` 有 15 处

**证据**

```
20 sites (except 后直接 pass/continue)：
  tools/kb_index.py:151                              except OSError:  → continue
  tools/lp_extract.py:176                            except Exception: → pass
  tools/verify_external.py:113                       except Exception: → pass
  tools/verify_external.py:121                       except Exception: → pass
  tools/verify_external.py:191                       except Exception: → continue
  tools/verify_feishu_index.py:279                   except Exception: → continue
  tools/verify_pending.py:109                        except json.JSONDecodeError: → continue
  research/governance/audit_citation_fidelity.py:608,860,971,1380   except Exception/OSError → continue
  research/governance/audit_evidence_integrity.py:227,267,289       except OSError → pass
  research/governance/audit_records_deep.py:265,271                 except ValueError → pass
  research/governance/audit_rule_consistency.py:219                 except re.error → continue
  research/governance/annotations/audit_permit_paths.py:48          except re.error → pass
  research/governance/skeleton/engine_manifest.py:269               except json.JSONDecodeError → continue
  research/governance/audit_escape_layers.py:124                    except re.error → pass
```

**分类判断（不是一律算债务）**：

- **可接受的**：`except re.error` / `except json.JSONDecodeError` 配 `pass` —— 输入是用户数据，跳过一个坏样本是正确策略。
- **危险的**：`except Exception: pass` 在 **`tools/verify_external.py:113` 与 `:121`** —— 这是**验收器**。它对页面里两处 JSON 块做容错解析，两处异常都吞掉，然后 `:118` 有个退路 `if not out:`。

```python
# tools/verify_external.py:118-123
    if not out:  # 退路：任何 <script type="application/json"> 块
        for m in re.finditer(..., body):
            try:
                ...
            except Exception:
                pass
    return out
```

也就是说：**「页面里没有 JSON-LD」与「我解析全失败了」返回同一个 `[]`** —— 正是 §2.4.1 的「假数据是真数据的形状」。这是**验收器自己的**盲区，而它验的对象是外部站点。

**影响**：`verify_external.py` 会把「站点结构变了、我的解析器全废了」报成「这个页面没有结构化数据」。

**建议动作**：解析失败计数（`parse_errors`）与「真的没有」分开返回，并让调用方在任何 `parse_errors > 0` 时落「未测」而不是「无数据」。

---

### 【E-6.3】`verify_external.py` 用 `curl` 子进程但**不看退出码**就把 stdout 当正文

**证据**

```python
# tools/verify_external.py:129-131
    r = subprocess.run(["curl", "-sS", "-L", "--max-time", "45", "-A", ua,
                        "-w", "\n__HTTP__%{http_code}", url],
                       capture_output=True, text=True)
```

**说明**：`-sS` 会把错误打到 stderr，`--max-time 45` 保证不挂死 —— 这是**不依赖 `timeout` 命令**的正确写法。但 `subprocess.run` 的返回值 `r` 之后**没有被断言 `r.returncode`**（`verify_external.py` 全文件对 `returncode` 零引用）。

**影响**：`curl` 超时（`--max-time`）时返回码 28、stdout 可能只有 `__HTTP__000`。若下游用 `__HTTP__` 之后的部分当正文，就会与「站点返回空页」混淆。

**建议动作**：显式断言 `r.returncode`，非 0 时把 stderr 一起带进读数并落「未测」。

---

### 【E-6.4】`subprocess.run` 共 **34 处**，其中 **19 处**没有 `check=True` 也没有读 `returncode`

**证据**（`tools/` + `base/` + `research/governance/skeleton/` 合计）

```bash
git grep -nE "subprocess\.(run|call|Popen|check_output)" -- 'tools/*.py' 'base/*.py' 'research/governance/skeleton/*.py' | wc -l
# 34
```

**读了 `returncode` / 用了 `check=True` 的（15 处）**：`base/media.py:120-121`（`if r.returncode != 0 or not OCR_BIN.exists()`）、`base/verify_base.py:218,325`、`tools/_rc_d37.py:71,93`、`tools/_rc_d38.py:45`、`tools/feishu_index.py:1612,1613`（`check=True`）、`tools/verify_depad.py:135,136`（`check=True`）、`tools/verify_engine_contract.py`（多处）、`tools/verify_shouheng_ops.py:84,89,315`、`tools/verify_skill.py:80`。

**没读的（19 处，主要是子进程产物的解析路径）**：`tools/ab_engine_diff.py:76,107`、`tools/verify_depad.py:99`、`tools/verify_external.py:129` 等。

**影响**：这是**混合**的 —— 关键判据路径（`_rc_*`、`verify_*`）都读了返回码，**这是好的**；`ab_engine_diff.py:107`（`subprocess.run([sys.executable, "engine_manifest.py", "--write"], ...)`）**不读返回码**，一个失败的写操作会被当成成功继续往下比。

**建议动作**：把「不读返回码的子进程调用」列成一张清单，逐条判断是「真的不关心」还是「漏了」。

---

### 【E-6.5】`base/README.md` 的模块自证项数**与实跑输出对不上**（文档里的数字没算出来）

**证据**

`base/README.md` 开头：

```
> 它自己会调**五个模块**的自证（41 + 26 + 20 + 26 + 19 项，含 20 条反向对照），
> 再跑四条仓库治理检查。
```

实跑 `python3 base/verify_base.py`（RC=0）输出的模块清单是 **6 个模块**，项数是：

```
✓ contract.py        ContentUnit 契约（B0.2）     退出 0 · 46 项（含 12 条必红）
✓ judge_adapter.py   judge(unit) 适配层（B0.3）    退出 0 · 26 项（含 4 条必红）
✓ sync_rules.py      权威源单向同步（B0.4）        退出 0 · 20 项（含 2 条必红）
✓ media.py           图片/视频进管道（B1）         退出 0 · 29 项（含 3 条必红）
✓ text_stage.py      文本两组三指标（B2）          退出 0 · 19 项（含 1 条必红）
✓ change_detect.py   变更判据 claim-set-v1（B2·A） 退出 0 · 16 项（含 4 条必红）
```

`41/26/20/26/19` vs 实际 `46/26/20/29/19/16` —— **模块数、每一项的数、以及「20 条反向对照」全部对不上。**

**这是 `AGENTS.md §2.2` 第 1 条（「文档里的数字要算出来，不能写进去」）在同一个文件里的第二次犯案** —— 而 `base/README.md` 的正文里紧接着就长篇记录了这条教训（「★ 一个把证据凭空变厚的错」）。

**影响**：读者无法从这句话判断「到底验了多少」。对照：`tools/verify_cards.mjs` 有 **I 段**专门断言「文档里写的自证项数必须等于实际项数」，`base/` 没有对应机制。

**建议动作**：把 `base/verify_base.py` 的清单做成唯一产地，`base/README.md` 那一行改成从清单生成（或删掉具体数字，只留命令）。

---

### 【E-6.6】`tools/verify_skill.py` 的验证对象**不在版本控制里** —— 全文唯一的「规程自证」指向一个被 gitignore 的文件

**证据**

```python
# tools/verify_skill.py:34
SKILL = os.path.join(ROOT, "skills", "内容合规审查", "SKILL.md")
```

```bash
git check-ignore -v "skills/内容合规审查/SKILL.md"
# .gitignore:39:skills/	"skills/内容合规审查/SKILL.md"      ← 被忽略
git ls-files "skills/内容合规审查/"   # 空 —— 未入库
ls -l "skills/内容合规审查/SKILL.md"
# -rw-------  1 lute  staff  6465 Sep 18 14:33 skills/内容合规审查/SKILL.md   ← 存在，但不在库里
```

**这与项目自己的规则直接冲突，而且项目里另一个检查器正在守这条规则**：

`AGENTS.md §2.3`：

> | **本项目自有的规程 / skill** | **`agent-skills/<名字>/SKILL.md`** | ✅ |
> 把自有规程写进 `skills/` 的后果是：写完之后 `git status` 一片干净…实际上它**不会进版本库**。
> `node tools/verify_cards.mjs` 的 H 段会把这件事变成红的。

而 `tools/verify_cards.mjs` **确实**在守：

```js
// tools/verify_cards.mjs:165
    path.join(ROOT, 'agent-skills', '守衡语域', 'SKILL.md'),
// tools/verify_cards.mjs:268-273
  // 这条是被真实踩到后才加的：本项目 .gitignore 第 39 行是 `skills/`，
  // 注释写明「第三方技能库与克隆」。项目**自有**的规程放进 skills/ 不会入库，
  const skill = path.join(ROOT, 'agent-skills', '守衡语域', 'SKILL.md');
```

`tools/verify_skill.py` 读的是 `skills/内容合规审查/SKILL.md` —— **同类文件（自有规程），放在了被忽略的目录里**。

**影响**：

- 换机器 / 重新 clone → **`tools/verify_skill.py` 直接 `FileNotFoundError`**（`:70` `open(SKILL, encoding="utf-8").read()` 无 try）。
- `AGENTS.md §2.1` 的自证表把它列为 12 个自证入口之一，而**它的验证对象今天只存在于这一台机器上**。
- 更微妙的一层：`AGENTS.md §2.7` 说「本仓库里唯一会把文档里命令跑一遍的是 `tools/verify_skill.py`，它只扫 `skills/内容合规审查/SKILL.md` —— **那个范围不许扩到 AGENTS.md**」。`verify_shouheng_ops.py` 的 **G 段**守着这个范围。**所以这个检查器的重要性是明确的，而它唯一的输入没有入库。**

**建议动作**：把 `skills/内容合规审查/SKILL.md` 移进 `agent-skills/内容合规审查/SKILL.md`（照 `agent-skills/守衡语域/SKILL.md` 的先例），同步改 `verify_skill.py:34`；并让 `verify_cards.mjs` H 段的同类断言覆盖全部 `agent-skills/*/SKILL.md`。

---

## 七、仓库卫生

### 复现命令

```bash
cd /Users/lute/Project/audit_multi_content
git ls-files | grep -i "DS_Store"                       # 空
git check-ignore -v .ua/knowledge-graph.json            # rc=1 → 未忽略
cat README.md | wc -lc                                  # 2 行 35 字节
git status --porcelain | wc -l                          # 12
git ls-files -z | xargs -0 ls -l | awk '$5>100000' | wc -l
```

### 【E-7.1】`.DS_Store` **没有被跟踪** —— 这一条与预期相反，实测无债

**证据**

```bash
git ls-files | grep -i "DS_Store" ; echo "rc=$?"
# （无输出） rc=1   ← 零个受控 .DS_Store
```

盘上确实有 4 个（`./.DS_Store`、`./PMO/.DS_Store`、以及 `skills/` 与 `.vendor/` 下的若干），但 `.gitignore:71-72` 已经拦住：

```
# macOS
.DS_Store
**/.DS_Store
```

**影响**：无。

**建议动作**：无需动作。（列出这条是为了**纠正一个先入的假设** —— 审计报告不能只报「预期的坏事」。）

---

### 【E-7.2】`README.md` 确认是 **2 行 / 35 字节**，仓库没有任何面向新人的入口

**证据**

```bash
cat README.md
# audit_multi_content
# 内容审计
wc -lc README.md     # 2  35
```

**对照**：`base/README.md` 有 **830 行**、`research/governance/README.md`（384 行）、`research/kb/README.md`（183）、`PRD/feishu/README.md`（145）、`research/feishu/README.md`（137）、`tools/reply-cards/README.md`（130）、`ADR/README.md`（117）、`research/landing/README.md`（86）—— **8 个子目录有详尽 README，根目录只有 2 行**（复现：`git ls-files | grep -i README.md | grep -v skills-inventory | wc -l` → `9`，含根 README）。

**影响**：新 agent 的第一入口是 `AGENTS.md`（596 行硬约束），而不是「这个仓库是什么」。`AGENTS.md` 第一节讲的是**提问方式**，不是项目。240 KB 的仓库没有一页「30 秒看懂」。

**建议动作**：给根 README 补一页入口：项目一句话 + 5 个顶层目录各一行 + 「先跑哪条自证」+ 指向 `AGENTS.md`。

---

### 【E-7.3】`.ua/`（16 MB 的知识图谱产物目录）**既没有被 gitignore，也没有被跟踪** —— 它正出现在 `git status` 里

**证据**

```bash
git check-ignore -v .ua/knowledge-graph.json ; echo "rc=$?"
# （无输出） rc=1        ← 未被忽略

git status --porcelain | head -3
# ?? .ua/

cat .gitignore | tail -6
# # macOS
# .DS_Store
# **/.DS_Store
# ← .ua 一个字都没有
```

目录实际内容（16 MB）：

```
1795419  knowledge-graph.json
 494959  fingerprints.json
    ...  assemble.cjs / gen-phase45.cjs / graph-diagnosis.cjs / duplication-check.cjs
         *.md（同名的分析报告）/ dispatch/（49 项）/ intermediate/ / .trash-1790050761/（69 项）
```

**影响**：

- `.gitignore` 头部写着「**本文件只写 L2 / L3。其余一律入历史**」+「改动本文件 = 改动分级 = 需回到 ADR-0013 §三 同步，否则台账与制品会漂移」。`.ua/` **两者都没有** —— 既不在 L2/L3 名单里，也不在 L1 的定义里。它是一类**未被分级**的东西。
- 后果是具体的：`git status` 永远不干净（12 项里有 1 项是它，且它会随分析长到几千个文件），而 `base/verify_base.py` 的 **E 面**会把「工作区 12 项未提交」当成一个读数报出来 —— **噪声会淹没信号**。
- 而且 `.ua/` 里含 `.trash-1790050761/`（69 项）与 `dispatch/`（49 项）—— 一个**带回收站的临时工作目录**。

**建议动作**：在 `.gitignore` 的 L2 段加一行 `.ua/`（并回到 `ADR-0013 §三` 登记这一级），同时把 `base/verify_base.py` E 面改成「只报受控文件的改动」。

---

### 【E-7.4】工作区**有 12 项未提交**（审计期间，`AGENTS.md` 本身也在其中）

**证据**

```bash
git status --short
#  M AGENTS.md
#  M "PRD/feishu/索引-v1.json"
#  M "PRD/feishu/美国市场内容治理项目-一页纸计划书.md"
#  M tools/lark_find.py
#  M tools/restart_shouheng.sh
#  M tools/verify_shouheng_ops.py
# ?? .ua/
# ?? "PMO/守衡-内容推送与被at登记-20260915至0922.md"
# ?? "PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin"
# ?? "PMO/守衡-回话草稿-M12材料逐条状态-20260922.md"
# ?? "PMO/守衡-知识库GAP分析与第一性原理决策-20260922.md"
# ?? "PMO/守衡-知识库构建完整方案-20260922.md"
git rev-list --count HEAD     # 26
```

**关于时间点的诚实说明**：审计开始时（12:14）只有 **3 个 M + 5 个 ??**；审计进行中（12:3x）变成 **6 个 M + 6 个 ??** —— `PRD/feishu/` 的两个文件与 `tools/lark_find.py` 是**审计窗口内被改的**（父代理按 `AGENTS.md §2.1` 新加的「落盘配方」重拉上游文档，见 §零第 6 条）。所以这 12 项**不是长期积压**，是**审计当时的快照**。

**影响**：26 个提交 vs 12 项未提交 —— 仓库处于**活跃开发态**，这本身不是债务。债务在于：`base/verify_base.py` 的 E 面把「工作区未提交项数」报成一个健康读数，而在活跃开发态它**永远是红的**，于是没人看它。

**建议动作**：E 面区分「受控文件的未提交改动」（有意义）与「未跟踪目录」（噪声），只报前者。

---

### 【E-7.5】受控二进制文件 **7 个**（全部是浏览器扩展图标），其中 `deepseek.ico` **209 KB**

**证据**

```bash
git ls-files -z | while IFS= read -r -d '' f; do
  python3 -c "import sys;open(sys.argv[1],encoding='utf-8').read()" "$f" 2>/dev/null || echo "$f"; done
# dsh-browser-ext/assets/icons/deepseek-256.png    8803
# dsh-browser-ext/assets/icons/deepseek.ico      209762
# dsh-browser-ext/assets/icons/icon128.png         8909
# dsh-browser-ext/assets/icons/icon16.png          1229
# dsh-browser-ext/assets/icons/icon32.png          2158
# dsh-browser-ext/assets/icons/icon48.png          3170
# dsh-browser-ext/panel/assets/deepseek-256.png    8803   ← 与第 1 个逐字节重复
```

**观察**：7 个二进制全部属于 `dsh-browser-ext/`，且 **`deepseek-256.png` 有两份完全相同的副本**（`assets/icons/` 与 `panel/assets/`，各 8,803 字节）。`deepseek.ico` 209 KB 对一个 16/32/48/128 的图标集来说偏大。

**影响**：低。这不是「大文件污染仓库」（最大的受控文件是 `research/kb/台账-v1.json` 1.26 MB，属正常数据），只是可整合的重复。

**建议动作**：`panel/assets/deepseek-256.png` 改为引用 `../assets/icons/deepseek-256.png`（或在 README 里写明为什么必须有两份）。

---

### 【E-7.6】`.bak` / 损坏痕迹：**1 个受控备用件（且已陈旧 5.4 KB）**、**1 个未跟踪的损坏产物**

**证据 —— 与预期不同的两处**

```bash
# ① 这个是受控的（确认）
git ls-files --error-unmatch 'research/governance/skeleton/rules-v1.json.bak'
# research/governance/skeleton/rules-v1.json.bak      rc=0

# ② 这个是**未跟踪**的（纠正预期）
git ls-files --error-unmatch 'PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin'
# error: pathspec … did not match any file(s) known to git     rc=1
git status --short | grep corrupt
# ?? "PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin"

# ③ 全仓只有一个受控 .bak
git ls-files | grep -E "\.(bak|orig|tmp|old)$"
# research/governance/skeleton/rules-v1.json.bak
```

**`.bak` 的真实风险（比「占地方」严重得多）**：

```bash
python3 -c "
import hashlib
for p in ['research/governance/skeleton/rules-v1.json','research/governance/skeleton/rules-v1.json.bak']:
    b=open(p,'rb').read(); print(p, len(b), hashlib.sha256(b).hexdigest()[:16])"
# rules-v1.json      47606  18c25d4be2ffaf0f      ← 现行
# rules-v1.json.bak  42174  99da09c9b9b593bc      ← 陈旧一代（差 5,432 字节）
```

而**谁在用这个 `.bak`**：

```python
# research/governance/skeleton/wire_whitelist.py:75-77
    if not BAK.exists():
        shutil.copy2(RULES, BAK)          # ★ 只在 .bak 不存在时才备份
        print(f"备份 → {BAK.name}")

# research/governance/skeleton/wire_whitelist.py:88   ← 写回受控制品
        RULES.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
# research/governance/skeleton/wire_context_guards.py:36,84  同样的 BAK + 同样的 write_text
```

**这是一个成对的缺陷**：

1. **`.bak` 因为已经入库，永远存在** → `if not BAK.exists()` 恒为假 → **重跑 `wire_whitelist.py` 不会备份现状**。它给未来读者的「改之前是什么样」的保证，指向的是**上一代（42,174 字节）**，不是上一秒。
2. **`rules-v1.json` 是被 `wire_whitelist.py:88` 用 `Path.write_text` 写的** —— 而 `AGENTS.md §2.1` 的实测矩阵明确：**Python 写出的文件会进 +4096 填充态**，`read` 工具打不开。这两个脚本**没有任何 depad 调用**：

```bash
git grep -n "depad" -- 'research/governance/skeleton/*.py' ; echo "rc=$?"     # rc=1，零命中
```

当前 `rules-v1.json` 是干净的：

```bash
python3 -c "import os;p='research/governance/skeleton/rules-v1.json';print(os.stat(p).st_size, len(open(p,encoding='utf-8').read().encode()))"
# 47606 47606   ← delta=0，未填充
```

**所以这是潜伏地雷，不是现行缺陷** —— 但 `wire_whitelist.py:24` 的 docstring 写着「**幂等：重复运行结果一致**」，**这是一句鼓励重跑的话**。

**影响**：一个幂等且被文档鼓励重跑的脚本，会在重跑时（a）不备份现状、（b）把一个 47.6 KB 的受控规则文件推进填充态。后者由 `verify_depad.py` 兜底（它现在报 0 个填充文件 / 6486 个），但只有在**有人想到去跑它**的时候。

**建议动作**：`wire_whitelist.py` / `wire_context_guards.py` 的写回之后加一次 `depad()`（`tools/feishu_index.py:1579` 是现成实现）；`.bak` 从版本控制移出（它是 L2「可复算的机器产物」），并改成带时间戳的备份名。

---

### 【E-7.7】`research/governance/_shards/`（976 KB / 6 个文件）与 `research/readmes/` 是**未被任何检查器覆盖**的散文

**证据**

```bash
du -sh research/governance/_shards        # 976K
git ls-files 'research/governance/_shards/*' | xargs wc -l | sort -rn
#   R7-W1-structures.md              296032 bytes
#   R7-W2-axis-design.md             196011
#   R8-W3-errorbook-severity-gaps.md 150765
#   R8-W2-elicitation-methods.md     138369
#   R7-W3-category-and-coldstart.md  105648
#   R8-W1-source-taxonomy.md         104187
git ls-files 'research/readmes/*' | wc -l    # 10
```

**观察**：知识图谱把这批划为 `layer:research-findings`（131 个节点）。`_shards/` 的 6 个文件合计近 1 MB，全部以 `_` 前缀命名（与「中间产物」的约定一致），但**它们是调研结论的主体**。`R8-W1-source-taxonomy.md:78,979` 里引用了 `pypdf` 抽出的 PDF 文本（那份 PDF 在 gitignore 的 `_evidence/` 里）—— **结论入库，取证不入库**。

**影响**：`_` 前缀 + `_shards/` 目录名让这 1 MB 读起来像「草稿」，而它们实际上是**外部标准库（62 条）的证据来源**。`verify_kb.py` 的 F3 断言了「外部标准库条目引用与归组完整」，但它比的是 JSON 台账，**不比 `_shards/` 里的原始引用是否还在**。

**建议动作**：`_shards/` 改名去掉下划线（或加 `_shards/README.md` 说明它是正式产物）；给 `research/kb/外部标准库-v1.json` 的 62 条补一条「来源指针可解析」的判据。

---

## 八、按严重度排序的处置建议

| 优先级 | 编号 | 一句话 |
|---|---|---|
| **P0** | E-7.6 | `wire_whitelist.py:88` 用 Python 写回 47.6 KB 受控规则文件且无 depad；`.bak` 因入库而永远不再备份现状 |
| **P0** | E-2.3 | `reply-cards/index.mjs:52` 存在第二套发送兜底（零消费者），§2.5 的 L2 断言查不到它 |
| **P0** | E-6.6 | `verify_skill.py:34` 的验证对象是被 gitignore 的 `skills/内容合规审查/SKILL.md` |
| **P0** | E-6.1 | `feishu_index.py:375` 分页失败静默 break，且与「顶到上限」共用一个 `truncated`，无语义消费者 |
| **P1** | E-3.2 | `_ingest_batch10/12.py` 无 `--write` 门，重跑会静默重写唯一台账 |
| **P1** | E-3.3 | `_rc_d37/d38.py` 往真文件注入缺陷，无 depad，与 §2.1 的「反向对照只在内存里做」冲突 |
| **P1** | E-5.1 | plist 4 处绝对路径；换机器守衡起不来，而 D1 断言两边都是绝对路径所以照常绿 |
| **P1** | E-4.5 | 418 KB 浏览器扩展 bundle 入 L1，源码只在不可寻址的 vendored tarball 里 |
| **P1** | E-6.5 | `base/README.md` 的模块自证项数与实跑输出对不上（41/26/20/26/19 vs 46/26/20/29/19/16） |
| **P2** | E-1.2 | `call()` 四份同形副本，超时 60/60/30/25、错误体上限 400/400/400/500 互相漂移 |
| **P2** | E-1.3 | 9 个函数在 ≥2 个文件里完全同形（sim ≥0.99），约 250 行纯副本 |
| **P2** | E-7.3 | `.ua/` 未分级、未忽略、未跟踪，且含 `dispatch/` 与 `.trash-*/` |
| **P2** | E-4.3 | `tools/package.json` 的 `main: index.js` 不存在、`npm test` 恒退 1；两份清单一个锁 |
| **P2** | E-3.4 | `_scratch/` 19 文件 / 136 KB 绝对路径硬编码，不可跑也不可读 |
| **P2** | E-6.2 | `verify_external.py:113,121` 的 `except: pass` 让「无数据」与「解析全失败」同形 |
| **P3** | E-5.3 | 凭据路径 16 处独立字面量，Python 侧无配置中心 |
| **P3** | E-5.2 | 群 ID 6 处硬编码，其中 3 处无环境变量兜底 |
| **P3** | E-7.2 | `README.md` 2 行，8 个子目录有 README 而根目录没有 |
| **P3** | E-4.4 | `.pylibs/` 61 MB 零消费者，而 ADR 说它「可由清单重建」（无清单） |
| **P3** | E-2.1 | 9 个 `tools/` 文件零引用（含 4 个仍有复查价值的诊断探针） |

---

## 九、本次审计**没有**发现问题的项（避免误读为「没查」）

| 项 | 实测读数 |
|---|---|
| `.DS_Store` 入库 | **0 个**（`.gitignore:71-72` 已拦住） |
| 硬编码密钥 / token | **0 处** |
| 不可覆盖的硬编码端口 | **0 处**（CDP 端口有 `CDP_PORT` 兜底） |
| Python 第三方依赖 | **0 个**（118 个 `.py` 只用 37 个标准库模块） |
| 裸 `except:` / 单行 `except: pass` | **0 处** |
| 调用外部 `timeout` 命令 | **0 处**（全用进程内超时，`AGENTS.md §2.2` 第 5 条已绕开） |
| 管道后取 `$?` 当判据 | **0 处**（`AGENTS.md §2.2` 第 6 条已绕开） |
| `ps` 被拒导致的崩溃 | **已修**（`verify_shouheng_ops.py:315` 落「未测」，本次实跑验证 rc=2 而非 traceback） |
| 生成物 +4096 填充态 | **0 个 / 6486 个文件**（`verify_depad.py` rc=0） |
| 受控的损坏产物（`corrupt-tail.bin`） | **未跟踪**（预期有误，见 E-7.6） |

---

*报告生成：2026-09-22 · 全部读数为当时现场值 · 未修改任何受审文件*
