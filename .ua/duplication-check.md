# 重复度实测（`tools/` + `research/` 下的 Python）

口径：按**函数体逐行相同**判重（去空行、去整行注释、≥4 行才算）。
被统计的 .py 文件：118；函数总数：906

## 完全相同函数体的组

**8 组**，组内重复行数合计 **90** 行。

| 函数名 | 行数 | 份数 | 出现在 |
|---|---:|---:|---|
| `check` | 6 | 7 | `base/change_detect.py:215`<br>`base/contract.py:744`<br>`base/judge_adapter.py:285`<br>`base/media.py:944`<br>`base/sync_rules.py:532`<br>`base/text_stage.py:407`<br>`tools/lp_stability.py:707` |
| `call` | 12 | 2 | `tools/kb_materials_lark.py:49`<br>`tools/migrate_kb_to_lark.py:45` |
| `scan_bash_trap` | 10 | 2 | `tools/verify_shouheng_ops.py:122`<br>`tools/verify_shouheng_ops.py:149` |
| `grab` | 9 | 2 | `research/governance/audit_make_errorbook.py:60`<br>`research/governance/audit_rule_consistency.py:35` |
| `percentiles` | 8 | 2 | `base/media.py:404`<br>`base/text_stage.py:80` |
| `split_md_row` | 6 | 2 | `research/governance/audit_make_errorbook.py:51`<br>`research/governance/audit_rule_consistency.py:26` |
| `match` | 5 | 2 | `tools/heldout_test.py:91`<br>`tools/offline_replay.py:208` |
| `load_snapshot` | 4 | 2 | `tools/heldout_test.py:47`<br>`tools/offline_replay.py:54` |

## 同名函数（跨文件重名，弱证据但指向复制粘贴）

**69** 个函数名出现在 ≥2 个文件里。Top 25：

| 函数名 | 文件数 | 举例 |
|---|---:|---|
| `main` | 92 | `.tools/obp.py`<br>`base/change_detect.py`<br>`base/contract.py` |
| `check` | 12 | `base/change_detect.py`<br>`base/contract.py`<br>`base/judge_adapter.py` |
| `__init__` | 9 | `base/media.py`<br>`research/governance/audit_citation_fidelity.py`<br>`research/governance/skeleton/score.py` |
| `token` | 9 | `base/sync_rules.py`<br>`tools/check_contact_scope.py`<br>`tools/kb_materials_lark.py` |
| `selftest` | 7 | `base/change_detect.py`<br>`base/contract.py`<br>`base/judge_adapter.py` |
| `build` | 6 | `research/governance/audit_migration_fidelity.py`<br>`research/governance/audit_risk_label.py`<br>`tools/feishu_index.py` |
| `band_target` | 6 | `research/governance/skeleton/build_context_guards.py`<br>`research/governance/skeleton/lint_context_guards.py`<br>`research/governance/skeleton/lint_whitelist.py` |
| `call` | 6 | `tools/kb_materials_lark.py`<br>`tools/migrate_kb_to_lark.py`<br>`tools/migrate_vocab_to_lark.py` |
| `pct` | 5 | `base/media.py`<br>`base/text_stage.py`<br>`tools/heldout_test.py` |
| `scan` | 5 | `research/distill/style_scan.py`<br>`research/governance/audit_citation_fidelity.py`<br>`research/governance/audit_evidence_integrity.py` |
| `split_md_row` | 5 | `research/governance/audit_make_errorbook.py`<br>`research/governance/audit_records.py`<br>`research/governance/audit_records_deep.py` |
| `judge` | 4 | `base/change_detect.py`<br>`research/governance/skeleton/judge.py`<br>`tools/verify_pending.py` |
| `render` | 4 | `research/distill/assets/gen_s4_rule_engine_shard.py`<br>`research/governance/audit_risk_label.py`<br>`research/governance/skeleton/judge.py` |
| `load` | 4 | `research/governance/audit_field_profile.py`<br>`research/governance/audit_migration_fidelity.py`<br>`research/governance/skeleton/score.py` |
| `_req` | 4 | `tools/kb_snapshot.py`<br>`tools/lark_find.py`<br>`tools/lark_people.py` |
| `get` | 3 | `.tools/obp.py`<br>`base/sync_rules.py`<br>`tools/lark_probe.py` |
| `percentiles` | 3 | `base/media.py`<br>`base/text_stage.py`<br>`tools/lp_metrics.py` |
| `p` | 3 | `base/media.py`<br>`base/text_stage.py`<br>`tools/lp_metrics.py` |
| `fetch` | 3 | `research/governance/fetch_seller_and_payment_policies.py`<br>`tools/verify_external.py`<br>`tools/verify_vocab_lark.py` |
| `add` | 3 | `research/governance/lint_rules.py`<br>`tools/verify_kb.py`<br>`tools/verify_prd_baseline.py` |
| `split_terms` | 3 | `research/governance/skeleton/build_context_guards.py`<br>`research/governance/skeleton/build_whitelist.py`<br>`research/governance/skeleton/lint_whitelist.py` |
| `report` | 3 | `research/governance/skeleton/score.py`<br>`tools/_migrate_ids_batch12.py`<br>`tools/verify_pending.py` |
| `sha` | 3 | `tools/_migrate_ids_batch12.py`<br>`tools/_rc_d37.py`<br>`tools/_rc_d38.py` |
| `write` | 3 | `tools/feishu_index.py`<br>`tools/kb_materials_lark.py`<br>`tools/route_landing_findings.py` |
| `txt` | 3 | `tools/kb_materials_lark.py`<br>`tools/migrate_kb_to_lark.py`<br>`tools/migrate_vocab_to_lark.py` |

## 家族视角：每个前缀家族有多少文件、多少函数、多少是同名的

| 家族 | 文件数 | 函数数 |
|---|---:|---:|
| `fix_*` | 15 | 2 |
| `verify_*` | 13 | 128 |
| `audit_*` | 13 | 123 |
| `kb_*` | 11 | 77 |
| `lp_*` | 5 | 66 |
| `build_*` | 4 | 12 |
| `migrate_*` | 4 | 37 |
| `step_*` | 3 | 1 |
| `lint_*` | 3 | 10 |
| `lark_*` | 3 | 23 |
| `text_*` | 2 | 24 |
| `measure_*` | 2 | 11 |
| `wire_*` | 2 | 3 |
| `obp.py` | 1 | 4 |
| `change_*` | 1 | 9 |

## 复现

```bash
node .ua/duplication-check.cjs
```