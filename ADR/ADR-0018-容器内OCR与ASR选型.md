# ADR-0018：容器内 OCR 与 ASR 选型

- 状态：`accepted`（2026-10-26 委托方批准 T-412 选型：容器内跨平台 OCR/ASR，宿主 macOS Vision 移出生产路径）
- 日期：2026-10-26
- 关联：Playbook **TS-16 / TS-17 / TS-18 / TS-19 / TS-21**（`内容审查Agent-产品Playbook-v1.1.md:63`、`:1291`–`:1311`）
- 前置：`PMO/audit/裁定-R118-媒体宿主原生-20261023.md`（行 118 空真）· `PMO/implement/T-412-OCR-ASR选型申请-v1-20261026.md`（候选与代价维度）
- 落地：`base/media.py` 的 `MEDIA_PROVIDERS` / `ContainerOcrProvider` / `ContainerAsrProvider`
- 执法点：`tools/verify_media_selection.py`（S1–S8 + 19 项反向对照）

---

## 〇 · 一页纸

| # | 问题 | 答案 |
|---|---|---|
| 1 | OCR 选谁 | **`rapidocr` 3.10.0**（Apache-2.0），PP-OCRv6 权重**随 wheel 分发**，onnxruntime CPU |
| 2 | ASR 选谁 | **`faster-whisper` 1.2.1**（MIT），CTranslate2 CPU int8，权重**镜像构建期**落盘 |
| 3 | 它落在哪 | `base/media.py` 的一层 provider 注册 + 两个适配器；**不是**散在各处 |
| 4 | 接进生产了吗 | **没有。** 默认引擎仍是 `host_vision`，`SUPPORTED_SOURCE_KINDS` 未改 |
| 5 | 行 118 现在是什么 | **仍是 `vacuous_true`**（空真），**不是** passed —— 见 §六 |
| 6 | 阻塞今天上线吗 | **不阻塞** —— 见 §七 |
| 7 | 本次没做什么 | 不进模型权重、不改判定主链、不开媒体进件、不装依赖 |

> ★ **第 4 行与第 5 行是本文档最容易被读错的两行。**
> 选型获批 = 「决定用哪个」，不等于「已经接上」，更不等于「行 118 做到了」。
> 这三件事在本文里分别落在 §二 / §三 / §六，**互不推导**。

---

## 一 · 要解决的问题

TS-16 要求「图片 / 视频的 OCR / ASR **全部使用容器内跨平台模型**，不使用宿主操作系统
原生能力」，并且明文规定 **既有 macOS + Vision 的实测读数不得沿用**。

今天的实现是**反过来的**：

| 事实 | 读数 | 复现 |
|---|---|---|
| OCR 是宿主 ObjC + Vision | `base/ocr_vision.m` 114 行 / `base/build_ocr.sh` 36 行 | `wc -l base/ocr_vision.m base/build_ocr.sh` |
| 编出来的二进制是 Mach-O arm64 | 53,584 字节 | `file .tools/bin/ocr` → `Mach-O 64-bit executable arm64` |
| **它在 Linux 容器里根本起不来** | `execv errno=8 Exec format error` | 见 §二.3 |
| 容器基础镜像里一个媒体引擎都没有 | tesseract / ffmpeg / whisper / sox 全部 absent | 见 §二.3 |
| ASR 完全不存在 | 全仓 0 个引擎、0 个依赖、0 份音频 | 申请文档 §1.4 |

所以选型要回答的不是「哪个模型更准」，而是：**换平台之后，能跑起来的是哪两个包，
它们的许可与体积各是什么。** 准确性读数**今天给不出来**（没有素材、没有标注、
没有容器内的真跑），本文**不编**，见 §六。

---

## 二 · 选定

### 2.1 两条登记

下表是**机器可读的正本**：`base/media.py` 的 `MEDIA_PROVIDERS` 与它逐字段相等，
由 `tools/verify_media_selection.py` 的 **S2 / S3 / S4** 双向断言
（缺一行红、多一行红、任一字段漂了红、adapter 类不存在红）。

| provider_id | package | version | license | bundled_models | adapter |
|---|---|---|---|---|---|
| `rapidocr_ppocr_v6` | `rapidocr` | `3.10.0` | `Apache-2.0` | `True` | `ContainerOcrProvider` |
| `faster_whisper` | `faster-whisper` | `1.2.1` | `MIT` | `False` | `ContainerAsrProvider` |

> ⚠️ **`bundled_models` 那一列是本次选型最关键的一列**，两行不同：
> OCR 的权重**在 wheel 里**，装上就有；ASR 的权重**不在 wheel 里**（1.1 MB 的 wheel
> 只带一个 VAD 小模型），必须镜像构建期落盘。这个差别决定了「离线」对两者是
> **两种不同的承诺**，混成一句「都支持离线」就是 §2.4.2 那个「没有执行点的承诺」。

### 2.2 为什么是它们

**OCR：`rapidocr` 3.10.0。**

| 判据 | 读数 | 为什么它决定选型 |
|---|---|---|
| 跨平台 | manylinux x86_64 **与** macOS arm64 都有 wheel | TS-16 的硬要求。两者都在 → 同一份代码在容器与本机都能跑 |
| **权重随包** | wheel 26.0 MB，`models/` 下 3 个 `.onnx`（PP-OCRv6 det/rec + PP-OCRv4 cls） | **容器内离线**最省事的形态：`pip install` 完就有模型，运行期零外呼 |
| 许可 | `Apache-2.0`（`License-Expression` 字段）；模型另有 `MODEL_LICENSES.md` | 商用可；**模型权重与代码分开声明**（上游是百度的 PP-OCR）—— 这一条必须写进法务可见处 |
| 中文 | PP-OCR 系列原生中文，`lang_type: ch` | 本项目审的是中文广告 |
| 依赖闭包 | **16 包 / 107.6 MiB**（`uv pip install --dry-run` 解析，再逐个取 wheel 字节） | 相比 PaddleOCR 的 63 包 / 146.8 MiB **+** 另装 `paddlepaddle` |
| **headless** | 依赖 `opencv-python-headless`，**不是** `opencv-python` | 见下条 —— 这条是实测踩出来的 |

★ **`headless` 这一条不是偏好，是本机实测的硬约束**：

```bash
$ docker run --rm python:3.12-slim sh -c 'ldconfig -p | grep -c "libGL\.so"'
0
```

容器基础镜像（`python:3.12-slim`，与 `Dockerfile:36` 的 runtime 同基底）
**没有 `libGL.so`**。非 headless 的 `opencv-python` 在 import 时会因缺 `libGL` 直接失败，
而那个报错长这样：`ImportError: libGL.so.1: cannot open shared object file` ——
它指向「装个系统包」，而真相是「你装错了 opencv 的变体」。
`rapidocr` 3.10.0 的元数据里写的是 `opencv-python-headless>=4.5.1.48`，
**这个坑由包自己避掉了**。这也是不选 `rapidocr-onnxruntime` 1.4.4 的原因之一：
它的依赖是 `opencv-python`（非 headless），会把这个坑重新引进来。

> ★ **为什么是 3.10.0 而不是 1.4.4。** 两个包的 API **不一样**，而这不是风格差异：
> `rapidocr-onnxruntime` 1.4.4 的 `RapidOCR()(img)` 返回 `(result, elapse)` 二元组；
> `rapidocr` 3.10.0 返回 `RapidOCROutput`（`.boxes` / `.txts` / `.scores`）。
> 按旧包写适配器、装上新包 → `TypeError`，而这只会在装了之后才发现。
> 适配器因此**按 3.10.0 的 API 写**，见 `ContainerOcrProvider.analyze` 的注释。
> 1.4.4 与 3.10.0 的 wheel 名也分别叫 `rapidocr_onnxruntime` / `rapidocr` ——
> 两个都还活着，装错一个就得到另一套 API。

**ASR：`faster-whisper` 1.2.1。**

| 判据 | 读数 | 说明 |
|---|---|---|
| 跨平台 | manylinux x86_64 / macOS arm64 / win_amd64 都有（`ctranslate2` 4.8.4 的 wheel 列表） | TS-16 |
| 许可 | `MIT`（`License :: OSI Approved :: MIT License`） | 权重另算：`Systran/faster-whisper-*` 也是 `MIT` |
| CPU | CTranslate2 支持 `compute_type="int8"` | TS-17 要求 CPU 优先、**不预设 GPU** |
| 依赖闭包 | **22 包 / 124.0 MiB**（含 `ctranslate2` 40.7 MB、`av` 33.4 MB、`onnxruntime` 22.7 MB） | 比 `openai-whisper` 省掉 `torch` 528.9 MiB |
| 时间码 | 每段自带 `start` / `end`（`transcribe()` 的 segment） | TS-24 的 `segment` 判据要它 |
| VAD 随包 | wheel 里带 `silero_vad_v6.onnx` | 长音频切分不必再引一个包 |
| 权重 | **不随包**：`Systran/faster-whisper-small` 的 `model.bin` = **484 MB**（tiny 76 MB / base 145 MB） | 体积在这里是**部署决定**，不是包选型的副作用 |

★ **为什么 ASR 的「离线」写法和 OCR 不一样**：`faster-whisper` 的 wheel 只有 1.1 MB，
权重是一个独立下载物。所以本文不对它说「装上就能离线」，而说
「**镜像构建期落盘，运行期零外呼**」—— 并且这一条有执行点：
`ContainerAsrProvider._load()` 在没给 `weights_dir` 时**抛异常**，不自己联网。
`base/media.py` 的 `[9]` 自证里有一条专门守它。

### 2.3 「宿主那条路在容器里真的不通」—— 这是实测，不是推论

申请文档写的是「docker daemon 不可达（`rc=1`）」。**本次实测 daemon 可达了**，
于是这件事第一次有了直接的读数：

```bash
$ docker info >/dev/null 2>&1; echo "rc=$?"
rc=0
$ docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
linux/arm64

# 把宿主二进制喂进容器（绑定挂载会丢可执行位，所以走 stdin）
$ docker run --rm -i python:3.12-slim python3 -c '
import os,sys
d=sys.stdin.buffer.read(); open("/tmp/ocr","wb").write(d); os.chmod("/tmp/ocr",0o755)
print("magic=%s" % d[:4].hex())
try: os.execv("/tmp/ocr",["/tmp/ocr"])
except OSError as e: print("execv errno=%d %s" % (e.errno, os.strerror(e.errno)))
' < .tools/bin/ocr
magic=cffaedfe
execv errno=8 Exec format error
```

`cffaedfe` 是 Mach-O 64 的魔数，容器只认 ELF。**这不是「没配好」，是格式不对。**

同一轮还量了容器里到底有什么：

```bash
$ docker run --rm python:3.12-slim sh -c \
  'for b in tesseract paddleocr ffmpeg whisper sox; do command -v $b >/dev/null || echo "absent:$b"; done; \
   ldconfig -p | grep -c "libGL\.so"'
absent:tesseract
absent:paddleocr
absent:ffmpeg
absent:whisper
absent:sox
0
```

> ⚠️ **这份读数使申请文档里的一条结论过期了**，必须更正而不是悄悄绕过：
> §2.4 当时写「读数今天跑不出来，因为 daemon 没起」。**daemon 现在起得来。**
> 但「能不能起容器」与「能不能出四项读数」仍是两件事：四项读数要
> 「装两套候选 + 真实中英文广告图 + 人工标注真值」，那是**素材与授权**问题，
> 不是 daemon 问题。所以「待测」这个状态没变，**卡点从 daemon 挪到了素材**。

---

## 三 · 它落在哪个抽象后面

### 3.1 一层注册 + 两个适配器，都在 `base/media.py`

```
base/media.py
├─ MediaProvider            ← 一条登记的**形状**（provider_id/task/package/version/license/
│                              bundled_models/weights_note/adapter）
├─ MEDIA_PROVIDERS          ← 登记表（今天 2 条）
├─ register_media_provider  ← 唯一写入口；重名报错，不静默覆盖
├─ media_provider_ids()     ← 机器可读的「选了什么」
├─ ContainerOcrProvider     ← 适配层：产出与 ocr_file() **同一份 schema**
└─ ContainerAsrProvider     ← 适配层：输出带 start/end，speaker 恒 unknown
```

**为什么必须是一个抽象层，而不是在调用点各写一段 `import`：**

1. **选型要能被断言。** 如果 `rapidocr` 的导入散在三处，`verify_media_selection.py`
   就没有「注册点」可对账 —— 它只能去 grep，而 grep 到的是**名字出现过**，
   不是**真的有一条注册**（AGENTS.md §2.4）。现在 `S4` 用 `ast` 查 `ClassDef`，
   `S2` 查注册表键集合，两者都是结构读数。
2. **换引擎时只改一行。** provider 换掉 = 换 `MEDIA_PROVIDERS` 的一个条目，
   调用方不动。这条对 TS-18/19 的「过门后才锁版本」是必要的 ——
   候选还要被测评，测评完可能要换。
3. **坐标系在一个地方对齐。** 见下。

### 3.2 一个具体的技术债：坐标系

宿主的 `base/ocr_vision.m` 给的 `x/y/w/h` 是 **Vision 的 `boundingBox`**：
**归一化 + 左下角原点**（y 向上）。
`rapidocr` 给的是**像素 + 左上角原点**。

适配器要翻一次 y：`y = 1 - (y0 + bh) / h`。

**这条是本次的已知未测。** 翻错不会抛异常，只会让所有框上下颠倒 ——
而 bbox 是 C4 判据（`bbox` 非空）与 TS-24（`ocr_output_hash`）的输入。
**要变成「测过」，需要**：在容器内对同一张图同时跑宿主与容器引擎，
逐框比对 y 的重心（§六.2 第 3 条）。

### 3.3 默认引擎**没有**改

```python
DEFAULT_OCR_ENGINE = "host_vision"    # ← 注册 ≠ 接线
DEFAULT_ASR_ENGINE = None
```

这条由 `verify_media_selection.py` 的 **S6** 守着，两个方向都断言：

* `DEFAULT_OCR_ENGINE` 变成容器引擎 → **红**（那是偷偷接线）；
* `SUPPORTED_SOURCE_KINDS` 出现 `image`/`video` → **红**（那是打开媒体进件）。

**为什么要在注册的同一票里把「不接线」写成断言**：注册一个 provider 之后，
最自然的下一步就是「顺手把它设成默认」。而设成默认 = 生产开始走容器 OCR =
媒体进件事实上被打开 —— 那是 `T-118-follow` 的范围，且必须与行 118 一起处理。
**「顺手」是本次最该被拦住的动作。**

---

## 四 · 不选的候选

### 4.1 OCR

| 候选 | 为什么不选（一句可核的） |
|---|---|
| `paddleocr` 3.7.0 | 依赖闭包 **63 包 / 146.8 MiB**，还要另装 `paddlepaddle` **185.8 MiB**（cp312 manylinux wheel）；而它带来的精度收益今天**没有读数可比** —— TS-18 要的四项读数一条都还没有 |
| `rapidocr-onnxruntime` 1.4.4 | 同一家的上一代包：权重也随包（15.4 MB 更小），但 API 是**二元组**且依赖 `opencv-python`（**非 headless** → 重新引入 `libGL` 坑）；两个包并存时更容易装错 |
| `tesseract`（系统包） | 要走 `apt-get install tesseract-ocr` + 语言包，把「依赖声明」从 `pyproject.toml` 挪到 Dockerfile 的 `RUN` 里；语言包与版本由 apt 源决定，**换基础镜像就换引擎**，锁不住版本 |
| **首轮就上 PaddleOCR** | 与上条同因（TS-18 的「过门后才锁版本」）—— 今天**没有**四项读数，所以不能锁 |
| 云 OCR（走 magpie 网关） | **这是外发**。须先过 `base/multimodal_provider.py` 的授权门 + ADR-0003 敏感样本分级；而默认注册表今天是空的（`provider_ids()` → `()`），外发通道一次都没走过 |

### 4.2 ASR

| 候选 | 为什么不选（一句可核的） |
|---|---|
| `openai-whisper`（官方） | 依赖 `torch`：cp312 manylinux x86_64 wheel **528.9 MiB**，是 `faster-whisper` 整条闭包（124.0 MiB）的 4.3 倍；CPU 上也没有 CTranslate2 的 int8 路径 |
| `sherpa-onnx` 2.0.0 | wheel 更小（4.0 MB），但**不带 ASR 权重**（只带运行时 + 各引擎绑定），精度/时间码要自备模型并自测 —— 那等于把 TS-19 的五项读数变成「先选权重再测」，顺序反了 |
| `vosk` 0.3.45 | 许可声明只在 classifier 里（`license` 字段为空），且模型生态以中英之外的语言居多；中文中小模型的时间码粒度不满足 TS-24 |
| 云 ASR（tokenhub 的 8 条） | **外发音频**，敏感度高于静图（申请文档 §四）；同云 OCR，授权门一次未走 |

★ 上表两两成对的原因：`verify_media_selection.py` 的 **S5** 要求这里 **≥2 个**
被否候选且**逐条有理由** —— 「只写赢了谁」的选型无法复核，也无法在半年后回答
「当时为什么不选 X」。

---

## 五 · 不做什么（本票的范围边界）

1. **不改 `SUPPORTED_SOURCE_KINDS`。** 仍是 `frozenset({"free_text", "ad_text"})`
   （`base/submission_service.py:33`）。打开媒体进件是 `T-118-follow`。
2. **不动生产判定主链。** `api/` 的 import 闭包今天不含 `base/media.py`，本票不改这个事实。
3. **不引模型权重进仓。** 仓里今天 `git ls-files` 的 `.onnx/.pt/.bin/.safetensors` = **0 个**，
   本票保持 0。OCR 的权重随 `pip install` 来，ASR 的权重构建期落盘，**都不入 git**。
4. **不装依赖、不拉镜像、不跑模型。** 选型的落地是**注册与契约**，不是把模型跑起来。
5. **不把行 118 改成 passed。** 见 §六。
6. **不给准确性读数。** 没有素材、没有标注真值 —— 编一个百分比比没有数字坏得多
   （`base/media.py:857` 已经记过同一句话）。

---

## 六 · 行 118 现在是 `vacuous_true`，**不是** `passed`

### 6.1 三句话必须一起读

| # | 事实 | 读数 |
|---|---|---|
| 1 | 仓里**仍有** 3 处宿主原生调用 | `verify_media_portability.py` → 命中 3 处 |
| 2 | 生产进件**不接**媒体，所以那 3 处不在生产路径上 | `SUPPORTED_SOURCE_KINDS = {free_text, ad_text}` |
| 3 | 所以行 118 是**空真**，既不是「做到了」也不是「违反了」 | `state = vacuous_true` |

**本次改动没有改变这三句中的任何一句。** 尤其第 1 句：宿主实现在盘上、
仍是 `ocr_file()` 的真实入口，这一次一行都没删。

### 6.2 要变成真正的 `passed`，需要什么

判据来自验收表第 118 行的两半句（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:261`）：
**静态断言不出现宿主原生调用** + **在 Linux 容器内跑一次真实图片与视频并断言能产出结果**。

按顺序共四件，缺一件都还是空真：

| # | 需要什么 | 为什么它是前提 | 今天的状态 |
|---|---|---|---|
| 1 | **素材**：真实中英文广告图（含低清、旋转）、视频、音频 | 「跑一次真实图片与视频」没有文件就是无对象 | 图片：仓内 11 张 tracked / 盘上 142 张；**视频 0、音频 0**（`git ls-files` 实测） |
| 2 | **容器内装引擎** | 见 §二.3：基础镜像里 5 个引擎全 absent | 未装（本票刻意不装） |
| 3 | **一次真跑 + 坐标系对拍** | 跑通不等于跑对：`y` 翻转错会让框上下颠倒而不报错（§3.2） | 未跑 |
| 4 | **改默认引擎 + 打开媒体进件**（`SUPPORTED_SOURCE_KINDS` 加 `image`） | 只有进件真接上，那 3 处宿主调用才**挡在生产路径上**，删掉它们才有意义 | 本票刻意不做 |

★ **第 4 件事与第 1–3 件是同一张票的两个方向，不能只做一个。**
只做 1–3（容器能跑）而不改进件 → 生产仍在用宿主 Vision → 行 118 还是空真。
只改第 4 件（打开进件）而不做 1–3 → 宿主 Vision 立刻变成**真违规**，且没有任何东西可用。

> **这就是为什么本票的正确交付物是「注册 + 契约 + 一句如实的状态」，
> 而不是「把 118 弄绿」。** 把 `vacuous_true` 改成 `passed` 只有两条路：
> 真跑通（做不到，缺 1–3），或者**改判据**（那是造假）。
> `verify_media_selection.py` 的 **S8** 就是挡第二条路的那条断言：
> ADR 里一旦把行 118 写成 `passed`/`已满足`，它变红。

### 6.3 一个必须报告的事实：本次**没有**减少宿主原生命中数

```
宿主原生命中：3 处（base/build_ocr.sh:12 · base/ocr_vision.m:23 · base/ocr_vision.m:27）
```

这是**刻意**的，而且 `verify_media_selection.py` 的 **S7** 把「不许减少」变成断言
（`len(hits) < 3` → 红）。

**为什么这条断言必须存在**：让行 118「看起来变好」最省事的办法就是删掉
`base/ocr_vision.m` 与 `base/build_ocr.sh`。那样宿主原生命中会掉到 0，
`verify_media_portability.py` 会打印 `clean`，行 118 看起来像通过了 ——
而实际上**生产什么都没变**（它本来就不在生产路径上），
**且本机唯一能跑的 OCR 被删掉了**（§二.3 证明它在本机能跑，两个真实样本都返回了结构化结果）。

**删掉一个不在生产路径上的能力，不是修复，是净损失。**

---

## 七 · 媒体进件今天不开，T-412 阻塞上线吗

**判断：不阻塞。** 三条依据，可逐条复核。

### 7.1 依据一：上线最小集里没有媒体

`PMO/implement/最终上线差距分析-v1-20261026.md` §五 的「上线准绪判断」是一张
**维度 × 状态**表：核心写链 / 生产判定 / 部署 / 前端 / 待裁定。
**媒体（P2、OCR/ASR）不在任何一格里** —— 它在 §2.1 的差距表里挂着（GA-03 / GA-04），
但**没有进上线最小集**。同一个文件的结论段只点名四件：
`T-323`（deploy owner）+ `T-320`（principals.json）+ `T-321`（OAuth 联调）
+ `T-401/T-402/T-403` 三批生产开放。

`PMO/implement/T400段-ready收尾报告-20261026.md` §四 把剩下的 4 票 blocked 列成表，
其中 T-412 的「拿不到会怎样」写的是：**「媒体进件尚未打开」** ——
即**影响面是「P2 停在设计态」，不是「上线不能发生」**。

### 7.2 依据二：媒体进件今天在代码里真的是关的

```bash
$ grep -n "SUPPORTED_SOURCE_KINDS" base/submission_service.py
33:SUPPORTED_SOURCE_KINDS = frozenset({"free_text", "ad_text"})
```

`source.kind=image` 走 `unsupported_source_kind` 被拒；`api/` 的 import 闭包
不含 `base/media.py`。所以**即使 T-412 一行代码都没写，上线也不会因为媒体而受阻** ——
因为那条能力今天不在生产路径上（这正是「空真」的含义）。

### 7.3 依据三：本票没有引入**任何**上线面风险

| 风险类别 | 本票做了什么 | 结论 |
|---|---|---|
| 生产行为 | 只加了 `MEDIA_PROVIDERS` 等**声明性**符号；`ocr_file()` / `ocr_file` 的调用路径一行未改 | 无变化 |
| 依赖 | 没装任何包、没改 `pyproject.toml` / `Dockerfile` / `uv.lock` | 无变化 |
| 仓体积 | 没进任何权重（`.onnx/.pt/.bin` tracked = 0） | 无变化 |
| 判定主链 | `api/` / `skeleton` / `base/rule_judge` 未触碰 | 无变化 |
| 默认引擎 | 仍是 `host_vision`（S6 断言） | 无变化 |

`base/media.py --selftest` 从 25 项变成 **44 项**（新增 19 项，含 5 条必红），
全绿；其余 20 项原有读数未变。

### 7.4 什么时候它会变成阻塞

T-412 本身永远不阻塞上线。**但「打开媒体进件」会立刻阻塞上线**，因为那一刻：

1. `SUPPORTED_SOURCE_KINDS` 加了 `image` → 行 118 从空真翻成**真违规**
   （`verify_media_portability.py` 的 G2 会退 1）；
2. 生产会调用 `ocr_file()` → 它走 `ensure_ocr()` → 在没有 macOS + CLT SDK 的
   容器里**直接抛异常**（`base/media.py:116` 的 `ensure_ocr` 只认本机 SDK 路径）。

所以正确的顺序是：**T-118-follow 先让 §六.2 的 1–4 全部成立，再把 `image` 加进集合。**
反过来做，第 1 天就会在容器里得到 `RuntimeError: OCR 源码或重建脚本缺失` 或
`ocr_build_failed`。

---

## 八 · 决策的可执行面

### 8.1 这次选型由什么守着

| 断言 | 拦什么 | 反向对照 |
|---|---|---|
| **S1** | ADR 状态/日期没落 | 状态改 `proposed` → 红；日期漂 → 红 |
| **S2** | 文档与代码的 provider 集合不等（双向） | 删一条注册 → 红；代码多注册 → 红 |
| **S3** | 逐字段漂移（package/version/license/bundled/adapter） | 版本 3.10.0→3.9.0 → 红；license 漂 → 红 |
| **S4** | adapter 类名在文档里有、代码里没有 | 去掉一个类 → 红 |
| **S5** | 被否候选 <2 或没理由 | 删两行 → 红 |
| **S6** | 注册偷偷变成接线 / 媒体进件被打开 | `DEFAULT_OCR_ENGINE` 改容器 → 红；加 `image` → 红 |
| **S7** | 靠删 `.m` 文件让宿主命中数变少 | 命中数 → 0 → 红；变多（4 处）**不误报** |
| **S8** | 把空真写成 passed | 写 `passed` → 红；通篇不提 `vacuous_true` → 红 |

### 8.2 复现命令

```bash
# 契约（本票的主判据）
python3 tools/verify_media_selection.py             # 期望 rc=0 · 14 项过
python3 tools/verify_media_selection.py --controls   # 期望 19/19

# 行 118 另一半（不该因本票而变）
python3 tools/verify_media_portability.py            # 期望 rc=0 · 3 命中 · vacuous_true
python3 tools/verify_media_portability.py --controls  # 期望 9/9

# 注册项的自证（19 项，含 5 条必红）
python3 base/media.py --selftest                     # 期望 44 项全绿

# 登记的覆盖关系
python3 tools/verify_coverage.py --controls

# 选型里每个体积数字的来源（不联网也可核：数值与包名版本都写在 §二.2）
uv pip install --dry-run --python-platform x86_64-manylinux_2_28 --python-version 3.12 \
  --target /tmp/x rapidocr==3.10.0          # → 16 packages
uv pip install --dry-run --python-platform x86_64-manylinux_2_28 --python-version 3.12 \
  --target /tmp/y faster-whisper==1.2.1     # → 23 packages
uv pip install --dry-run --python-platform x86_64-manylinux_2_28 --python-version 3.12 \
  --target /tmp/z paddleocr==3.7.0          # → 64 packages
```

> ★ `uv` 输出的**包数**是 `Would download` + 已在镜像里的那几个之差，
> 本文用的是 `grep -c "^ + "` 的数（16 / 23 / 64），与「依赖闭包 16 / 22 / 63」
> 相差 1 —— 差额是**根包自身**。两个数都写在这里，别当成矛盾。

### 8.3 本次读数的时点

全部为 **2026-10-26** 本机现场跑出，基于 `HEAD=4a7d764`。
PyPI 的版本号会变（`rapidocr` 今天最新是 3.10.0，`faster-whisper` 是 1.2.1）——
本文锁的是**这两个具体版本**，不是「latest」。

---

## 九 · 已知未测（明着留着）

| # | 未测的是什么 | 为什么没测 | 要测需要什么 |
|---|---|---|---|
| 1 | **容器内真跑一次 OCR** | 本票不装依赖；且无标注真值 | 装 `rapidocr==3.10.0` + 一张真实广告图 → 断言 `ok=true` 且 `lines` 非空 |
| 2 | **准确率 / bbox 正确性**（TS-18 四项的 2 项） | 同上；无人工标注 | 低清 + 旋转子集各 ≥10 张，人工标框 |
| 3 | **坐标系翻转对不对**（§3.2） | 没有容器内引擎可比 | 同一张图两边跑，逐框比 y 重心 |
| 4 | **CPU 时延**（TS-18 第 4 项） | 同上 | 容器内 p50/p95，标注 CPU 核数 |
| 5 | **ASR 任何读数**（TS-19 五项全部） | **全仓 0 个音频文件** | 四类语料（中英/噪声/多人/长视频）+ 人工转写 |
| 6 | PaddleOCR 的精度是否真优于所选 | 没跑 PaddleOCR | 起容器装 `paddleocr`，同一批图对比 |

**这六项一条都不是「应该没问题」。** 它们是「今天没有读数」——
按 AGENTS.md §2.4.2 的口径，没有读数不是绿，是**未测**。

---

## 十 · 与既有文档的关系

| 文档 | 本 ADR 对它做了什么 |
|---|---|
| `PMO/implement/T-412-OCR-ASR选型申请-v1-20261026.md` | 它**申请**，本 ADR **裁定**。其中 §2.4「daemon 不可达」一条**已过期**（§二.3 实测 rc=0），其余候选与代价维度沿用 |
| `PMO/audit/裁定-R118-媒体宿主原生-20261023.md` | 未推翻。「空真」这个状态**不变**，本 ADR 只是让「换哪个引擎」有了答案 |
| `ADR/ADR-0013`（基座入库分级） | 未推翻。本 ADR 的 §五 第 3 条（不引权重进仓）是它的直接推论 |
| `tools/verify_media_model_lock.py`（行 120/121 机器半边） | **不冲突，且互补**。它管「锁版本前四项读数齐不齐」，本 ADR 的 S3 管「文档与注册点一致」。今天两边都不锁版本 —— 因为四项读数一条都没有 |
| Playbook TS-18 / TS-19 | **未违反**。那两条要求「过门后才锁版本」，而本文锁的是**包与版本号**（工程依赖），不是**评测结论**。准确的表述是：**引擎定了、读数未出**。这是本 ADR 与 TS-18/19 的接缝，明着写出来 |

> ★ **最后那一行是本文最需要被人挑战的地方。**
> TS-18/19 的原意是「不许在四项读数出来之前把候选写成『我们用的 OCR』」。
> 本 ADR 确实把 `rapidocr` 写成了选定项。**我认为这不违反它，理由是**：
> 那两条管的是**评测门**（accuracy / bbox / latency 决定用哪个模型），
> 而本票解的是**工程门**（哪个包能在容器里跨平台跑、许可能不能过、体积多少）。
> 两者的输入不同：工程门不需要真跑就能定（wheel 元数据、许可证、依赖闭包都是可查的），
> 评测门必须真跑。
>
> **但这个判断有代价**：一旦评测出来 `rapidocr` 的准确率不可接受，换引擎要改
> `MEDIA_PROVIDERS` 一行 + 本 ADR（不是改调用点）。这就是把它做成一个 provider 层的原因。
> 若委托方认为「工程选型也必须等评测」，那就该把本 ADR 的状态改成 `proposed`，
> 并把 `S1` 的期望从 `accepted` 改掉 —— **那是一条需要人裁的改动，不是工程判断。**

---

*2026-10-26 · HEAD=4a7d764 · 全部体积/版本读数来自 PyPI 元数据与 `uv pip install --dry-run`，
容器读数来自 `docker run --rm python:3.12-slim`，命令见 §二.3 与 §8.2*
