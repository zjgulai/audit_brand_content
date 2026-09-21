## 4. 案例族 C：垂直合规 / 内容审核 Agent —— 「规则库 + 案例库 + 误判申诉」三件套

### C1. OpenAI Moderation：把「阈值」显式交给部署方，并要求用混淆矩阵定阈

**出处**：OpenAI 官方 Cookbook `examples/How_to_use_moderation.ipynb`（GitHub 原始文件，【一手】<https://github.com/openai/openai-cookbook/blob/main/examples/How_to_use_moderation.ipynb>）；配套 `examples/How_to_use_guardrails.ipynb`【一手】

**它的三层结构（官方章节标题，即"知识/规则"的三种组织方式）**：
1. **Input moderation**：在 LLM 之前/并行拦截有害输入。
2. **Output moderation**：在返回用户前校验模型输出。
3. **Custom moderation**：**不使用 Moderation API**，而是用一次额外的模型调用，按**调用方自定义的 `parameters`** 打分。官方给出的返回结构是严格的 JSON：
   ```
   { "flagged": bool, "reason": str, "parameters": { "political content": bool, "misinformation": bool } }
   ```
   ——即：**判定结论 + 理由 + 所用参数（规则）三元组**。`[推断]` 这正是"规则库驱动判定"的最小可审计形态。

**分类法（官方列出的 image moderation categories，【一手】）**：
`sexual` / `sexual-minors` / `harassment` / `harassment-threatening` / `hate` / `hate-threatening` / `illicit` / `illicit-violent` / `self-harm` / `self-harm-intent` / `self-harm-instructions` / `violence` / `violence-graphic`
注意其结构：**顶层类别 + 斜杠子类别**，且子类别是"更严重/更具体"的那一档。`[推断]` 这种"父类用于统计、子类用于处置"的两级分类法，是合规审核知识库的通用形状。

**阈值哲学（官方原文，本报告最重要的一段引用之一）**：
> "OpenAI has selected thresholds for moderation categories that **balance precision and recall for our use cases**, but **your use case or tolerance for moderation may be different**. Setting this threshold is a common area for optimization - we recommend **building an evaluation set and grading the results using a confusion matrix** to set the right tolerance for your moderation."

并明确写出代价方向：
> "More **false positives** leads to a **fractured user experience**, where customers get annoyed and the assistant seems less helpful.
> More **false negatives** can cause **lasting harm to your business**."

以及**同一模型在不同业务下阈值应不同**的例子：创意写作平台对某些敏感话题应把阈值调高以保留创作自由。

**延迟与成本的取舍（官方原文）**："send your moderations **asynchronously along with your main LLM call**. If your moderation gets triggered you send back a **placeholder response**, otherwise send back the LLM response."并提醒异步可能"lead to unnecessary costs"（因为内容若在进入 LLM 前就被拦，本可省掉生成成本）。

**Guardrails 手册补充的三条硬约束（【一手】`How_to_use_guardrails.ipynb`）**：
- Guardrail 的三方权衡是 **accuracy / latency / cost**；提升准确率的手段包括 fine-tune、few-shot，以及一句关键的表述：**"RAG can also be effective if you have a corpus of information that can help determine whether a piece of content is allowed or not."**——即：**把"允许/不允许"的判定知识本身当成检索语料**。
- **Guardrail 的已知失效模式**（官方自陈）：① "When using LLMs as a guardrail, be aware that they have **the same vulnerabilities as your base LLM call itself**"，例如 prompt injection 可能**同时**绕过 guardrail 与主调用；② "As conversations get longer, LLMs are more susceptible to **jailbreaking** as your instructions become **diluted** by the extra text"；③ 过度收紧会造成 **over-refusals**（"your guardrails reject innocuous user requests because there are similarities with prompt injection"）。
- **官方给的缓解手段（三条，直接可用）**：① "**combine guardrails with rules-based or more traditional machine learning models** for detection"；② "have guardrails that **only ever consider the latest message**, to alleviate the risks of the model being confused by a long conversation"；③ "**gradual roll-out with active monitoring of conversations**"，把新发现的行为模式"add more guardrails to cover these new types of behaviour, or **include them as training examples to your existing guardrails**"。
- **输出侧阈值举例**：官方示例用 G-Eval 式评分（domain + criteria + steps → 1–5 分），并"block anything scoring a **3 or higher**"；同时给出**按风险差异定阈**的示范——防 jailbreak 应用极低阈值，而宠物推荐场景愿接受少量漏判，因为"the worst that could happen is someone ends up with a Bichon Frise ... which though harmless will probably not cause lasting damage to our business"。

**对守衡的映射** `[推断]`：
| OpenAI 的做法 | 守衡的对应物 |
|---|---|
| Input / Output / Custom 三层 | 语境守卫（输入侧）+ 判定引擎（主体）+ 结论自检（输出侧） |
| `parameters` 随判定一起落库 | 判定结论必须记录"本次用了哪些规则/白名单版本" |
| 混淆矩阵定阈 | 守衡的评测必须分开统计**误判率（误报）**与**漏判率（漏放）**，而不是一个总分 |
| 官方缓解手段②"只看最新消息" | 语境守卫应考虑"只对当前待审内容 + 最小必要上下文"判定，避免长上下文稀释规则 |
| 官方缓解手段①"规则/传统模型混合" | 关键词/正则/白名单这类确定性检查**不应**交给模型 |

---

### C2. Google Perspective API：阈值所有权归部署方，且阈值会随模型漂移

**出处与证据强度说明**：`developers.perspectiveapi.com` 与 `support.perspectiveapi.com` 均为 JS 渲染（`web_fetch` 返回 `Loading` 骨架）。以下表述来自**搜索引擎返回的官方页面原句**与官方 GitHub 仓库，逐条标注证据强度。

- 【一手】`conversationai/perspectiveapi` 官方仓库 README（<https://github.com/conversationai/perspectiveapi>，经 `raw.githubusercontent.com` 读取）："Perspective is a free API that helps you host better conversations online. The API uses machine learning models to **score the perceived impact a comment might have on a conversation**. You can use this score to **give feedback to commenters, help moderators more easily review comments, allow readers to more easily find interesting or productive comments**"；由 **Jigsaw 与 Google Counter Abuse Technology 团队**在 Conversation-AI 研究计划下创建。
- 【官方·仅搜索摘要】官方 FAQ 页（`support.perspectiveapi.com/s/about-the-api-faqs`）原文：**"if you select a [threshold] ... need to update that threshold when the models update. However you may see that a specific score changed due to an update. Note that we are **not able to notify users each time an update is released**."**
  → **这是本报告最值得守衡记住的一条外部证据**：*阈值不是常量，模型更新会让同一个阈值的行为改变，而且厂商不会通知你*。因此阈值必须自带"校准日期 + 对应模型版本"。
- 【官方·仅搜索摘要】官方 Key Concepts 页（`.../about-the-api-key-concepts`）原文：主属性 **TOXICITY** 定义为 **"a rude, disrespectful, or unreasonable comment that is likely to make you leave a discussion"**；其他属性包括 **PROFANITY、THREAT、SEXUALLY_EXPLICIT** 等。
- 【官方·仅搜索摘要】官方 Limits 页（`.../about-the-api-limits-and-errors`）原文：默认配额为 **"an average of 1 query per second (QPS) for all Perspective projects"**，仅供测试与开发环境。
- 【搜索摘要中可见的官方描述】分数语义：`TOXICITY` 返回 **0.0–1.0** 的单个数值，且 `type` 为 **PROBABILITY**；即"模型估计约 X% 的人类评审者会认为该内容有毒"——**它衡量的是"感知影响"，不是"危害程度"**。
- 【二手，第三方分析】常见实践是把 **0.6–0.8** 区间用作"送人工复核"的阈值；但**该区间不是官方推荐值**，本报告不把它当事实使用。
- 【推断】第三方资料一致指出 Perspective **按单条评论孤立打分，不参考说话者、受众与对话上下文**，因此反讽/语境类内容误报率更高。这解释了为什么"语境守卫"这类组件在垂直审核里不可或缺。

**三件套的组织方式（从上述证据可确认的部分）**【推断 + 部分事实】：
- **规则库**：以"属性（attribute）"为规则单元，而非以"违规词"为单元；每条属性有独立定义句（如 TOXICITY 的定义）。
- **阈值库**：阈值**不属于 API，属于部署方**——API 只给概率，判定由调用方决定。这是"规则（属性定义）+ 策略（阈值）分离"的教科书式做法。
- **申诉/反馈**：官方 README 明确 score 可用于 "give feedback to commenters" 与 "help moderators review"，即**分数是给人用的输入，而非终局裁决**。

---
