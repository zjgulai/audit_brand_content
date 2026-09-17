# 回执账本损失记录（2026-09-16）

## 发生了什么

开发者在给 `tools/push_receipts.py` 做联调时，把 `cp` 的参数写反了：

```
cp _tmp_test_receipts.jsonl receipts_backup_tmp.jsonl   # 本想备份真账本，实际把 1 行的测试文件当成了备份
cat _tmp_test_receipts.jsonl >> receipts.jsonl          # 真账本 5 → 6 行
cp receipts_backup_tmp.jsonl receipts.jsonl             # 「恢复」把 6 行真账本覆盖成 1 行测试回执
```

真账本原有 **5 条**回执，现仅存 **1 条**。

| run_id | origin | 状态 |
|---|---|---|
| `jr-99e37b2be5-183e745c` | dev-batchA | ❌ 丢失 |
| `jr-a4cef47206-f6c1c02d` | dev-batchA | ❌ 丢失 |
| `jr-d512451d71-c48eb73e` | dev-batchA | ❌ 丢失 |
| `jr-0d07595186-a9ec0a59` | shouheng | ❌ 丢失 |
| `jr-a2cbfa4a97-ef3a5af7` | shouheng | ✅ 已恢复（逐字，来自事故前的一次读取输出） |

## 为什么不补

那 4 条的内容（`input_sha256` / `verdict_digest` / `issued_at` …）**无法重建**：
原文没有落库（ADR-0008 决策 2），时间是真实发生过的时刻。

★ **补一条内容靠猜的回执，比缺一条更坏。** 回执的整个存在理由是
ADR-0005 约束 5：「没有 receipt 的判定不算发生过」。伪造一条，就把
「不确定发生过没有」变成了「确定发生过」—— 那是账本最不能犯的错。

## 可恢复性核查（已做，结论：不可恢复）

- `git`：本目录不是仓库（`fatal: not a git repository`）。
- APFS 本地快照：`tmutil listlocalsnapshots /` → 空。
- Time Machine：未配置（`PreferencesVersion = 6`，无备份目的地）。
- `~/.Trash`：空。
- 全仓搜索残留副本（`_data/backup-*/`、`manifest-history.jsonl`）：无。

## 三道防重犯的机制（本轮加）

1. **前缀哈希链**（`receipts.chain.json` + `append_receipt` 维护）：
   账本每追加一条，记下「截至第 N 行的整文件 sha256」。校验时逐条重算 ——
   截断、改写、覆盖都会红。**账本从此是只追加的，而且这件事可机检。**
2. **测试回执不得写进生产账本**：`append_receipt` 在 `path == RECEIPTS_PATH`
   且 `origin == "test"` 时**硬失败**。这次事故的直接成因正是「一条测试回执
   进了真账本」—— 闸门就装在那一步上。
3. **`--status` 记行数**：推送工具每次运行都打印账本行数，人看得见它变小。

## 这一条为什么写进仓库而不是私下修掉

与 §七 异议留档里的「飞书词表跑两次翻倍」同一种形状：
**一个把「我以为」当成「它是」的动作，而两次的输出看起来都正常。**
那次是 `batch_create` 追加 + 验证比集合；这次是 `cp` 反向 + 「恢复」动作本身
就是破坏动作。两次都不是技术难题，是**没有一道检查站在那一步上**。
