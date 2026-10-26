#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_media_selection.py —— T-412 选型的**注册级契约**

## 它验的是哪一跳

`ADR/ADR-0018-容器内OCR与ASR选型.md` 选定了两个引擎，并把它们登记进
`base/media.py` 的 `MEDIA_PROVIDERS`。本脚本断言**文档与注册点是同一件事**。

模板是 `verify_adr_status.py`（ADR 台账 ≡ ADR 文件）：
**两处各写一遍 → 各自漂移 → 读的人得到两个答案**。同一个病在选型上更贵，
因为「文档说用 A、代码装的是 B」不会报错，只会安静地用错引擎。

## 为什么不改造 `verify_media_portability.py`

那个脚本管的是**行 118 的另一半**：仓里还有没有宿主原生调用、媒体进件开了没。
本脚本管的是「**选定的是哪个、它真的注册了吗**」。两者失败后要查的东西不同：

| 失败 | 该去改哪 |
|---|---|
| `verify_media_portability` 红 | `base/ocr_vision.m` / `SUPPORTED_SOURCE_KINDS` |
| 本脚本红 | ADR-0018 与 `MEDIA_PROVIDERS` 的某一行对不上 |

合成一个退出码就分不清该改哪一侧 —— 与 `verify_secret_patterns` 不并进 DG 同一条理由
（AGENTS.md §2.1）。**并且**：改造会让 §2.1 表里那一行的读数含义变宽，
而那一行现在是**空真**（`vacuous_true`），正是最不该动它的时候。

## 断言

| 段 | 断言 | 拦什么 |
|---|---|---|
| **S1** | ADR-0018 存在、状态是 `accepted`、日期是 2026-10-26 | 选了却没落成决策 |
| **S2** | ADR 点名的 provider_id **集合恒等**于 `MEDIA_PROVIDERS` 的键集合 | 文档多写一个 / 代码少注册一个 |
| **S3** | 逐字段相等：`package` / `version` / `license` / `bundled_models` | 「文档说 3.10.0、代码装 3.9」（最容易漂的一列） |
| **S4** | ADR 点名的 adapter 类**在 `base/media.py` 里真实存在**（`ast` 查到 ClassDef） | 名字出现在文档里 ≠ 代码里有那个类 |
| **S5** | 每个登记项都有**至少一条**「不选它」的理由写在 ADR 里（被否候选 ≥2 个） | 只列赢了谁，不列输了谁 → 无法复核选型 |
| **S6** | 默认引擎仍是 `host_vision` / `None`，且 `SUPPORTED_SOURCE_KINDS` 无 image/video | **注册偷偷变成接线**（打开媒体进件是另一张票） |
| **S7** | 宿主原生命中数 **≥3**（不许因为本次改动减少） | 靠删 `.m` 文件「解决」行 118 |
| **S8** | 空真不许写成通过：行 118 的 state 仍是 `vacuous_true` 时，ADR 必须写着 `vacuous_true` | 把空真读成 passed（本案的核心禁令） |

★ S7 的判据是 `>=` 而不是 `==`：本脚本不该因为「有人又加了一处宿主调用」而红
（那是 `verify_media_portability` 的 G2 的活），它只防**减少**。

退出码：**0** 全过 · **1** 有红 · **2** 未测（ADR 读不出 / media.py 导入失败 /
宿主扫描跑不了）。★ 未测与红与通过三者退出码互不相同（AGENTS.md §2.4.2）。

用法：
    python3 tools/verify_media_selection.py
    python3 tools/verify_media_selection.py --controls   # 离线反向对照
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADR = ROOT / "ADR" / "ADR-0018-容器内OCR与ASR选型.md"
MEDIA = ROOT / "base" / "media.py"
SUBMISSION = ROOT / "base" / "submission_service.py"

PASS: list[str] = []
FAIL: list[tuple[str, str]] = []
UNTESTED: list[str] = []


def ok(label: str) -> None:
    PASS.append(label)


def no(seg: str, why: str) -> None:
    FAIL.append((seg, why))


def untested(why: str) -> None:
    UNTESTED.append(why)


# ──────────────────────────────────────────────────────────────────────────
# ADR 解析
#
# ★ 判据是「读到结构」，不是「grep 到关键词」。ADR 里那张 provider 表是本脚本的输入，
#   所以表格的形状必须被**解析**而不是被**搜索**：搜索「rapidocr」在一个散文段落里
#   也能命中，而那样 S3 的逐字段对账就没有对象了。
# ──────────────────────────────────────────────────────────────────────────

STATUS_RE = re.compile(r"^-\s*状态[:：]\s*(.+)$", re.M)
DATE_RE = re.compile(r"^-\s*日期[:：]\s*(\d{4}-\d{2}-\d{2})$", re.M)


def status_token(text: str) -> str:
    m = STATUS_RE.search(text)
    if not m:
        return ""
    t = re.search(r"`([^`]+)`", m.group(1))
    return (t.group(1) if t else m.group(1).strip()).strip()


def parse_provider_table(text: str) -> dict[str, dict[str, str]]:
    """解析 ADR 里那张 provider 表，**按表头列名映射字段**。

    表头必须含 `provider_id` / `package` / `version` / `license` /
    `bundled_models` / `adapter` 六个名字，缺一个就整表解析成空
    （返回 `{}`，调用方落 S2 红）。

    ★ 为什么按**列名**而不是按**列序**：按列序解析时，谁把 `package` 与
      `version` 两列对调，表照样「解析成功」，只是 3.10.0 被读成包名 ——
      而 S3 的逐字段对账会拿错值去比，比出来是绿。**这就是 §2.4.1 那个形状。**
      按列名解析后，列序打乱不影响读数，但**缺列**或**改列名**一定红。
    """
    FIELDS = ("provider_id", "package", "version", "license",
              "bundled_models", "adapter")
    rows: list[list[str]] = []
    cols: list[str] | None = None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if cols is not None and rows:
                break            # 这张表结束了
            continue
        cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
        low = [c.lower() for c in cells]
        if cols is None:
            if all(f in low for f in FIELDS):
                cols = low
            continue
        if set("".join(cells)) <= set("-: "):
            continue             # 分隔行
        rows.append(cells)

    if cols is None:
        return {}
    idx = {f: cols.index(f) for f in FIELDS}
    out: dict[str, dict[str, str]] = {}
    for cells in rows:
        if len(cells) <= max(idx.values()):
            continue
        pid = cells[idx["provider_id"]]
        if not re.match(r"^[a-z0-9_]+$", pid):
            continue
        out[pid] = {
            "provider_id": pid,
            "package": cells[idx["package"]],
            "version": cells[idx["version"]],
            "license": cells[idx["license"]],
            "bundled_models": cells[idx["bundled_models"]].lower() in
                              ("true", "是", "✅", "yes", "随包"),
            "adapter": cells[idx["adapter"]],
        }
    return out


def parse_rejected(text: str) -> list[str]:
    """解析「不选的候选」表：返回被否掉的候选名。

    判据（两条都要满足，缺一条就会漏或误报）：

    1. **小节范围**：某级标题命中 `不选|否掉|落选|不采用` 后进入「被否区」，
       直到**同级或更高级**的标题离开。★ 只认「标题命中」不够 ——
       真实文档里 `## 四 · 不选的候选` 下面还有 `### 4.1 OCR` / `### 4.2 ASR`
       两个子标题，若一见标题就关，两张表都会被漏掉（实测漏 0/2）。
    2. **候选名**：取第一格；有反引号就取反引号里那一段（`paddleocr` 3.7.0 → paddleocr）。
    """
    out: list[str] = []
    active_level: int | None = None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(#{1,6})\s*(.*)$", s)
        if m:
            level, title = len(m.group(1)), m.group(2)
            if active_level is not None and level <= active_level:
                active_level = None          # 走出被否区
            if re.search(r"不选|否掉|落选|不采用", title):
                active_level = level
            continue
        if active_level is None or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if not first or set(first) <= set("-: ") or first.strip("`") == "候选":
            continue
        bt = re.search(r"`([^`]+)`", first)
        name = bt.group(1) if bt else first
        if name and name not in out:
            out.append(name)
    return out


# ──────────────────────────────────────────────────────────────────────────
# 代码侧读数
# ──────────────────────────────────────────────────────────────────────────

def code_registrations() -> dict[str, dict]:
    """从 `base/media.py` 拿**真实登记项**。导入失败 → 未测（不是红）。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from base import media as M          # noqa: PLC0415
    return {
        pid: {
            "provider_id": p.provider_id,
            "package": p.package,
            "version": p.version,
            "license": p.license,
            "bundled_models": p.bundled_models,
            "adapter": p.adapter,
        }
        for pid, p in M.MEDIA_PROVIDERS.items()
    }


def code_class_names() -> set[str]:
    """`base/media.py` 里真实定义的类名（`ast`，不是 grep）。

    ★ 用 `ast` 而不是 `"class X" in src`：后者在注释里出现一次就恒真 ——
      这正是 AGENTS.md §2.4 点名的「名字出现过 ≠ 拦得住」。
    """
    tree = ast.parse(MEDIA.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def default_engines() -> tuple:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from base import media as M          # noqa: PLC0415
    return M.DEFAULT_OCR_ENGINE, M.DEFAULT_ASR_ENGINE


def supported_kinds() -> frozenset | None:
    try:
        from base import submission_service as S   # noqa: PLC0415
        return frozenset(S.SUPPORTED_SOURCE_KINDS)
    except Exception:                                # noqa: BLE001
        return None


def native_hits() -> list[str] | None:
    """复用 `verify_media_portability` 的扫描器 —— **不复制一份**。

    复制一份就会有两个分母，然后各自漂移（本项目已栽过多次）。
    """
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import verify_media_portability as P        # noqa: PLC0415
        return P.scan(P.collect())
    except Exception:                                # noqa: BLE001
        return None


# ──────────────────────────────────────────────────────────────────────────
# 判定（纯函数：控制组直接复用）
# ──────────────────────────────────────────────────────────────────────────

def audit(adr_text: str | None, code: dict[str, dict], classes: set[str],
          defaults: tuple, kinds, hits) -> tuple[list[str], list[tuple[str, str]]]:
    P: list[str] = []
    F: list[tuple[str, str]] = []

    # ── S1 存在性 / 状态 / 日期 ───────────────────────────────────────
    if adr_text is None:
        F.append(("S1", "ADR-0018 不存在 —— 选型没有落成决策"))
        return P, F
    st = status_token(adr_text)
    if st != "accepted":
        F.append(("S1", "ADR-0018 的状态是 %r，不是 `accepted`（委托方已批准，须写明）"
                  % (st or "(无)")))
    else:
        P.append("S1 状态 accepted")
    d = DATE_RE.search(adr_text)
    if not d or d.group(1) != "2026-10-26":
        F.append(("S1", "ADR-0018 的日期不是 2026-10-26（读到 %r）"
                  % (d.group(1) if d else "(无)")))
    else:
        P.append("S1 日期 2026-10-26")

    doc = parse_provider_table(adr_text)

    # ── S2 集合恒等（双向）─────────────────────────────────────────
    if not doc:
        F.append(("S2", "ADR 里解析不出 provider 表 —— 选型没有可对账的对象"))
        return P, F
    missing = sorted(set(doc) - set(code))
    extra = sorted(set(code) - set(doc))
    if missing:
        F.append(("S2", "ADR 点了名但**代码里没注册**：%s" % "、".join(missing)))
    if extra:
        F.append(("S2", "代码里注册了但**ADR 没点名**：%s（注册一个未决策的引擎）"
                  % "、".join(extra)))
    if not missing and not extra:
        P.append("S2 provider 集合恒等（%d 个）" % len(doc))

    # ── S3 逐字段相等 ──────────────────────────────────────────────
    FIELDS = ("package", "version", "license", "bundled_models", "adapter")
    for pid in sorted(set(doc) & set(code)):
        for f in FIELDS:
            want, got = doc[pid][f], code[pid][f]
            if want != got:
                F.append(("S3", "%s 的 %s 不一致：ADR=%r / 代码=%r"
                          % (pid, f, want, got)))
        if doc[pid] == {k: code[pid][k] for k in ("provider_id",) + FIELDS}:
            P.append("S3 %s 五个字段逐项相等" % pid)

    # ── S4 adapter 类真实存在 ──────────────────────────────────────
    for pid, row in sorted(doc.items()):
        a = row["adapter"]
        if not a:
            F.append(("S4", "%s 没写 adapter 类名" % pid))
        elif a not in classes:
            F.append(("S4", "%s 的 adapter %r 在 base/media.py 里**没有这个类**"
                      % (pid, a)))
        else:
            P.append("S4 %s → class %s（ast 查到）" % (pid, a))

    # ── S5 被否候选 ≥2 ─────────────────────────────────────────────
    rej = parse_rejected(adr_text)
    if len(rej) < 2:
        F.append(("S5", "ADR「不选的候选」只解析到 %d 个（%s），必须 ≥2 —— "
                        "只写赢了谁，选型无法复核" % (len(rej), "、".join(rej) or "无")))
    else:
        P.append("S5 被否候选 %d 个：%s" % (len(rej), "、".join(rej)))

    # ── S6 注册 ≠ 接线 ─────────────────────────────────────────────
    ocr_default, asr_default = defaults
    if ocr_default != "host_vision":
        F.append(("S6", "DEFAULT_OCR_ENGINE 变成了 %r —— 注册偷偷变成了接线，"
                        "打开媒体进件是 T-118-follow，不在本票范围" % (ocr_default,)))
    else:
        P.append("S6 默认 OCR 仍是 host_vision（注册未接线）")
    if asr_default is not None:
        F.append(("S6", "DEFAULT_ASR_ENGINE 被设成 %r —— 仓里没有 ASR 素材，"
                        "设默认等于宣称已接" % (asr_default,)))
    else:
        P.append("S6 默认 ASR 仍是 None")
    if kinds is None:
        untested("读不出 SUPPORTED_SOURCE_KINDS —— S6 的进件半边无法判定")
    else:
        opened = sorted(k for k in ("image", "video") if k in kinds)
        if opened:
            F.append(("S6", "SUPPORTED_SOURCE_KINDS 含 %r —— 媒体进件被打开了，"
                            "那会让行 118 从空真变成真违规，必须走 T-118-follow"
                            % (opened,)))
        else:
            P.append("S6 媒体进件未打开（%s）" % sorted(kinds))

    # ── S7 宿主原生命中数不许减少 ──────────────────────────────────
    if hits is None:
        untested("宿主原生扫描跑不了 —— S7 无法判定")
    elif len(hits) < 3:
        F.append(("S7", "宿主原生命中只剩 %d 处（应 ≥3）。**不许靠删 base/ocr_vision.m "
                        "来「解决」行 118** —— 那是把空真换成假绿"
                  % len(hits)))
    else:
        P.append("S7 宿主原生命中 %d 处（未减少）" % len(hits))

    # ── S8 空真不许写成通过 ────────────────────────────────────────
    #
    # 判据：ADR 里必须**同时**出现 `vacuous_true` 这个词，且
    # **不得**把行 118 描述成 passed / 已满足。
    # ★ 反向对照证明它两种都拦得住（S8a 绿 / S8b 红）。
    has_vac = "vacuous_true" in adr_text
    claims_pass = bool(re.search(r"行\s*118\s*(是|已|为)\s*\**\s*(passed|通过|已满足)", adr_text))
    if not has_vac:
        F.append(("S8", "ADR 里没有 `vacuous_true` —— 行 118 今天是空真，"
                        "文档必须这么写，否则读者会以为已经做到了"))
    elif claims_pass:
        F.append(("S8", "ADR 把行 118 写成了 passed/已满足 —— **空真不是通过**"))
    else:
        P.append("S8 行 118 被如实写成 vacuous_true（未冒充 passed）")

    return P, F


# ──────────────────────────────────────────────────────────────────────────
# 控制组
# ──────────────────────────────────────────────────────────────────────────

GOOD_ADR = """- 状态：`accepted`（2026-10-26 委托方批准）
- 日期：2026-10-26

| provider_id | package | version | license | bundled_models | adapter |
|---|---|---|---|---|---|
| `rapidocr_ppocr_v6` | `rapidocr` | `3.10.0` | `Apache-2.0` | `True` | `ContainerOcrProvider` |
| `faster_whisper` | `faster-whisper` | `1.2.1` | `MIT` | `False` | `ContainerAsrProvider` |

### 2.2 不选的候选

| 候选 | 理由 |
|---|---|
| `paddleocr` | 依赖闭包 63 包 / 147 MiB |
| `tesseract` | 需要系统包与语言包 |
| `宿主 macOS Vision` | 不可跨平台 |

行 118 今天是 `vacuous_true`（空真），不是 passed。
"""

GOOD_CODE = {
    "rapidocr_ppocr_v6": {"provider_id": "rapidocr_ppocr_v6", "package": "rapidocr",
                          "version": "3.10.0", "license": "Apache-2.0",
                          "bundled_models": True, "adapter": "ContainerOcrProvider"},
    "faster_whisper": {"provider_id": "faster_whisper", "package": "faster-whisper",
                       "version": "1.2.1", "license": "MIT",
                       "bundled_models": False, "adapter": "ContainerAsrProvider"},
}
GOOD_CLASSES = {"ContainerOcrProvider", "ContainerAsrProvider"}
GOOD_DEFAULTS = ("host_vision", None)
GOOD_KINDS = frozenset({"free_text", "ad_text"})
GOOD_HITS = ["a.m:1", "a.m:2", "b.sh:3"]


def controls() -> int:
    def run(adr=GOOD_ADR, code=None, classes=None, defaults=GOOD_DEFAULTS,
            kinds=GOOD_KINDS, hits=GOOD_HITS):
        return audit(adr, GOOD_CODE if code is None else code,
                     GOOD_CLASSES if classes is None else classes,
                     defaults, kinds, hits)

    def is_green(**kw) -> bool:
        p, f = run(**kw)
        return not f

    def red_seg(seg: str, **kw) -> bool:
        p, f = run(**kw)
        return any(s == seg for s, _ in f)

    no_adr = dict(rapidocr_ppocr_v6=GOOD_CODE["rapidocr_ppocr_v6"],
                  faster_whisper=dict(GOOD_CODE["faster_whisper"]))
    no_adr.pop("faster_whisper")

    cases = [
        # 正向：好样本必须绿（否则整套断言是恒红）
        ("正样本：ADR 与注册一致 → 必须绿", lambda: is_green()),

        # S2 集合恒等（双向，缺一边另一边就恒真）
        ("★ S2 坏样本：删掉一条注册 → 必须红",
         lambda: red_seg("S2", code=no_adr)),
        ("★ S2 坏样本：代码多注册一个 ADR 没点名的 → 必须红",
         lambda: red_seg("S2", code={**GOOD_CODE, "extra_engine": {
             "provider_id": "extra_engine", "package": "x", "version": "1.0.0",
             "license": "MIT", "bundled_models": True,
             "adapter": "ContainerOcrProvider"}})),

        # S3 逐字段：最易漂的是 version
        ("★★ S3 坏样本：ADR 写 3.10.0、代码装 3.9.0 → 必须红",
         lambda: red_seg("S3", code={**GOOD_CODE, "rapidocr_ppocr_v6": {
             **GOOD_CODE["rapidocr_ppocr_v6"], "version": "3.9.0"}})),
        ("★★ S3 坏样本：license 漂了（Apache-2.0 → MIT）→ 必须红",
         lambda: red_seg("S3", code={**GOOD_CODE, "rapidocr_ppocr_v6": {
             **GOOD_CODE["rapidocr_ppocr_v6"], "license": "MIT"}})),

        # S4 名字出现过 ≠ 代码里有那个类
        ("★★ S4 坏样本：adapter 类在代码里不存在 → 必须红",
         lambda: red_seg("S4", classes={"ContainerOcrProvider"})),

        # S5 被否候选
        ("S5 坏样本：只列 1 个被否候选 → 必须红",
         lambda: red_seg("S5", adr=GOOD_ADR.replace(
             "| `tesseract` | 需要系统包与语言包 |\n"
             "| `宿主 macOS Vision` | 不可跨平台 |", ""))),

        # ★ 这一条是为一个**真实踩到的** bug 写的：第一版一见 `#` 标题就离开被否区，
        #   于是真实 ADR 里 `## 四 · 不选的候选` 下的 `### 4.1 OCR` / `### 4.2 ASR`
        #   两张表全被漏掉 —— 而 `--controls` 当时是绿的，因为样本里没有子标题。
        #   「自己写的样本盖不住的形状，就是上线会漏的形状」。
        ("★★ S5 子标题：被否区里有 `### 4.1` 子标题时不许提前收尾",
         lambda: parse_rejected(
             "## 四 · 不选的候选\n"
             "### 4.1 OCR\n"
             "| 候选 | 理由 |\n|---|---|\n"
             "| `paddleocr` 3.7.0 | 63 包 |\n"
             "| `tesseract` | 系统包 |\n"
             "### 4.2 ASR\n"
             "| 候选 | 理由 |\n|---|---|\n"
             "| `openai-whisper` | torch 529 MB |\n"
         ) == ["paddleocr", "tesseract", "openai-whisper"]),
        ("S5 反向：同级标题离开被否区后，新表不许被算进去",
         lambda: parse_rejected(
             "## 四 · 不选的候选\n"
             "| 候选 | 理由 |\n|---|---|\n"
             "| `paddleocr` | x |\n"
             "| `tesseract` | y |\n"
             "## 五 · 别的东西\n"
             "| 名字 | 备注 |\n|---|---|\n"
             "| `不该被算进来` | z |\n"
         ) == ["paddleocr", "tesseract"]),

        # S6 注册偷偷变成接线
        ("★★ S6 坏样本：DEFAULT_OCR_ENGINE 改成容器引擎 → 必须红",
         lambda: red_seg("S6", defaults=("rapidocr_ppocr_v6", None))),
        ("★★ S6 坏样本：SUPPORTED_SOURCE_KINDS 加了 image → 必须红",
         lambda: red_seg("S6", kinds=frozenset({"free_text", "image"}))),
        ("S6 未测侧：kinds 读不出 → 必须落 untested 而不是绿",
         lambda: _untested_when_kinds_none()),

        # S7 不许靠删文件解决行 118
        ("★★ S7 坏样本：宿主原生命中数掉到 0 → 必须红",
         lambda: red_seg("S7", hits=[])),
        ("S7 反向：命中数变多（4 处）**不许**误报",
         lambda: is_green(hits=GOOD_HITS + ["c.m:9"])),

        # S8 空真不许写成通过（成对）
        ("★ S8a 正样本：写着 vacuous_true → 必须绿",
         lambda: is_green()),
        ("★★ S8b 坏样本：把行 118 写成 passed → 必须红",
         lambda: red_seg("S8", adr=GOOD_ADR.replace(
             "行 118 今天是 `vacuous_true`（空真），不是 passed。",
             "行 118 是 **passed**（已满足）。"))),
        ("★★ S8 坏样本：通篇不提 vacuous_true → 必须红",
         lambda: red_seg("S8", adr=GOOD_ADR.replace(
             "行 118 今天是 `vacuous_true`（空真），不是 passed。", ""))),

        # S1 状态/日期
        ("S1 坏样本：状态写成 proposed → 必须红",
         lambda: red_seg("S1", adr=GOOD_ADR.replace("`accepted`", "`proposed`"))),
        ("S1 坏样本：日期漂了 → 必须红",
         lambda: red_seg("S1", adr=GOOD_ADR.replace("- 日期：2026-10-26",
                                                   "- 日期：2026-10-20"))),

        # 解析器自身：缺列必须解析不出来（而不是按列序猜）
        ("★ 解析器：表头缺一列 → provider 表必须解析成空（不许按列序猜）",
         lambda: parse_provider_table(
             "| provider_id | version | package | license | bundled_models |\n"
             "|---|---|---|---|---|\n"
             "| `x` | `1.0.0` | `p` | `MIT` | `True` |\n") == {}),
        ("解析器：列序打乱但六列齐全 → 仍按列名对上（不许错位）",
         lambda: parse_provider_table(
             "| provider_id | version | package | license | bundled_models | adapter |\n"
             "|---|---|---|---|---|---|\n"
             "| `x` | `1.0.0` | `p` | `MIT` | `True` | `C` |\n"
         ).get("x", {}).get("package") == "p"),
    ]
    bad = 0
    print("=" * 78)
    print("T-412 选型契约 · ADR-0018 ≡ base/media.py 注册点（离线对照）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            good = bool(fn())
        except Exception as e:                       # noqa: BLE001
            good = False
            name += "（%s: %s）" % (type(e).__name__, e)
        if not good:
            bad += 1
        print(f"  {'✅' if good else '❌'} [{i}/{len(cases)}] {name}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def _untested_when_kinds_none() -> bool:
    """kinds=None 时 S6 的进件半边必须落 untested —— 而不是当成「没开」判绿。"""
    before = len(UNTESTED)
    audit(GOOD_ADR, GOOD_CODE, GOOD_CLASSES, GOOD_DEFAULTS, None, GOOD_HITS)
    grew = len(UNTESTED) > before
    del UNTESTED[before:]
    return grew


# ──────────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()

    text = None
    if ADR.is_file():
        text = ADR.read_text(encoding="utf-8")

    code = None
    try:
        code = code_registrations()
    except Exception as e:                           # noqa: BLE001
        untested("base/media.py 导入失败：%s: %s" % (type(e).__name__, e))
    try:
        classes = code_class_names()
    except Exception as e:                           # noqa: BLE001
        classes = set()
        untested("base/media.py 解析失败：%s: %s" % (type(e).__name__, e))
    try:
        defaults = default_engines()
    except Exception:                                # noqa: BLE001
        defaults = ("<unknown>", "<unknown>")
        untested("读不出 DEFAULT_OCR_ENGINE / DEFAULT_ASR_ENGINE")

    kinds = supported_kinds()
    hits = native_hits()

    print("=" * 78)
    print("T-412 选型契约 · ADR-0018 ≡ base/media.py 的 MEDIA_PROVIDERS")
    print("=" * 78)

    if text is None:
        no("S1", "ADR-0018 不存在：%s" % ADR.relative_to(ROOT))
        return report()

    if code is None:
        return report()

    P, F = audit(text, code, classes, defaults, kinds, hits)
    PASS.extend(P)
    FAIL.extend(F)
    return report()


def report() -> int:
    for l in PASS:
        print(f"  ✅ {l}")
    for seg, why in FAIL:
        print(f"  ❌ {seg} {why}")
    for w in UNTESTED:
        print(f"  ⚠️ 未测 {w}")
    print("-" * 78)

    if FAIL:
        print(f"❌ {len(FAIL)} 项红 / {len(PASS)} 项过 / {len(UNTESTED)} 项未测")
        # ★ 有红时也必须报出未测 —— 否则只看最后一行的人会以为「其余都验过了」
        #   （与 verify_shouheng_ops 的 H 段同一条）
        if UNTESTED:
            print(f"   ⚠️ 另有 {len(UNTESTED)} 项**未测**：上面这些红之外，还有东西没验到")
        return 1
    if UNTESTED:
        print(f"⚠️ 未测：{len(UNTESTED)} 项读不出来（不是通过，也不是红）")
        return 2
    print(f"✅ {len(PASS)} 项全过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:                          # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
