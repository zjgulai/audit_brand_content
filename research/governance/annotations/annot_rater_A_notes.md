# annot_rater_A 备注（rater A 独立盲标）

规则来源：`ANN-GUIDE-001-T1.4-T2.1.2.md`（§3 三问 A/B/C、§6 边界例、§9 教训 L1/L2）。
判定在**素材段**上做（L1），一条记录取**最严**结论一行（任务约定）。
本文件是 `annot_rater_A.tsv` 的 note 列替代物 —— TSV 严格保持 3 列无表头。

## 一、存疑 6 条：全部落在 §8 开放问题 O1

§8 O1 原文即写「**现在不能定**」：`Soulage Les Engorgements`（缓解涨奶）归 **T1.4 红** 还是 **T2.2.2 黄**，
Cochrane 2020（engorgement is *pathological*）与 FTC（措辞/语境决定）互相拉扯，且现行 H01 边界已把
「缓解涨奶」判为允许，需 **W1 品线 + 法务**决。分歧点在 **A→B 那一步**：涨奶算不算「病理对象」。
按 B1 的显式清单（mastitis / nipple damage / cracked nipple / verstopfte Milch / blocages / 堵奶）
**engorgement 不在其中**，故 B 表无法唯一落桶 → 照实标存疑，不强行选边。

| blind_id | 语种 | 触发素材段 | 分歧点 |
|---|---|---|---|
| B002 | 英语 | `Ease Engorgement Comfort` | A/B：涨奶=病理（→T1.5+T1.4 红）还是可用过程/不适（→T2.2.2 黄），即 O1 |
| B032 | 英语 | 同 B002（同一素材） | 同上 |
| B036 | 法语 | `Soulage Les Engorgements Grâce Au Massage Chauffant à 360°`（同段另有 `Tirage Sans Douleur`=B2 黄） | 同上；记录级最严等级取决于涨奶落桶 |
| B038 | 法语 | 同 B036 | 同上 |
| B040 | 法语 | 同 B036 | 同上 |
| B041 | 法语 | 同 B036 | 同上 |

> 反例（**不是**存疑）：`Entlastung bei verstopfter Milch`(B022/B047)、`réduit les blocages`(B001/B024/B037)
> 命中 B1 显式清单 → 红，无歧义。

## 二、未标存疑但值得上游知道的张力点

1. **O3（`Pump` 名词/动词同形）**：B044/B045 `Momcozy M5 Pain-Free Pump`、B029 `Pain-Free Warm Massage
   Pump` 按 §3 B3 + §6 E05（`Pain-Free Wearable Pump`→红）判 **红**。O3 说「构词判据说它修饰器械，
   语义上很可能指过程」，但 O3 是**未来是否细分 B3** 的品线问题，O1 才是「现在不能定」；
   故仍按指南现行规则出红，未标存疑。若 α 要暴露这条线，分歧会集中在 B029/B044/B045 三条。
2. **O4（多语构词表未覆盖）**：B012/B025 `Extrae Leche Sin Dolor` 按 §6 E04 判 **红**（B4 保守默认）。
   虽有语义「吸乳过程无痛」的拉力，但 E04 是明示例，指南已定案。
3. **E14 保留带**：`Comfortable, gentle pumping` 类（`Comfort/ Discreet/ Portable Pumping`、
   `design douillet`、`expérience d'expression douce`、`Gentle and Secure Fit`）按 §6 E14 → T2.2.2 **不判**，
   未被红/黄吸收。
4. **§7 的 11 条红灯名单不是 64 条的全量红灯清单**：§6 E05(`Pain-Free Wearable Pump`) 与
   E10(`Experience Strong Suction with Zero Pain`) 都标 **[实测]**（即出自这 64 条），
   但对应记录 **B021 / B011 均不在 §7 的 11 条名单内**。§7 标题自述范围是「51 条现行 H07 命中的重新归类」，
   故 §7 名单只覆盖现行 H07 命中者。本标注按 §3 程序独立执行，红灯为 16 条（11×T1.4 + 5×T1.5+T1.4），
   与 §7 的 11 条不可直接相减 —— 差额 5 条（B011/B021/B029/B044/B045）应视为**现行 H07 的召回缺口**或
   §7 名单口径问题，建议上游核对。

## 三、口径约定（如与其它 rater 不一致需先对齐）

- B1（病理对象）叶子写作 `T1.5+T1.4`（依 §3 B1 与 §11 `H07.a` 的 `T1.5 · T1.4`）。
- 记录内 B1 与 B2 并存时（§6 E07/E08 型：B001/B022/B024/B037/B047），只出**最严**一行，即 `T1.5+T1.4` / `红 L4`，
  未把从属的 `T2.2.2` 并入叶子串。
- 无疼痛/不适/病理素材段的记录（B004/B016/B027/B028/B034/B035/B039/B042/B043/B055/B061）记 `不判` / `不判`。

## 四、分布

| 结论 | 条数 | blind_id |
|---|---:|---|
| T1.4 · 红 L4 | 11 | B000 B011 B012 B013 B014 B021 B025 B029 B031 B044 B045 |
| T1.5+T1.4 · 红 L4 | 5 | B001 B022 B024 B037 B047 |
| T2.2.2 · 黄 L2 | 31 | B003 B005–B010 B015 B017–B020 B023 B026 B030 B033 B046 B048–B054 B056–B060 B062 B063 |
| 存疑 | 6 | B002 B032 B036 B038 B040 B041 |
| 不判 | 11 | B004 B016 B027 B028 B034 B035 B039 B042 B043 B055 B061 |
