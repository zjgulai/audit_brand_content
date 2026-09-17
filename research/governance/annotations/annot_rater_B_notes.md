# annot_rater_B 附属说明（TSV 严格三列，note 另存于此）

主文件 `annot_rater_B.tsv` 按任务规定的严格格式：64 行、3 列、无表头。
req.5 要求的「note 列」若写进 TSV 会破坏该格式，故记在此处。

## 一、标为「存疑」的 7 条及分歧所在步骤

| blind_id | 素材段 | 分歧步骤 | 分歧点 |
|---|---|---|---|
| B002 | `Ease Engorgement Comfort`（另 `Soothe Tension as You Pump`） | **B** | 涨奶（engorgement）归 B1 病理 → T1.4 红，还是按「过程/不适」→ T2.2.2 黄。§8 **O1** 明确写「现在不能定」（Cochrane/ICD-10 O92.79 指向病理，FTC 指向措辞语境，且现行 H01 已允许「缓解涨奶」）。 |
| B032 | 同上（与 B002 文案相同） | **B** | 同 O1。 |
| B036 | `Soulage Les Engorgements Grâce Au Massage Chauffant à 360°` + `Tirage Sans Douleur` | **B** | 同 O1：`Tirage Sans Douleur` 本身是 B2 黄 L2，但整条记录的等级取决于「缓解涨奶」判红还是判黄。 |
| B038 | 同上 | **B** | 同 O1。 |
| B040 | 同上 | **B** | 同 O1。 |
| B041 | 同上 | **B** | 同 O1。 |
| B010 | `Pump Like Baby's Latch — No Pain` / `105° flange + micro-vibration = painless pumping` | **B** | 同段内两个方向拉扯：按 §6 **E10** 的写法，「No Pain」是裸主张、无句法中心语 → B4 → T1.4 红；按 §6 **E02/E09** 的写法，同段 `Pump`/`pumping` 是动作名词 → B2 → T2.2.2 黄。第二段 `painless pumping` 明确黄 L2，记录级等级完全取决于第一段怎么读，指南未给该构词的裁定。 |

## 二、判读口径（供复核）

- **判定在素材段上做，不在整条广告上做**（§9 L1）：如 B000 的 `Tire-Lait Sans Douleur` 只按该段判，不因同条广告另有 `Pomper à tout moment` 之类过程表述而改判。
- **机制归因不参与管辖**（§9 L2）：`105° flange + micro-vibration = painless pumping` 按 E09 判 T2.2.2，加热/法兰/微振动只记证据要求。
- **E14 口径**：`comfortable / gentle / doux / Komfort` 无否定、无消除 → 不判（B004、B016、B055、B061 等）。
- **B1 的叶子写法**：§3 B1 与 §11 `H07.a` 均为「T1.5 · T1.4」，故记录级写作 `T1.5+T1.4`；同段若并存 B2（T2.2.2 黄），按任务要求只保留最严叶子，未重复列出。

## 三、需要上报的一处指南内部不一致（影响 α 比对，非标注错误）

§6 与 §7 对**英文裸形容词 + 器械名词**这一类给出不同结果：

- §6 **E05**：`Pain-Free Wearable Pump`（[实测]）→ `Pump`（器械）→ **T1.4 红 L4**；
  §6 **E10**：`Experience Strong Suction with Zero Pain`（[实测]）→ 无名词可依 → **T1.4 红 L4**。
- §7 的「仍判红 11 条」名单里**没有** B011（E10 的原段）、B021（E05 的原段）、B029、B044、B045。
  即 §7 的脚本结果与 §6 的手工边界例互相矛盾（该脚本疑似把同段出现的 `Pump` 当成了动作名词，属 §9 L3 已警告的词典污染类问题）。

本标注按任务指定的「§3 程序 + §6 边界例表」执行，因此 B011/B021/B029/B044/B045 均判 T1.4 红 L4，
红灯共 16 条（§7 为 11 条）。差异全部来自上述 §6↔§7 冲突，未涉及 O1 之外的开放问题。

另注：§8 **O3**（英语 `Pump` 名动同形，`Pain-Free Pump` 语义上可能指过程）已被考虑；
因 §6 E05 对该构词有明确裁定，故未标存疑，仅在此记录该线在 α 上可能不稳。
