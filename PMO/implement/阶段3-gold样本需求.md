# 阶段 3 gold 样本需求（OCR / ASR）

> **状态：样本请求，不是交付承诺。**
> 当前**未安装任何 OCR/ASR 工具或模型**，也**没有跑过 benchmark**；本文只说明
> 「要测准确率，需要业务/委托方提供什么」。
>
> 依据：[`阶段3-准备评估.md`](./阶段3-准备评估.md) §3 的 OB/AB 分层；
> 消费方：[`tools/benchmark_media.py`](../../tools/benchmark_media.py)。
>
> **一句话**：没有 gold 就只能跑 smoke，不能算准确率。请按下面的目录、命名和文本要求提供样本。

---

## 0. 为什么必须要 gold

`benchmark_media.py` 只做一件事：把工具输出与 gold 文本对齐，算 **CER（OCR）** 或
**WER（ASR）**。没有 `<id>.gold.txt` 的样本会被逐条记为 `untested`，**不会**被算成
「0 错误」；如果一条 tested 都没有，harness 退 **2**（未测），不是 0（通过）。

当前盘上已有 212 张图，但**没有一张有逐字/bbox gold**；音频/视频 **0 个**。
所以现在能做的只有 harness 自证，不是准确率读数。

---

## 1. 目录与命名

建议按模态分目录交付：

```text
stage3-samples/
  ocr/
    ocr_clear_001.png
    ocr_clear_001.gold.txt
    ocr_lowlight_002.jpg
    ocr_lowlight_002.gold.txt
    ...
  asr/
    asr_clean_001.wav
    asr_clean_001.gold.txt
    asr_noise_002.mp3
    asr_noise_002.gold.txt
    ...
```

硬要求：

- `<id>` 只用 ASCII 字母、数字、下划线、短横线；**不要有空格、中文、斜杠**。
- 同一目录内 `<id>` 唯一；扩展名大小写不敏感。
- 每个样本必须有同名 `<id>.gold.txt`；gold 与媒体文件放在同一目录。
- OCR 媒体：`.png` / `.jpg` / `.jpeg` / `.webp`。
- ASR 媒体：`.wav` / `.mp3` / `.mp4` / `.mov`。
- gold 文本：**UTF-8**，不要 BOM；不要空文件。
- 不要把 gold 写成 JSON；harness 直接按纯文本读取。

---

## 2. OCR 样本：目标 50 张

分层沿用阶段 3 评估的分层（**这是目标量，不是 harness 强制门槛**）：

| 层 | 目标数 | 来源建议 | 要求 |
|---|---:|---|---|
| 清晰产品图/白底 | 15 | catalog 图 | 文字清楚、完整 |
| 低清/旋转/压缩 | 10 | catalog + landing 证据图 | 保留真实退化，不做超分/修复 |
| 多语言/小字/艺术字 | 10 | catalog + 风险图 | 记录语种；中英混合也收 |
| 复杂背景/图文混排 | 10 | landing 证据图 | 含 UI、价签、角标、叠字 |
| 构造对照（可选） | 5 | 渲染已知文本 | 只做解析/位置 sanity，**不计入主准确率** |

> 如果构造对照不提供，前四层 45 张仍可开工；但正式结论的目标样本量仍是 50 张。
> 关键区域完全无法人工辨认的图，请不要放进正式集 —— harness 目前没有「跳过某张」的字段，
> 放进去只会把不可读算成模型错误。

### OCR gold 要求

- 写**图中可见的全部文字**，按自然阅读顺序（从上到下、从左到右，多栏按栏）。
- **保留原始字符**：不要翻译、不要纠错、不要补全品牌名、不要把价格改写成统一格式。
- **标点计入 CER**；空白（空格/换行）不计，所以 gold 可以按行写，不必复刻排版。
- 图中无法辨认的局部不要猜；如果它影响关键判定，请换一张或先人工确认。
- 可选附加：`<id>.bbox.json`（人工框），本版 harness **不消费**，留给后续 LOC/bbox 评测。

---

## 3. ASR 样本：目标 30 段

| 层 | 目标数 | 来源建议 | 要求 |
|---|---:|---|---|
| 干净单人语音 | 10 | 业务提供/有授权录制 | 人工逐字稿 |
| 噪声/远场/口音 | 10 | 业务提供 | 记录噪声类型；不后期降噪 |
| 多人/重叠说话 | 5 | 业务提供 | 阶段一不做 diarization，只要求不崩 |
| 长视频（>5 分钟） | 5 | 业务提供 | 验证分段策略 |

### ASR gold 要求

- 写**逐字转写**：不要概括、不要润色、不要删口语填充词。
- 标点、大小写、空白**不计分**；harness 的 WER tokenizer 会忽略它们。
- 中文按 CJK 逐字成 token，英文/数字按连续段成 token；因此中文 WER 近似字符级，
  避免「整句一个 token」导致 WER 只有 0/1。
- 多人重叠处，以主说话人可辨认内容为准；辨认不了的部分不要编造。
- 可选附加：`<id>.timecode.json`（句级时间码），本版 harness **不消费**，留给 AB-4。

---

## 4. manifest（建议提供，便于分层审计）

建议附一份 `manifest.csv`（UTF-8），每行一个样本：

```csv
id,modality,layer,source,authorization,pii_redacted,notes
ocr_clear_001,ocr,clear,catalog,业务提供,yes,
asr_noise_002,asr,noise,业务提供,yes,yes,咖啡厅背景
```

- `layer` 用上面表格里的层名。
- `authorization` 写「业务提供」「已授权录制」等，不要留空。
- `pii_redacted` 写 `yes/no`；如果 `no`，说明为什么必须保留。
- manifest 是**辅助材料**，harness 当前不读取它；没有 manifest 也能跑。

---

## 5. 脱敏与存放（红线）

- **样本与 gold 不要直接进公开仓。** 仓库是公开的，图片/音频/逐字稿可能含客户素材、
  个人信息或未公开业务信息。
- 请通过双方约定的业务通道交付；落盘目录放在**仓外**，目录权限 `0700`。
- 能脱敏的先脱敏：人脸、姓名、手机号、地址、订单号、身份证号、内部链接。
  脱敏会改变 OCR 文本，请在 manifest 里注明；**不要**把「脱敏后的文本」和「未脱敏的图」
  配成一对。
- 如果样本来自飞书附件，按现行下载治理登记来源与落盘路径（`verify_download_governance.py`）；
  **下载来的东西不许进公开仓**。
- 业务方明确要求保留原样的敏感样本，只用于本地评测，不复制进任何提交。

---

## 6. harness 会怎么报

```bash
python3 tools/benchmark_media.py --modality ocr \
  --samples /path/to/stage3-samples/ocr --out /tmp/ocr-bench.json
python3 tools/benchmark_media.py --modality asr \
  --samples /path/to/stage3-samples/asr --out /tmp/asr-bench.json
```

输出 JSON：

```json
{
  "modality": "ocr",
  "tools": {"tesseract": {"ok": false, "path": null}, "ffmpeg": {"ok": false, "path": null}},
  "missing": ["tesseract"],
  "samples": [
    {"id": "ocr_clear_001", "file": "ocr_clear_001.png",
     "status": "untested", "reason": "tool_missing:tesseract",
     "cer": null, "ms": null}
  ],
  "summary": {"tested": 0, "untested": 1}
}
```

三态：

| 退出码 | 含义 |
|---:|---|
| `0` | 至少一条 `tested`（`summary.untested` 仍可能 >0，逐条看 reason） |
| `2` | **没有一条 tested**：工具缺失 / 无 gold / 模型不在本地 / 无样本 |
| `1` | harness 用法或写盘错误（不是「未测」） |

**工具缺失时整个模态记 untested 并退 2**；不会把缺工具写成 0 条样本，也不会写成通过。
ASR 侧不会下载模型：faster-whisper 用 `local_files_only=True`，openai-whisper 先检查
`~/.cache/whisper/<model>.pt`，不存在就记 untested。

---

## 7. 交付前自检清单

- [ ] 每个媒体文件都有同名 `.gold.txt`，且 gold 非空。
- [ ] `<id>` 唯一、无空格/中文/斜杠；扩展名在允许列表内。
- [ ] gold 是 UTF-8 纯文本，不是 JSON，没有 BOM。
- [ ] OCR gold 按阅读顺序写全可见文字；标点保留；没有翻译/纠错。
- [ ] ASR gold 是逐字稿；没有概括/润色；多人样本标注了重叠情况。
- [ ] 已脱敏；未脱敏样本只留在仓外授权目录。
- [ ] 附了 manifest（可选，但强烈建议）。

---

## 8. 收到样本之后

1. **不安装任何工具/模型**，先跑一次 harness，确认样本配对与三态读数；
2. 工具安装/镜像拉取需要单独批准；批准后先跑 OCR CPU 小样本，再跑 ASR；
3. benchmark 结论出来前，不承诺 20s/60s NFR，不把候选写成成功案例。

> 本文件没有自动执行点：它是一份**样本请求清单**。执行点在
> `tools/benchmark_media.py`（配对、gold、工具、三态、退出码）和它自己的 `--self-test`。
