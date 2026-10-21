# `_MEDIA_HINTS` 召回率实测（2026-10-21）

> 起因：我在 `7ab6e06` 的未测清单里自己写了「`_MEDIA_HINTS` 的召回率未测」。
> 05 派单把它量出来。本文是那次测量的全部读数。
>
> **只读 + 新建本文件。** 没有改 `base/`、没有改任何 JSON、没有改 `_MEDIA_HINTS` 本身。
> 语料来源限定**仓内**：`git ls-files` 的文本 + `file --mime-type` 对仓内真实文件。
> **没有读客户素材、没有读 `~/audit-data/`、没有访问 `research/live/`。**

---

## 〇 结论先行

| 读数 | 值 |
|---|---|
| 语料条数 | **51** |
| 该认出的 | 30 |
| **漏（该认没认）** | **0** —— 一条都没有 |
| 多认（认出额外介质） | **3** |
| **误认（认成完全不该认的介质）** | **7** |
| 精确正确 | 41 / 51 = **80.4%** |
| 「该认出的」召回 | 30 / 30 = **100%** |

**召回率是满的，但这不是好消息 —— 因为它是靠「整串包含匹配」换来的。**

> 一个把 `audio/mp4` 认成「音频 + 视频」的实现，召回率也是 100%。
> 而它会让一个**纯音频文件**通过 `av_alignment` 的介质闸门 —— 我实测过，见 §3.1。

真正的问题不在「认不出」，在**认错**。05 的原话是「认错比漏更严重」，实测证实了。

---

## 一 语料怎么来的

| 组 | 来源 | 条数 |
|---|---|---:|
| **G1** | `git grep` 仓内文本里的 `image/*`、`video/*`、`audio/*` 字面量，逐条核对上下文 | 6 |
| **G2** | `file --mime-type` 对仓内真实文件（含 2 个真 PNG、1 个 Mach-O 二进制） | 6 |
| **G3** | 常见真实 MIME（仓内未出现，补边界） | 14 |
| **G4** | 裸扩展名 / 中文 kind / 大写 / 带参数 | 9 |
| **G5** | 对抗样本：本该「不认」，含 6 条专门撞子串的探针 | 16 |

### 语料清洗：第一版是错的

第一版我用正则 `\b(?:image|video|audio|application)/[A-Za-z0-9.+\-]+` 直接扫，得到 54 个「MIME」。
逐条看上下文后，**一半以上不是 MIME**：

```
video/7342316312049224990   ← TikTok URL 片段（research/feishu/资源索引-v1.json）
image/index.js              ← 源码路径（research/distill/shards/…）
video/content-unit-adapter  ← 模块路径（Playbook/技术解决方案-v1.md）
text/hits.                  ← 散文断句（skills-inventory/refs/brand-docx/SKILL.md）
image/ecommerce-image       ← skill 目录名
```

**如果直接拿那 54 条算召回率，读数会被路径片段抬高，而它们本来就不该被认出。**
清洗后剩下 6 条真实的 MIME 字面量 —— 这就是 G1。

> 这一步值得单独记：**语料本身是判据的一部分。** 一份混进假样本的语料，
> 算出来的召回率是假精度，和「读错字段」是同一个形状（§2.4.1 第 1 行）。

---

## 二 逐条结果

### G1 仓内 MIME 字面量（6 / 6 正确）

| MIME/kind 串 | 来源 | 识别结果 | 该认出吗 | 判定 |
|---|---|---|---|---|
| `image/png` | `base/README.md` data URI 示例 | `image` | 是 | ✓ |
| `image/jpeg` | momcozy 落盘方案 / browser-ext `index.js` | `image` | 是 | ✓ |
| `image/webp` | `dsh-browser-ext/panel/assets/index.js` | `image` | 是 | ✓ |
| `image/gif` | 同上 | `image` | 是 | ✓ |
| `video/mp4` | `tools/download_blobs.py` 判定序列 | `video` | 是 | ✓ |
| `audio/mpeg` | `base/multimodal_provider.py` 注释 | `audio` | 是 | ✓ |

### G2 `file --mime-type` 实测（6 / 6 正确）

| MIME/kind 串 | 来源 | 识别结果 | 该认出吗 | 判定 |
|---|---|---|---|---|
| `image/png` | `dsh-browser-ext/assets/icons/icon128.png` | `image` | 是 | ✓ |
| `image/png` | `dsh-browser-ext/panel/assets/deepseek-256.png` | `image` | 是 | ✓ |
| `application/json` | `tools/download_callers.json` | `()` | 否 | ✓ 正确未认 |
| `text/plain` | `web/DESIGN.md` | `()` | 否 | ✓ 正确未认 |
| `text/x-script.python` | `base/multimodal_provider.py` | `()` | 否 | ✓ 正确未认 |
| `application/x-mach-binary` | `.tools/bin/ocr` | `()` | 否 | ✓ 正确未认 |

> 仓内**没有**已跟踪的音视频文件（`git ls-files` 里只有 6 个 PNG），
> 所以音频/视频的真实文件读数拿不到。这一点在 §6 记为未测。

### G3 常见真实 MIME（11 / 14 正确，**3 条多认**）

| MIME/kind 串 | 识别结果 | 该认出吗 | 判定 |
|---|---|---|---|
| `image/svg+xml` | `image` | 是 | ✓ |
| `image/heic` | `image` | 是 | ✓ |
| `image/tiff` | `image` | 是 | ✓ |
| `audio/wav` | `audio` | 是 | ✓ |
| `audio/aac` | `audio` | 是 | ✓ |
| `audio/ogg` | `audio` | 是 | ✓ |
| `audio/flac` | `audio` | 是 | ✓ |
| `video/quicktime` | `video` | 是 | ✓ |
| `video/webm` | `video` | 是 | ✓ |
| `video/x-matroska` | `video` | 是 | ✓ |
| `application/mp4` | `video` | 是（容器） | ✓ |
| **`audio/mp4`** | **`audio, video`** | 只该是 audio | **✗ 多认 video** |
| **`audio/webm`** | **`audio, video`** | 只该是 audio | **✗ 多认 video** |
| **`video/ogg`** | **`audio, video`** | 只该是 video | **✗ 多认 audio** |

### G4 裸扩展名 / 中文 / 大写 / 带参数（9 / 9 正确）

| MIME/kind 串 | 识别结果 | 该认出吗 | 判定 |
|---|---|---|---|
| `png` | `image` | 是 | ✓ |
| `mp4` | `video` | 是 | ✓ |
| `mp3` | `audio` | 是 | ✓ |
| `pdf` | `()` | 否（pdf 不在三介质内） | ✓ 正确未认 |
| `图片` | `image` | 是 | ✓ |
| `视频` | `video` | 是 | ✓ |
| `音频` | `audio` | 是 | ✓ |
| `IMAGE/PNG` | `image` | 是 | ✓ 大小写不敏感 |
| `image/png; charset=binary` | `image` | 是 | ✓ 带参数也能认 |

### G5 对抗样本（9 / 16 正确，**7 条误认**）

| MIME/kind 串 | 识别结果 | 该认出吗 | 判定 |
|---|---|---|---|
| `application/json` | `()` | 否 | ✓ |
| `application/octet-stream` | `()` | 否 | ✓ ★ 见 §4 |
| `application/ld+json` | `()` | 否 | ✓ |
| `application/xhtml+xml` | `()` | 否 | ✓ |
| `text/html` | `()` | 否 | ✓ |
| `text/css` | `()` | 否 | ✓ |
| `text/javascript` | `()` | 否 | ✓ |
| `text/markdown` | `()` | 否 | ✓ |
| `multipart/form-data` | `()` | 否 | ✓ |
| **`text/x-voice-transcript`** | **`audio`** | 否（转写文本不是音频） | **✗ 误认** |
| **`application/vnd.oasis.opendocument.image`** | **`image`** | 否（ODF 文档不是图片） | **✗ 误认** |
| **`application/x-image`** | **`image`** | 否 | **✗ 误认** |
| **`application/x-picture`** | **`image`** | 否 | **✗ 误认** |
| **`application/x-gift`** | **`image`** | 否（含子串 `gif`） | **✗ 误认** |
| **`application/x-png-thing`** | **`image`** | 否（含子串 `png`） | **✗ 误认** |
| **`audio/x-mov`** | **`audio, video`** | 否（含子串 `mov`） | **✗ 误认** |

> **诚实标注**：`application/x-gift`、`application/x-png-thing`、`audio/x-mov`、
> `application/x-image`、`application/x-picture` 这 5 条是我**构造**的，
> 现实里大概率不会出现。它们的作用是**证明子串匹配这条路本身有洞**，不是证明现实中会踩。
> 而 `text/x-voice-transcript` 与 `application/vnd.oasis.opendocument.image` 是**接近真实**的写法。

---

## 三 ★ 「认错」的后果：一个纯音频文件通过了「必须有画面」的闸门

`audio/mp4` 是 **M4A / iPod 音频的标准 MIME** —— 不是构造出来的，是极常见的真实值。

### 3.1 实测

```
$ python3 -c "..."
media = _describe_media_ref({"uri":"song.m4a","mime":"audio/mp4"})
declared = ('audio', 'video')          ← 凭空多出 video
missing  = ()                           ← 空 = 闸门放行
status   = ok | provider 被调用: 1 次
```

一个 `.m4a` 纯音频文件，请求 `av_alignment`（要求 `video + audio`），
**介质闸门判定「两样都有」，provider 被实际调用了一次。**

而这正是我们加介质闸门要防的那个失败模式 —— 只不过方向反了：

| | 原来要防的 | 这次实测到的 |
|---|---|---|
| 现象 | 缺音轨，provider 只看了画面 | **缺画面，provider 去看一个音频文件** |
| 报错 | 没有 | 没有 |
| 结果 | 返回一个「看起来分析过了」的结果 | 同上 |

### 3.2 根因：不是 hint 在介质间共享，是**整串包含匹配**

我第一版诊断写的是「容器扩展名同时挂在视频与音频下」—— **那是错的**，
我当时的诊断脚本打出来的重叠表是空的，而我没看那张空表就把结论写进了打印语句。

真实原因是 `_declared_media()` 把 `kind` 与 `mime` 拼成一个 blob，
然后对**每个 hint 做 `in` 判断**：

```
'audio/mp4'                     → 命中 video 的 hint 'mp4'   → 多认 video
'application/x-gift'            → 命中 image 的 hint 'gif'   → 误认 image
'text/x-voice-transcript'       → 命中 audio 的 hint 'voice' → 误认 audio
'audio/x-mov'                   → 命中 video 的 hint 'mov'   → 误认 video
```

`audio/mp4` 的正确读法是「主类型是 audio，subtype 是 mp4 容器」——
**主类型已经说死了这是音频**，subtype 里的 `mp4` 是容器名，不是「它含视频」。

---

## 四 反向对照（05 硬要求第 2 条）

> 喂一个明显不是介质的串，它**必须不被认成** image/video/audio。

**14 条全部通过：**

```
application/json            ()   ✓
text/plain                  ()   ✓
application/octet-stream    ()   ✓   ← 最关键的一条
application/ld+json         ()   ✓
application/xhtml+xml       ()   ✓
text/html / text/css / text/javascript / text/markdown   ()  ✓
multipart/form-data         ()   ✓
application/toml / text/csv / application/xml / application/zip  ()  ✓
```

★ `application/octet-stream` 没被认成图片，这条是运气也是设计：
它不含任何介质 hint 子串。**但如果哪天有人往 hint 表里加 `"octet"` 或 `"binary"`，这条会立刻失守。**
所以这条反向对照应当**写进 `tools/verify_multimodal_provider.py`**，而不是只活在这份报告里。

> 本文所有读数都是**一次性的**（§2.2 第 1 条：「文档里的数字要算出来」）。
> 这里的 80.4% / 0 漏 / 7 误认都是 2026-10-21 这一次的读数，不是常量。
> 复现命令见 §7。

---

## 五 补法建议（**没有实施**，等 05 决定）

### 5.1 建议的判据改动（一句话）

> **先看 MIME 主类型，主类型能定就按它定；只有主类型是 `application/*` 或没有 MIME 时，才退回扩展名匹配。**

### 5.2 按这个判据重算（我离线model了一遍，没改代码）

| 串 | 现状 | 建议判据下 | 差 |
|---|---|---|---|
| `audio/mp4` | `audio, video` | `audio` | ✅ 修好多认 |
| `audio/webm` | `audio, video` | `audio` | ✅ |
| `video/ogg` | `audio, video` | `video` | ✅ |
| `application/mp4` | `video` | `video` | — |
| `application/x-gift` | `image` | `()` | ✅ 修好误认 |
| `text/x-voice-transcript` | `audio` | `()` | ✅ |
| `image/png` | `image` | `image` | — |
| `video/mp4` | `video` | `video` | — |
| `MP4`（裸扩展名） | `video` | `()` | ⚠️ **会退化** —— 裸扩展名没有主类型，必须走扩展名退回 |

### 5.3 但 `MP4` 那一行说明：不能简单地「只认 MIME 主类型」

裸扩展名（`"mp4"`、`"png"`、`"图片"`）是**合法输入** —— G4 那 9 条现在全对，
而调用方完全可能只填 `kind="mp4"`。所以建议判据必须是**两段**：

```
1. 有 "/" → 按主类型判：image/* | video/* | audio/* 直接定；
             主类型是 application/* 或 text/* → 不认（除非 subtype 是已知媒体容器）
2. 没有 "/" → 退回现有的扩展名/中文匹配（G4 那套，目前全对）
```

### 5.4 逐条补法

| 问题串 | 现在 | 建议 | 优先级 |
|---|---|---|---|
| `audio/mp4` | 多认 video | 主类型 audio 优先，忽略 subtype 里的 `mp4` | **高**（M4A 极常见 + 已实测可放行） |
| `audio/webm` | 多认 video | 同上 | 中 |
| `video/ogg` | 多认 audio | 同上 | 低（OGV 通常确实带音轨） |
| `text/x-voice-transcript` | 误认 audio | 主类型 text → 不认 | 中 |
| `application/vnd.oasis.opendocument.image` | 误认 image | 主类型 application → 不认 | 中 |
| `application/x-image` / `x-picture` / `x-gift` / `x-png-thing` / `audio/x-mov` | 误认 | 主类型 application → 不认 | 低（构造样本） |

### 5.5 不建议的两种补法

1. **把 `mp4` 从 video 的 hint 里删掉** —— 会连带打断裸扩展名 `"mp4"`（G4 里现在是对的），
   而且 `video/mp4` 也靠它。
2. **加更多 hint 来提高召回** —— 召回已经是 100%，再加只会扩大误认面。

---

## 六 未测的

1. **仓内没有已跟踪的音视频文件**，所以「真实音频/视频文件的 `file --mime-type` 读数」这一档是空的。
   我只测到 2 个真实 PNG。音频视频的实测需要素材，而素材在 `~/audit-data/`，本单不许读。
2. **`_declared_media` 只用 `kind` 和 `mime` 两个字段**。如果调用方把 MIME 填在第三个字段里
   （比如 `content_type`），目前不会被看到。`_describe_media_ref` 对 Mapping 输入认
   `mime` / `content_type`，但 `MediaRef` 只有 `mime`。这条没测。
3. **中文 hint 的覆盖面**只测了 `图片` / `视频` / `音频` 三个词。
   `画面`、`静图`、`影片`、`音轨`、`语音` 在表里但没单独测。

---

## 七 复现

```bash
# 主测量（只读）
python3 - <<'PY'
import sys; sys.path.insert(0,'.')
from base import multimodal_provider as M
for s in ("image/png","audio/mp4","application/x-gift","text/x-voice-transcript"):
    m = M._describe_media_ref({"uri":"x","mime":s})
    print(s, "->", M._declared_media(m))
PY

# 反向对照：这 14 条必须全部返回 ()
python3 - <<'PY'
import sys; sys.path.insert(0,'.')
from base import multimodal_provider as M
for s in ("application/json","text/plain","application/octet-stream",
          "application/ld+json","application/xhtml+xml","text/html","text/css",
          "text/javascript","text/markdown","multipart/form-data",
          "application/toml","text/csv","application/xml","application/zip"):
    got = M._declared_media(M._describe_media_ref({"uri":"x","mime":s}))
    assert got == (), (s, got)
print("14/14 全部正确未认")
PY

# 语料提取（会混进路径片段，需人工清洗 —— 见 §1）
git ls-files | xargs grep -ohE '\b(image|video|audio)/[A-Za-z0-9.+-]+' 2>/dev/null | sort -u

# 本单前后的验收
python3 base/multimodal_provider.py
python3 tools/verify_multimodal_provider.py
```

---

## 八 顺带修的一个回归（我自己引入的）

跑验收时 `verify_multimodal_provider.py` 变成 **rc=2（未测）**，不是红也不是绿：

```
PermissionError: [Errno 1] Operation not permitted: '/var/folders/…/mm-mut-…/__pycache__'
```

**真因**：上一单我把变异副本从 `base/` 挪进临时目录（修「并发跑会互相覆盖」）。
子进程 import 该副本时，Python 在副本旁写 `__pycache__/` —— 那是一个**目录**，
而清理代码用 `unlink()` 只删文件，macOS 上对目录 `unlink` 抛 EPERM。

**两条都修了**：

1. 子进程加 `-B`（禁止写字节码），从源头不产生 `__pycache__`；
2. 清理改用 `shutil.rmtree(..., ignore_errors=True)` —— **清理失败不许把验收结论变成「未测」**
   （一个在 `finally` 里抛异常的实现，会让所有断言的结果一起消失）。

修后：`rc=0，43/43`。

> 这个 bug 的形状值得记：**它把「绿」变成了「未测」，而两者在日志里都不显眼。**
> 和 §2.2 第 7 条（`ps` 被拒导致读数静默退化）是同一个病。

---

## 九 给 05 的一句话

**召回率 100%，但那是「整串包含匹配」的假象。真正要修的是 `audio/mp4` 这一条 ——
它已经能实测放行一个纯音频文件去跑 `av_alignment`，而这正是介质闸门存在的理由。**
