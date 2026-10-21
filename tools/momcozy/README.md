# tools/momcozy

> 本目录:Momcozy 采集器实现 + 试点入口。
> 方案文件:`PMO/Momcozy-采集方案-20261017-v1.1.md`(只读参考)。

## 范围

采集 `support.momcozy.com` + `momcozy.com` 的产品 + 支持文档对账数据。

**产物落到仓外** `~/audit-data/momcozy-catalog/<series-key>/`（可用
`MOMCOZY_CATALOG_ROOT` 覆盖）。

> ★★ **2026-10-21 改**：原先写的是「产物落到 `PMO/audit/momcozy-catalog/`」——**仓内**。
> 本仓是**公开**仓（`AGENTS.md` §2.6），而这里下载的是客户产品图；
> 那种写法只靠 `.gitignore` 挡着，而 `verify_download_governance.py` 的 DG-2
> 整条立论正是「**`.gitignore` 不是边界**，`git add -f` 照样能进」。
> 现在落盘根由 `assert_outside_repo()` **硬拒**仓内路径（退 2，不是警告后继续）。

## 怎么跑

```bash
# 试点只跑 breast-pump 一个 series（落盘根在仓外）
MOMCOZY_CATALOG_ROOT=~/audit-data/momcozy-catalog \
  python3 tools/momcozy/batch_download.py \
  ~/audit-data/momcozy-catalog/breast-pump

# 单张图的集成 smoke（真实网络；落盘同样在仓外）
node tools/momcozy/lib/image.smoke.mjs
```

> ⚠️ 本目录**没有** `scrape_breast_pump.mjs` 与 `lib/selfcheck.mjs` ——
> README 曾引用它们，但盘上不存在。要么补齐，要么删掉这条引用（目前是删掉）。

## 怎么验(本项目 §2.1)

```bash
# 写完任何 .mjs 之后立即跑(本会话发生过 +4096 填充)
python3 tools/verify_depad.py

# 写完 python 校验脚本以后(本项目 §2.1.1)
rm -rf ~/Library/Caches/com.apple.python/Users/lute/Project/audit_multi_content
```

## 边界

- 只读/只写:`tools/momcozy/` + **仓外** `~/audit-data/momcozy-catalog/`
- 不动:`Playbook/` `PRD/` `tools/` 下任何 verifier
- 不爬评论 / PDF / 客服区(项目红线 §2.6)
- **不往仓内写任何采集产物** —— 执行点是 `assert_outside_repo()` 与
  `image.smoke.mjs` 的仓外守卫
