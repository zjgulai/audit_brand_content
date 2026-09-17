# 标注指南 ANN-GUIDE-001：T1.4 ↔ T2.1.2 的判定边界

> **版本**：v2（v1 的 §7 数字与 B3/B4 拆分已被实测推翻，见 §9）
> **v2.1 补**：§6 增补记录级口径（由 α 实测暴露）；标题所指边界经实测修正，见下方「★ 范围修正」
> ### ★ 范围修正：真正的边界是 T1.4 ↔ T2.2.2，不是 T1.4 ↔ T2.1.2
>
> 本指南标题沿用 `topic-tree-v1.md` 缺口 G-ANNO-1 的原始表述「T1.4 ↔ T2.1.2」。
> **实测后必须修正**：51 条 H07 命中里，**没有任何一条落在 T2.1.2**。
>
> | 落点 | 条数 | 性质 |
> |---|---:|---|
> | **T1.4** | 12 | 疼痛词修饰器械名词，或对象未写出 |
> | **T1.5 / T1.4** | 5 | 疼痛词被病理名词限定（`blocages` / `verstopfte Milch`） |
> | **T2.2.2** | 34 | 疼痛词修饰**吸乳动作**名词 |
> | **T2.1.2** | **0** | —— |
>
> **T2.1.2（「缓解疼痛」作为针对疼痛本身的人体结果声明）在这批语料里根本不存在。**
> 这不是边界模糊，是**该叶子缺少存在证据**。
> 它是否为一个真实叶子，需要独立的证据集来确认 —— 在此之前，
> `topic-tree-v1.md` 应把 T2.1.2 标为**未证实叶子**，而非「有内容但边界待定」。
>
> **结论：真实且高频的边界是「医疗管辖（T1.4/T1.5） ↔ 机器性能管辖（T2.2.2）」。**

> **解决的缺口**：`topic-tree-v1.md` §3 的 **G-ANNO-1**
> **适用规则**：H07、U04（以及任何含「疼痛 / 不适 / 病理场景」术语的规则）
> **实测语料**：291 条广告中的 64 条疼痛/病理相关盲样 · 现行 H07 命中 51 条
> **写作日期**：2026-09-15

---

## 0. 为什么这件事必须先于规则改写

现行规则表里，H07 的 `boundary_content` 只有一句话：

```
疼痛功效承诺（pain-free/no pain/without pain/pain relief/less pain/缓解疼痛等；
吸奶疼痛因人而异，只可讲 comfort/gentle 舒适与缓解胀满不适 discomfort）
```

U04 的 `boundary_content` 写着：

```
疼痛/堵奶场景化名词表述（sore/painful/clogged ducts）：
需人工判定是痛点场景描述还是功效承诺；与 goodbye/no more/not anymore/relieve 等消除性表述连用应升级 H01/H07
```

**「需人工判定」这四个字就是问题本身。** 这条判定从未被写下来 —— 它在审核员脑子里，
不在任何文档里。于是 α 无法计算，H07 无法拆分，新审核员无法被培训。

---

## 1. 核心判据

> ### 疼痛词修饰的是【动作名词】还是【器械名词】—— 这决定管辖。
> ### 疼痛是被【承诺消除】还是被【描述为场景】—— 这决定等级。

| 问题 | 决定 | 层 |
|---|---|---|
| 疼痛词修饰**哪个名词**？ | **管辖**：T1.4 / T2.2.2 / T1.5 | 主题层 |
| 是**承诺**还是**场景描述**？ | **等级**：红 / 黄 / 不判 | 严重度层 |

**现行规则表把这两件事压成了一件**，这是边界模糊的根因。

---

## 2. 判据的来源：语法构词，不是语义推测

### 2.1 实测：51 条 H07 命中里，57 个素材段几乎全是一个模板的四语翻译

把全部含疼痛词且含动作词的素材段按「疼痛词 + 过程词」骨架归一化后：

| 次数 | 骨架 | 语言 |
|---:|---|---|
| 13 | `[PAIN] [PROC] mit hoher Effizienz, Auswahl zur Förderung des Milchflusses` | 德语 |
| 11 | `[PAIN] [PROC] With High Efficiency` | 英语 |
| 8 | `M5 Hands Free Breast [PROC] - [PAIN] [PROC] With High Efficiency` | 英语 |
| 4 | `[PROC] [PAIN]` | 法语（`Tirage sans douleur`） |
| 3 | `Momcozy - Erstklassige Freihändige Milchpumpe - [PAIN] [PROC]` | 德语 |

**51 条命中、57 个段，去重后只有 13 个模板，绝大多数是同一条英文素材的四语翻译。**

### 2.2 但这 57 个段不是同一种构词 —— 差异正好落在语种上

对每个疼痛段判定**疼痛词修饰的名词类型**：

| 构词 | 德语 | 法语 | 英语 | 西语 | 合计 |
|---|---:|---:|---:|---:|---:|
| **① 修饰动作名词**（`Abpumpen` / `Pump` / `Tirage` / `Pompage`） | 16 | 2 | 22 | 0 | **40** |
| **② 修饰器械名词**（`Tire-Lait` / `breast pump`） | 0 | 4 | 3 | 0 | **7** |
| **③ 两者皆可**（`Pump` 本身名词/动词同形） | 5 | 0 | 19 | 0 | 24 |
| **④ 词形表未覆盖**（`Extrae Leche Sin Dolor` / `indolore` 后置） | 0 | 9 | 3 | 2 | 14 |

> **关键行是 ② 与 ④**：判红的裸对象记录，全部落在**法语/西语** ——
> `Tire-Lait Sans Douleur` / `Extrae Leche Sin Dolor`。
> 疼痛词在那里是**加在器械名词上的形容词**：**「无痛的吸奶器」**。
>
> 而判黄的过程对象记录，覆盖**四种语言** ——
> `Schmerzfreies Abpumpen` / `Painlessly Pump` / `Tirage sans douleur` / `Pompage efficace et indolore`。
> 疼痛词是**加在动作名词上的**：**「无痛地吸乳」这个动作被描述了**。

**这不是语义推测，是构词事实。** 而且它给出了 B5 默认值的**语言依据**，
使「对象未写出 → 判红」从兜底条款变成一个可解释的规则。

---

## 3. 三问决策程序

> 对每个疼痛/不适素材段**独立**执行。**判定在素材段上做，不在整条广告上做**（见 §9 教训 L1）。

### 问题 A：这句话说的是疾病/损伤，还是过程/体验？

| 现象 | 判为 | 例 |
|---|---|---|
| 治疗 / 治愈 / 诊断 / 预防 / 消除 **某疾病** | **T1.1–T1.3**（交 H01/H02） | `treat mastitis`、`cure engorgement` |
| 疏通 / 清除 / 改善 **阻塞类病理** | **→ 问题 B（按 B1）** | `unclog ducts`、`Entlastung bei verstopfter Milch` |
| 症状缓解（对某种痛/不适的消除承诺） | **→ 问题 B** | `sans douleur`、`pain-free` |
| **只描述**疼痛场景，不含产品主张 | **→ 问题 C** | `Sore nipples?`、`Sore nipples are common.` |
| 吸乳/使用过程中的体验 | **T2.2 机器性能** | `quiet pumping`、`efficient pumping` |

> **A 与 B 的分工**：`treat/cure/prevent` 这类**动词**直接定案（交 H01）；
> 名词性/形容词性的**症状缓解**走 B，因为同一个痛可以落在三个不同管辖上。

### 问题 B：疼痛词修饰的是哪个名词？（**核心**）

> 判据优先级：**显式病理名 > 动作名词 > 器械名词 > 均无**

| # | 构词/对象 | 管辖 | 等级 | 证据要求 |
|---|---|---|---|---|
| **B1** | 疼痛词**修饰或被病理名词限定** —— mastitis / 乳腺炎 / nipple damage / 乳头损伤 / cracked nipple / verstopfte Milch / blocages / 堵奶 | **T1.5 · T1.4** | **红 L4** | 临床级 |
| **B2** | 疼痛词**修饰动作名词** —— `Abpumpen` / `Pump(ing)` / `Tirage` / `Pompage` / `Abpumpen` / 吸乳 | **T2.2.2 机器性能** | **黄 L2** | 产品测试 |
| **B3** | 疼痛词**修饰器械名词** —— `Tire-Lait` / `breast pump` / `wearable pump` / 吸奶器 | **T1.4**（对象未写出） | **红 L4** | 临床级，举证责任在投放方 |
| **B4** | **两者皆无**（构词表未覆盖、无名词可依） | **T1.4**（对象未写出） | **红 L4** | 同上 |

> **为什么 B3/B4 的默认值是红**：设计文档 §B「举证责任倒置」。当文案对象不可确定时，
> **由投放方证明它不是医疗主张**，而不是由审核方猜它是。这与 T2.3.2
> 「未标注来源的效果数据默认判红」是同一条原则。
>
> **B3/B4 不产生召回损失** —— 它们是现行表的默认行为，只是从「碰巧对了」变成「有理由地对」。

### 问题 C：承诺，还是场景描述？

| 现象 | 判定 | 例 |
|---|---|---|
| 消除性/结果性词 + 痛/病 | **功效承诺** → 按 B 定级 | `say goodbye to`、`no more`、`relieve`、`reduces`、`Entlastung`、`Soulage`、`告别`、`消除` |
| **裸形容词式主张**（无动词） | **功效承诺** → 按 B 定级 | `pain-free`、`sans douleur`、`schmerzfrei`、`sin dolor`、`无痛` |
| 疑问 / 共情 / 场景引导，**产品未被指为主语** | **场景描述，非功效** | `Sore nipples?`、`Tired of clogged ducts?` |
| 名词短语指代痛点对象（无动词、无产品） | **场景描述，非功效** | `sore nipples are common` |

---

## 4. U04 → H07 的升级规则（现行版本的缺陷）

现行 U04 边界说「与 goodbye/no more/relieve 连用时升级」——**这条规则条件不足**：
它只检查了「有没有消除性动词」，**没检查「被消除的是什么」**。

`Say goodbye to cold, painful pumping` 满足「goodbye + painful」的全部字面条件，
但被消除的是**吸乳这个动作的冷与痛**（解法是 360° 加热），不是疾病。
**按现行规则它必须升级到 H07 高危 —— 而这是错的。**

**正确的升级条件：**

```
升级到 T1.4 红  ⟺  有消除性/结果性表述 ∨ 裸形容词式主张
                 ∧  管辖落在 B1（病理）或 B3/B4（对象未写出）

降为 T2.2.2 黄  ⟺  管辖落在 B2（疼痛词修饰动作名词）
```

---

## 5. 边界与相邻规则的接口

| 相邻规则 | 关系 | 说明 |
|---|---|---|
| **H01 / H02** | **优先** | 出现 `treat/cure/prevent/diagnos` 或明确疾病名 → 交 H01，本指南不介入 |
| **M02**（吸力） | 并列 | `zero pain + strong suction` 是两个主张，**同叶不同规则**，互不吸收 |
| **M07**（奶流/效率） | 并列 | `smoother milk flow` 归 T2.1.3；与疼痛表述不互相吸收 |
| **H05**（虚假安全） | **独立且叠加** | `100% painless` **同时**构成 H07 + H05，**两边都出** |
| **U04** | **改为 context 字段** | C 表判为「场景描述」时，U04 **不出违规结论**，只记 context |
| **T9 安全词** | 不适用 | 实测 E3：安全词不是规则，当规则跑产生 142 次误报 |
| **qualifier_axis** | 正交 | `100%` / `never` / `guaranteed` 记入正交轴，**不改主题归属** |

---

## 6. 边界例（**必须逐条过，这是 α 的主要来源**）

> **[实测]** 来自 64 条盲样；**[构造]** 为触发边界而写。

| # | 文案 | 修饰的名词 | 管辖 | 等级 | 理由 |
|---|---|---|---|---|---|
| **E01** | `Schmerzfreies Abpumpen mit hoher Effizienz` **[实测]** | `Abpumpen`（动作） | T2.2.2 | 黄 L2 | 德语动词化名词，对象明确是吸乳动作 |
| **E02** | `Painlessly Pump With High Efficiency` **[实测]** | `Pump`（动作） | T2.2.2 | 黄 L2 | 副词修饰动词 |
| **E03** | `Tire-Lait Sans Douleur` **[实测]** | `Tire-Lait`（器械） | **T1.4** | **红 L4** | 形容词修饰器械 → 对象未写出 |
| **E04** | `Extrae Leche Sin Dolor` **[实测]** | 动词短语，无动作名词 | **T1.4** | **红 L4** | 构词表未覆盖 → 默认保守 |
| **E05** | `Pain-Free Wearable Pump` **[实测]** | `Pump`（器械） | **T1.4** | **红 L4** | 同 E03，英语侧同一构词 |
| **E06** | `Say goodbye to cold, painful pumping` **[实测]** | `pumping`（动作） | T2.2.2 | 黄 L2 | 解法是 360° 加热 → 体验而非医学 |
| **E07** | `Schmerzfreies Abpumpen …, Entlastung bei verstopfter Milch` **[实测]** | **两个名词** | T2.2.2 + **T1.5** | 黄 + **红** | **必须拆成两条结论**（B1 与 B2 并存） |
| **E08** | `Pompage efficace et indolore. Augmente la production de lait` **[实测]** | `Pompage`（动作） | T2.2.2 + T2.1.1 | 黄 L2 | 后半句属 H02，**同段两管辖** |
| **E09** | `M5 Smart's 105° flange + micro-vibration = painless pumping` **[实测]** | `pumping`（动作） | T2.2.2 | 黄 L2 | 有机制归因，**但机制不参与管辖判定**（见 §9 L2） |
| **E10** | `Experience Strong Suction with Zero Pain` **[实测]** | 无名词可依 | **T1.4** | **红 L4** | `suction` 是前文参数，**不是疼痛的修饰对象** |
| **E11** | `Sore nipples? Our pump helps.` **[构造]** | 病理对象 | **T1.4** | **红 L4** | 疑问句非承诺，但 `helps` 把产品指为主语 → 承诺成立 |
| **E12** | `Sore nipples are common while breastfeeding.` **[构造]** | 病理对象 | — | **不判** | 纯场景陈述，产品未被指为主语 |
| **E13** | `Eliminates nipple pain` **[构造]** | 病理对象 | **T1.4** | **红 L4** | 消除性动词 + 病理对象 |
| **E14** | `Comfortable, gentle pumping` **[实测]** | 动作名词，**无否定/消除** | T2.2.2 | **不判** | H07 边界明确保留 `comfort/gentle`。**见下方记录级口径** |
| **E15** | `Breastfeeding shouldn't hurt.` **[构造]** | 哺乳（非吸乳器） | **T1.4** | **红 L4** | 对象是哺乳不是器械，不落入 B2 |

> ### ★ 记录级口径（v2.1 补，由 α 实测暴露）
>
> α 实测中 5/64 条分歧全部来自**记录级口径未写明**，而非判定规则有歧义。补两条：
>
> **① `不判` 的两种含义必须区分 —— 记录级一律写 `不判`。**
>
> | 情形 | 段级 | **记录级** |
> |---|---|---|
> | 整条广告**没有任何**疼痛/不适/病理素材段 | 无段 | **`不判`** |
> | 有素材段，但该段是 `comfort`/`gentle` 这类**边界保留表述**（E14），不构成违规 | 该段记 `T2.2.2` + `不判` | **`不判`** |
> | 有素材段，且判为机器性能主张（如 `quiet pumping`） | 该段 `T2.2.2` + `黄 L2` | 按最严出 `黄 L2` |
>
> **即：机器性能语言本身不是违规。** 只有当它与疼痛/功效词结合时才产生等级。
> 实测：B004 / B027 / B055 / B061 因这一条写法不同产生 4 条假分歧 —— 它们含
> `Gentle and Secure Fit`、`Plus confortable` 等，**均应为记录级 `不判`**。
>
> **② 英语 `Pump` 同形：按 §3 B 步的 D1/D2/D3 三步走，不标存疑。**
>
> 判据由实测数据得出（全部 21 处「疼痛词 + 空格 + pump」中，`pump` 前的词只有三种）：
>
> | `pump` 前一个词 | 段数 | 判定 | 例 |
> |---|---:|---|---|
> | **段首** 或 **破折号后** | 11 + 8 | **动词原形 → 动作名词 → 黄 L2** | `Painlessly Pump With High Efficiency`、`… Breast Pump - Painlessly Pump …` |
> | **型号 / 限定语**（如 `M5`） | 2 | **名词短语中心语 → 器械名词 → 红 L4** | `Momcozy M5 Pain-Free Pump` |
>
> 因此 `Pump Like Baby's Latch — No Pain`（破折号后） → **黄 L2，不是存疑**。
> **O3 从此有确定答案，不再需要标注者自行裁量。**

> **E03/E05 vs E14 是本指南最需要守住的一对**：
> 判据不是「有没有提到疼痛」，而是**「疼痛词修饰的是器械、动作，还是什么都没修饰」**。
> `Pain-Free Pump`（修饰器械）→ 红；`comfortable pumping`（修饰动作且无否定）→ 不判。

---

## 7. 实测结果：51 条现行 H07 命中的重新归类

| 记录级结论 | 条数 | 触发桶 | 现行等级 | 建议等级 |
|---|---:|---|---|---|
| **仍判红** | **17** | B1 病理 **5 条** / B3 器械名词 **10 条** / B4 无名词可依 **2 条** | 红 | **红（不变）** |
| **降为黄** | **34** | B2 动作名词 | 红 | **黄 L2** |
| **合计** | **51** | | | **降级率 34/51 = 66.7%** |

> 本节数字由 `annotations/classify_with_guide.py` 复算（自带断言：红+黄 = 现行 H07 命中数）。
> **v2 首版此处曾写 11/38 —— 那是错的**：分类器把英语 `Painlessly Pump` 的 `Pump`
> 当成动作名词处理，漏掉 §6 E05/E10 明示的 5 条（B011/B021/B029/B044/B045）。
> 该不一致由**两位独立标注者分别指出**（见 §9 L4），已并入 D1/D2/D3 同形消解修复。

**仍判红的 17 条全名单（降级后唯一留在红灯下的）：**

| 盲样号 | 语种 | 触发 | 素材段 |
|---|---|---|---|
| B000 | 法语 | B3 | `Tire-Lait Sans Douleur` |
| B001 | 法语 | B1 | `Pompage efficace et indolore. Augmente la production de lait/réduit les blocages` |
| B012 | 西语 | B4 | `Extrae Leche Sin Dolor` |
| B013 | 法语 | B3 | `Tire Lait Sans Douleur` |
| B014 | 法语 | B3 | `Tire-Lait Sans Douleur` |
| B022 | 德语 | B1 | `Schmerzfreies Abpumpen …, Entlastung bei verstopfter Milch` |
| B024 | 法语 | B1 | `Pompage efficace et indolore. Augmente la production de lait/réduit les blocages` |
| B025 | 西语 | B4 | `Extrae Leche Sin Dolor` |
| B031 | 法语 | B3 | `Tire-Lait Sans Douleur` |
| B037 | 法语 | B1 | `Pompage efficace et indolore. Augmente la production de lait/réduit les blocages` |
| B047 | 德语 | B1 | `Schmerzfreies Abpumpen …, Entlastung bei verstopfter Milch` |

**38 条降级的不是「放宽」，是纠正管辖错误** —— 它们被现行规则当成
「声称器械有医疗功效」，**而它们声称的是器械好用**。

**代价必须说清**：这 38 条中若有真实违规（例如某个 `schmerzfrei` 实际暗示了医疗效果），
**会被漏掉**。B2 的「黄 L2」意味着**仍需产品测试证据**，不是「不判」——
这是降级而非豁免。

---

## 8. ★ 开放问题（不掩盖）

| # | 问题 | 为什么现在不能定 | 需要谁决 |
|---|---|---|---|
| **O1** | `Soulage Les Engorgements`（缓解涨奶）归 T1.4 红还是 T2.2.2 黄？ | **两条一手依据互相拉扯**：Cochrane 综述 2020 明确写 *"Breast engorgement is the **pathological** overfilling of the breasts"*，须与 *normal breast fullness*（生理性）区分，ICD-10 编入 **O92.79 哺乳期其他疾患** → 指向「是病」；但 **FTC** 的标准是 *"Depending on how it is phrased or the context in which it is presented, a statement about a product's effect on the normal structure or function of the body may also convey an implied claim that the product is beneficial for the treatment of a disease."* → 措辞与语境决定，不由疾病分类决定。**且「允许」在四处被写下**（主题树 L61、H01 `boundary_content`、`H01.exceptions`、在用审核表 `命中原因`）。★ **但「H01 现行边界已经判为允许」这个说法要更正**：见 §9 的 **L6** —— 四处都**不是代码**，通行的是 `exceptions` 分支，而该分支**全库 93/94 条没有进入条件**。引擎的「允许」是不可见的副作用，不是实现 | **W1 品线 + 法务**：`缓解涨奶` 是否需要测试报告背书？现行 H01 的豁免是否维持？**已出单：`CONSULT-001-engorgement-permit.md`**（三问 + 答复后的动作表） |
| **O2** | 51 条里那 2 条「无可判段」是什么？ | 它们命中 H07 但段内找不到裸主张词，需逐条人工看 | 标注者 |
| **O3** | B3（器械名词）的红是否需要区分「器械无痛」与「吸乳过程无痛」？ | 英语 `Pain-Free Pump` 中 `Pump` 名词/动词同形，**构词判据说它修饰器械，但语义上很可能指过程** | α 实测会暴露这条线是否可执行 |
| **O4** | 多语言是否需要各自一份构词表？ | 本版只覆盖英/德/法/西四种，构词表覆盖 49/64 段（④ 类 14 段未覆盖） | 后续按语种补 |

---

## 9. 我在写这份指南时犯的错误（记在案）

| # | 错误 | 后果 | 教训 |
|---|---|---|---|
| **L1** | 第一版分类器在**整条广告**（几十个素材拼成的 blob）里搜「疼痛的对象」 | `Pump Wherever, Whenever` 这行让裸 `Zero Pain`「找到」了对象 → 47 条被误判成过程声明 | **判定必须在素材段上做。** 与 `rules-v1` 实测的 E1 是同一类文档级误匹配 |
| **L2** | 第一版把「机制归因」（flange / 微振动 / 加热）当作管辖判据，拆出 B3/B4 两桶 | 实测只挪动 **3/57** 段，**机制归因不区分任何东西** | **判据必须在数据上验证区分度再写进指南。** 保留「机制」字段仅用于**证据要求**，不参与管辖 |
| **L3** | 第一版声称拆分是 31/18/2 | 实测是 **17/34**；且 `PROCESS` 词典误收了产品名（`tire-lait`/`milchpumpe`），把裸对象判成了过程对象 | **不要把推测的数字写进交付物当结论。** 本版所有数字均由 `annotations/classify_with_guide.py` 复算 |
| **L4** | §6 的 E05/E10 判 `Pain-Free Wearable Pump` / `Zero Pain` 为红，但 §7 的红名单里没有对应记录 —— 因为同形消解规则**只写进了诊断脚本，没折回主分类器** | §6 与 §7 自相矛盾，**两位独立标注者分别指出**（差额 5 条：B011/B021/B029/B044/B045） | **同一判据写在两处就会漂移。** 任何判据只能有一个权威实现（本版为 `classify_with_guide.py`），文档中的数字一律由它复算后填入，不手写 |
| **L5** | 修 L4 时连续三轮「改一次正则、跑一次、发现误伤」，包括 `[A-Z][a-z]+` 把副词 `Painlessly` 当成限定语 | 反复误判 13 条 → 28 条红 | **当正则需要第三次修补时，停止修补，去打印数据。** 最终把全部 21 处匹配的「前一个词」列出来后，判据一眼可见（段首/破折号/型号三种），一次写对 |
| **L6** | 我在本指南 §8 的 O1 里写「**H01 现行边界已经把「缓解涨奶」判为允许**」，把它当成一个**已被实现并生效**的既有决策 | 追查后实测：H01 的 `exceptions`（44 条）**44/44 自身不在检出词表里**，该分支**从上线起从未执行**；全库 `exceptions` 94 条中 93 条同样无效。「允许」的四处出处全是文本，**零处是代码** | **「文档里写了」不等于「系统里生效」。** 引用任何既有边界之前，必须先机械验证它有没有进入条件 —— 否则会把一个**从未运行过的分支**当成现行决策，再基于它推出结论（本单的 O1 就是这样被误述的） |

---

## 10. α 测量协议（本指南的验收方式）

**α 不能靠读指南读出来，必须实测。**

1. **盲样**：`pain-corpus-annotator-view.json`，64 条，**已剥离现行命中与等级**
   （若标注者能看到现行答案，α 测的是「他们是否同意现行表」，不是「他们是否同意指南」）
2. **标注者**：≥3 名独立标注者，各自独立按本指南出结论，互不可见
3. **标注单位**：`(blind_id, 素材段, 管辖叶子, 等级)`
4. **统计**：Fleiss' κ（多标注者、类别型）
5. **门槛**：**κ ≥ 0.80** 视为「先对齐人」达成（设计文档 §3.4）
6. **不达标时的动作**：不是放宽门槛，而是**定位分歧集中在 A/B/C 哪一步**，重写那一步
   —— 与实测中修 H05 正则的方式一致：**定位到具体那一步，而不是整条重写**

---

## 11. 与规则的落地对应

| 新 rule_key | parent_rule | 叶子 | 等级 | 触发 | 复算条数 |
|---|---|---|---|---|---|
| `H07.a` | H07 | T1.5 · T1.4 | 红 L4 | B1（病理对象） | **5** |
| `H07.b` | H07 | T1.4 | 红 L4 | B3 ∪ B4（对象未写出） | **12** |
| `H07.c` | H07 | T2.2.2 | 黄 L2 | B2（疼痛词修饰动作名词） | **34** |
| `U04.a` | U04 | T1.4 | — | C 表判为「场景描述」→ **不出结论，记 context** | — |

> `H07.a ∪ H07.b ∪ H07.c` 恰好等于原 H07 的全部命中（**5 + 12 + 34 = 51**，已由脚本断言校验）。
> **拆分不产生新的召回，也不丢失原有命中**，只改变管辖与等级。

---

## 12. 复算方式

```bash
cd research/governance
python3 annotations/classify_with_guide.py     # 按 §3 程序对 51 条现行 H07 命中重新归类
python3 annotations/measure_alpha.py           # 统计多标注者 α
```

---

## 附：证据出处

| 结论 | 出处 |
|---|---|
| 57 段 = 13 个模板的四语翻译 | `annotations/classify_with_guide.py` 输出 |
| 构词 × 语种交叉表（40/7/24/14） | 同上 |
| 「缓解涨奶」已被 H01 允许 | `skeleton/_data/rules_raw.json` H01 `boundary_content` |
| 涨奶在医学上是 pathological | Cochrane 2020《Treatments for breast engorgement during lactation》[PMC8094412](https://pmc.ncbi.nlm.nih.gov/articles/PMC8094412/) |
| 涨奶 ICD-10 编码 O92.79 | [ICD-10-CM O92.79](https://www.icd10data.com/ICD10CM/Codes/O00-O9A/O85-O92/O92-/O92.79) |
| 措辞与语境决定主张性质 | [FTC Health Products Compliance Guidance](https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance) |
| 对象不可确定时举证责任倒置 | 设计文档 §B；与 T2.3.2「无来源数据默认判红」同构 |
| α 是对齐人的前置条件 | 设计文档 §3.4「先对齐人，再对齐机器」 |
