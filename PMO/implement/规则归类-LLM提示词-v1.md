# 规则归类 LLM 提示词 v1（2026-10-19）

> 用途：把一条**规则**归类到七个审查轴之一。这是「规则归类」，不是「内容判定」。
> 事实前提：纯文本规则（正则/关键词）在这个任务上只能到 **22.07%**（UNKNOWN 57.42%），已实测。
> 因此本提示词是 `classify_rule(rule, llm=...)` 的模型侧契约。

---

## 1. 输入

单条规则的以下字段（全部来自规则库，不含任何基准标签）：

| 字段 | 必填 | 说明 |
|---|---|---|
| `rule_text` | ✅ | 规则正文（触发条件 / 判定 / 处置三段的自然语言） |
| `condition` | — | 结构化命中条件（若有） |
| `subcategory_original` | — | 原子类名（**仅作参考，不得作为判定依据**） |
| `category_original` | — | 原一级分类（**仅作参考，不得作为判定依据**） |
| `nature_raw` | — | 原表「规则性质」，值域 atomic/inductive（与 rule_nature 无关） |

> ⚠️ **禁止输入**：`primary_initial`、`primary_reviewed`、`quality_tag`、`policy_fragment`。
> 这些是标注结果或派生标签，喂给模型等于告诉答案。

## 2. 输出契约

严格 JSON，不要解释文字：

```json
{
  "primary": "FACT|CLAIM|DISC|SCENE|RIGHT|CHAN|BRAND",
  "secondary": "同上或 null",
  "rule_nature": "prohibition|mandate|disclosure|substantiation|recommendation",
  "jurisdiction": "GLOBAL|US|CA|EU|UK|CN|BR|AU|SG|AT|BH|PLATFORM|MULTI",
  "confidence": "high|medium|low",
  "reason": "一句话：按第几条判定条件命中，为什么不是相邻轴",
  "unknown": null
}
```

判不了时：

```json
{"primary": null, "unknown": "U3", "reason": "为什么判不了"}
```

## 3. 系统提示词（可直接使用）

```
你是一个内容合规规则的分类器。任务：判断一条规则要求的是哪一种审查动作。

七轴（按判定顺序，先命中先归）：
1 CHAN 渠道 — 这条内容能不能在这个平台/地区/版位/以这种素材投放
2 RIGHT 权利 — 使用真人/未成年人/AI 人物/第三方标识，授权链成立吗
3 SCENE 场景 — 内容演示的动作，受众照做会不会受伤
4 DISC 披露 — 必须让受众看到的信息元素，说全了吗
5 BRAND 品牌 — 事实全真、证据齐全，是否仍因调性/立场/情绪操纵/贬损竞品而不该这样说
6 FACT 事实 — 这句话说的知识/参数/功能/场景，与可核验事实一致吗
7 CLAIM 宣称 — 这条对外宣称，拿得出与断言强度相称、可核查、范围匹配的证据吗

关键分界（最常判错的地方）：
- 「改成 2~3 天」= FACT（改数值）；「补充一句就医提示」= DISC（加披露）。两者都出现时，
  看**规则的主动作**是什么：改数值 → FACT；加一句独立的告知 → DISC。
- 「研究人群 ≠ 推荐对象」= FACT（适用人群事实错误）；「没有证据支持这个断言」= CLAIM。
- 「补充证据来源」是修订元语言，不构成 DISC；只有要求「向受众展示某条信息」才是 DISC。
- 「画面/镜头/示范」出现但动作是「补充说明」→ DISC；只有动作本身不安全 → SCENE。
- 「标语/焦虑/紧迫感/贬损」→ BRAND；但「竞品对比没数据」→ CLAIM。
- 规则正文里的「原表述：… 修订为：… 修订原因：…」是格式，不是义务类型；
  真正的动作在「修订为」后面那句祈使句里。

判定步骤：
1. 先找「修订为 / 应 / 必须 / 需 / 建议」后面的**祈使动作**
2. 问这个动作修复的是什么：换渠道(CHAN) / 拿授权(RIGHT) / 改动作(SCENE) /
   补受众可见信息(DISC) / 改表达(BRAND) / 改与来源不符的事实(FACT) / 补证据或降断言(CLAIM)
3. 只选一个 primary。确实同时有两个独立动作时才填 secondary（删掉前者后者仍独立成立）
4. 判不了就返回 unknown，code 用 U3（指代不明）或 U9（七轴均不命中）

输出严格 JSON，不要 markdown 围栏，不要解释。
```

## 4. 用户消息模板

```
规则正文：
{rule_text}

结构化条件（可能为空）：
{condition}

仅作参考、不得作为判定依据：
- 原一级分类：{category_original}
- 原子类名：{subcategory_original}
- 原表性质：{nature_raw}
```

## 5. 评测方法

| 项 | 值 |
|---|---|
| 基准 | 512 条（七轴、非 needs_split、非 policy_fragment） |
| 抽样 | 分层抽样 65 条（`/tmp/llm_eval_sample.json`），按轴比例 |
| 指标 | `axis_exact`（primary 完全一致）/ `unknown_rate` / `secondary_exact` |
| 门槛 | `axis_exact ≥ 95%`、`unknown_rate ≤ 5%` |
| 对照 | 纯文本 22.07%（已实测）、category 多数轴 85.16%（含统计先验，仅作参照） |

## 6. 已知风险

1. **模型可能见过这批规则的原文**（公开法规、FTC 指南）。凡来自公开来源的规则，模型可能"背过答案"。需要在评测里区分「内部规则」与「公开法规规则」，分别报读数。
2. **`subcategory_original` 是强提示**。已验证：子类 → 多数轴 56/56 与 gold 相同。若模型大量依赖子类名，等于换了一种泄漏。**必须跑一次「隐藏子类名」的盲测**，报两个读数。
3. **`reason` 字段必须能指到具体判定条件**，否则无法人工复核。要求模型写「按第 N 条」。
4. 未测：模型在 `needs_split` 聚合体上的行为（这类应直接返回 SPLIT_REQUIRED，不调模型）。

## 7. 接入结构

```python
def classify_rule(rule, llm=None):
    """
    llm: callable(prompt: str) -> str，可注入。
         None → 返回 status="UNKNOWN", unknown_code="U11"（无模型可用）。
         不得回退到关键词猜测。
    """
```

**U11 = 无模型可用**，需加入规范 §2.6 的 UNKNOWN code 表。
