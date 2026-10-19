# `tools/` 工具索引

> **这份文件不是自证表。** 各子系统的验收入口在 [`AGENTS.md`](../AGENTS.md) §2.1 那张表
> 与 [`README.md`](../README.md) 第三节 —— 改了哪个子系统就跑哪一条，这里不重复。
>
> 这份索引回答的是**另一个问题**：`tools/` 下有一批**探针与诊断器**，它们不在任何自证链上、
> 平时也不跑，于是「留在盘上」但**没人找得回来**。2026-09-22 的结构性诊断
> （`.ua/debt-engineering.md` §E-2.1）点名的就是这件事，它给的治法不是删掉它们，而是
> **建这样一份索引**：一行一个 —— 什么时候用它、产物落哪。
>
> 为什么保留而不删（诊断原话）：诊断类探针的价值**就在故障时**。下次长连接静默失效、
> 模型忽然不发起工具调用时，重新写一个探针的代价远大于现在写这一行。

---

## 一、探针 / 诊断器（平时不跑，故障时直接用）

| 工具 | 什么时候用它 | 需要什么 | 产物 |
|---|---|---|---|
| [`probe_models.mjs`](./probe_models.mjs) | 换模型、配额报错、想知道**当前帐号能调到哪些模型 id** 时 | `DEEPSEEK_API_KEY`（脚本自己从 `~/.dsh/.credentials.yaml` 读） | 打到 stdout（模型清单 + 逐模型一次试调用） |
| [`probe_tools.mjs`](./probe_tools.mjs) | 模型**不发起 function calling** / 工具调用格式变了时 | 同上 | 打到 stdout（`finish_reason` / `tool_calls`） |
| [`ws_handshake.mjs`](./ws_handshake.mjs) | 守衡「连不上飞书」时，先分清是**凭据**问题还是**网络**问题 | 读 `~/.dsh/credentials/shouheng-lark.json` | 打到 stdout（open / error / close 三个事件与耗时） |
| [`ws_raw_trace.mjs`](./ws_raw_trace.mjs) | 连接**建立了但守衡收不到消息**（SDK 层看不出死了）时 —— 绕开 SDK 看原始帧 | 同上 | 打到 stdout（原始帧；**不落盘**） |
| [`ws_watch.sh`](./ws_watch.sh) | 平时想看**守衡此刻在干什么**（事件流） | 无（日志路径由脚本位置推导） | 跟随 `PMO/logs/`；用法见它自己的头注释 |
| [`probe_cards.mjs`](./probe_cards.mjs) · [`probe_cards2.mjs`](./probe_cards2.mjs) | 飞书卡片 schema 又变了、要**重测白名单**时 | 飞书凭据 | 打到 stdout / `PMO/logs/card_probe.jsonl`（**该产物在 `.gitignore` 里**）。结论的固化处是 [`reply-cards/contract.md`](./reply-cards/contract.md) —— 那份的每一条都是**实测**出来的，改前者要同步后者 |
| [`build_product_line_matrix.py`](./build_product_line_matrix.py) | 要给产品**重新发一份品线确认表**时 | 无 | 覆盖 `research/governance/品线确认表.csv` |

> ⚠️ **`build_product_line_matrix.py` 是这批里唯一会写已入库文件的**（其余都只打 stdout）。
> 它写的 `product_lines` 是**收窄动作** —— 它自己的注释就写着「写错一个值会让规则在所有品线上
> 静默消失（漏报）」，而这个脚本**没有自证**、也不在 `verify_engine_contract.py` 的覆盖里。
> 跑它之前先 `git diff` 一次产物。这条不是建议，是 §2.2 第 1 条的实例。

## 二、`.tools/` —— 本仓自己的浏览器 / 标准库工具

`.tools/` **不是**第三方依赖目录（第三方在 `.vendor/`，见 `ADR-0013` §三）：这里的
几个脚本是本仓自己写的，`.tools/bin/` 是本仓自己编译的 OCR 二进制（源码 `base/ocr_vision.m`）。

| 工具 | 什么时候用它 | 需要什么 |
|---|---|---|
| [`.tools/cdp.mjs`](../.tools/cdp.mjs) | 要在一个**已开着远程调试端口**的 Chrome 上跑脚本（端口 `CDP_PORT`，默认 9222） | `--remote-debugging-port` 起着的 Chrome |
| [`.tools/cdp2.mjs`](../.tools/cdp2.mjs) | 同上，第二个端口（默认 9223），支持从文件载入脚本 | 同上 |
| [`.tools/cdpeval.mjs`](../.tools/cdpeval.mjs) | 只想在页面里**求值一条表达式**（最短路径） | 同上 |
| [`.tools/obp.py`](../.tools/obp.py) | 要读 **ISO OBP**（在线浏览平台）上某份标准的条文原文时 | 无凭据（走 anonymous 读通道）；会落一个 `*_obp_datapackage.json` |

## 三、`tools/` 下的功能家族（一眼看全，别一个个猜）

| 家族 | 干什么 | 入口文档 |
|---|---|---|
| `verify_*.py` · `verify_*.mjs` | **各子系统自证**。要跑哪条看 `AGENTS.md` §2.1 | `AGENTS.md` §2.1 · [`verifier-coverage.json`](./verifier-coverage.json) |
| `kb_*.py` | 需求知识库：建库 / 查询 / 缺口 / 条款 / 台账 | [`research/kb/README.md`](../research/kb/README.md) |
| `lp_*.py` | 落地页抓取与指标（批次 C 的管道） | [`research/landing/README.md`](../research/landing/README.md) |
| `lark_*.py` | 飞书 HTTP 与人员/文档查找 | `AGENTS.md` §2.1（`lark_people.py --controls` 是自证入口） |
| `migrate_*.py` | **一次性**迁移脚本（把本地词表/规则/知识库推到飞书表）。已跑完，**别再跑** —— 同名表已存在时它会拒绝（这是设计） | `PMO/规则库-落地记录-20260922.md` 等落地记录 |
| `agent/` | 守衡（飞书机器人）的运行时。**改这个目录要先读 `AGENTS.md` §2.5 / §2.7** | [`PMO/守衡-架构说明.md`](../PMO/守衡-架构说明.md) |
| `reply-cards/` | 飞书卡片的模版、登记表与信封 | [`reply-cards/README.md`](./reply-cards/README.md) |

## 四、benchmark / 评测

| 工具 | 什么时候用它 | 需要什么 | 产物 |
|---|---|---|---|
| [`benchmark_media.py`](./benchmark_media.py) | 阶段 3 要跑 OCR/ASR 准确率，或先确认样本配对/gold 是否齐全时 | 样本按 `<id>.<媒体扩展名>` + `<id>.gold.txt` 命名；真实工具缺失时整模态记 untested | `--out` 指定 JSON（不指定则 stdout）；`--self-test` 不依赖任何真实工具 |

> 这条工具**不安装、不下载**：ASR 侧对 faster-whisper 用 `local_files_only=True`，
> 对 openai-whisper 先检查本地模型文件。工具缺失退 **2（未测）**，不是通过。
> 样本与 gold 的交付要求见 [`PMO/implement/阶段3-gold样本需求.md`](../PMO/implement/阶段3-gold样本需求.md)。

## 五、任务与联调入口

| 工具 | 什么时候用它 | 产物 / 退出 |
|---|---|---|
| [`case_watch_tick.py`](./case_watch_tick.py) | C-51 转出后超时升级的执行点；scheduler 每次触发调一次。默认 **dry-run**，只有 `--apply` 才发通知/写台账；它自己不定时 | 台账/去重文件由参数指定；`--self-test` 自证；退 3 表示没跑起来 |
| [`test_verify_acceptance_run.py`](./test_verify_acceptance_run.py) | 验收执行器 `verify_acceptance_run.py` 的自测（只读真实验收表，反向对照用临时表） | stdout；0 全过 / 1 有红 |
| [`verify_api_integration.py`](./verify_api_integration.py) | API ↔ 落盘 IR 联调：smoke 链路产 IR，TestClient 挂 review-api，断言 decision/coverage/release_status 逐字段一致且 API 不重算 | 0 全过 / 1 有红 / 2 未测（缺 `httpx`/TestClient 时） |

---

## 这份索引自己也有执行点

它点名的工具一旦消失，会由 [`verify_reference_census.py`](./verify_reference_census.py) 的
**A7 段**抓住：那份普查要求「池子里不许有人**枚举**基线名单」——
本文件把几个零引用工具从「没人提过」变成「索引里有名字」，读数会从零引用面**移出**
（`★ 已改善`，不判红）；但若本文件把整份基线名单抄一遍，A7 就会红。
**「建索引」与「抄名单」在这里是两条不同的路**，判据分得开。
