# 结构性诊断 · 图与横切面（编排者直接算出，非 subagent 结论）

> 基线：工作区 2026-09-22 12:00–12:20 状态。`git rev-parse HEAD` = `243c6bf`，
> 但工作区相对该 commit 有 **未提交改动**（`AGENTS.md` +52/−4、`tools/restart_shouheng.sh` +39、
> `tools/verify_shouheng_ops.py` +82）。本次图谱的 `meta.gitCommitHash` 记的是 `243c6bf`，
> 而读到的内容是工作区内容 —— **两者不同**，这一点本身按 §2.2 第 1 条必须写明。

---

## 一、体量真相：这不是一个成熟代码库，是一个四天的工作区

| 判据 | 读数 | 复现 |
|---|---|---|
| 提交数 | **26** | `git rev-list --count HEAD` |
| author date 跨度 | **2026-09-17 → 2026-09-21**（两个工作日） | `git log --format='%ad' --date=short \| sort -u` |
| 已跟踪文件 | 464（280,283 行） | `git ls-files \| wc -l` |
| 全部提交的 committer date | 2026-09-21 19:48（一次 rebase 压平） | `git log --format='%cd'` + `git reflog` |

**五个提交（26 个中的 19%）的提交信息本身就是在撤回前一个提交的结论**：

```
撤回我的甲/乙分类；改用实测：旧豁免语义 36 个自我触发词里只剩 2 个还能放行
D15 执行：撤回「源表漏放」这句错话 —— 真相反过来，是迁移翻了语义
ADR-0013 §七 重写：更正初稿的过强判断，钉死机制
ADR-0014：…更正 ADR-0009 §八 的「即：不生效」
修冻结台账漂移；补 V11d 真目录门；改判 manifest-history 为 primary
```

> 复现：`git log --format='%s' | grep -cE '撤回|更正|修正|纠错|改判|重写|错话|错误'` → **5**

这不是「债务累积」的形状，是「四天高速产出、自我纠错频繁、尚未收口」的形状。
**结论会因此不同：重点不是重构一个成熟系统，是在债务定型之前把口径钉住。**

---

## 二、体量分布：88% 不是可执行面

| 目录 | 文件 | 行数 | 行占比 |
|---|---:|---:|---:|
| `research/` | 194 | 191,299 | **68.3%** |
| `skills-inventory/`（第三方 vendored） | 91 | 34,717 | 12.4% |
| `tools/` | 87 | 27,096 | 9.7% |
| `kb2agent-research/` | 20 | 8,729 | 3.1% |
| `base/` | 11 | 6,353 | 2.3% |
| `ADR/` | 15 | 5,063 | 1.8% |
| `PMO/` | 13 | 3,130 | 1.1% |
| `PRD/` | 7 | 1,993 | 0.7% |
| 其余 | 26 | 1,903 | 0.6% |

复现：见 `.ua/` 生成脚本同款口径（`git ls-files -z` + 逐文件 `wc -l`）。

**可执行面（`tools/` + `base/`）= 11 个文件目录里的 12.0%。**
但 88% 不是废料 —— 它是一个**循证型项目**的证据层，本身是交付物。

---

## 三、运行时可达面：25 / 464 = 5.4%

从三个真入口沿已解析的 import 图做闭包（`node .ua/runtime-surface.cjs`）：

| 入口 | 可达文件 |
|---|---:|
| `tools/ws_daemon.mjs`（守衡） | 15 |
| `research/governance/skeleton/judge.py`（引擎） | 6 |
| `base/text_stage.py`（基座） | 4 |
| **并集** | **25** |

**口径警告（按 §2.4.1「这句话比我的输入大吗？」）**：这一步只证「**不被 import**」，
**不证「是死的」**。本项目 AGENTS.md §2.7 自己把可执行面分成两段 ——
「`ws_daemon.mjs` import 得到的」与「**被 spawn 的脚本**」。
验算器、CLI 工具、被 daemon spawn 的脚本都不在 import 闭包里，但它们**是活的**。
所以下面的「引用普查」才是死代码判据，本节的 5.4% 只说明**静态加载面很窄**。

---

## 四、引用普查：32 / 155 个可执行文件无人提及

`node .ua/reference-census.cjs` —— 对每个已跟踪可执行文件，统计**其它**已跟踪文本文件里
出现其 basename 的个数（import、spawn、shell 调用、散文都算）。

| 档位 | 个数 |
|---|---:|
| 0 次被提及 | **32** |
| 恰 1 次 | 8 |
| ≥2 次 | 115 |

0 次被提及的 32 个（`node .ua/reference-census.cjs`）：

- `.tools/cdp.mjs` · `.tools/cdp2.mjs` · `.tools/cdpeval.mjs` · `.tools/obp.py`
- `research/distill/assets/gen_s4_rule_engine_shard.py`
- `research/governance/_scratch/R5-integration-scripts/` 下 **17 个**（`fix_113.py` `fix_86.py`
  `fix_amazon.py` `fix_bpa.py` `fix_disclaimer.py` `fix_enforce.py` `fix_eubpa.py` `fix_final.py`
  `fix_ftc.py` `fix_g7.py` `fix_g8.py` `fix_gaps.py` `fix_inv.py` `fix_inv2.py` `fix_prio.py`
  `step_platforms.py` `step_platforms_dedupe.py` `step_platforms_fixup.py`）
- `tools/_ingest_batch10.py` · `tools/build_product_line_matrix.py`
- `tools/probe_cards.mjs` · `tools/probe_cards2.mjs` · `tools/probe_models.mjs` · `tools/probe_tools.mjs`
- `tools/ws_handshake.mjs` · `tools/ws_raw_trace.mjs` · `tools/ws_watch.sh`

### ⚠ 我先把这条数字算错过一次，必须记下来

第一版算出「39 个 0 次被提及」。**是错的**，而且错法与 AGENTS.md §2.4.1 描述的完全同形：

`git ls-files`（不带 `-z`）对含非 ASCII 的路径**加引号转义**（`"ADR/ADR-0009-\350\257\255…"`），
于是 `fs.readFileSync` 对**每一个中文名文件**都失败 → 那些文件**静默地没进统计池** →
所有引用计数被**系统性低估**，而 0 次桶被**系统性高估**。
表现是「查无此人」式的假否定：`wire_context_guards.py` 被算成 0 次，
实际被 4 个文件提到（`git ls-files -z | xargs -0 grep -l wire_context_guards`）。

修法：`git ls-files -z` + 按 NUL 切分，并在跳过文件时**打印**（现在只剩 7 个 PNG/ICO，符合预期）。
修后 39 → **32**。

---

## 五、文档可达性：README 只能到 1 个文档；143 / 226 个文档没有入口

`node .ua/doc-reachability.cjs` —— 从 `README.md` 与 `AGENTS.md` 出发，
沿 markdown 链接 / 反引号路径 / 目录相对路径做闭包。

| 起点 | 闭包内文件 | 其中文档 |
|---|---:|---:|
| `README.md` | **1** | **1** |
| `AGENTS.md` | 227 | 83 |
| 两者并集 | 227 | **83** |

- **`README.md` 只有 2 行**：`# audit_multi_content` + `内容审计`。它的链接闭包是它自己。
- **不可达文档 143 / 226 = 63.3%**，其中：
  - `skills-inventory/refs/`（第三方 vendored）**71**
  - **第一方 72 个**，按目录：`research/distill` 20 · `kb2agent-research/raw` 18 ·
    `research/readmes` 10 · `research/governance` 8 · 其余散件
- 最刺眼的一类：**6 篇 `PMO/守衡-*-修复记录.md`**（发送者身份 / 回复截断 / 时间基准 / 查名 /
  看不见的东西要说出来 / 创建全景图讨论稿）**全部不可达** ——
  而 AGENTS.md §2.2 恰恰把这些事故记录当作「别再踩的坑」的**唯一存档**。

---

## 六、ADR 状态双源冲突：2 / 14 不一致，且都朝「索引比文件更权威」

`node .ua/adr-status-check.cjs`

| ADR | 文件自述 | `ADR/README.md` 索引表 |
|---|---|---|
| **ADR-0001 数据权威与双账本** | `proposed` | **`accepted`** ❌ |
| **ADR-0012 判定引擎产品化** | `proposed` | **`accepted`** ❌ |
| 其余 12 个 | — | 一致 ✅ |

两份都读过全文，**没有任何一处后续状态更新**（`ADR-0001` 第 3 行 `- 状态：\`proposed\``
是全文唯一的状态行；`ADR-0012` 第 3 行同理）。

冲击面：`ADR/README.md` 的「当前决策台账」是**可达的**（在 83 个可达文档里），
是人和 agent 查「哪条决策已生效」的主入口；而 ADR-0001 与 ADR-0012 分别是
**数据权威方向**与**引擎契约形状**两条最底层的决策。
→ 读索引表会把两条 `proposed` 当成已决，**没有任何东西会红**。

同时：14 个 ADR 里 **7 个是 `proposed`**（0001/0002/0003/0005/0011/0012/0014），
7 个 `accepted`（0004/0006/0007/0008/0009/0010/0013）——
而 AGENTS.md 通篇把 ADR 当「绑定约束」引用。

---

## 七、验证层在图里不可见：`tested_by` 边 = 0

- 图谱边类型统计里 **`tested_by` = 0 条**，被标 `tested` 标签的节点 **0 个**。
- 但仓库里有 **25 个 `verify_*.py` / `verify_*.mjs` / `audit_*.py`** 验算器。
- 原因不是「没写」：是**命名无法机械映射**。实测每个 verifier 的真实目标：

| 验算器 | 真实目标 |
|---|---|
| `tools/verify_engine_contract.py` | `research/governance/skeleton/` + `tools/ab_engine_diff.py` + `tools/push_receipts.py` |
| `tools/verify_kb.py` | `tools/kb_build.py` `kb_classes.py` `kb_facts.py` `kb_gaps.py` `kb_query.py` |
| `tools/verify_cards.mjs` | `tools/reply-cards/cards.mjs` `contract.md` `README.md` |
| `tools/verify_feishu_index.py` | `tools/feishu_index.py` |
| `tools/verify_prd_baseline.py` | `tools/lark_find.py` `tools/verify_depad.py` |
| `tools/verify_pending.py` | `tools/agent/prd_baseline.mjs` |
| `tools/verify_shouheng_ops.py` | `tools/ws_daemon.mjs` `tools/verify_pending.py` `tools/verify_skill.py` |
| `tools/verify_landing.py` | `tools/lp_stability.py` `research/live/snapshot-*.json` |

`verify_shouheng_ops` 验的是 `ws_daemon.mjs`，`verify_pending` 验的是 `prd_baseline.mjs` ——
**没有一条能靠名字推出来**。

> 也就是说：本项目**最重要的工程纪律（§2.1「每个子系统都有自证入口」）在它自己的结构图里
> 完全不可见**。覆盖关系只存在于每个 verifier 的源码文本里，任何工具都读不到。
> 这是「工程债务」与「文档债务」的交点：纪律存在、执行存在、**登记不存在**。

---

## 八、层耦合矩阵（12 层）

`node .ua/graph-diagnosis.cjs` → `.ua/graph-diagnosis.md`

层内边 737 / 跨层边 451 → 层内占比 62.0%。

值得注意的几格：

| 源层 | 目标层 | 边数 | 占源层出边 |
|---|---:|---:|---:|
| `pmo-operations` | `shouheng-daemon` | 66 | **50.4%** |
| `shouheng-daemon` | —（**只有层内**） | 53 | **100.0%** |
| `foundation-rules` | 层内 / research / engine / harness | 52 / 26 / 24 / 14 | 33.8% / 16.9% / 15.6% / 9.1% |

两条读数：

1. **`PMO/` 是守衡的事实规格书**：PMO 层一半的出边指向守护进程。
   `PMO/守衡-回复卡片模版与语域规程.md` 这样的运营文档，实际承担的是**接口规格**的角色 ——
   但它住在「运营与事故记录层」里。**规格与记录混住**。
2. **守护进程层 100% 是层内边**：`tools/agent/` + `tools/reply-cards/` + `ws_daemon.mjs`
   **不向 ADR 层、不向引擎层、不向验证层伸一条边**。它遵守的规则（§2.5 形态决策唯一、
   §2.7 重启闸门）只写在 `AGENTS.md` 里，**代码里没有任何指回规则的链接**。

各层的边类型构成还显示：`foundation-rules`（ADR + AGENTS.md）**160 条 `documents` 边、
0 条 `calls`/`imports`** —— 纯声明层，与代码之间**没有任何机械连接**（无 `configures`、无 `validates`）。
这正是 §2.4「写进文档的上限必须指得出哪一行在拦它」在结构上的成因。

---

## 九、图自身的质量读数（诚实项）

- 节点 1362 / 边 2657 / 层 12 / 导览 11 步；内联确定性校验 **issues = 0**、orphan 警告 113。
- 合并脚本报告：**109 条悬挂边被丢弃**；assemble-reviewer 复核后**恢复了 98 条**
  （94 条是 `file:` 与 `document:`/`config:` 前缀不一致导致，不是真悬挂）。
- assemble-reviewer 另报（本报告未独立复核，标为**未测**）：
  - 文档交叉引用只有约 50% 变成边，**至少还有 187 条缺失**（下界）；
  - **113 个零边节点**，含 `research/readmes/*` 六篇与 29KB 的 `SKILLS-INVENTORY.md`；
  - **355 个源码定义（跨 81 个代码文件）没有节点** → 图谱**低估**了函数数量。
- 导览 11 步、层 12 个，覆盖 586/586 文件级节点，归一化报告 0 条异常。

---

## 十、我自己造的两处污染（已处理，记下来）

1. **`.pnpm-store/` 480MB / 7306 个文件落在项目根**。我在 `skills/Understand-Anything/`
   下跑 `pnpm install` 时，DSH 的 pnpm wrapper 把 store 建到了**工作目录上级的项目根**。
   已 `rm -rf` 回收，UA 的 core 仍正常加载（`node -e "import(...)"` 78 exports）。
   `git status` 已确认干净。
2. **`.ua/` 未被 `.gitignore` 忽略**（`git check-ignore .ua/knowledge-graph.json` 无输出）。
   按项目自己的 ADR-0013 分级，`.ua/` 是「机器生成 / 可复算」= **L2 入盘不入历史**，
   应当进 `.gitignore`。但 `.gitignore` 抬头写明「改动本文件 = 改动分级 = 需回到 ADR-0013 §三 同步」——
   所以这**不是我该顺手改的**，列为待决。

---

## 十一、本轮验算器读数（我自己跑的，非转述）

| 命令 | 退出码 | 末行 |
|---|---:|---|
| `python3 tools/verify_engine_contract.py` | 0 | 验收 176/176 全绿 |
| `python3 tools/verify_kb.py` | 0 | ✅ G1 + G3 全部通过 |
| `node tools/verify_cards.mjs` | 0 | 通过 232 项 · 不通过 0 项 |
| `python3 tools/verify_depad.py` | 0 | 扫描 6475 个文本文件 · 被填充 **0** 个 |
| `python3 tools/verify_pending.py` | 0 | 结构全过、无到期未收；最近到期 2026-10-02 |
| `python3 tools/lark_people.py --controls` | 0 | ✅ 全部 23 项通过 |
| `node tools/agent/prd_baseline.mjs --selftest` | 0 | ✅ 38 项全过 |
| **`python3 tools/verify_prd_baseline.py`** | **1** | ❌ **23 项中 2 项失败** |
| **`python3 tools/verify_shouheng_ops.py`** | **2** | ⚠ 1 项未测（E1 跑不了 `ps`） |

### 十一.1 §2.4.2 的机制**第一次完整跑通**了 —— 而且这次是**真事**，不是演练

> ⚠️ 本节是**移动靶**：我测量期间，另有一个会话在同一个工作区上并发修复这条。
> 下面把「我测到的」「日志里读到的」「现在是什么」分开写。

**我测到的那一刻（12:1x）—— 唯一的红：**

```
❌ [L3] C3 上游 sha256 = 索引指纹 · 美国市场内容治理项目-一页纸计划书.md
        索引 d78fdef6d7f2b61e… / 现场 8211abc09a731dc1…
❌ [L3] C4 上游字数 = chars · 美国市场内容治理项目-一页纸计划书.md
        索引 2831 / 现场 2932
```

独立复核（我另跑，不靠该 verifier）：本地副本 6367 B / 2831 字符 / sha256 `d78fdef6…`，
与索引记录**逐字一致**；`git status -- PRD/feishu/` 当时为空。
→ **本地副本 == 基线，漂移只发生在上游。**

**日志里读到的完整链路**（`PMO/logs/ws_daemon.log`，非我推断）：

```
[+59988.195s] ★ 收到消息 chat=oc_3eadfdb4… msg=om_x100b641446c3f8a0c3177456d544701
                原文="<p>https://momcozy-in.feishu.cn/wiki/NB55wAq8liEOdKkquL2cgtPEnmg?…</p>"
[+59991.214s]    · 基线检查[link] 退出码 1 —— 上游改版了（这是本检查存在的理由）
[+59992.088s]    · 基线告警已发到 oc_3eadfdb47618327d41f9be9d07786258
[+60006.577s]    · 基线检查跳过（冷却中（上次 2026-09-22T04:13:56.732Z，不足 30 分钟））
```

**三层全在**：判据（退 1）· 触发者（`[link]`）· 对外告警（已发到群）。
这是 §2.4.2 造出来之后**第一次真的兑现**，而且抓到的是一件真事。

**时间线（全部是读数，不是估计）：**

| 时点 | 事件 | 出处 |
|---|---|---|
| 2026-09-22 11:12:14 | 上游就地改版（`obj_edit_time_bj`） | 重拉后索引新记录 |
| 2026-09-22 12:13:53 | 有人在群里粘了一个飞书 wiki 链接 | `ws_daemon.log` |
| 2026-09-22 12:13:56 | `[link]` 检查退 1，告警已发 | `ws_daemon.log` |
| 2026-09-22 12:25:14 | 重拉两份正文 + 重记读数（并记 `prev_fingerprints`） | 索引 `fetched_at` |
| 2026-09-22 12:2x | `verify_prd_baseline.py` 23/23 **全过** | 我复跑 |

- **曝光窗口 = 1 小时 01 分 42 秒**（11:12:14 → 12:13:56）
- **发现→修好 = 11 分 18 秒**

**但有一条必须说清楚，否则就是把这次成功读大了（§2.4.1「这句话比我的输入大吗？」）：**

被抓到的这次是**就地改版**（同一个 wiki 节点 `BlKswESKkiyfakkWGIgcFKx3nxf`，没产生新链接），
而**发现它的却正是 `[link]` 触发器** —— 因为有人把 wiki 链接**又粘了一遍**。
而 §2.4.2 给「每日兜底」写的立项理由**恰恰是**：「改的是已经推过的那一篇，那种改动不会产生新链接」。

> 也就是说：**每日兜底这条路径，至今没有被任何一次真实漂移验证过。**
> 今晨的 daily 检查跑在改版**之前**（`p_lastDay=2026-09-21`，今日 daily 已在启动时跑过，
> 而改版发生在 11:12），所以它**还没来得及轮到** —— 不是它失败了。
> 但按本项目的规矩「**没红过的断言不算验证过它**」，它现在仍是**未验证**，不是**已验证**。

**顺带一个结构性观察**：触发它的链接指向的是 `NB55wAq8liEOdKkquL2cgtPEnmg`，
**不是**漂移那份文档的 token。也就是说 `[link]` 触发会重扫**全部**基线文档，而不是只看被链接的那一份 ——
这是对的设计，也说明**覆盖不依赖用户粘对链接**。

### 十一.2 一处退 2：`ps` 被沙箱拒绝 → 进程存活**未测**

`verify_shouheng_ops.py` 的 **E1** 落 `⚠ 未测`（`PermissionError: 'ps'`），
脚本按 §2.4.2 同口径退 **2**，且 **H7** 断言「有红时也必须报出有未测」。
这是**设计正确**的表现（未测 ≠ 通过 ≠ 红），但后果是：
**在这台机器的这个沙箱里，这个自证永远不可能变绿。**

### 十一.3 一个与文档相反的读数 —— **我先写错了，这里更正**（按「读数」写，不写成「文档错了」）

`AGENTS.md` §2.1 断言「**本环境里用 Python 写出的文件**，`stat` 报的大小会比真实内容多 4096 字节」。
我的第一版笔记写的是「本轮实测不支持这个触发条件」，理由是：
我自己用 Python 写的 `.ua/` 产物逐个查 `stat` vs 真实字节**全部相等**，
且 `verify_depad.py` 报「扫描 6475 个文本文件 · 被填充 **0** 个」。

**这条写错了，必须更正。** 在我写完之后，`AGENTS.md` 被并发会话更新，§2.1 补了一格
**2026-09-22 的实测**：判据是「**写这个文件的进程是不是 Python**」，而不是「谁做的重定向」——

```bash
python3 tools/lark_find.py readdoc <token> > 'PRD/feishu/美国市场内容治理项目-一页纸计划书.md'
#   产出方是 python3，重定向只是 shell 转手 —— 文件照样进填充态：
#   verify_depad.py → 真实 6540B · stat 10636B
```

而这**正是 `verify_prd_baseline.py` 变红时自己打印出来的那条重拉命令**。

**我错在哪一层**：我把「**我没复现出它**」写成了「**这个触发条件不成立**」。
我的输入只是「我这几个文件没被填充」+「此刻全仓 0 个被填充」；
我说出去的却是关于**触发条件本身**的判断。**这句话比我的输入大**（§2.4.1）。
正确的写法是：**「我这次的写入没有复现；今天另一次写入复现了；两者不矛盾。」**

**当前读数（我复核，2026-09-22 12:2x）**：

| 判据 | 读数 |
|---|---|
| `python3 tools/verify_depad.py` | 扫描 **6486** 个文本文件 · 被填充 **0** 个 · 其他不一致 0 个 |
| `PRD/feishu/美国市场内容治理项目-一页纸计划书.md` | stat=6540 · 真实字节=6540 · 2932 字符 · sha256 `8211abc0…` |
| `PRD/feishu/内容审查Agent-PRD-v1.0.md` | stat=14614 · 真实字节=14614 · 7144 字符 |

→ **此刻全仓 0 个填充态**，因为并发会话刚刚跑过 `verify_depad.py --fix`。
**这不证明触发条件消失** —— 只说明「刚清过」。
本节保留的价值是它自己的教训：**我用一个 0 去否定一条带日期的实测读数，这是同一个病。**
