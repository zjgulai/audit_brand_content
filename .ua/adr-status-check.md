# ADR 状态双源对照：`ADR/README.md` 索引表 vs 每个 ADR 文件自己的 `状态` 字段

口径：ADR 文件取头部 12 行内第一条含「状态」的行里的枚举值；索引表取该 ADR 行内出现枚举值的单元格。
枚举：proposed / accepted / superseded / rejected

| ADR | 文件自述 | 索引表 | 一致 |
|---|---|---|---|
| ADR-0001 | `proposed` | `accepted` | ❌ **不一致** |
| ADR-0002 | `proposed` | `proposed` | ✅ |
| ADR-0003 | `proposed` | `proposed` | ✅ |
| ADR-0004 | `accepted` | `accepted` | ✅ |
| ADR-0005 | `proposed` | `proposed` | ✅ |
| ADR-0006 | `accepted` | `accepted` | ✅ |
| ADR-0007 | `accepted` | `accepted` | ✅ |
| ADR-0008 | `accepted` | `accepted` | ✅ |
| ADR-0009 | `accepted` | `accepted` | ✅ |
| ADR-0010 | `accepted` | `accepted` | ✅ |
| ADR-0011 | `proposed` | `proposed` | ✅ |
| ADR-0012 | `proposed` | `accepted` | ❌ **不一致** |
| ADR-0013 | `accepted` | `accepted` | ✅ |
| ADR-0014 | `proposed` | `proposed` | ✅ |

## 结论：14 个 ADR 中 **2 个两处不一致**

不一致清单：

- **ADR-0001** — 文件自述 `proposed`，索引表写 `accepted`（`ADR/ADR-0001-数据权威与双账本.md` vs `ADR/README.md`）
- **ADR-0012** — 文件自述 `proposed`，索引表写 `accepted`（`ADR/ADR-0012-判定引擎产品化与处置分层.md` vs `ADR/README.md`）

> 影响：`ADR/README.md` 的「当前决策台账」是读者与 agent 查「哪条决策已生效」的**主要入口**
> （它不在 143 个不可达文档里 —— 它可达）。表与文件冲突时，没有任何东西会红。

## 复现

```bash
node .ua/adr-status-check.cjs
```