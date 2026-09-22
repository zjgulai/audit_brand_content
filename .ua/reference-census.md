# 引用普查：每个可执行文件被多少个其它已跟踪文件提到过

已跟踪可执行文件 161 个（.py/.mjs/.js/.sh/.plist）。对每个文件，统计**其它**已跟踪文本文件里出现其文件名 basename 的个数。

> 口径说明：这一步**只证「有没有人提到它」**，不证「它是否是活的」。
> 被 mention 也可能只是散文里提了一句；0 次 mention 则是更强的信号 ——
> 它既不被 import、也不被 spawn、也不在文档里出现。

| 档位 | 个数 |
|---|---|
| 0 次被提及 | 31 |
| 1 次 | 7 |
| ≥2 次 | 123 |

## 0 次被提及（最强的死代码候选）

- `.tools/cdp.mjs`
- `.tools/cdp2.mjs`
- `.tools/cdpeval.mjs`
- `.tools/obp.py`
- `research/distill/assets/gen_s4_rule_engine_shard.py`
- `research/governance/_scratch/R5-integration-scripts/fix_113.py`
- `research/governance/_scratch/R5-integration-scripts/fix_86.py`
- `research/governance/_scratch/R5-integration-scripts/fix_amazon.py`
- `research/governance/_scratch/R5-integration-scripts/fix_bpa.py`
- `research/governance/_scratch/R5-integration-scripts/fix_disclaimer.py`
- `research/governance/_scratch/R5-integration-scripts/fix_enforce.py`
- `research/governance/_scratch/R5-integration-scripts/fix_eubpa.py`
- `research/governance/_scratch/R5-integration-scripts/fix_final.py`
- `research/governance/_scratch/R5-integration-scripts/fix_ftc.py`
- `research/governance/_scratch/R5-integration-scripts/fix_g7.py`
- `research/governance/_scratch/R5-integration-scripts/fix_g8.py`
- `research/governance/_scratch/R5-integration-scripts/fix_gaps.py`
- `research/governance/_scratch/R5-integration-scripts/fix_inv.py`
- `research/governance/_scratch/R5-integration-scripts/fix_inv2.py`
- `research/governance/_scratch/R5-integration-scripts/fix_prio.py`
- `research/governance/_scratch/R5-integration-scripts/step_platforms_dedupe.py`
- `research/governance/_scratch/R5-integration-scripts/step_platforms_fixup.py`
- `research/governance/_scratch/R5-integration-scripts/step_platforms.py`
- `tools/build_product_line_matrix.py`
- `tools/probe_cards.mjs`
- `tools/probe_cards2.mjs`
- `tools/probe_models.mjs`
- `tools/probe_tools.mjs`
- `tools/ws_handshake.mjs`
- `tools/ws_raw_trace.mjs`
- `tools/ws_watch.sh`

## 恰 1 次被提及（只在一处出现）

- `dsh-browser-ext/background.js`  ← 仅 `dsh-browser-ext/manifest.json`
- `research/governance/annotations/disambiguate_pump.py`  ← 仅 `research/kb/索引-本地资产.json`
- `tools/_ingest_batch10.py`  ← 仅 `tools/verify_doc_reachability.py`
- `tools/_rc_d37.py`  ← 仅 `research/governance/skeleton/legal-decisions-v1.json`
- `tools/send_once.mjs`  ← 仅 `PMO/守衡-架构说明.md`
- `tools/verify_open_items.py`  ← 仅 `tools/verifier-coverage.json`
- `tools/ws_test.mjs`  ← 仅 `PMO/守衡-飞书打通测试报告.md`

## 被提及最多的 25 个

| 文件 | 被提及次数 |
|---|---|
| `base/contract.py` | 33 |
| `tools/verify_engine_contract.py` | 29 |
| `tools/verify_kb.py` | 27 |
| `research/governance/skeleton/score.py` | 26 |
| `research/governance/skeleton/judge.py` | 19 |
| `tools/agent/feishu.mjs` | 19 |
| `tools/ws_daemon.mjs` | 19 |
| `tools/agent/agent.mjs` | 18 |
| `tools/offline_replay.py` | 18 |
| `research/governance/skeleton/vocab.py` | 16 |
| `tools/agent/config.mjs` | 16 |
| `tools/kb_classes.py` | 16 |
| `research/governance/audit_rule_table.py` | 14 |
| `tools/reply-cards/cards.mjs` | 14 |
| `tools/agent/tools.mjs` | 13 |
| `tools/kb_gaps.py` | 13 |
| `tools/kb_query.py` | 13 |
| `research/governance/audit_migration_fidelity.py` | 12 |
| `research/governance/skeleton/severity.py` | 12 |
| `tools/feishu_index.py` | 12 |
| `tools/kb_facts.py` | 12 |
| `tools/kb_materials_lark.py` | 12 |
| `tools/lark_find.py` | 12 |
| `tools/lark_people.py` | 12 |
| `tools/lp_consistency.py` | 12 |