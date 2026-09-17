# S5 · 视频门禁 + 方法论模板 + 人机闸门 + 批次模型

> 源码核对基于 `research/repos/` 下仓库快照（2026-09-15 抓取），
> ad-review-agent commit 见 `research/repos/ad-review-agent/`，行号口径 `splitlines()`。

本片覆盖四个仓库：`sceneforge/`（视频质量审计的方法论与门禁）、`soe-legal/`（零代码的规则文档写法，其余部分可迁移到发布前把关）、`contract_audit/`（把人工闸门做进 LangGraph 状态机）、`PolySafe/`（批次模型、三段式阈值与三态处置）。最后一张卡是对 `PolySafe/` 与 `omniguard/` 关系的独立核查。

---

### S5-01 视频质量门禁 8 项清单

- **出处**：`sceneforge/README.md:235-246`（已实读核实）、`sceneforge/SKILL.md:133-145`（已实读核实）、`sceneforge/references/quality-audit.md:18-25`（已实读核实）
- **一句话**：门禁是一张 8 行清单，每行只回答「是 / 否」，判定手段拆到算法文档与速查表里；交付前逐行确认，任一行不通过就停在门禁前。

- **原文**（README 版清单，8 行）：

  ```235:246:sceneforge/README.md
## 质量门禁

交付前至少检查：

- 视频能否从头到尾完整解码；
- 是否存在异常黑帧、长冻结、非预期重复或黑屏补时长；
- 音视频时长差是否在配置阈值内；
- 原音轨、字幕轨和数据轨是否按要求移除；
- 烧录字幕是否位于安全区，时间线是否单调且无明显重叠；
- 输出分辨率、帧率、SAR、像素格式、编码和响度是否符合交付规范；
- 审计报告是否记录算法版本、参数、阈值和限制；
- 开源目录是否通过路径、凭据、隐私和媒体白名单扫描。
  ```

- **原文**（SKILL.md 里的同一道门，只有 7 行）：

  ```133:145:sceneforge/SKILL.md
## 质量闸门

交付前必须确认：

- 视频可以从头到尾完整解码；
- 无异常黑屏和长冻结段；
- 声画尾差在配置阈值内；
- 字幕位于安全区且时间线单调；
- 原音频和旧字幕轨已按要求移除；
- 输出目录不包含源素材副本；
- 开源目录不包含绝对路径、真实文案、账号、凭据和生产报告。

任一隐私检查失败时，停止公开或提交操作，先完成脱敏。
  ```

  **README 与文档不一致**：`sceneforge/SKILL.md:133-145` 的质量闸门是 7 条，缺「输出分辨率、帧率、SAR、像素格式、编码和响度」这一条；README 的同名门禁是 8 条。两处不是同一条清单的重复表述，条目集合本身不同。逐项判定方式与阈值如下（阈值取自 `sceneforge/assets/config.example.yaml:13-43`）。

  **第 1 项 · 完整解码**。判定方式为实际读取全部帧，而不是读容器元数据。原文见 `sceneforge/references/quality-audit.md:24`：「完整解码：实际读取全部帧，不只依赖容器元数据。」阈值开关为 `audit.full_decode: true`（`config.example.yaml:42`）。`sceneforge/docs/ALGORITHMS.md:179` 补充了要对照的中间量：容器声明帧数与实际解码帧数是否合理。

  **第 2 项 · 黑帧、冻结、重复帧**。五项子判定与阈值全部在 `references/quality-audit.md:20-23` 与 `docs/ALGORITHMS.md:151-173`。黑帧按平均亮度与有效像素比例联合判断，`docs/ALGORITHMS.md:153` 明确「深色产品镜头不能仅凭均值低就直接判黑」，这条对母婴品类的暗调产品镜头直接适用。冻结段按连续近重复帧的持续时间判断，`docs/ALGORITHMS.md:165` 只写「只有超过最短持续时间才报警」，**未找到该持续时间的数值默认值**；检索关键词为 `freeze`、`冻结`、`duration`、`min_duration`、`threshold`，`config.example.yaml` 的 `audit` 段只有布尔开关（`black_frames`、`freeze_frames`），没有时长门槛。非相邻复现与首尾循环候选见 `docs/ALGORITHMS.md:167-173`，首尾循环的抽样口径为开头约 1 秒与结尾约 1 秒的 pHash 相似度。

  **第 3 项 · 声画尾差**。判定方式为比较最终可播放音视频流的持续时间（`references/quality-audit.md:25`）。`sceneforge/SKILL.md:139` 的表述是「声画尾差在配置阈值内」，**未找到该阈值的具体数值**；检索关键词为 `尾差`、`av_offset`、`duration_diff`、`tolerance`。这是一处门禁声明了阈值存在、配置模板里却查不到对应键的位置。

  **第 4 项 · 字幕安全区与时间线单调**。`sceneforge/docs/ALGORITHMS.md:243-244` 给出判定：「时间线必须单调、无负值、无异常重叠」「字幕位于平台 UI 与主体之外的安全区」。配置侧只有安全区比例的数值：`subtitles.safe_area_bottom_ratio: 0.15`（`config.example.yaml:33`）。注意 `docs/ALGORITHMS.md:93` 在多视图规范化里用的是另一个数字，去底部约 18% 的字幕高发区，两者口径不同，一个用于出片留白、一个用于比对视图。

  **第 5 项 · 轨道移除**。三个开关全开：`remove_audio_tracks: true`、`remove_subtitle_tracks: true`、`remove_data_tracks: true`（`config.example.yaml:21-23`）。烧录字幕走单独的策略键 `burned_subtitle_strategy: review`（`config.example.yaml:24`），即无法可靠清除时进人工复核。`sceneforge/SKILL.md:84` 把这条底线写成了行为约束：「对烧录字幕使用安全裁切、缩放和重新构图；无法可靠清除时拒绝伪造"已移除"。」

  **第 6 项 · 输出规格**。`sceneforge/SKILL.md:85`：「统一输出画布、帧率、SAR、像素格式和编码参数。」具体值在 `config.example.yaml:13-18`：`width: 1080`、`height: 1920`、`fps: 30`。`docs/ALGORITHMS.md:198-202` 列出落地这些规格的 FFmpeg 能力，其中 `setsar=1` 统一像素宽高比、`format=yuv420p` 提升兼容性。

  **第 7 项 · 审计报告记录算法版本、参数、阈值、限制**。判定方式见 `references/quality-audit.md:29`：「记录算法、抽样频率、阈值和版本。」这一项是元要求，不通过则报告本身不可复核，详见 S5-04。

  **第 8 项 · 开源目录扫描**。`sceneforge/SKILL.md:143` 的判定对象是「绝对路径、真实文案、账号、凭据和生产报告」。`sceneforge/docs/PRIVACY_AND_COMPLIANCE.md:79-150` 把这条拆成了三张扫描表：路径与身份扫描、凭据扫描、媒体白名单。配置侧对应的五个开关在 `config.example.yaml:45-51`，其中 `allow_production_reports_in_repository: false` 与 `allow_real_media_in_repository: false` 默认关闭。

- **为什么这样做 / 不这样做会出什么事**：把门禁写成扁平的「是 / 否」清单，好处是不通过时定位快、无需读算法文档就能执行。如果反过来把门禁做成一个综合质量分，`sceneforge/docs/ALGORITHMS.md:269` 明确禁止了这种压缩：「不得把多个指标压缩成一个缺乏解释的"原创度分数"。应分别报告覆盖率、最佳候选、时间偏移、告警区间和人工结论。」综合分会把「解码失败」和「黑帧比例略高」混成同一个数字，前者是必须停机重渲，后者可能只是暗调镜头，处置动作完全不同。

- **代价与局限**：清单是文档级约定，仓库里没有执行它的代码。`sceneforge/README.md:208` 自己承认「仓库当前提供的是 Skill、方法论和安全配置模板，不提供一键运行的完整生产脚本」。因此门禁的实际拦截率取决于下游是否真的逐条跑。8 项里有 2 项（冻结最短持续时间、声画尾差阈值）在配置模板里找不到对应键，照抄清单实现时会在这两项上被迫自行定值。

- **横向对比**：`PolySafe/` 走的是相反路线，把门禁固化成代码里的三段式阈值（见 S5-12），好处是同一份判断对每一条内容都必然执行、无法跳过，代价是阈值只能靠 `if/elif/else` 表达，规则一多就没有 `sceneforge` 那种「先记录事实再人工判读」的余地。

- **Momcozy 迁移形态**：建立 `pre_publish_gate` 表，字段固定为 `gate_id`、`gate_name`、`verdict`（`pass`/`fail`/`manual`）、`evidence_ref`、`threshold_key`、`checked_at`。8 项直接沿用，但按美国市场与母婴品类改写两处：第 2 项追加「婴儿皮肤特写镜头不得仅凭低均值判黑」，第 6 项把 `fps: 30` 与 `1080x1920` 换成 Momcozy 实际投放规格，并新增一条 TikTok / Meta 各自的字幕安全区比例字段。第 8 项的开源扫描要替换为「对外交付物扫描」（不得含未授权素材、未脱敏的达人肖像、未存档的 substantiation 文件）。

- **证据强度**：已实读核实（清单与配置键）；冻结持续时间阈值与声画尾差阈值在配置模板中未找到，"8 项 vs 7 项"的不一致已逐行核对。

---

### S5-02 可解释相似度指标：pHash / dHash 加权 + 多视图 + ORB

- **出处**：`sceneforge/docs/ALGORITHMS.md:54-116`（已实读核实）、`sceneforge/references/quality-audit.md:3-9`（已实读核实）
- **一句话**：三条哈希链路各管一段失效场景，pHash 管低频结构、dHash 管局部梯度、ORB 管裁切与遮挡，三者按固定权重合成一个分数，并且每一条都写明了它会在什么情况下失效。

- **原文**：

  ````54:84:sceneforge/docs/ALGORITHMS.md
## 3. pHash

1. 图像转灰度并缩放为 32×32；
2. 使用 OpenCV 计算二维 DCT；
3. 取左上角 8×8 低频系数；
4. 排除 DC 系数后计算中位数；
5. 每个系数与中位数比较，生成 64 位哈希；
6. 使用汉明距离计算差异。

```text
similarity_phash = 1 - hamming_distance / 64
```

pHash 对轻微亮度、压缩和缩放较稳定，但可能受大幅裁切、字幕覆盖和构图变化影响。

## 4. dHash

1. 图像转灰度并缩放为 9×8；
2. 比较每一行的水平相邻像素；
3. 左像素大于右像素记为 1，否则为 0；
4. 生成 64 位梯度哈希；
5. 使用汉明距离转换为相似度。

原型组合分数：

```text
visual_hash_similarity = 0.72 × similarity_phash
                       + 0.28 × similarity_dhash
```

pHash 更关注低频结构，dHash 更关注局部梯度。组合能够降低单一哈希误判，但仍不能输出“绝对同源”结论。
````

  pHash 对轻微亮度、压缩和缩放较稳定，但可能受大幅裁切、字幕覆盖和构图变化影响。

  ## 4. dHash

  1. 图像转灰度并缩放为 9×8；
  2. 比较每一行的水平相邻像素；
  3. 左像素大于右像素记为 1，否则为 0；
  4. 生成 64 位梯度哈希；
  5. 使用汉明距离转换为相似度。

  原型组合分数：

  ```text
  visual_hash_similarity = 0.72 × similarity_phash
                         + 0.28 × similarity_dhash
  ```

  pHash 更关注低频结构，dHash 更关注局部梯度。组合能够降低单一哈希误判，但仍不能输出“绝对同源”结论。
  ```

- **原文**（多视图规范化，含 9:16 / 3:4 前景视图与去底部字幕区）：

  ```86:95:sceneforge/docs/ALGORITHMS.md
## 5. 多视图规范化

为了降低竖屏重构、边框、裁切和旧字幕区域的影响，同一帧生成多个视图：

1. 原始画面；
2. 中心裁切；
3. 面向 9:16 或 3:4 输出的前景视图；
4. 去除底部约 18% 字幕高发区后的视图。

候选帧与来源帧在各视图间比较，记录最佳视图组合和时间码。多视图提高召回率，也可能增加误报，因此命中必须进入人工复核。
  ```

- **原文**（ORB 参数表与匹配判据）：

  ````97:116:sceneforge/docs/ALGORITHMS.md
## 6. ORB 局部特征

原型参数：

```text
ORB 特征上限: 500
规范化尺寸: 256 × 256 灰度图
匹配器: BFMatcher
距离: Hamming
KNN: k = 2
Lowe Ratio: 0.75
```

对每个描述子取两个最近邻：

```text
first.distance < 0.75 × second.distance
```

报告可记录双方关键点数量、good match 数量、匹配比例、最小关键点门槛和最佳时间码。ORB 能补强裁切、缩放、局部遮挡和重编码下的匹配，但对低纹理、快速运动模糊和重复图案较弱。
````

  对每个描述子取两个最近邻：

  ```text
  first.distance < 0.75 × second.distance
  ```

  报告可记录双方关键点数量、good match 数量、匹配比例、最小关键点门槛和最佳时间码。ORB 能补强裁切、缩放、局部遮挡和重编码下的匹配，但对低纹理、快速运动模糊和重复图案较弱。
  ```

- **原文**（三指标分开报告，不合成单一结论）：

  ```3:9:sceneforge/references/quality-audit.md
## 视觉相似性

- 使用 pHash 评估整体结构近似。
- 使用 dHash 补充边缘与梯度变化。
- 使用中心裁切、去字幕区域和尺度归一化等多视图比较降低版式差异影响。
- 使用 ORB 与 Lowe Ratio Test 处理裁切、缩放和局部遮挡。
- 将“命中帧比例”“最佳来源”和“时间覆盖率”分开报告，不输出单一绝对结论。
  ```

- **为什么这样做 / 不这样做会出什么事**：加权而不是取最大值，是因为两种哈希的失效模式互补。`docs/ALGORITHMS.md:67` 说明 pHash 受大幅裁切与字幕覆盖影响，`docs/ALGORITHMS.md:74` 说明 dHash 是逐行水平梯度、对整体亮度不敏感。只用 pHash，竖屏重构加底部字幕条会把它拉低到误判为不相似；只用 dHash，整体构图换了但局部纹理保留时会误判为相似。0.72 / 0.28 的偏置表示仍然以整体结构为主证据，梯度只做修正。ORB 独立于这条加权链，是因为它对裁切与遮挡的鲁棒性来自局部特征匹配，不来自全局统计量，塞进同一个加权和里会稀释掉它的判别力。`docs/ALGORITHMS.md:84` 明确了组合分的能力上界：降低单一哈希误判，但不输出「绝对同源」结论。

- **代价与局限**：多视图会抬高召回率也抬高误报率，`docs/ALGORITHMS.md:95` 的处置是「命中必须进入人工复核」，意味着这个模块只做候选排序，不做拦截。ORB 的错误场景写得很具体：低纹理、快速运动模糊、重复图案。母婴品类里的纯色硅胶瓶身、白底产品图都是低纹理画面，ORB 在这类素材上会退化到接近随机，Lowe Ratio 0.75 这个门槛在低纹理图上会同时拒掉正确匹配。`docs/ALGORITHMS.md:5` 还提醒所有权重都是「可配置的工程默认值」，不是跨数据集通用的科学常数。

- **横向对比**：`PolySafe/backend/app/services/rule_engine.py:14-15` 解决「这条内容像不像已知违规」的方式是用 FAISS 检索相似规则，相似度门槛固定 0.3，而不是对媒体本身做哈希比对。它这样做的前提是审核对象是「违规文本描述」而不是「同一支素材的重复出现」，所以相似的对象是规则库，不是画面。代价是它无法回答「这条素材是不是上次那条」，而 `sceneforge` 的哈希链恰好只能回答这个，两者在同一套系统里是互补的两层。

- **Momcozy 迁移形态**：建 `asset_similarity` 表，字段 `source_asset_id`、`candidate_asset_id`、`phash_sim`、`dhash_sim`、`visual_hash_similarity`、`best_view`（`original`/`center_crop`/`foreground_9x16`/`foreground_3x4`/`no_subtitle_bottom`）、`orb_good_matches`、`timecode`、`requires_human_review`。权重对 Momcozy 要重调：母婴素材大量使用白底棚拍与纯色瓶身，pHash 的稳定区更可靠，dHash 的梯度差在小体量商品上信噪比低，建议把 0.72 / 0.28 改为 0.82 / 0.18 并记录在报告里（S5-04 要求记录阈值与版本）。ORB 在低纹理瓶身上不作为拦截依据，只作为「疑似复用同一素材」的线索。

- **证据强度**：已实读核实。权重、参数、失效场景均在 `docs/ALGORITHMS.md` 原文中，`sceneforge/README.md:116-129` 是同一组参数的复述，两处一致。

---

### S5-03 音频指纹：31 位局部指纹 + 滑窗偏移 + 随机基线扣除

- **出处**：`sceneforge/docs/ALGORITHMS.md:118-147`（已实读核实）、`sceneforge/references/quality-audit.md:11-16`（已实读核实）
- **一句话**：自定义频带指纹负责细粒度比对（旁白、BGM、静音、时间偏移），Chromaprint 作为独立的第二条证据链负责整体内容判同，两条链路都拒绝把编码差异当成内容差异。

- **原文**：

  ```118:136:sceneforge/docs/ALGORITHMS.md
## 7. 自定义音频指纹

### 7.1 解码与时频分析

- FFmpeg 解码为单声道 PCM；
- 采样率：11025 Hz；
- FFT 窗口：2048；
- Hop：1024；
- 窗函数：Hann；
- 分析频率：80 Hz～5 kHz；
- 频率轴划分为 16 个几何频带。

每个时间窗计算频带能量及相邻时间差分，再编码为 31 位局部指纹。按当前参数估算，每个指纹步长约 93 ms。

### 7.2 时间偏移搜索

对两个指纹序列做滑窗对齐，搜索最优偏移并计算位匹配率。随机位序列也会出现约 0.5 的基线匹配，因此原型在归一化时扣除随机基线，避免把随机一致解释为内容相似。

报告应输出最佳偏移、有效重叠长度、原始匹配率、基线校正分数、静音状态、参数和算法版本。
  ```

- **原文**（Chromaprint 第二条链）：

  ```138:147:sceneforge/docs/ALGORITHMS.md
## 8. Chromaprint

Chromaprint 作为独立证据链：

- 通过 FFmpeg Chromaprint 输出或兼容工具生成指纹；
- 比较完整指纹是否完全一致；
- 对指纹字符串记录 SHA-256，便于版本追踪；
- 不把文件 MD5、码率或封装格式变化当作音频内容差异。

Chromaprint 更适合识别整体音频内容，不替代对旁白、BGM、静音段和时间偏移的细粒度分析。
  ```

- **原文**（音频侧的报告口径）：

  ```11:16:sceneforge/references/quality-audit.md
## 音频指纹

- 使用 Chromaprint 比较音频内容结构。
- 必要时使用频谱峰值地标和时间偏移对齐。
- 单独报告旁白、BGM、静音和综合响度。
- 不把编码格式、码率或 MD5 差异当成声音内容已经改变的证据。
  ```

- **为什么这样做 / 不这样做会出什么事**：`docs/ALGORITHMS.md:134` 是这张卡最值钱的一句：随机位序列的基线匹配率约为 0.5。任何位级指纹比对如果不扣掉这个基线，两条毫不相干的音频会得到 0.5 左右的原始匹配率，这个数字看上去像「有一半相似」，落进报告就是一个纯噪音。扣除基线之后，0.5 被重标定为 0，偏离 0 的部分才是证据。31 位的来源是 16 个几何频带加相邻时间差分，`docs/ALGORITHMS.md:130` 把步长也给了：约 93 ms，`2048 / 11025` 与 `1024 / 11025` 都在这个量级，抽样口径与 S5-04 要求的「记录抽样频率」正好对应。

- **代价与局限**：93 ms 的步长意味着短于约 0.1 秒的音效差异落不进指纹，对「换了一处咔哒声」这类改动不敏感。`docs/ALGORITHMS.md:147` 划清了 Chromaprint 的边界：它识别整体内容，不替代对旁白、BGM、静音段和时间偏移的细粒度分析。两条链路的组合方式是不一致的，Chromaprint 只比「完整指纹是否完全一致」，是布尔判定；自定义指纹才给连续的匹配率。因此报告里这两列不能加权合成一个「音频相似度」。

- **横向对比**：这条链路在 `sceneforge` 里占一整个算法章节加一个速查小节。`PolySafe/` 对音频完全没有独立处理，`backend/app/models.py:26` 的 `content_type` 注释只列了 `image / video / text`，音频作为视频的一部分交给 VLM 一起看。它这样省掉一层是因为它的判定目标是「内容是否违规」，声音里有没有违规信息可以直接问多模态模型；而 `sceneforge` 要回答的是「这条素材是不是从那条素材来的」，这个问题 VLM 答不了，必须有可比对的指纹。而`soe-legal/` 侧完全无对应物，它的审计对象是文本合同。

- **Momcozy 迁移形态**：建 `audio_fingerprint` 表，字段 `asset_id`、`sample_rate_hz`、`fft_window`、`hop`、`band_count`、`fingerprint_bits`、`step_ms`、`best_offset_ms`、`overlap_ms`、`raw_match_rate`、`baseline_corrected_score`、`chromaprint_sha256`、`algorithm_version`。两处按 Momcozy 场景改：一是把分析频率下限从 80 Hz 抬高，母婴产品的 BGM 与旁白几乎不占超低频，80 Hz 以下只会收进环境噪声；二是把「旁白 / BGM / 静音」三项换成 Momcozy 关心的「口播 / 音乐 / 音效」三项，因为美国市场的内容审核关注点里有「背景音乐是否有商用授权」这一类，需要在报告里单独成列。

- **证据强度**：已实读核实。参数、指纹位数、步长、基线扣除机制均在原文；基线值「约 0.5」为文档给出的估算，不是实测常数，卡片按估算处理。

---

### S5-04 审计报告三件套与五条报告原则

- **出处**：`sceneforge/README.md:210-226`（已实读核实）、`sceneforge/references/quality-audit.md:27-33`（已实读核实）、`sceneforge/docs/ALGORITHMS.md:7-12`（已实读核实）、`sceneforge/assets/audit-report-template.md:1-37`（已实读核实）
- **一句话**：一次审计出三个文件，机器可读的 JSON、逐帧明细的 CSV、给人看的 Markdown；报告本身受五条原则约束，最硬的一条是每个告警必须带时间码。

- **原文**（三件套的输出契约）：

  ````210:226:sceneforge/README.md
## 输出契约

生产环境可按需生成：

```text
outputs/
├─ final_video.mp4
├─ subtitles.srt
├─ subtitles.ass
├─ cover_3x4.jpg
├─ cover_9x16.jpg
├─ timeline.json
└─ audit/
   ├─ report.json
   ├─ frame_metrics.csv
   └─ report.md
```
````

- **原文**（三件套的分工，以及禁止合成单一分数）：

  ```262:269:sceneforge/docs/ALGORITHMS.md
## 16. 报告输出

- **JSON**：完整机器可读结果；
- **CSV**：逐帧、来源候选和指标明细；
- **Markdown**：面向人的结论、告警和限制；
- **联系表**：仅用于内部复核，默认不进入公开仓库。

不得把多个指标压缩成一个缺乏解释的“原创度分数”。应分别报告覆盖率、最佳候选、时间偏移、告警区间和人工结论。
  ```

- **原文**（五条报告原则）：

  ```27:33:sceneforge/references/quality-audit.md
## 报告原则

- 记录算法、抽样频率、阈值和版本。
- 区分事实、指标和推断。
- 为每个告警保留时间码。
- 不声称本地指标代表第三方平台内部系统。
- SHA-256 用于现代完整性记录；MD5 仅作兼容性记录。
  ```

- **原文**（「区分事实、指标和推断」的四分类展开）：

  ```7:12:sceneforge/docs/ALGORITHMS.md
报告必须区分：

- **事实**：容器参数、轨道数量、实际解码帧数；
- **指标**：哈希距离、匹配率、冻结时长、响度；
- **推断**：可能来源、疑似循环、建议复核；
- **限制**：抽样误差、裁切遮挡、编码变化、阈值敏感性。
  ```

- **原文**（空白报告模板的骨架）：

  ```10:37:sceneforge/assets/audit-report-template.md
## 媒体完整性

| 指标 | 结果 |
|---|---|
| 完整解码 | 待检测 |
| 黑帧 | 待检测 |
| 冻结段 | 待检测 |
| 声画尾差 | 待检测 |

## 视觉审计

| 指标 | 结果 |
|---|---|
| pHash 覆盖率 | 待检测 |
| dHash 覆盖率 | 待检测 |
| ORB 覆盖率 | 待检测 |

## 音频审计

| 指标 | 结果 |
|---|---|
| 音频指纹 | 待检测 |
| 综合响度 | 待检测 |
| 峰值 | 待检测 |

## 说明

本报告使用虚构文件名和空白指标。不得使用第三方平台审核、推荐或版权判定语言解释本地检测结果。
  ```

- **为什么这样做 / 不这样做会出什么事**：五条原则各堵一类事故。「记录算法、抽样频率、阈值和版本」堵的是报告不可复核，同一支素材换了阈值后结论不同、却无从知道当时用的是哪一版。「区分事实、指标和推断」堵的是把推断写成事实，`docs/ALGORITHMS.md:11` 把「可能来源、疑似循环」明确归入推断，报告里就必须带「疑似」这类限定词。「为每个告警保留时间码」堵的是无法定位，`docs/ALGORITHMS.md:169` 在非相邻复现一处说明了原因：正常回顾镜头也会命中，必须输出时间码供复核。「不声称本地指标代表第三方平台内部系统」堵的是越权结论，`sceneforge/README.md:272` 把 pHash、dHash、ORB、Chromaprint 统一定性为「本地工程指标」。「SHA-256 用于现代完整性记录；MD5 仅作兼容性记录」堵的是拿字节哈希冒充内容判定，`docs/ALGORITHMS.md:275` 列了 MD5 不适合的四件事，其中一件就是「证明内容原创」。

- **代价与局限**：三件套要求同一批指标落到三种载体，CSV 那一层（逐帧、来源候选、指标明细）在长视频上是像素级抽样乘帧数，体积会失控；`sceneforge/README.md:208` 承认仓库不含实现，所以降采样与分卷策略没有现成答案。模板文件本身是空白的，`audit-report-template.md:37` 声明「本报告使用虚构文件名和空白指标」，它给的是骨架而不是填充逻辑。还有一个边界要注意：五条原则里没有任何一条要求记录「谁做的判定」，报告的可追责性只到算法版本一级。

- **横向对比**：`PolySafe/` 的报告载体是数据库字段加一张过程日志，`backend/app/models.py:30-36` 的 `ai_result`、`matched_rules`、`process_logs` 都是 Text 列存 JSON。它这样能省掉三件套的同步问题，因为只有一个真相来源；代价是逐帧级别的指标无处安放，`frame_metrics.csv` 那一层它没有对等物，且报告只能按任务 id 逐条读，没有给人看的 Markdown 汇总。`soe-legal/examples/sample_report.md` 则是纯 Markdown 单文件，它不需要 JSON 层是因为审计对象是文本、结论是人读的条款级判断。

- **Momcozy 迁移形态**：目录固定为 `audit/{report.json, frame_metrics.csv, review.md}`，但字段要加两列 `jurisdiction: "US"` 与 `benchmark_version`。五条原则全部保留，另加第六条 Momcozy 专属原则：**AIGC 溯源字段必须区分事实与推断**，`c2pa_present`（读到的清单是否存在）属事实，`likely_ai_generated`（画面特征推断）属推断，两者不得写在同一列。时间码要求在视频侧保留，在图片侧替换为 `region_bbox`（违规区域的像素框），因为静态图没有时间轴可定位。

- **证据强度**：已实读核实。三件套路径、五条原则、四分类、模板骨架均为逐字节引用。

---

### S5-05 基准表 + 黄 / 红双阈值

- **出处**：`soe-legal/skill.md:231-242`（已实读核实）
- **一句话**：把行业惯例写成一张 8 行的三列表，左列是条款名、中列是惯例值、右两列分别是黄色与红色预警的边界，LLM 只需要把「观察到的值」映射到某一格，不需要自己发明严重度。

- **原文**：

  ```231:242:soe-legal/skill.md
## 市场/行业惯例基准(国企语境)

| 条款 | 惯例/合规要求 | 黄色预警 | 红色预警 |
|------|----------------|----------|----------|
| 工程履约保证金 | 不超过合同价3% | 3-5% | 超过5%或未约定退还条件 |
| 工程质量保修期(主体结构) | 设计文件规定的合理使用年限 | 约定期限模糊 | 明显短于法定最低要求 |
| 采购合同预付款比例 | 一般不超过合同价30% | 30-50% | 超过50%且无预付款保函 |
| 工程款支付周期 | 符合《保障中小企业款项支付条例》,一般不超过验收合格后60日 | 60-90日 | 90日以上或无明确约定 |
| 三重一大决策留痕 | 决策文件与合同金额、条款完全对应 | 决策文件与合同存在细节差异 | 无任何决策文件 |
| 廉洁协议签署 | 工程、采购、销售类合同应附廉洁协议 | 仅有廉洁承诺条款,无独立协议 | 完全未涉及廉洁条款 |
| 产权转让信息披露期 | 依32号令要求的最低披露期限(一般不少于20个工作日) | 披露期限压缩但仍在合规区间 | 未公开披露或披露期严重不足 |
| 关联交易定价说明 | 有独立评估/市场比价支撑 | 仅有内部测算无外部依据 | 无任何定价依据说明 |
  ```

- **为什么这样做 / 不这样做会出什么事**：三列表把「定级」这件事从生成任务降级为查表任务。LLM 对「5% 的履约保证金算不算高」这类判断在不同轮次会给出不同答案，同一个 5% 可能这轮是中、下轮是偏高；但如果表里已经写明「超过 5% 是红色、3-5% 是黄色」，模型要做的事情只剩下读出合同里的数字再定位到一行。阈值边界由人预先钉死，模型只负责抽取与匹配，定级漂移的空间因此被压掉。右侧两列同时给出可量化的边界（3-5%、30-50%、60-90 日）和不可量化的边界（「约定期限模糊」「未公开披露」），后者覆盖那些没有数字可比的条款，例如廉洁协议是「完全未涉及」还是「仅有承诺无独立协议」，两者分属红黄两档。

- **代价与局限**：这张表的价值完全取决于它是否覆盖被审对象。8 行里有 6 行的中列直接引用了中国法规或部门规章的数值（3%、30%、60 日、32 号令的 20 个工作日），法域一变整列失效。剩下的 2 行（三重一大决策留痕、廉洁协议签署）连主体概念都是中国国企语境的。表里也没有任何一行告诉模型「不在表内时怎么办」，模型遇到表外条款会回落到自由定级，此时漂移照旧。

- **横向对比**：`contract_audit/legal_agent/nodes/evaluator.py:35-39` 走的是与查表相反的路线，风险定级完全交给 LLM 的 prompt：「Role: 首席法务官 (CLO)。Criteria: High (核心资产损失/法律违规) / Medium (商业条件不利) / Low (文字瑕疵)」。三档判据是定性的形容词，没有数值边界，同一个 $10,000 的责任限额在两次运行里可以落进不同档。它这样做是因为契约审查的标的是通用商事合同、条款组合无穷，预先造表覆盖不了；代价就是严重度不可复现。`PolySafe/backend/app/services/rule_engine.py:17-25` 用第三种办法，把定级写死在代码里的三段式阈值上，可复现但不含语义。

- **Momcozy 迁移形态**：把这张表整体重写为美国市场版本，保留三列结构（`clause` / `benchmark` / `yellow` / `red`），替换全部 8 行的内容。可迁移的结构性写法有两条：一是量值型条款给数值区间，二是程序型条款给「有 / 有无混合 / 无」的三档。Momcozy 侧的候选条目包括 `substantiation_evidence`（宣称是否有存档证据，红档为无证据）、`aigc_disclosure`（AI 生成内容是否按平台要求标注，红档为生成但未标注）、`portrait_release`（可识别人物是否有肖像授权，红档为无授权）、`endorsement_disclosure`（达人合作是否披露，红档为付费但未披露，对应 FTC 的 Endorsement Guides）、`health_claim_class`（吸乳器相关宣称属于结构功能宣称还是医疗宣称，红档为把器械宣称当普通商品宣称）。中国法域那 6 行数值型基准全部作废，不得改写后沿用。

- **证据强度**：已实读核实。8 行表格与表头逐字节引用，行数按 `splitlines()` 口径统计为 8 条数据行。

---

### S5-06 结论态取值集与「左事实 / 右后果」风险信号表

- **出处**：`soe-legal/skill.md:112-123`（已实读核实）、`soe-legal/skill.md:132-149`（已实读核实）、`soe-legal/skill.md:253`（已实读核实）
- **一句话**：核查表的结论列不用高 / 中 / 低，用一组动作态取值，每一态指向一个不同的下一步动作；风险信号表则是左列可观测事实、右列法律后果与责任主体的固定配对。

- **原文**（专项核查表，注意结论列的实际取值）：

  ```112:123:soe-legal/skill.md
## 国资合规专项核查

| 核查维度 | 结论 | 说明 |
|----------|------|------|
| 招标采购合规 | ⚠️ 需关注 | 合同工期条款与招标文件不一致,建议核实是否构成实质性变更,涉嫌违反"中标人不得对招标文件确定的事项作实质性变更"的要求 |
| 三重一大决策 | ⚠️ 待补充材料 | 未附决策文件,建议提供董事会决议或总经理办公会纪要 |
| 国有资产交易审批 | 不适用 | 本合同不涉及产权转让 |
| 关联交易 | 否 | 经核对,承包方与发包方无关联关系迹象;建议进一步核实是否存在离职人员设立的关联公司 |
| 廉洁风控 | ⚠️ 建议补充 | 未见廉洁协议,建议作为合同附件补签 |
| 境外投资/涉外 | 不适用 | 双方均为境内主体,履行地在境内 |
| 合规前置审查留痕 | 待确认 | 建议核实是否已经合规管理牵头部门或法律顾问出具审查意见 |
| 国有资产保值增值 | ✓ | 付款节奏、履约担保比例符合行业惯例,未见明显不利安排 |
  ```

  **先修正取值集本身**：这一列在原文里出现的实际取值是 6 种，`⚠️ 需关注`、`⚠️ 待补充材料`、`⚠️ 建议补充`、`待确认`、`不适用`、`✓`。样本报告 `soe-legal/examples/sample_report.md:43-51` 里另有 `⚠️ 需整改`、`⚠️ 待补充`、`否（待核实）`、`✓ 基本符合`、`✓ 符合` 五种写法，与 skill.md 的取值集并不一致。上一份调研报告在同一份文档里先写了 5 种取值（漏掉 `⚠️ 建议补充`），后一处又列了 5 种（漏掉 `⚠️ 建议补充`），两处互相矛盾，且都没有把 `✓` 的原文形态标出来。**结论：取值集是开放枚举，不是封闭的五值 / 六值集合**，任何按固定枚举做校验的实现都会在这两份文件上失败。

  **六种取值的动作指向**（判定依据是同一行的「说明」列给出的动词）：

  | 取值 | 说明列里的动词 | 下一步动作 |
  |---|---|---|
  | `⚠️ 需关注` | 建议核实 | 已有迹象但不构成结论，交人工判断 |
  | `⚠️ 待补充材料` | 建议提供 | 缺的是外部材料，动作在对方或用户手上，不在审查方 |
  | `⚠️ 建议补充` | 建议作为合同附件补签 | 缺的是可自行补上的条款或附件，动作在起草方 |
  | `待确认` | 建议核实 | 取决于内部信息，需向用户追问 |
  | `不适用` | 本合同不涉及 | 终止该维度，不产生任何后续动作 |
  | `否` | 经核对，无关联关系迹象 | 与 `不适用` 的区别在于已查过并得出否定结论 |

  `⚠️ 待补充材料` 与 `⚠️ 需关注` 的分野在读原文时最清楚：前者的说明是「未附决策文件,建议提供董事会决议或总经理办公会纪要」，动作是索要材料；后者的说明是「合同工期条款与招标文件不一致,建议核实是否构成实质性变更」，动作是复核已有事实。**「有风险」这个提法在 `soe-legal/skill.md` 全文未找到**，检索关键词为 `有风险`、`风险态`、`存在风险`；把 `⚠️ 需关注` 读作「有风险」是转述，不是原文取值。

- **原文**（风险信号表，左列可观测事实、右列法律后果与责任主体）：

  ```132:149:soe-legal/skill.md
## 风险速查(国企语境优先核查项)

除通用版"违约金畸高""责任限额过低"等风险信号外,国企合同应额外优先排查:

| 风险信号 | 重要性说明 |
|----------|------------|
| 强制招标项目未招标,或以"战略合作""框架协议"名义规避招标 | 违反《招标投标法》第49条,可处合同金额千分之五至千分之十罚款,并可能追究相关人员责任 |
| 合同实质性条款(工期、价款、质量标准)与招标文件/中标通知书不一致 | 属于中标后串通或变相压价/让利,可能导致合同无效或被认定为规避招标 |
| 合同金额/担保/期限接近或超过"三重一大"决策门槛但无决策文件 | 决策程序缺失,构成越权代理及内部问责风险 |
| 交易对方为离职人员、员工亲属设立的公司且未披露 | 潜在利益输送与商业贿赂风险,是国企腐败高发领域 |
| 未附廉洁协议或廉洁条款(尤其工程、采购、销售类合同) | 与国资委、行业主管部门对廉洁风控全覆盖的要求不符 |
| 涉及产权转让但未走产权交易所公开挂牌程序 | 可能违反32号令,导致交易无效或被认定国有资产流失 |
| 关联交易未履行关联方回避表决及公允定价说明 | 可能被认定为损害国有资产的关联交易,构成违规经营投资追责情形 |
| 境外合同未履行ODI备案/核准 | 违反发改委11号令/国资委35号令,可能面临无法办理购付汇、事后追责 |
| "阴阳合同"或与招标/网签合同价格不一致的补充协议 | 严重合规风险,可能构成串通投标、虚假交易 |
| 单方赋予对方任意变更、无对等制约的权利 | 违反《民法典》公平原则,亦可能被追究国有资产保值增值失职责任 |
| 违约金/赔偿责任设置畸低,明显低于对方过错可能造成的损失 | 可能被审计、巡视认定为"未尽到勤勉尽责义务" |
| 合同缺少审计/监督配合条款 | 国企对外合同一般应保留审计署、国资委、纪检监察机关的检查权 |
  ```

- **原文**（正面条目也是一条硬要求）：

  ```253:253:soe-legal/skill.md
- **兼顾正面评价**:审查报告应包含"已审查、可接受"及国资合规专项核查中"✓ 符合"的条目,避免只列风险不列结论
  ```

  这一行是本片唯一出现 `✓ 符合` 连写形态的位置，skill.md 的示例表里写的是裸 `✓`。

- **为什么这样做 / 不这样做会出什么事**：分档回答「有多严重」，结论态回答「谁该做什么」。用高 / 中 / 低三级时，「缺决策文件」和「工期与招标文件不一致」可以同时被评为「中」，但两者的下一步动作完全不同，一个是索要材料、一个是复核事实，落进工作流会走向不同的队列。风险信号表的两列配对堵的是另一个事故：只写「未附廉洁协议」这种事实，读者不知道该不该紧张；右列把后果（与国资委要求不符）和责任主体（国资委、行业主管部门）一起给出，读者才能判断优先级。这个配对的写法也解释了为什么左列必须是可观测事实：「交易对方为离职人员、员工亲属设立的公司且未披露」是可以从工商与人事记录里查出来的，而「存在利益输送」不是。

- **代价与局限**：取值集不封闭是这张表最大的实操障碍。skill.md 的示例用 6 种，样本报告用 9 种，两个文件对同一套语义给出了不同的字面量，下游做统计或看板时会分裂成十几个桶。风险信号表的右列全部指向中国法域的具体条文（《招标投标法》第 49 条、32 号令、发改委 11 号令、国资委 35 号令、民法典公平原则），迁移时右列要整列重写。表也没有给「严重度排序」，12 行是并列的，读者无法从表本身知道哪一行更该优先处理。

- **横向对比**：`PolySafe/backend/app/models.py:29` 用的是一个扁平的 `status` 列，注释写明了取值：`pending / pass / block / review / error`，五个值里只有 `review` 带人工动作。它这样够用是因为审核对象是单条内容、处置只有一个出口（发 / 拦 / 人看）；`soe-legal` 需要更细的动作态，是因为合同审查后的动作可能是要材料、要改写、要核实、要上报，出口不止一个。代价是 `PolySafe` 无法表达「缺材料待补」，这类情形只能落进 `review`。

- **Momcozy 迁移形态**：给审计结果表加 `verdict` 列，取值按 Momcozy 的动作出口重新定义成封闭枚举：`pass`（符合）、`needs_evidence`（缺 substantiation 存档，动作在业务方）、`needs_rewrite`（文案可自行改写）、`needs_review`（有迹象待人工判断）、`not_applicable`（该维度不适用于此内容类型）、`blocked`（明确违规）。风险信号表保留两列结构并整表重写：左列写成内容侧可观测事实（例如「吸乳器文案出现 `treats` / `cures` / `prevents` 一类动词」「广告中出现可识别的婴儿面部但无肖像授权记录」「画面带合成人脸但无 C2PA 清单或平台 AI 标注」），右列写完后果与责任主体（对应 FDA 器械宣称分类、FTC 的 substantiation 要求、平台 AIGC 披露政策，责任主体写 Momcozy 品牌方而非平台）。

- **证据强度**：已实读核实（两个取值集与两张表均逐字节引用，取值集不封闭的结论来自对 `soe-legal/skill.md:112-123` 与 `soe-legal/examples/sample_report.md:43-51` 的逐行比对）；`有风险` 一词在 `soe-legal/` 全目录未找到，为检索后未命中。

---

### S5-07 三条反幻觉底线（可直接进 system prompt）

- **出处**：`soe-legal/skill.md:246-254`（已实读核实）
- **一句话**：三条底线分别管三种不同的幻觉：把不确定的判断说成确定（不得臆断）、把不存在的材料说成存在（不得编造）、把只列风险当成完整结论（必须包含正面条目）。

- **原文**：

  ```246:254:soe-legal/skill.md
## 央企/国企合规审查底线与免责事项

- **不替代内部合规审批**:本审查为法律及合规风险识别参考,不能替代本企业合规管理牵头部门、总法律顾问、法律顾问及上级国资监管机构的正式审查、核准或备案程序
- **不替代律师意见**:重大合同、涉及国有资产交易和境外投资的合同,应聘请具有中国大陆执业资格的律师及必要时的评估、审计机构出具专业意见
- **决策程序优先**:任何合同条款风险的严重性判断,应结合是否已履行"三重一大"决策程序综合评估——程序合规是实体条款合规的前提,不能相互替代
- **表达不确定性**:对是否落入强制招标范围、是否构成关联交易等存在争议或依赖内部信息(如股权结构、任职情况)难以从合同文本本身判断的,应明确提示需要用户提供补充信息核实,不得臆断
- **禁止杜撰**:仅依据合同文本及用户提供的信息进行分析,不得编造决策文件、招标文件等不存在的材料内容
- **兼顾正面评价**:审查报告应包含"已审查、可接受"及国资合规专项核查中"✓ 符合"的条目,避免只列风险不列结论
- **留痕意识**:审查报告本身也应作为合规留痕材料对待,建议用户保存归档
  ```

- **第三条的落点**：`soe-legal/skill.md:58` 与之配套，把「信息不足时先问」做成了流程的第一道门：

  ```58:58:soe-legal/skill.md
**如企业属性、合同类型或立场不明确,应先询问用户,再开展详细审查。**
  ```

- **为什么这样做 / 不这样做会出什么事**：「不得臆断」针对的是从文本推不出来的结论。skill.md 举的例子很具体：是否落入强制招标范围、是否构成关联交易，「依赖内部信息(如股权结构、任职情况)难以从合同文本本身判断」。模型在信息缺口处最容易被推着给一个看起来完整的答案，这条把它改成必须显式索要补充信息。「禁止杜撰」针对的是引用虚构材料，「不得编造决策文件、招标文件等不存在的材料内容」，与 S5-11 里 `contract_audit` 的解析器约束是同一类防线，后者在 `legal_agent/nodes/parser.py:38` 写成「必须提取原文段落，不得改写。若条款缺失则返回 null」。「兼顾正面评价」针对的是报告形态，如果一个系统每次都只输出风险清单，用户无法区分「查过且没问题」和「没查」，`soe-legal/skill.md:118` 的 `不适用` 与 `:123` 的 `✓` 就是用来占住这两个位置的。

- **代价与局限**：三条都是行为约束，靠 prompt 生效，仓库里没有任何机制验证输出是否遵守。第三条尤其难验，因为它约束的是「报告的完整性」，需要一个外部清单才能判断某个维度是否被漏报。另外这三条写在「央企 / 国企合规审查底线与免责事项」标题下，前两条（不替代内部合规审批、不替代律师意见）是责任边界声明，与反幻觉无关，抄的时候要拆开：真正能进 system prompt 的是后四条里的三条，加上流程门 `skill.md:58`。

- **横向对比**：`contract_audit/legal_agent/nodes/parser.py:38` 把反幻觉做成了结构约束（提取原文段落、缺失返回 null），比 prompt 约束强，因为下游拿到的是文本片段而不是模型转述。`sceneforge/references/quality-audit.md:32` 的做法是限定结论口径（不声称本地指标代表第三方平台内部系统），管的是「不许把局部证据说成平台判定」。`PolySafe/backend/app/services/doubao_service.py:107-127` 则完全不表达这类约束，模型输出解析失败时直接落回默认值，把 `violation_detected` 置 false、`confidence` 置 0，等于把解析失败当成「无风险」，这是另一种失效模式，见 S5-12。

- **Momcozy 迁移形态**：直接进 system prompt 的三条，按美国市场与发布前把关改写：

  1. 表达不确定性：「对是否构成医疗宣称、是否属于 FTC 要求 substantiation 的客观宣称、是否存在可识别的真实人物等无法仅从内容本身判断的，必须明确列出需要补充的信息，不得臆断。」
  2. 禁止杜撰：「仅依据提供的内容与用户给出的材料分析，不得编造检测报告、授权文件、平台政策条款等不存在的材料内容。」
  3. 兼顾正面结论：「审计报告必须包含 `pass` 与 `not_applicable` 条目，不得只列风险。未执行检查的维度必须标为 `not_checked`，不得省略。」

  第三条里新增的 `not_checked` 是针对 Momcozy 场景补的，因为发布前一次性把关会出现「图片链路已跑、视频链路未跑」的中间态，原文档没有对应取值。

- **证据强度**：已实读核实。七条底线与流程门 `skill.md:58` 均为逐字节引用；「可直接进 system prompt 的是三条」为对原文归类后的判断。

---

### S5-08 双层审计框架与「先定位再审查」前置门禁

- **出处**：`soe-legal/skill.md:26`（已实读核实）、`soe-legal/skill.md:38-58`（已实读核实）、`soe-legal/skill.md:62-82`（已实读核实）
- **一句话**：审查分两层，一层看文本本身的法律风险，一层看形成文本的过程是否合规；而两层之前还有一道更前的门，先把企业属性、合同类型、是否强制招标、金额与决策层级四件事问清楚，不清楚就先反问。

- **原文**（双层结构的定义）：

  ```26:26:soe-legal/skill.md
> **重要说明:** 国企/央企的合同审查存在"双层结构"——第一层是**合同文本本身的法律风险**(与普通企业合同审查相同),第二层是**缔约过程与决策程序的合规性**(国企特有,往往比条款措辞更容易引发问责)。本技能要求两层审查缺一不可,后者常被忽视但恰恰是审计、巡视、纪检监督的高频问题。
  ```

- **原文**（前置门禁的四问与强制反问）：

  ```38:58:soe-legal/skill.md
## 第一步:审查前定位——识别企业属性与合同类型

**先明确以下背景信息,不明确时应主动询问用户:**

1. **企业属性:**
   - 中央企业本级 / 央企各级子企业 / 地方国有独资企业 / 国有控股企业 / 国有参股企业(仅对国有资本有实际支配力才适用32号令)
   - 上市公司(如为上市公司或其控股子公司,还需叠加交易所信息披露及关联交易规则)
2. **合同类型**(决定适用哪套审查清单,见下文"分类型审查清单"):
   - 采购/物资类合同(货物、服务、工程材料采购)
   - 工程施工/EPC总承包合同
   - 政府采购合同(国企作为供应商参与政府采购项目)
   - 股权转让/产权交易类合同(企业国有产权转让、增资扩股)
   - 关联交易合同(与股东、实际控制人、其他关联方签订)
   - 境外投资/涉外合同
   - 战略合作协议/框架协议(非最终交易文本)
   - 融资租赁、担保、财务资助类合同
   - 劳动合同/薪酬福利类合同(适用通用版技能中的劳动合同清单,叠加国企负责人薪酬管制)
3. **是否属于依法必须招标项目:** 依据《招标投标法实施条例》第2条及16号令、843号文,判断本合同标的是否落入强制招标范围(全部或部分使用国有资金/国家融资的工程建设项目、大型基础设施和公用事业项目等)
4. **金额与决策层级:** 合同金额是否触发本企业"三重一大"事项清单/权责手册中规定的党委前置研究、董事会决策、股东会决策等门槛

**如企业属性、合同类型或立场不明确,应先询问用户,再开展详细审查。**
  ```

- **原文**（两层里的第二层，九个核查维度作为必须单列的一章）：

  ```68:70:soe-legal/skill.md
### 第二层:国企特有合规审查(核心增值点)

在完成文本审查后,**必须**逐项核对以下国企特有合规维度,并在报告中单列"国资合规专项核查"章节:
  ```

  ```72:82:soe-legal/skill.md
| 核查维度 | 审查要点 |
|----------|----------|
| **招标采购合规** | 该合同标的是否属于依法必须招标范围?若是,是否附招标文件、中标通知书、评标报告等前置文件?合同实质性条款是否与招标文件、投标文件保持一致(禁止"招大定小""明招暗定"、中标后另行签订背离性协议)? |
| **三重一大决策** | 合同金额、期限、担保方式等是否触发本企业"三重一大"决策清单门槛?是否已履行党委前置研究、董事会/总经理办公会集体决策、职工代表大会(涉及职工利益时)等程序?决策文件(会议纪要、表决记录)是否与合同签署主体、金额、条款一致? |
| **国有资产交易审批** | 若涉及股权转让、增资扩股、资产处置等,是否符合32号令关于进场交易、公开挂牌、资产评估、信息披露的要求?是否存在应评估未评估、应进场未进场、协议转让规避公开挂牌的情形? |
| **关联交易审查** | 交易对方是否为股东、实际控制人、董监高关联方或其近亲属控制的企业?是否按照公司章程、关联交易管理制度履行关联方回避表决、独立董事意见(如适用)、信息披露(上市公司)程序?定价是否符合公允性要求(避免利益输送)? |
| **廉洁风控** | 合同是否附带《廉洁协议》/《廉洁合作协议》/廉洁承诺条款?对方主要负责人、项目经办人是否与本企业相关人员存在利益关联(近亲属、离职人员"影子公司"等)?合同金额较大或行业敏感(工程、采购、销售)时应重点核查 |
| **境外投资/涉外合规** | 若合同一方为境外主体或标的涉及境外资产,是否符合《企业境外投资管理办法》(11号令)、《中央企业境外投资监督管理办法》(35号令)的核准/备案要求?是否涉及外汇登记、跨境担保、ODI审批? |
| **合规前置审查留痕** | 依据《中央企业合规管理办法》,重要合同签订应经过合规管理牵头部门的合法合规性审查,是否已留存审查意见、法律顾问/总法律顾问签字意见? |
| **国有资产保值增值** | 合同定价机制、付款安排、担保安排是否存在导致国有资产流失或不当风险敞口的情形(如无偿让利、超常规账期、无对价担保)? |
| **信息披露与保密衔接** | 是否涉及国家秘密、工作秘密或对上市公司构成应披露的重大事项?保密条款是否与国企信息公开、审计配合义务相冲突? |
  ```

- **为什么这样做 / 不这样做会出什么事**：第二层的存在理由是「往往比条款措辞更容易引发问责」。一份条款写得毫无瑕疵的采购合同，如果该招标没招标、该上会没上会，风险仍然成立，而且是审计与巡视的高频命中点。只做第一层会得出「合同很规范」的结论，这个结论在问责场景里没有防御力。前置门禁的理由是后续所有判断都挂在它上面：招标合规清单要不要跑，取决于第 3 问；三重一大要不要查，取决于第 4 问。四问不清楚就往下审，产出的是一份看似完整、实际用错清单的报告。`skill.md:58` 用加粗把反问设成硬约束。

- **代价与局限**：前置门禁要求用户先提供四类背景信息，实际使用中用户往往只丢一份文件过来，系统会停在反问上。skill.md 没有给出「用户不回答时怎么办」的降级路径，没有「按最严格清单先跑一遍」这类兜底。第二层的九个维度全部锚定中国国资监管框架（32 号令、11 号令、35 号令、三重一大、中央企业合规管理办法），**迁移到美国市场时这九个维度整体作废**，只剩「存在第二层」这个结构性判断可用。

- **横向对比**：`PolySafe/backend/app/models.py:26` 把「定位」这一步做成了内容类型的自动判定（`content_type` 取 `image / video / text`），由文件扩展名决定，用户不需要回答任何问题。它这样做是因为内容审核的清单不随内容类型变化太大，三类走的是同一个 prompt（`doubao_service.py:10-22` 的 `AUDIT_PROMPT` 对三类共用）。代价是它无法表达「同一个画面在 TikTok 和 Meta 上判定不同」这种依渠道而变的清单，而 `soe-legal` 的前置门禁恰好是为了解决这类「先确定适用哪套规则」的问题。

- **Momcozy 迁移形态**：双层结构直接搬，第二层的内容整层替换为**内容生产链路合规**：

  | 核查维度 | 审查要点 |
  |---|---|
  | AIGC 生成标识 | 该内容是否由生成式模型产出？若是，是否按投放平台要求标注？是否有 C2PA 或等效来源清单？ |
  | 肖像与人物授权 | 画面中可识别的人物（含婴儿）是否有签署的肖像授权？授权范围是否覆盖该投放渠道与期限？ |
  | 素材来源与版权 | 音乐、字体、影视片段、第三方产品图是否有可核验的授权记录？ |
  | 宣称证据存档 | 每一条功效或性能宣称是否有对应的 substantiation 文件？存档时间是否早于内容发布时间？ |
  | 达人合作披露 | 付费合作是否按 FTC Endorsement Guides 披露？披露位置与形式是否达标？ |
  | 生产过程留痕 | 从 brief 到成片的修改记录、审核记录是否可追溯？ |

  前置门禁改写为四问：**投放渠道**（TikTok / Amazon / Meta / 独立站，决定适用哪套平台政策）、**内容类型与是否含 AIGC**（决定是否进入溯源层）、**目标人群是否涉及儿童或婴幼儿**（决定是否叠加儿童隐私与儿童广告的额外清单）、**宣称强度与是否含医疗 / 器械类表述**（决定是否需要 FDA 路径复核）。四问任一不明时按 `skill.md:58` 的做法强制反问。

- **证据强度**：已实读核实。双层结构的定义、四个前置问题、九个核查维度均为逐字节引用；「迁移到美国市场时九个维度整体作废」为对原文法域依赖的判断。

---

### S5-09 HITL 做进状态机：`interrupt_after` + checkpointer

- **出处**：`contract_audit/legal_agent/graph.py:59-69`（已实读核实）、`contract_audit/legal_agent/main.py:75-98`（已实读核实）
- **一句话**：人工闸门不是流程外的一步确认，而是状态机的一次中断；图在风险定级节点之后停下并落盘快照，人工读快照、确认或改写状态，再用同一个线程 id 续跑。

- **原文**（中断点的声明位置）：

  ```59:69:contract_audit/legal_agent/graph.py
    # 设置 Checkpointer 以支持状态持久化和中断
    checkpointer = MemorySaver()

    # 编译图
    # 在 RiskEvaluator 后中断，以便人工审核风险
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["risk_evaluator"]
    )
    
    return app
  ```

- **原文**（图与边的完整定义，中断点落在哪条边上）：

  ```31:57:contract_audit/legal_agent/graph.py
def create_graph():
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("contract_parser", contract_parser_node)
    workflow.add_node("compliance_auditor", compliance_auditor_node)
    workflow.add_node("risk_evaluator", risk_evaluator_node)
    workflow.add_node("redline_generator", redline_generator_node)
    workflow.add_node("final_assembler", final_assembler_node)

    # 构建边
    workflow.set_entry_point("contract_parser")
    workflow.add_edge("contract_parser", "compliance_auditor")
    workflow.add_edge("compliance_auditor", "risk_evaluator")

    # 条件边
    workflow.add_conditional_edges(
        "risk_evaluator",
        route_risks,
        {
            "redline_generator": "redline_generator",
            "final_assembler": "final_assembler"
        }
    )

    workflow.add_edge("redline_generator", "final_assembler")
    workflow.add_edge("final_assembler", END)
  ```

- **原文**（人工侧：读快照、取 `snapshot.next`、续跑）：

  ```75:98:contract_audit/legal_agent/main.py
    # 4. 检查中断状态
    snapshot = app.get_state(config)
    if snapshot.next:
        print(f"\n[中断] 工作流暂停位置: {snapshot.next}")
        print("等待人工审核风险...")
        
        # 获取当前状态中的 risks
        current_risks = snapshot.values.get("risks", [])
        print(json.dumps(current_risks, indent=2, ensure_ascii=False))
        
        # 模拟人工审核：我们假设用户确认了风险
        # 在实际应用中，这里可以修改 state，例如 snapshot.values["risks"][0]["level"] = "Medium"
        # 然后使用 app.update_state(config, {"risks": modified_risks})
        
        print("\n[人工操作] 风险已确认。恢复工作流...")
        
        # 5. 恢复运行
        # 传入 None 表示继续执行
        for event in app.stream(None, config, stream_mode="updates"):
            for node_name, node_output in event.items():
                print(f"\n[节点完成] {node_name}")
                if node_name == "redline_generator":
                    revisions = node_output.get("revisions", [])
                    print(f"--> 生成了 {len(revisions)} 条修订建议。")
  ```

- **为什么这样做 / 不这样做会出什么事**：中断点选在风险定级之后、修订生成之前，对应的是「最贵的下游动作开跑之前先让人看一眼」这个经济判断，见 S5-10。`snapshot.next` 是判断「是否真停在中断处」的依据，`main.py:77` 用它做分支。续跑的调用形态是 `app.stream(None, config, stream_mode="updates")`，第一个参数传 `None` 表示不注入新输入，直接从检查点往下走；`config` 里的 `thread_id` 必须与首次运行一致，`main.py:56-57` 在启动时生成 `thread_id = str(uuid.uuid4())` 并放进 `configurable`。改写人工判断的接口在 `main.py:86-87` 的注释里写明：先改 `snapshot.values["risks"][0]["level"]`，再 `app.update_state(config, {"risks": modified_risks})`。整个机制成立的前提是编译时挂了 `MemorySaver()`，没有 checkpointer 就没有可落盘的中断点。

- **代价与局限**：`MemorySaver` 是内存检查点，进程退出后快照消失，`main.py:56` 的 `thread_id` 也在每次启动时新生成，因此这套中断只活在单次进程生命周期内。`main.py:85-87` 把人工审核写成了「我们假设用户确认了风险」，真实的改写调用被注释掉了，仓库里没有可运行的交互层（`contract_audit/legal_agent/ui.py` 与 `app.py` 存在，但不在本次核对范围内）。中断点只有一个，落在 `interrupt_after=["risk_evaluator"]`，无法在解析后也插一道人工确认。另外人工改的是 `risks` 这一项，而下游 `redline_generator` 读的正是 `high_risks`（`nodes/redliner.py:31-32`），所以改写 `level` 会真实改变路由结果，这一点是可靠的。

- **横向对比**：`PolySafe/backend/app/routers/tasks.py:78-90` 用数据库状态列实现同一件事：`review_task` 先检查 `task.status != "review"` 则报 400，然后 `task.status = body.action` 写库。它这样做的好处是中断状态天然持久化，服务重启后仍可继续，且天然支持多批次并行复核；`contract_audit` 的 `MemorySaver` 只活在进程里，重启即丢。代价是 `PolySafe` 的人工复核只能改「结论」这一个字段，无法回写中间推理结果再让下游按新结果重跑，因为它的流程没有图、没有可续跑的中间态。

- **Momcozy 迁移形态**：在内容审计流水线上设两个中断点，而不是一个。第一个落在「AI 判定完成、规则匹配完成、结论尚未落库」之间，字段 `interrupt_after=["rule_match"]`，此时人工看到的是 `confidence`、`violation_types`、命中规则列表三样，对应的动作是「确认定级」。第二个落在「AIGC 溯源检查完成、发布前最终把关之前」，人工看到的是 `c2pa_present` 与 `likely_ai_generated` 两个字段，动作是「确认是否放行到渠道」。checkpointer 不用 `MemorySaver`，改为落库（Postgres / SQLite 皆可），`thread_id` 用 `content_id` 而不是随机 uuid，这样同一条内容在人工复核后重新进入流水线时可以复用同一个线程。人工改写接口固定为 `update_state(config, {"verdict": ..., "reviewer_id": ..., "reviewed_at": ...})`，把复核人写进状态，补上 `contract_audit` 这套里缺失的可追责字段。

- **证据强度**：已实读核实。`interrupt_after`、`MemorySaver`、`snapshot.next`、`stream(None, config)` 的调用形态均在原文中；「人工改写 `risks` 会改变路由」为顺着 `main.py:86` 的注释与 `graph.py:24` 的判据再做一跳后的判断，已核对 `nodes/redliner.py:31-32` 读取的字段名。

---

### S5-10 条件路由：仅 High 才触发最贵的下游节点

- **出处**：`contract_audit/legal_agent/graph.py:16-29`（已实读核实）、`contract_audit/legal_agent/nodes/redliner.py:25-32`（已实读核实）
- **一句话**：路由判据是一行 `any(...)`，只要风险列表里出现一个 `level == "High"` 就走修订生成节点，否则直接跳到汇总；判据只看等级字符串，不看分数、不看数量。

- **原文**（路由函数）：

  ```16:29:contract_audit/legal_agent/graph.py
def route_risks(state: AgentState):
    """
    路由逻辑：
    - IF 存在 level == 'High': 进入 RedlineGenerator
    - ELSE: 进入 FinalAssembler
    """
    risks = state.get("risks", [])
    
    has_high_risk = any(r.get("level") == "High" for r in risks)
    
    if has_high_risk:
        return "redline_generator"
    else:
        return "final_assembler"
  ```

- **原文**（被保护的下游节点开头，先做同一判据的二次过滤）：

  ````22:34:contract_audit/legal_agent/nodes/redliner.py
    risks = state.get("risks", [])
    clauses = state.get("clauses", [])
    
    # 筛选出需要修订的风险项
    high_risks = [r for r in risks if r.get("needs_revision")]
    
    if not high_risks:
        return {"revisions": []}
        
    context_str = json.dumps({
        "risks": high_risks,
        "clauses": clauses
    }, ensure_ascii=False, indent=2)
````

- **为什么这样做 / 不这样做会出什么事**：修订生成是这条链上唯一需要把高风险条款原文再送一次模型、并产出可直接替换的条款文本的节点，输入长度与输出长度都远超前面几个节点。用 `any()` 做闸门，等于只要没有 High 就一次都不调用它。这个判断还改变了报告形态：没有 High 的合同拿到的是「风险清单 + 汇总」，有 High 的合同拿到的是「风险清单 + 逐条修订建议 + 汇总」。`redliner.py:28-30` 在节点内部重复了同一个判据，注释写明了它是防御性的，因为「路由应该已经阻止了这种情况」，这类双重校验在状态被人工改写过之后确实有意义（见 S5-09，人工可以把某个风险的 `level` 从 High 改成 Medium，此时中断恢复后的路由与节点内部的判据会同时按新值走）。

- **代价与局限**：判据只看一个字符串是否等于 `"High"`，大小写与拼写都要精确匹配。等级字符串由 LLM 给出，`nodes/evaluator.py:11` 的字段说明是 `level: str = Field(description="High, Medium, or Low")`，`Risk` 模型没有枚举约束，因此 `"high"`、`"HIGH"`、`"高风险"` 都会让 `any()` 返回 False，静默地跳过修订生成。这处没有兜底，也没有对未知等级的告警。另外 `any()` 只回答「有没有」，不回答「有几条」，一条 High 和十条 High 走同一条路径。

- **横向对比**：`PolySafe/backend/app/services/rule_engine.py:17-25` 没有条件跳过这一层，规则匹配对每条内容都执行，判据是三段式阈值，对置信度与规则命中同时设界，不需要先判「有没有某个等级」。它这样做的前提是规则匹配很便宜（一次 FAISS 检索加两个列表推导），跳不跳过省不下多少。`contract_audit` 之所以需要这道闸门，是因为下游是又一次完整的大模型调用，成本量级不同。代价是 `PolySafe` 的每条内容都要付规则匹配的钱，而 `contract_audit` 省下的这笔钱需要一个精确的字符串判据来换。

- **Momcozy 迁移形态**：把闸门从「等级字符串」改成「下一跳的动作类型」，判据落在 S5-06 定义的封闭枚举上：`verdict == "needs_rewrite"` 才进入文案改写生成节点，`verdict == "needs_evidence"` 进入证据索要通知节点（不调模型，只发工单），`verdict == "blocked"` 直接终止并记录。这样闸门同时承担了分派职责，避免所有非通过的内容都被送进最贵的改写链路。等级字符串那一层的隐患要在 Momcozy 侧堵掉：`verdict` 用枚举常量而不是模型输出的自由文本，模型输出先过一层归一化再写入状态。

- **证据强度**：已实读核实。路由函数、条件边映射、下游节点的二次过滤均为逐字节引用；「大小写不匹配会静默跳过」为对 `evaluator.py:11` 字段定义（无枚举约束）与 `graph.py:24` 判据比对后的判断，已核对 `Risk` 模型定义。

---

### S5-11 显式状态契约，以及「reducer 缺失导致覆盖而非累加」这一论断的实读核查

- **出处**：`contract_audit/legal_agent/state.py:1-14`（已实读核实，全文 14 行）、`contract_audit/legal_agent/nodes/evaluator.py:86-95`（已实读核实）、`contract_audit/legal_agent/nodes/parser.py:64-74`（已实读核实）、`contract_audit/legal_agent/nodes/redliner.py:68-77`（已实读核实）
- **一句话**：状态契约用 7 个字段把图的全部中间产物写在一个 `TypedDict` 里，字段名即数据流；但契约只声明了字段类型，没有声明合并规则。

- **原文**（state.py 全文）：

  ```1:14:contract_audit/legal_agent/state.py
from typing import List, Dict, Any, Optional, TypedDict
import operator

class AgentState(TypedDict):
    """
    全局状态定义 (Graph State)
    """
    raw_text: str               # 原始合同文本
    metadata: Dict[str, Any]    # 合同类型、主体等
    clauses: List[Dict[str, Any]]         # 提取的原始条款片段
    audit_results: List[Dict[str, Any]]   # 发现的合规缺口
    risks: List[Dict[str, Any]]           # 风险分级与评估
    revisions: List[Dict[str, Any]]       # 最终修订建议
    error_log: List[str]        # 容错重试记录
  ```

- **核查对象**：上一份调研报告的论断是「`import operator` 引入后未使用、无 reducer、节点返回是覆盖而非累加」。逐条核实如下。

  **子论断一（`import operator` 引入后未使用）：成立。** `state.py` 全文 14 行，`import operator` 在第 2 行，此后 `operator` 这个标识符在文件内不再出现。全文检索该仓库的 `operator` 只命中这一行：

  ```1:2:contract_audit/legal_agent/state.py
from typing import List, Dict, Any, Optional, TypedDict
import operator
  ```

  同一行的 `Optional` 也未被使用，属于同类情况（`List`、`Dict`、`Any`、`TypedDict` 都在字段声明里出现）。

  **子论断二（无 reducer）：成立。** `TypedDict` 的每个字段都是裸类型标注，没有任何一个写成 `Annotated[..., reducer]` 形式。判断依据是全文 14 行里 `Annotated` 一次都没出现，且 7 个字段的标注分别是 `str`、`Dict[str, Any]`、`List[Dict[str, Any]]`（四例）、`List[str]`，没有一处带下标以外的第二个参数。在 LangGraph 里，字段只有写成 `Annotated[list, operator.add]` 这类形式才会在节点返回时做合并，否则返回的键直接替换旧值。`state.py:2` 的 `import operator` 恰好是写 reducer 时最常用的那个函数，引入而未使用这一事实本身说明契约曾经打算声明 reducer 而最终没有。

  **子论断三（节点返回是覆盖而非累加）：成立，且这一点在原文里有直接证据。** 三个正常路径的返回都是整值替换：

  ```64:67:contract_audit/legal_agent/nodes/parser.py
        return {
            "metadata": metadata,
            "clauses": clauses
        }
  ```

  ```60:62:contract_audit/legal_agent/nodes/auditor.py
        return {
            "audit_results": audit_results
        }
  ```

  ```86:88:contract_audit/legal_agent/nodes/evaluator.py
        return {
            "risks": risks
        }
  ```

  更直接的证据是 `error_log` 的处理方式。四个节点在异常分支里都手写了列表拼接，而不是依赖框架合并：

  ```72:74:contract_audit/legal_agent/nodes/parser.py
        return {
            "error_log": state.get("error_log", []) + [f"ContractParser Error: {str(e)}"]
        }
  ```

  ```93:95:contract_audit/legal_agent/nodes/evaluator.py
        return {
            "error_log": state.get("error_log", []) + [f"RiskEvaluator Error: {str(e)}"]
        }
  ```

  ```75:77:contract_audit/legal_agent/nodes/redliner.py
        return {
            "error_log": state.get("error_log", []) + [f"RedlineGenerator Error: {str(e)}"]
        }
  ```

  `state.get("error_log", []) + [...]` 这个写法只有在「返回会整体覆盖旧值」的前提下才必要。如果字段声明了 `operator.add` 作为 reducer，节点只需返回增量列表，框架会负责拼接；手写拼接正是对缺少 reducer 的补偿。`nodes/auditor.py:65-67` 是同一形态的第四例。

  **核查结论：三条子论断全部成立。** 补一处上一份报告没写的：覆盖行为在 `error_log` 上是**单次覆盖**而非跨节点累加。因为在同一轮里只有一个节点会走异常分支并返回，且它返回的是「旧值 + 新条目」的完整列表，所以单次运行的最终 `error_log` 看起来是正确的；但如果两个节点先后异常，第二个节点读到的 `state.get("error_log")` 是第一个节点写入后的值（LangGraph 会把返回值合并进状态树），拼接仍然成立。真正会丢数据的是同一节点在同一轮内被多次调用，此时后一次的返回会覆盖前一次，而这份图里没有环，所以当前形态下不会触发。也就是说，这个缺陷是**潜伏的**：图的拓扑一旦引入循环或并行分支，`error_log` 与 `risks` 都会静默丢失前一次写入的内容。

- **为什么这样做 / 不这样做会出什么事**：用 `TypedDict` 声明全部字段，好处是数据流在单个文件里可读，14 行就能看清一条合同从原文到修订建议经过哪些中间产物。不声明 reducer 则省掉了为每个字段挑选合并函数的决策成本。但这两件事合在一起会形成一个陷阱：契约读起来像「字段是累积的容器」（四例都是 `List[...]`），实际行为是「每次返回替换整个字段」。开发者在后期给图加一个循环或并行节点时，会预期 `audit_results` 越跑越多，实际拿到的是最后一轮的。

- **代价与局限**：类型标注只约束形状，不约束合并语义，静态检查发现不了这处问题。`import operator` 的存在会让读者以为 reducer 已经在用。除了合并语义之外，这份契约还有一处留白：7 个字段里没有承载「谁做的判定」「用了哪版规则」的位置，`raw_text` 到 `revisions` 全是内容字段，`error_log` 是唯一的元信息字段，而这些恰好是 S5-04 报告原则里要求记录的东西。

- **横向对比**：`PolySafe/backend/app/models.py:20-40` 用数据库列表达状态契约，`Task` 表把 7 类信息拆成独立列（`ai_result`、`matched_rules`、`confidence`、`violation_types`、`risk_description`、`review_comment`、`process_logs`），每一步都是 `db.commit()` 落盘（`task_service.py:47`、`:64`、`:74`、`:82`）。它这样做避开了合并语义的问题，因为 SQLAlchemy 的列赋值就是替换，没有「累加」的暗示；代价是每次更新都是全量行写，而且没有中间态的快照，无法像 `contract_audit` 那样回到某个节点之前重跑。两边的选择对应两种不同的失败模式：`contract_audit` 的风险是契约看起来像累加实际是覆盖，`PolySafe` 的风险是列赋值语义明确但丢失了可回溯的中间历史。

- **Momcozy 迁移形态**：状态契约写成 9 个字段，比 `contract_audit` 多两个元信息字段：

  ```python
  class ContentAuditState(TypedDict):
      content_id: str
      content_type: str                 # image / video / text
      channel: str                      # tiktok / amazon / meta / dtc
      raw_artifact: Dict[str, Any]      # 素材引用与哈希
      extract_results: List[Dict[str, Any]]
      verdicts: Annotated[List[Dict[str, Any]], operator.add]
      aigc_trace: Dict[str, Any]        # c2pa_present / likely_ai_generated
      error_log: Annotated[List[str], operator.add]
      audit_trail: List[Dict[str, Any]] # reviewer_id / reviewed_at / rule_version
  ```

  两处与 `contract_audit` 不同：`verdicts` 与 `error_log` 显式标注 `operator.add`，把合并语义写进契约而不是靠节点手写拼接；新增 `audit_trail` 承载复核人与规则版本，对应 S5-04 的报告原则与 S5-09 的可追责要求。`Annotated` 与 `operator` 要真的用起来，`import operator` 才有意义。

- **证据强度**：已实读核实。三条子论断逐条核对，证据为 `state.py` 全文、四个节点的返回语句、三处 `error_log` 手写拼接；「缺陷是潜伏的、图的拓扑引入循环后才会触发」为【推断】，依据是本仓库的图拓扑无环（`graph.py:42-57` 的边集合）。

---

### S5-12 批次 + 任务模型、统一多模态输出契约与三段式阈值

- **出处**：`PolySafe/backend/app/models.py:8-67`（已实读核实）、`PolySafe/backend/app/routers/batches.py:20-40`（已实读核实）、`PolySafe/backend/app/services/task_service.py:10-101`（已实读核实）、`PolySafe/backend/app/services/rule_engine.py:1-36`（已实读核实）、`PolySafe/backend/app/services/doubao_service.py:10-22`（已实读核实）、`PolySafe/backend/app/services/doubao_service.py:107-127`（已实读核实）、`PolySafe/backend/seed_data.py:11-19`（已实读核实）、`PolySafe/backend/seed_data.py:117-133`（已实读核实）
- **一句话**：三层数据模型（批次 / 任务 / 策略-规则两级），所有模态统一输出同一个四字段 JSON，再由一个纯函数把它压成三种处置之一。

- **原文**（批次与任务模型，注意 `status` 列注释里的五值）：

  ```8:40:PolySafe/backend/app/models.py
class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), default="")
    total_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    tasks = relationship("Task", back_populates="batch", lazy="joined")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    original_filename = Column(String(500), default="")
    content_type = Column(String(20), nullable=False)  # image / video / text
    content_url = Column(String(500), default="")
    content_text = Column(Text, default="")
    status = Column(String(20), default="pending")  # pending / pass / block / review / error
    ai_result = Column(Text, default="")  # JSON: AI模型分析结果
    matched_rules = Column(Text, default="")  # JSON: 命中的规则列表
    confidence = Column(Float, default=0.0)
    violation_types = Column(String(200), default="")
    risk_description = Column(Text, default="")
    review_comment = Column(Text, default="")
    process_logs = Column(Text, default="")  # JSON: 任务处理过程日志
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    batch = relationship("Batch", back_populates="tasks")
  ```

- **原文**（策略与规则的两级模型）：

  ```43:67:PolySafe/backend/app/models.py
class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    rules = relationship("Rule", back_populates="policy", cascade="all, delete-orphan")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    violation_type = Column(String(50), nullable=False)  # porn / violence / hate / spam / illegal / other
    action = Column(String(20), default="block")  # block / review / pass
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    policy = relationship("Policy", back_populates="rules")
  ```

- **原文**（统一多模态输出契约，三类内容共用一个 prompt）：

  ```10:22:PolySafe/backend/app/services/doubao_service.py
AUDIT_PROMPT = """你是一个专业的内容审核AI助手。请分析以下内容，判断是否存在违规信息。

请按以下JSON格式返回分析结果（只返回JSON，不要其他内容）：
{
    "violation_detected": true/false,
    "violation_types": ["违规类型1", "违规类型2"],
    "confidence": 0.0-1.0,
    "risk_description": "风险描述"
}

违规类型包括：色情、暴力、仇恨言论、垃圾广告、违法违规、其他
confidence 为你对判断的置信度，0表示完全无风险，1表示确定违规。
如果内容正常无风险，violation_types为空数组，confidence接近0。"""
  ```

- **原文**（三段式阈值，以及同一函数里的两处 0.3 门槛）：

  ```1:36:PolySafe/backend/app/services/rule_engine.py
from app.services.faiss_service import faiss_service


def judge(ai_result: dict, db=None) -> dict:
    confidence = ai_result.get("confidence", 0.0)
    violation_types = ai_result.get("violation_types", [])
    risk_desc = ai_result.get("risk_description", "")

    similar_rules = []
    if risk_desc:
        query = f"{' '.join(violation_types)} {risk_desc}"
        similar_rules = faiss_service.search_similar_rules(query, top_k=5)

    block_rules = [r for r in similar_rules if r.get("action") == "block" and r.get("similarity", 0) > 0.3]
    review_rules = [r for r in similar_rules if r.get("action") == "review" and r.get("similarity", 0) > 0.3]

    if confidence >= 0.8 and (block_rules or ai_result.get("violation_detected")):
        action = "block"
        reason = "高置信度违规，命中拦截规则"
    elif confidence <= 0.3 and not block_rules and not review_rules:
        action = "pass"
        reason = "低风险内容，未命中违规规则"
    else:
        action = "review"
        reason = "置信度中等或命中复核规则，需人工复核"

    matched = [
        {"id": r["id"], "name": r["name"], "action": r["action"], "similarity": round(r["similarity"], 3)}
        for r in similar_rules if r.get("similarity", 0) > 0.3
    ]

    return {
        "action": action,
        "reason": reason,
        "matched_rules": matched,
    }
  ```

- **原文**（批次聚合：终态集合与各计数）：

  ```20:40:PolySafe/backend/app/routers/batches.py
def _batch_to_out(batch: Batch) -> dict:
    tasks = batch.tasks or []
    status_counts = {}
    for t in tasks:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1
    terminal = {"pass", "block", "review", "error"}
    done = sum(v for k, v in status_counts.items() if k in terminal)
    return {
        "id": batch.id,
        "name": batch.name,
        "total_count": batch.total_count,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at,
        "tasks": tasks,
        "pass_count": status_counts.get("pass", 0),
        "block_count": status_counts.get("block", 0),
        "review_count": status_counts.get("review", 0),
        "error_count": status_counts.get("error", 0),
        "pending_count": status_counts.get("pending", 0) + status_counts.get("processing", 0),
        "done_count": done,
    }
  ```

- **原文**（任务处理主流程的五个落盘点）：

  ```10:10:PolySafe/backend/app/services/task_service.py
TERMINAL_STATUS = {"pass", "block", "review", "error"}
  ```

  ```39:63:PolySafe/backend/app/services/task_service.py
async def process_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        task.status = "processing"
        db.commit()
        append_log(db, task, "start", "任务进入处理队列")

        append_log(db, task, "model", f"正在调用{task.content_type}识别模型")
        if task.content_type == "image":
            ai_result = await doubao_service.analyze_image(task.content_url)
        elif task.content_type == "video":
            ai_result = await doubao_service.analyze_video(task.content_url)
        elif task.content_type == "text":
            ai_result = await doubao_service.analyze_text(task.content_text)
        else:
            raise ValueError(f"不支持的内容类型: {task.content_type}")

        task.ai_result = json.dumps(ai_result, ensure_ascii=False)
        task.confidence = ai_result.get("confidence", 0.0)
        task.violation_types = ",".join(ai_result.get("violation_types", []))
        task.risk_description = ai_result.get("risk_description", "")
  ```

  ```71:86:PolySafe/backend/app/services/task_service.py
        append_log(db, task, "rule_match", "开始匹配策略规则")
        judgment = rule_engine.judge(ai_result, db)
        task.matched_rules = json.dumps(judgment["matched_rules"], ensure_ascii=False)
        db.commit()
        append_log(db, task, "rule_match", "规则匹配完成", {
            "matched_count": len(judgment["matched_rules"]),
            "matched_rules": judgment["matched_rules"],
        })

        task.status = judgment["action"]
        task.updated_at = datetime.now()
        db.commit()
        append_log(db, task, "decision", "策略决策完成", {
            "final_action": judgment["action"],
            "reason": judgment["reason"],
        })
  ```

- **原文**（解析失败时的默认值，把不可解析当成无风险）：

  ```107:127:PolySafe/backend/app/services/doubao_service.py
def _parse_result(text: str) -> dict:
    default = {
        "violation_detected": False,
        "violation_types": [],
        "confidence": 0.0,
        "risk_description": "解析失败",
    }
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        result = json.loads(text)
        return {
            "violation_detected": bool(result.get("violation_detected", False)),
            "violation_types": result.get("violation_types", []),
            "confidence": float(result.get("confidence", 0.0)),
            "risk_description": result.get("risk_description", ""),
        }
    except (json.JSONDecodeError, ValueError):
        return default
  ```

- **原文**（种子数据的结构，12 策略 / 30 规则）：

  ```11:20:PolySafe/backend/seed_data.py
SEED_POLICIES = [
    {
        "name": "色情内容审核策略",
        "description": "识别和拦截包含色情、低俗、裸露等不良内容",
        "rules": [
            {"name": "色情图片检测", "description": "检测图片中的色情、裸露、性暗示等内容", "violation_type": "色情", "action": "block", "priority": 10},
            {"name": "低俗文字过滤", "description": "过滤文本中的低俗、淫秽、挑逗性语言", "violation_type": "色情", "action": "block", "priority": 9},
            {"name": "擦边内容复核", "description": "对可能存在擦边球的暧昧内容进行人工复核", "violation_type": "色情", "action": "review", "priority": 5},
        ],
    },
  ```

  ```117:133:PolySafe/backend/seed_data.py
def seed():
    db = SessionLocal()
    existing = db.query(Policy).count()
    if existing > 0:
        print(f"数据库已有 {existing} 条策略，跳过种子数据初始化")
        db.close()
        return

    for p_data in SEED_POLICIES:
        policy = Policy(name=p_data["name"], description=p_data["description"])
        for r_data in p_data["rules"]:
            rule = Rule(**r_data)
            policy.rules.append(rule)
        db.add(policy)

    db.commit()
    print(f"成功初始化 {len(SEED_POLICIES)} 条审核策略")
  ```

  种子数据的规模按 `splitlines()` 口径逐条统计：`SEED_POLICIES` 含 **12 个策略字典**，`"action"` 键出现 **30 次**（即 30 条规则），分布为 `block` 17 条、`review` 12 条、`pass` 1 条；`violation_type` 覆盖 12 类，`色情` / `暴力` / `违法违规` / `隐私泄露` / `未成年人保护` / `自伤自残` 各 3 条，`仇恨言论` / `垃圾广告` / `网络欺凌` / `版权侵权` / `虚假宣传` / `平台秩序` 各 2 条（按代码内 `violation_type` 字面统计）。

- **为什么这样做 / 不这样做会出什么事**：统一四字段契约让图片、视频、文本走同一条下游链路。`doubao_service.py:48-70` 的三个函数只在构造 `content` 数组时不同（`input_image` / `input_video` / `input_text`），`_call_model` 与 `_parse_result` 完全共用，因此规则匹配、状态流转、批次统计都只需实现一次。三段式阈值的关键在于中间那一段：只有 `confidence >= 0.8` **且** 命中拦截规则才 `block`，只有 `confidence <= 0.3` **且** 没有任何命中才 `pass`，其余全部进 `review`。这条设计让模型说了「违规」但置信度不高、或置信度很高但规则库不认识的情况都落到人工手上，而不是被自动放行或自动拦截。`rule_engine.py:14-15` 与 `:29` 用了同一个 0.3 作为规则相似度门槛，与置信度阈值的 0.3 数值相同但语义不同，读代码时容易混淆。

- **代价与局限**：`_parse_result` 是这套设计里最脆弱的一处。模型输出解析失败时返回 `default`，其中 `violation_detected` 为 `False`、`confidence` 为 `0.0`。这份默认值进入 `rule_engine.judge` 后，若 `risk_description` 为「解析失败」这一非空字符串，会去检索规则库；检索结果为空则三个条件分支都不满足第一、第二条，落到 `review`。也就是说，解析失败在当前实现下最终会进人工复核，这个结果是对的，但**路径是偶然的**：它依赖 `risk_description` 非空这一事实触发检索、再依赖检索无命中。如果规则库里恰好有一条与「解析失败」相似的规则，结论就会变成 `block`。另一处局限是 `Task.status` 的取值没有数据库层约束（`String(20)` 加默认值），注释里列了 5 个值而实际代码会写入 `processing`，共 6 个值，而 `_batch_to_out` 的 `terminal` 集合只认 4 个。`pending_count` 的计算方式是把 `pending` 与 `processing` 相加，说明作者知道 `processing` 这个值不在注释的枚举里。

- **横向对比**：`contract_audit` 对同一问题（把模型输出转成可路由的结论）的做法是让 LLM 自己定级，`nodes/evaluator.py:35-39` 的 prompt 给出三档定义，然后由 `graph.py:24` 的字符串判据路由。`PolySafe` 的做法是在模型之后加一层确定性函数 `rule_engine.judge`，阈值写死在代码里。两者的代价相反：前者可以在任意细粒度上表达风险，但定级结果不可复现；后者完全可复现，但规则库没覆盖的违规类型只能落到 `review`，且 `confidence` 的语义完全由模型的自我报告决定，`doubao_service.py:21` 只说了「0表示完全无风险，1表示确定违规」，没有校准要求。`PolySafe` 还有个 `contract_audit` 没有的能力，批次聚合（`batches.py:20-40`），代价是它按 `status` 字符串来汇总，`status` 一旦出现枚举外的值就会从所有计数里消失。

- **Momcozy 迁移形态**：三层模型保留，第二层的 `Task` 表按发布前把关场景调整：`status` 取值封闭为 `pending / processing / pass / block / review / error / not_checked` 七个，`not_checked` 用于「视频链路未跑」这类中间态，并给 `status` 加数据库层 CHECK 约束（`PolySafe` 这一处没有约束，见上）。统一输出契约保留四字段并新增三个 Momcozy 专属字段：`claim_types`（命中的宣称类型，如 `medical` / `comparative` / `performance`）、`aigc_signals`（`c2pa_present` / `synthetic_face_suspected` / `platform_ai_label_present`）、`jurisdiction_findings`（按渠道分列，因为同一条内容在 Amazon 与 TikTok 上的结论不同）。三段式阈值改写成：`confidence >= 0.85 且命中拦截规则 → block`；`confidence <= 0.25 且无任何命中且 aigc_signals 全为阴性 → pass`；其余 → `review`。中间段在 Momcozy 场景下会比 `PolySafe` 更宽，因为美国市场的合规判断（例如一句功效宣称是否构成医疗宣称）本身就是需要人判断的问题，自动化只负责把候选挑出来。

- **证据强度**：已实读核实。模型定义、三段式阈值、统一 prompt、批次聚合、主流程落盘点、种子数据结构均为逐字节引用；「12 策略 30 规则」为按 `SEED_POLICIES` 与 `"action"` 键逐条统计所得；「解析失败最终进 review 的路径是偶然的」为【推断】，依据是 `rule_engine.py:17-25` 三个分支的条件组合与 `doubao_service.py:112` 的默认 `risk_description` 取值。

---

### S5-13 独立核查：`PolySafe/` 与 `omniguard/` 是否为同一个项目

- **出处**：`PolySafe/` 与 `omniguard/` 两个目录全树比对（已实读核实）
- **一句话**：是同一个项目的两份快照，文件清单与目录结构完全一致（各 68 个文件），但有 7 个文件内容不同；这 7 处里只有 5 处是纯改名，另外 2 处是真实内容变更，且 `omniguard/` 内部仍留有两处旧名残留。

- **核查方法**：

  ```bash
  diff -rq --exclude=.git PolySafe omniguard
  ```

- **核查结果**（7 个文件不同，与已知初步结论的文件数一致）：

  ```
  Files PolySafe/.gitignore and omniguard/.gitignore differ
  Files PolySafe/README.md and omniguard/README.md differ
  Files PolySafe/assets/首页.png and omniguard/assets/首页.png differ
  Files PolySafe/backend/.env.example and omniguard/backend/.env.example differ
  Files PolySafe/frontend/index.html and omniguard/frontend/index.html differ
  Files PolySafe/frontend/src/pages/HomePage.tsx and omniguard/frontend/src/pages/HomePage.tsx differ
  Files PolySafe/frontend/src/pages/LoginPage.tsx and omniguard/frontend/src/pages/LoginPage.tsx differ
  ```

  文件总数对比：`find PolySafe -type f -not -path "*/.git/*" | wc -l` 得 68，`find omniguard -type f -not -path "*/.git/*" | wc -l` 得 68。两个目录的全部后端 Python 文件、前端其余组件、`LICENSE`、`public/vite.svg` 等均逐字节相同。

- **逐项差异性质**（5 处纯改名）：

  **1. `README.md` 标题**。`PolySafe/README.md:1` 是 `# PolySafe —— 多模态内容智能审核系统`，`omniguard/README.md:1` 是 `# OmniGuard —— 多模态内容智能审核系统`，其余一字未动。项目结构小节里的目录名同样被改：

  ```1:1:PolySafe/README.md
# PolySafe —— 多模态内容智能审核系统
  ```

  ```1:1:omniguard/README.md
# OmniGuard —— 多模态内容智能审核系统
  ```

  **2. `frontend/index.html:7` 的页面标题**：

  ```7:7:PolySafe/frontend/index.html
    <title>PolySafe - 多模态内容智能审核系统</title>
  ```

  ```7:7:omniguard/frontend/index.html
    <title>OmniGuard - 多模态内容智能审核系统</title>
  ```

  **3. `frontend/src/pages/HomePage.tsx:109` 的品牌文字**（相邻行作为定位锚点一并引用）：

  ```106:110:PolySafe/frontend/src/pages/HomePage.tsx
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-slate-800 tracking-tight">
              PolySafe
            </span>
  ```

  ```106:110:omniguard/frontend/src/pages/HomePage.tsx
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-xl text-slate-800 tracking-tight">
              OmniGuard
            </span>
  ```

  **4. `frontend/src/pages/LoginPage.tsx:70` 的品牌文字**：

  ```67:70:PolySafe/frontend/src/pages/LoginPage.tsx
            <div className="w-10 h-10 rounded-xl bg-white/70 backdrop-blur-sm flex items-center justify-center border border-white/80 shadow-sm">
              <ShieldCheck className="w-6 h-6 text-[#1a5276]" />
            </div>
            <span className="text-slate-800 font-bold text-xl">PolySafe</span>
  ```

  ```67:70:omniguard/frontend/src/pages/LoginPage.tsx
            <div className="w-10 h-10 rounded-xl bg-white/70 backdrop-blur-sm flex items-center justify-center border border-white/80 shadow-sm">
              <ShieldCheck className="w-6 h-6 text-[#1a5276]" />
            </div>
            <span className="text-slate-800 font-bold text-xl">OmniGuard</span>
  ```

  **5. `backend/.env.example` 的行尾换行**。两个文件都是 5 行，内容逐行相同，唯一差别是末尾换行：

  ```1:5:PolySafe/backend/.env.example
ARK_API_KEY=your_api_key_here
ARK_MODEL_ID=your_model_id_here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

DISABLE_FAISS=1
  ```

  ```1:5:omniguard/backend/.env.example
ARK_API_KEY=your_api_key_here
ARK_MODEL_ID=your_model_id_here
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

DISABLE_FAISS=1
  ```

  `diff` 对该文件的报告是同一行前后各出现一次，即 `PolySafe` 侧文件末尾无换行符、`omniguard` 侧有。这一处连改名都算不上，只是文件末字节不同。

- **逐项差异性质**（2 处不是改名）：

  **6. `.gitignore` 被整体重写。** 行数从 66 行变为 129 行，`diff` 报告 145 行发生变化（新增与删除合计）。`PolySafe` 侧是分节的简短忽略表，`omniguard` 侧换成了带分隔线注释的完整版本：

  ```1:4:PolySafe/.gitignore
# Python / backend
backend/__pycache__/
backend/**/*.py[cod]
backend/.venv/
  ```

  ```1:4:omniguard/.gitignore
# =============================================================================
# PolySafe — .gitignore
# Stack: FastAPI + SQLAlchemy + SQLite + FAISS  |  React + TS + Vite + Tailwind
# =============================================================================
  ```

  注意 `omniguard/.gitignore:2` 的注释里写的仍然是 `PolySafe`。这一处是内容重写，且重写后的文件里保留了旧项目名。

  **7. `assets/首页.png` 是重新导出的图片。** 两文件同名、同格式，但尺寸与色彩模式都不同：`PolySafe/assets/首页.png` 为 2304 x 1290、8-bit/color RGBA，`omniguard/assets/首页.png` 为 1695 x 1248、8-bit/color RGB。MD5 分别为 `25126e2fdd56c63bb6e65fc7261c6571` 与 `7b153a59e7b67991c30de9f5f8cbdf9c`。其余 4 张截图（`图片检测.png`、`数据看板.png`、`策略配置.png`、`视频检测.png`）两边的字节数与 MD5 完全一致。因此这不是单纯的改名，是首页截图被替换成了另一次截取或另一次导出的版本。

- **旧名残留检查**。在 `omniguard/` 全目录检索 `PolySafe`，命中 2 处：

  ```
  omniguard/README.md:48:cd PolySafe
  omniguard/.gitignore:2:# PolySafe — .gitignore
  ```

  第一处的上下文是安装步骤：

  ````46:49:omniguard/README.md
```bash
git clone <your-repo-url>
cd PolySafe
```
````

  反方向检索 `PolySafe/` 目录里的 `OmniGuard`，命中 0 处。也就是说改名是单向的，`omniguard/` 里有两处忘了改，`PolySafe/` 里没有任何 `omniguard` 的痕迹。

- **版本历史**。`omniguard/` 目录下存在 `.git`，但只有一个提交：

  ```
  2b59f76 chore: trigger contributors graph refresh (retry)
  ```

  `PolySafe/` 目录下没有 `.git`。因此无法从提交历史判断哪一侧是原始项目、哪一侧是复制品，只能从内容推断：`omniguard/.gitignore:2` 的注释里写着 `PolySafe`，说明该 `.gitignore` 是在 `PolySafe` 项目的语境里写下后被放进 `omniguard/` 的。

- **结论**：`PolySafe/` 与 `omniguard/` 是同一个项目。判定依据有三条：文件总数相同（各 68 个）、目录结构相同、除 7 个文件外的全部文件逐字节相同。**需要修正初步结论中「全是改名」这一措辞**：7 个差异文件里，`README.md`、`frontend/index.html`、`HomePage.tsx`、`LoginPage.tsx` 属品牌名替换，`backend/.env.example` 属末行换行差异，这三类共 5 处符合「改名」的描述；但 `.gitignore` 是行数翻倍的整体重写（66 行到 129 行），`assets/首页.png` 是尺寸与色彩模式都变了的另一份图片，这 2 处不是改名。另外 `omniguard/` 内部仍有 2 处旧名残留，说明改名不彻底。

- **为什么这样做 / 不这样做会出什么事**：把两个仓库当成两个独立项目分别提炼，会重复劳动并得出两套互相矛盾的结论。判定为同一项目的直接后果是：本分片的 S5-12 只从 `PolySafe/` 取证，`omniguard/` 只用于交叉核对；而 S5-13 这一项本身的价值在于确认「同一个代码库被改名后重新发布」这件事，提醒读者不要按 star 数或仓库数来估计这套设计的采用广度。

- **代价与局限**：本次核查只做了文件级与行级比对，没有做语义级比对（例如两个目录下是否存在同名但逻辑不同的函数）。`--exclude=.git` 排除了版本目录，而 `omniguard/.git` 只有一个提交、`PolySafe/` 没有 `.git`，所以无法通过 commit 时间判断先后。`assets/首页.png` 的差异只能描述为「不同尺寸的截图」，无法确认内容上是否还改了界面文案，因为图片内容不在逐字节比对的覆盖范围内。

- **Momcozy 迁移形态**：这条核查本身不产生可直接迁移的机制，它产生的是资产清单的修正。Momcozy 侧真正可复用的是 `PolySafe/` 的批次模型（S5-12），`omniguard/` 不提供额外信息。核查方法可以固化为第三方素材入库时的一道检查：对候选的「不同来源」素材做 `diff -rq --exclude=.git`，若差异只集中在品牌名文件上，则合并为同一来源，避免同一套实现被计成两份能力。

- **证据强度**：已实读核实。`diff -rq` 输出、文件计数、`grep` 残留命中、图片尺寸与 MD5 均为实际命令输出；`omniguard/.gitignore` 是在 `PolySafe` 语境下写成这一判断为【推断】，依据是 `omniguard/.gitignore:2` 的注释文本。
