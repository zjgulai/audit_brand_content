# 运行时可达面（从两个真入口沿 import 图算出）

入口：`tools/ws_daemon.mjs`（守衡守护进程）、`research/governance/skeleton/judge.py`（判定引擎）、`base/text_stage.py`（基座管道）

| 入口 | 可达文件数 |
|---|---|
| `tools/ws_daemon.mjs` | 15 |
| `research/governance/skeleton/judge.py` | 6 |
| `base/text_stage.py` | 4 |
| **并集（去重）** | **25** |
| 全部已跟踪文件 | 464 |

→ 运行时可达标面占全仓 **5.4%**；
  其余 **439** 个文件（94.6%）不在任何运行时路径上。

## 守护进程可达集（守衡上线时真正被加载的东西）

- `tools/agent/agent.mjs`
- `tools/agent/config.mjs`
- `tools/agent/feishu.mjs`
- `tools/agent/llm.mjs`
- `tools/agent/memory.mjs`
- `tools/agent/persona.mjs`
- `tools/agent/prd_baseline.mjs`
- `tools/agent/timefmt.mjs`
- `tools/agent/tools.mjs`
- `tools/agent/truncate.mjs`
- `tools/reply-cards/cards.mjs`
- `tools/reply-cards/envelope.mjs`
- `tools/reply-cards/index.mjs`
- `tools/reply-cards/registry.mjs`
- `tools/ws_daemon.mjs`

## 判定引擎可达集

- `research/governance/skeleton/engine_manifest.py`
- `research/governance/skeleton/judge.py`
- `research/governance/skeleton/matcher.py`
- `research/governance/skeleton/score.py`
- `research/governance/skeleton/severity.py`
- `research/governance/skeleton/vocab.py`

## 基座管道可达集

- `base/contract.py`
- `base/judge_adapter.py`
- `base/media.py`
- `base/text_stage.py`

## 不在任何运行时路径上的**可执行**文件（129 / 154）

按目录：

- 45  `research/governance`
- 3  `research/distill`
- 3  `skills-inventory/refs`
- 1  `.tools/cdp.mjs`
- 1  `.tools/cdp2.mjs`
- 1  `.tools/cdpeval.mjs`
- 1  `.tools/obp.py`
- 1  `base/build_ocr.sh`
- 1  `base/change_detect.py`
- 1  `base/sync_rules.py`
- 1  `base/verify_base.py`
- 1  `dsh-browser-ext/background.js`
- 1  `dsh-browser-ext/content.js`
- 1  `dsh-browser-ext/panel`
- 1  `research/kb`
- 1  `tools/_ingest_batch10.py`
- 1  `tools/_ingest_batch12.py`
- 1  `tools/_migrate_ids_batch11.py`
- 1  `tools/_migrate_ids_batch12.py`
- 1  `tools/_rc_d37.py`
- 1  `tools/_rc_d38.py`
- 1  `tools/_recon_legacy.py`
- 1  `tools/ab_engine_diff.py`
- 1  `tools/build_product_line_matrix.py`
- 1  `tools/check_contact_scope.py`
- 1  `tools/decisions.py`
- 1  `tools/feishu_index.py`
- 1  `tools/heldout_test.py`
- 1  `tools/kb_analyze.py`
- 1  `tools/kb_build.py`
- 1  `tools/kb_classes.py`
- 1  `tools/kb_evidence.py`
- 1  `tools/kb_facts.py`
- 1  `tools/kb_gaps.py`
- 1  `tools/kb_index.py`
- 1  `tools/kb_materials_data.py`
- 1  `tools/kb_materials_lark.py`
- 1  `tools/kb_query.py`
- 1  `tools/kb_snapshot.py`
- 1  `tools/lark_find.py`
- 1  `tools/lark_people.py`
- 1  `tools/lark_probe.py`
- 1  `tools/live_snapshot.py`
- 1  `tools/lp_consistency.py`
- 1  `tools/lp_extract.py`
- 1  `tools/lp_fetch.py`
- 1  `tools/lp_metrics.py`
- 1  `tools/lp_stability.py`
- 1  `tools/measure_cross_line_homographs.py`
- 1  `tools/migrate_kb_to_lark.py`
- 1  `tools/migrate_vocab_to_lark.py`
- 1  `tools/migrate_whitelist_to_lark.py`
- 1  `tools/offline_replay.py`
- 1  `tools/probe_cards.mjs`
- 1  `tools/probe_cards2.mjs`
- 1  `tools/probe_models.mjs`
- 1  `tools/probe_tools.mjs`
- 1  `tools/push_receipts.py`
- 1  `tools/reply-cards`
- 1  `tools/restart_shouheng.sh`
- 1  `tools/route_landing_findings.py`
- 1  `tools/run_shouheng.sh`
- 1  `tools/send_once.mjs`
- 1  `tools/shouheng.py`
- 1  `tools/test_agent.mjs`
- 1  `tools/verify_cards.mjs`
- 1  `tools/verify_depad.py`
- 1  `tools/verify_engine_contract.py`
- 1  `tools/verify_external.py`
- 1  `tools/verify_feishu_index.py`
- 1  `tools/verify_kb.py`
- 1  `tools/verify_landing.py`
- 1  `tools/verify_pending.py`
- 1  `tools/verify_prd_baseline.py`
- 1  `tools/verify_shouheng_ops.py`
- 1  `tools/verify_skill.py`
- 1  `tools/verify_vocab_lark.py`
- 1  `tools/ws_handshake.mjs`
- 1  `tools/ws_raw_trace.mjs`
- 1  `tools/ws_test.mjs`
- 1  `tools/ws_watch.sh`

<details><summary>逐个列出</summary>

- `.tools/cdp.mjs`
- `.tools/cdp2.mjs`
- `.tools/cdpeval.mjs`
- `.tools/obp.py`
- `base/build_ocr.sh`
- `base/change_detect.py`
- `base/sync_rules.py`
- `base/verify_base.py`
- `dsh-browser-ext/background.js`
- `dsh-browser-ext/content.js`
- `dsh-browser-ext/panel/assets/index.js`
- `research/distill/assets/gen_s4_rule_engine_shard.py`
- `research/distill/style_scan.py`
- `research/distill/verify_citations.py`
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
- `research/governance/_scratch/R5-integration-scripts/step_platforms.py`
- `research/governance/_scratch/R5-integration-scripts/step_platforms_dedupe.py`
- `research/governance/_scratch/R5-integration-scripts/step_platforms_fixup.py`
- `research/governance/annotations/audit_permit_paths.py`
- `research/governance/annotations/classify_with_guide.py`
- `research/governance/annotations/disambiguate_pump.py`
- `research/governance/annotations/measure_alpha.py`
- `research/governance/audit_citation_fidelity.py`
- `research/governance/audit_dimensions.py`
- `research/governance/audit_escape_layers.py`
- `research/governance/audit_evidence_integrity.py`
- `research/governance/audit_field_profile.py`
- `research/governance/audit_make_errorbook.py`
- `research/governance/audit_migration_fidelity.py`
- `research/governance/audit_records.py`
- `research/governance/audit_records_deep.py`
- `research/governance/audit_risk_label.py`
- `research/governance/audit_rule_consistency.py`
- `research/governance/audit_rule_table.py`
- `research/governance/fetch_seller_and_payment_policies.py`
- `research/governance/lint_rules.py`
- `research/governance/skeleton/attribute_misses.py`
- `research/governance/skeleton/build_context_guards.py`
- `research/governance/skeleton/build_rules.py`
- `research/governance/skeleton/build_whitelist.py`
- `research/governance/skeleton/lint_context_guards.py`
- `research/governance/skeleton/lint_whitelist.py`
- `research/governance/skeleton/migrate_misrouted_guards.py`
- `research/governance/skeleton/wire_context_guards.py`
- `research/governance/skeleton/wire_whitelist.py`
- `research/kb/load.py`
- `skills-inventory/refs/brand-docx/scripts/cli.py`
- `skills-inventory/refs/iflytek-text-proofread/scripts/text_proofread.py`
- `skills-inventory/refs/subtitle-correction/subtitle-correction/scripts/subtitle_tool.py`
- `tools/_ingest_batch10.py`
- `tools/_ingest_batch12.py`
- `tools/_migrate_ids_batch11.py`
- `tools/_migrate_ids_batch12.py`
- `tools/_rc_d37.py`
- `tools/_rc_d38.py`
- `tools/_recon_legacy.py`
- `tools/ab_engine_diff.py`
- `tools/build_product_line_matrix.py`
- `tools/check_contact_scope.py`
- `tools/decisions.py`
- `tools/feishu_index.py`
- `tools/heldout_test.py`
- `tools/kb_analyze.py`
- `tools/kb_build.py`
- `tools/kb_classes.py`
- `tools/kb_evidence.py`
- `tools/kb_facts.py`
- `tools/kb_gaps.py`
- `tools/kb_index.py`
- `tools/kb_materials_data.py`
- `tools/kb_materials_lark.py`
- `tools/kb_query.py`
- `tools/kb_snapshot.py`
- `tools/lark_find.py`
- `tools/lark_people.py`
- `tools/lark_probe.py`
- `tools/live_snapshot.py`
- `tools/lp_consistency.py`
- `tools/lp_extract.py`
- `tools/lp_fetch.py`
- `tools/lp_metrics.py`
- `tools/lp_stability.py`
- `tools/measure_cross_line_homographs.py`
- `tools/migrate_kb_to_lark.py`
- `tools/migrate_vocab_to_lark.py`
- `tools/migrate_whitelist_to_lark.py`
- `tools/offline_replay.py`
- `tools/probe_cards.mjs`
- `tools/probe_cards2.mjs`
- `tools/probe_models.mjs`
- `tools/probe_tools.mjs`
- `tools/push_receipts.py`
- `tools/reply-cards/cli.mjs`
- `tools/restart_shouheng.sh`
- `tools/route_landing_findings.py`
- `tools/run_shouheng.sh`
- `tools/send_once.mjs`
- `tools/shouheng.py`
- `tools/test_agent.mjs`
- `tools/verify_cards.mjs`
- `tools/verify_depad.py`
- `tools/verify_engine_contract.py`
- `tools/verify_external.py`
- `tools/verify_feishu_index.py`
- `tools/verify_kb.py`
- `tools/verify_landing.py`
- `tools/verify_pending.py`
- `tools/verify_prd_baseline.py`
- `tools/verify_shouheng_ops.py`
- `tools/verify_skill.py`
- `tools/verify_vocab_lark.py`
- `tools/ws_handshake.mjs`
- `tools/ws_raw_trace.mjs`
- `tools/ws_test.mjs`
- `tools/ws_watch.sh`

</details>