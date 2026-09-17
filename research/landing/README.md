# 落地页内容获取实测（批次 C）

> 委托：2026-09-16 用户批准「先 C 后 A」。
> 上游依据：法务 Sharon《202608 营销内容生命周期内容合规审核规范建设》§（二）后续安排
> 　→ 本地全文：`research/kb/materials/202608-营销内容生命周期内容合规审核规范建设-需求框架整理.txt`
> 方法论：`research/method/codex_research-方法论提炼.md`（工具只补证据）

---

## 这个批次回答什么

**法务验证表第二层：「工具能否稳定获取并处理目标内容」。**

法务原文逐字——指标是它定的，不是我们编的：

> **可用性及覆盖能力** ｜ 内容获取成功率 / 页面/素材识别完整度 / 处理耗时等
> **标准**：满足初步验证范围内的基本覆盖和稳定运行要求

这三个指标在本批次之前**一个数字都没有**。

---

## 一页纸读数

见 `内容获取实测报告.md`。复现：

```bash
cd /Users/lute/Project/audit_multi_content
python3 tools/lp_fetch.py --check        # ① 先核对 robots.txt（不发页面请求）
python3 tools/lp_fetch.py                # ② 抓取 92 个落地页
python3 tools/lp_extract.py --show 3     # ③ 提取六类要素
python3 tools/lp_metrics.py --md         # ④ 三个指标
python3 tools/lp_consistency.py          # ⑤ 广告 vs 落地页 / 跨 locale
python3 tools/verify_landing.py          # ⑥ 验收（V1–V6）
```

---

## 文件地图

| 文件 | 内容 |
|---|---|
| `方案.md` | 北极星、三个指标的操作化定义、范围边界、六条验收 |
| `urls.json` | 204 条广告引用 → 92 个唯一 URL，带地区/平台/品线/`record_id` 反查 |
| `抓取结果.json` | 逐 URL 的获取事实（status / bytes / elapsed / sha256 / final_url） |
| `要素提取.json` | 逐页六类要素：title · body_text · images · claims · links · locale_signals |
| `指标.json` | 三个指标的汇总读数，含分域名/分类型切片与**失败明细** |
| `一致性分析.json` | 表 A 广告文案 vs 落地页；表 B 跨 locale 版本一致性 |
| `内容获取实测报告.md` | 面向法务的报告 |
| `_evidence/snapshot-<ts>/` | 原始响应（内容寻址 gzip）+ `MANIFEST.json` |

代码：`tools/lp_fetch.py` · `lp_extract.py` · `lp_metrics.py` · `lp_consistency.py` · `verify_landing.py`

---

## 为什么是这 92 个 URL

`research/live/snapshot-20260916T050845Z.json` 的 `ad_copy` 表（291 条广告）里，
**204 条带落地页 URL**，去重后 **92 个唯一页面**。这组 URL 同时满足三件事：

1. 它们是**真实投放中的广告**的落地页 —— 法务「公司实际对外发布了什么」的最直接样本；
2. 10 个产品跨 2–10 个地区站 —— 现成的「跨页面、跨版本整改闭环」测试集；
3. 其中 23 篇 SEO 博客 —— **没有进入任何人工审核流程**的内容类型。

---

## 边界（先读这段）

1. **只读**。不登录、不提交表单；抓取前逐域名核对 `robots.txt`，被禁止的 URL 不发请求。
2. **礼貌**。同域名串行、间隔 ≥1.2s、带真实 UA、遵守 429/`Retry-After`。
3. **不判定**（ADR-0005）。本批次只回答「拿不拿得到、拿得全不全、快不快」。
   `claims` 是「页面上出现了哪些声明性表述」的**清单**，不是「这些声明是否合规」的结论。
4. **一次快照，不是持续监测**。定时化待明确消费者后再评估。

---

## 与其他批次的关系

| 批次 | 状态 | 说明 |
|---|---|---|
| **C · 落地页内容获取**（本目录） | 执行中 | 法务验证表**第二层** |
| A · 判定引擎产品化 | 待办 | 把散落脚本收成稳定契约并接入守衡 |
| B · 规则识别能力验证 | 待办 | 法务验证表**第一层**，需 A 的稳定契约才能出可复现报告 |

**C 的产物是 A 的新输入**：落地页正文是判定引擎此前从未处理过的内容类型
（此前只吃广告文案）。这一步会让「引擎的输入契约」必须显式化。
