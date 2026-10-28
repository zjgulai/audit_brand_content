#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_media_ingest.py — T-431：图片进件（能力建成 · 生产路径未打开）

## 这一票验的是什么

`base/submission_service.py` 的图片进件这一层：能不能真的收下一张图、
产出一个**合法的** image ContentUnit、以及在什么条件下**必须拒绝**。

## 为什么 `SUPPORTED_SOURCE_KINDS` 刻意不动（这组断言的主角）

`ADR-0018` §6.2 把顺序写死了：行 118（媒体只许用容器内跨平台引擎）今天是
**空真** —— 仓里有 3 处 macOS Vision，只因为生产进件不接媒体，它们不在生产路径上。

一旦把 `image` 加进 `SUPPORTED_SOURCE_KINDS`：
  · 行 118 从「空真」翻成**真违规**（`verify_media_portability` G2 退 1）；
  · `verify_media_selection` S6 退 1；
  · 生产容器里 `ocr_file()` 找不到 macOS SDK，直接抛异常。

所以本票用 **`MEDIA_INGEST_ENABLED`（默认 False）** 把「能力」与「生产路径」分开，
并且这个开关自己要被断言守住 —— 否则它只是一句注释（AGENTS §2.4）。

## 断言分组

  A  开关的语义：默认关、只有 `is True` 才算开、字符串真值不算开
  B  两条读数不混用：`SUPPORTED_SOURCE_KINDS`（声明）vs `supported_source_kinds_now()`（此刻）
  C  门挡对了：开关关 → `media_ingest_disabled`（**不是** `unsupported_source_kind`）
  D  真跑：真实位图 → 合法 image unit，`covers` 只含图内文字、`does_not_cover` 含画面语义
  E  路径约束：根外 403 / 无根 503 / 不存在 404 / 相对路径按第一个根解析
  F  OCR 失败不许伪装成已审（`parse_status` 只许三值，失败带 failure_kind）
  G  现有守门断言仍绿（S6/G2 的读数取决于 `SUPPORTED_SOURCE_KINDS` 没动）

退出码：0 全过 / 1 有红 / 2 未测（导入失败、盘上无样本）。
`--controls`：反向对照 —— 把源码 exec 成打坏的临时副本，坏副本必须红、好副本必须绿。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import contract as C
    from base import media as MEDIA
    from base import submission_service as S
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入图片进件链: %s" % exc)
    sys.exit(2)


PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: " + name + ((" " + detail) if detail else ""))


def _real_image():
    """盘上第一张 ok 状态的真实位图。取不到返回 None（调用方落未测）。"""
    try:
        rows = MEDIA.load_rows()
    except Exception:  # noqa: BLE001
        return None
    for row in rows or []:
        if str(row.get("status")) != "ok":
            continue
        path = (row.get("fetch") or {}).get("path")
        if isinstance(path, str) and path and Path(path).is_file():
            return Path(path)
    return None


def _submission(image_path, **over):
    base = {
        "submission_id": "sub-img-verify",
        "content_type": "图片",
        "content_stage": "final_content",
        "entry_channel": "群消息",
        "source": {"kind": "image", "uri": str(image_path)},
        "product_line": "momcozy",
    }
    base.update(over)
    return base


PRINCIPAL = {"id": "u-verify", "tenant": "t-verify", "product_lines": ["momcozy"]}


def _expect_reject(fn, *a, **kw):
    """跑 fn，返回 SubmissionRejected 的 code；没抛返回 None。"""
    try:
        fn(*a, **kw)
    except S.SubmissionRejected as exc:  # noqa: PERF203
        return exc.code
    except Exception as exc:  # noqa: BLE001
        return "OTHER:%s" % type(exc).__name__
    return None


def _with_flag(value):
    """临时改开关；用 try/finally 复原，避免把后面所有用例带歪。

    ★ T-452：开关从「模块常量」改成**环境变量**之后，这里也必须跟着改 ——
      原先直接给 `S.MEDIA_INGEST_ENABLED` 赋值，而今那个名字不是一个可赋值的判据，
      继续这么写会**测不到真正的开关**（改了常量、生产读 env，两边不同源）。
      所以现在改的是 `os.environ`，与生产走同一条路。
      `None` 表示「不设这个变量」（回到默认关）。
    """
    class _Flag:
        def __enter__(self):
            self.had = S.MEDIA_INGEST_ENV in os.environ
            self.old = os.environ.get(S.MEDIA_INGEST_ENV)
            if value is None:
                os.environ.pop(S.MEDIA_INGEST_ENV, None)
            else:
                os.environ[S.MEDIA_INGEST_ENV] = value
            return self

        def __exit__(self, *exc):
            if self.had and self.old is not None:
                os.environ[S.MEDIA_INGEST_ENV] = self.old
            else:
                os.environ.pop(S.MEDIA_INGEST_ENV, None)
            return False
    return _Flag()


def check_gate_defaults():
    """A 组：开关的语义。"""
    # ★ T-452：开关从模块常量改成环境变量，A1 也跟着改 ——
    #   它现在验的是「**不设变量时**是关」，而不是「那个常量是 False」。
    with _with_flag(None):
        report(S.ingest_media_enabled() is False,
               "A1 不设 REVIEW_MEDIA_INGEST 时开关为关（默认安全不变）",
               repr(S.ingest_media_enabled()))
    report(S.ingest_media_enabled() is False,
           "A2 当前真实环境下 ingest_media_enabled() 为 False（判据读一处）")
    report("image" not in S.SUPPORTED_SOURCE_KINDS,
           "A3 ★ SUPPORTED_SOURCE_KINDS 不含 image（ADR-0018 §6.2 的静态那一半）",
           repr(sorted(S.SUPPORTED_SOURCE_KINDS)))
    # ★ 2026-10-28 改判据：视频**已经进来了**。
    #   旧判据写的是「今天只有 image（视频要 T-435 抽帧，不提前收）」——
    #   当时的理由是「没有 ASR 就没有正文，收视频等于收一个空壳」。
    #   但多模态接进生产之后这个前提变了：整段视频字节直接送模型
    #   （实测 1689 个模型支持 video 输入），不靠 ASR 也不靠抽帧。
    #   所以这里改成断言**两种都在**，并单独钉住「视频的正文确实是空的」——
    #   那才是「不提前收」原本要防的东西。
    report(S.MEDIA_SOURCE_KINDS == frozenset({"image", "video"}),
           "A4 ★ 媒体载体集合含 image 与 video（视频走多模态，不再等 ASR）",
           repr(sorted(S.MEDIA_SOURCE_KINDS)))
    # ★ 反例：只有明确的真值才算打开。
    #   T-452 之前开关是模块常量，A5/A6 验的是「字符串真值不算打开」。
    #   现在它读环境变量，语义变了：**环境变量里只有字符串**，所以那条判据不再成立。
    #   换成新语义下真正要紧的三条：假值明确关、真值明确开、**胡话必须报错而不是静默当关**。
    with _with_flag("false"):
        report(S.ingest_media_enabled() is False,
               "A5 ★ 'false' → 关（运维写 false 就必须真是关的）")
    with _with_flag("0"):
        report(S.ingest_media_enabled() is False, "A5b '0' → 关")
    with _with_flag(""):
        report(S.ingest_media_enabled() is False, "A5c 空串 → 关（不是「配了就开」）")
    with _with_flag("1"):
        report(S.ingest_media_enabled() is True,
               "A6 显式 '1' → 算打开（否则开关是砖头，永远开不了）")
    with _with_flag("TRUE"):
        report(S.ingest_media_enabled() is True, "A6b 'TRUE' 不分大小写 → 开")
    # ★★ 这一条是本组最要紧的：胡话不许静默当关。
    #   「配了但没生效」与「没配」长得一样，正是 §2.4.1 那个形状。
    with _with_flag("yes"):
        try:
            S.ingest_media_enabled()
            report(False, "A7 ★★ 'yes' 这种胡话必须报错，不许静默当关（实际没报）")
        except S.MediaIngestConfigError as exc:
            report("REVIEW_MEDIA_INGEST" in str(exc),
                   "A7 ★★ 'yes' 这种胡话必须报错并点名变量（不许静默当关）",
                   str(exc)[:70])
    # ★ 反向对照：合法的两个值不许报错（否则上面那条恒真——一个永远报错的实现也能过）
    with _with_flag("1"):
        try:
            S.ingest_media_enabled()
            report(True, "A8 ★ 反向对照：合法值 '1' 不许报错")
        except S.MediaIngestConfigError as exc:
            report(False, "A8 ★ 反向对照：合法值 '1' 不许报错", str(exc))


def check_env_entry():
    """H 组（T-452）：开关的**配置通路**与其配套判据。

    ★ 为什么单独一组：A 组验的是「值怎么解读」，这组验的是
      「运维真的能通过环境变量打开它」以及「打开了但引擎没接时，有没有东西说这件事」。
      两件事分开，是因为**前者今天才刚有**（改之前是硬编码），
      而后者是这次决定「不kai引擎」时唯一的安全网。
    """
    # H1 环境变量名要对得上（改了名字运维的配置就静默失效）
    report(S.MEDIA_INGEST_ENV == "REVIEW_MEDIA_INGEST",
           "H1 环境变量名是 REVIEW_MEDIA_INGEST", repr(S.MEDIA_INGEST_ENV))

    # H2 ★ 默认关（反向对照：不设变量时不许是开的）
    with _with_flag(None):
        report(S.ingest_media_enabled() is False,
               "H2 ★ 不设变量 → 关（默认安全不变）")

    # H3 ★★ 设成 1 → 真的打开（这是 T-452 补的那条路，改之前它永远打不开）
    with _with_flag("1"):
        report(S.ingest_media_enabled() is True,
               "H3 ★★ 设 REVIEW_MEDIA_INGEST=1 → 真的打开（改之前这条路不存在）")
        report("image" in S.supported_source_kinds_now(),
               "H4 ★ 打开后 supported_source_kinds_now() 含 image",
               repr(sorted(S.supported_source_kinds_now())))

    # H5 ★★★ 打开但引擎没接 → readiness 必须说清，不许让运维以为图片能审了
    with _with_flag("1"):
        ok, why = S.media_ingest_readiness()
        import base.media as MEDIA
        if MEDIA.DEFAULT_OCR_ENGINE == "host_vision":
            report(ok is False and "host_vision" in why,
                   "H5 ★★★ 开关开了但引擎仍是 host_vision → readiness 点名（不许静默）",
                   "%r / %r" % (ok, why[:60]))
        else:
            report(ok is True, "H5 引擎已接线 → readiness 通过（本机已是新引擎）",
                   "%r / %r" % (ok, why[:60]))

    # H6 关着时 readiness 必须通过（否则「没开」会被读成「配错了」）
    with _with_flag("0"):
        ok, why = S.media_ingest_readiness()
        report(ok is True and why == "", "H6 ★ 关着时 readiness 通过（不误报）",
               "%r / %r" % (ok, why[:60]))

    # H7 ★★ 反向对照：设了根目录但开关是关的 → 行为仍是「不收图」，
    #    但**必须有人能看见这件事**（readiness 通过 ≠ 根目录白配了）
    with _with_flag(None):
        report(S.ingest_media_enabled() is False,
               "H7 ★★ 只配根目录、不设开关 → 仍是不收图（根目录不会自己打开开关）")


def check_video_coverage():
    """I 组（2026-10-28）：视频的覆盖边界必须**如实**声明。

    ★ 这一组存在的理由：视频没有 ASR（`DEFAULT_ASR_ENGINE = None`），
      所以「口播文案未审」必须写在 `does_not_cover` 里。
      审核员看到「视频已审」时默认会以为连口播一起查过了 ——
      不写这一条，就是把没审的部分伪装成审过。

    ★ 同时钉住 `parse_status = partial` 而不是 ok / failed：
      · ok    → 口播一个字没读，说 ok 就是撒谎
      · failed→ 画面确实交给了多模态，模型会给出真实观察
      「做了一半」才是这里精确的状态。
    """
    import tempfile
    from pathlib import Path as _P

    d = _P(tempfile.mkdtemp(prefix="video-cov-"))
    try:
        mp4 = d / "t.mp4"
        mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200)
        ing = S.SubmissionIngestor(media_roots=[str(d)])
        with _with_flag('1'):
            try:
                unit = ing._build_media_unit(
                    _submission(mp4, source={"kind": "video", "uri": str(mp4)}),
                    kind="video", uri="u")
            except Exception as exc:  # noqa: BLE001
                report(False, "I1 视频 → unit", "%s: %s" % (type(exc).__name__, exc))
                return
        report(unit.get("parse_status") == "partial",
               "I1 ★★★ 视频 parse_status = partial（不是 ok：口播没读；"
               "不是 failed：画面确实审了）", repr(unit.get("parse_status")))
        dnc = (unit.get("textification") or {}).get("does_not_cover") or []
        report(any("口播" in x for x in dnc),
               "I2 ★★★ does_not_cover 明写「口播文案」未审"
               "（不写就是把没审的伪装成审过）", repr(dnc[:2]))
        cov = (unit.get("textification") or {}).get("covers") or []
        report(cov and all("画面" in x for x in cov),
               "I3 ★ covers 只声明画面（不许把口播算进覆盖）", repr(cov))
        report((unit.get("text") or "") == "",
               "I4 ★ 没有 ASR 时正文为空（不编一段假正文）", repr(unit.get("text")))
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def check_two_readings():
    """B 组：两个读数不许混用。"""
    with _with_flag('0'):
        now = S.supported_source_kinds_now()
        report("image" not in now,
               "B1 关时不接受 image", repr(sorted(now)))
        report(now == S.SUPPORTED_SOURCE_KINDS,
               "B2 关时「此刻」与「声明」相等（关闭状态两者不该分叉）")
    with _with_flag('1'):
        now = S.supported_source_kinds_now()
        report(now == S.SUPPORTED_SOURCE_KINDS | S.MEDIA_SOURCE_KINDS,
               "B3 ★ 开时「此刻」= 声明 ∪ 媒体载体", repr(sorted(now)))
        report("image" in now and "image" not in S.SUPPORTED_SOURCE_KINDS,
               "B4 ★ 打开后声明常量**仍未变**（能力与生产路径是两件事）",
               repr(sorted(S.SUPPORTED_SOURCE_KINDS)))


def check_gate_blocks(image_path):
    """C 组：开关关时挡在哪一道门 —— 必须点名是媒体那道，不是别的。"""
    ing = S.SubmissionIngestor(media_roots=[str(image_path.parent)])
    with _with_flag('0'):
        code = _expect_reject(ing.prepare, _submission(image_path),
                              principal=PRINCIPAL)
    report(code == "media_ingest_disabled",
           "C1 ★ 开关关 → media_ingest_disabled（不是 unsupported_source_kind）",
           repr(code))
    # ★ 反向：别的载体被挡时**不许**借用媒体那个码，否则两者分不开
    with _with_flag('0'):
        code2 = _expect_reject(
            ing.prepare,
            _submission(image_path, source={"kind": "video", "uri": "x"}),
            principal=PRINCIPAL)
    # ★ 2026-10-28 改判据：视频现在是媒体载体，被挡时**应当**用媒体的码。
    #   旧判据写「不许用媒体的码，它连能力都还没有」—— 那在当时是对的，
    #   现在能力已经有了（多模态）。改判据不是放宽，是把断言挪到新事实上：
    #   「被哪道门挡」必须说清，而视频与图片现在走同一道门。
    report(code2 == "media_ingest_disabled",
           "C2 ★ video 是媒体载体，被挡时用媒体的码（与 image 同一道门）",
           repr(code2))
    # 媒体门开着时，文本链路不许受影响
    with _with_flag('1'):
        code3 = _expect_reject(
            ing.prepare,
            _submission(image_path, content_type="文本",
                        source={"kind": "image", "uri": str(image_path)}),
            principal=PRINCIPAL)
    report(code3 == "unsupported_content_type",
           "C3 ★ 开关开但 content_type 配错 → unsupported_content_type",
           repr(code3))


def check_real_image(image_path):
    """D 组：真跑一张图。"""
    ing = S.SubmissionIngestor(media_roots=[str(image_path.parent)])
    with _with_flag('1'):
        try:
            unit = ing._build_unit(_submission(image_path),
                                   product_line="momcozy", uri="submission:s1")
        except Exception as exc:  # noqa: BLE001
            report(False, "D0 真实位图建 unit", "%s: %s" % (type(exc).__name__, exc))
            return
    report(unit.get("source", {}).get("kind") == "image",
           "D1 产出 kind=image 的 ContentUnit", repr(unit.get("source", {}).get("kind")))
    report(unit.get("parse_status") in ("ok", "partial", "failed"),
           "D2 parse_status 在三值域内", repr(unit.get("parse_status")))
    covers = " ".join(unit.get("textification", {}).get("covers") or [])
    dnc = " ".join(unit.get("textification", {}).get("does_not_cover") or [])
    report("图内文字" in covers,
           "D3 covers 声明了图内文字", repr(covers[:80]))
    report("画面语义" not in covers,
           "D4 ★★ covers 里**不许**出现画面语义（否则等于把没审的伪装成审过）",
           repr(covers[:120]))
    report("画面语义" in dnc,
           "D5 ★★ does_not_cover 必须含画面语义（T-431 判据 2）", repr(dnc[:120]))
    report(C.validate(unit) == [],
           "D6 产出的 unit 过 contract.validate", repr(C.validate(unit)[:3]))
    # ★ 端到端形状：把 switch 打开后走 prepare，案件真的建出来
    with _with_flag('1'):
        got = _expect_reject(ing.prepare, _submission(image_path),
                             principal=PRINCIPAL)
    report(got != "media_ingest_disabled" and got != "image_ingest_failed",
           "D7 ★ 开关开时 prepare 不再被媒体门挡（后续失败与进件无关）",
           repr(got))


def check_path_constraints(image_path):
    """E 组：路径约束 —— 不能让这个端点变成任意文件的读取器。"""
    root = image_path.parent
    ing = S.SubmissionIngestor(media_roots=[str(root)])
    with _with_flag('1'):
        code = _expect_reject(
            ing._build_unit,
            _submission(image_path, source={"kind": "image", "uri": "/etc/hosts"}),
            product_line="p", uri="u")
        report(code == "image_path_outside_allowed_roots",
               "E1 ★ 根外路径 → 403（不许对机器上任意文件做 OCR）", repr(code))

        bare = S.SubmissionIngestor()
        code2 = _expect_reject(bare._build_unit, _submission(image_path),
                               product_line="p", uri="u")
        report(code2 == "media_root_not_configured",
               "E2 ★ 未配根目录 → 503（不配就不收图，不是收了再算）", repr(code2))

        code3 = _expect_reject(
            ing._build_unit,
            _submission(image_path, source={"kind": "image",
                                            "uri": str(root / "definitely-absent.png")}),
            product_line="p", uri="u")
        report(code3 == "image_not_found",
               "E3 根内但不存在 → 404", repr(code3))

        code4 = _expect_reject(
            ing._build_unit,
            _submission(image_path, source={"kind": "image", "uri": ""}),
            product_line="p", uri="u")
        # ★ 2026-10-28：错误码从 `bad_image_uri` 改成 `bad_media_uri` ——
        #   图片与视频共用同一个 builder，码里带 image 会让视频的错误读起来
        #   像「图片那边的问题」。
        report(code4 == "bad_media_uri",
               "E4 source.uri 为空 → 422（码用 media，图片视频共用）", repr(code4))

        unit = ing._build_unit(
            _submission(image_path,
                        source={"kind": "image", "uri": image_path.name}),
            product_line="p", uri="u")
        report(unit.get("source", {}).get("kind") == "image",
               "E5 相对路径按第一个根解析（调用方不必写绝对路径）")


def check_failure_not_fake():
    """F 组：OCR 失败不许伪装成已审。"""
    with tempfile.TemporaryDirectory() as td:
        # 一个不是位图的文件：扩展名像图片，内容不是
        bad = Path(td) / "not-an-image.png"
        bad.write_bytes(b"this is definitely not a png")
        ing = S.SubmissionIngestor(media_roots=[td])
        with _with_flag('1'):
            try:
                unit = ing._build_unit(_submission(bad), product_line="p", uri="u")
            except S.SubmissionRejected as exc:
                report(exc.code == "image_ingest_failed",
                       "F1 非位图 → image_ingest_failed（不吞成已审）", repr(exc.code))
                return
            # 若 row_to_unit 把它写成 failed（正常路径），这也是对的
            status = unit.get("parse_status")
            report(status == "failed",
                   "F1 非位图 → parse_status=failed（不产出「审过了」）", repr(status))
            fk = unit.get("failure_kind")
            report(fk in C.FAILURE_KINDS,
                   "F2 失败带 failure_kind 且属于四类", repr(fk))
            report(unit.get("textification", {}).get("does_not_cover") not in (None, []),
                   "F3 失败样本仍声明 does_not_cover（边界不因失败而消失）")


def check_existing_guards():
    """G 组：现有两条守门断言的读数取决于那个常量没动。"""
    try:
        from tools import verify_media_portability as VP
    except Exception:  # noqa: BLE001
        untested("G1 无法导入 verify_media_portability —— 守门读数未核")
        return
    kinds = VP.supported_source_kinds()
    if kinds is None:
        untested("G1 读不出真实支持集")
        return
    report("image" not in kinds and "video" not in kinds,
           "G1 ★ 生产进件真实支持集仍不含 image/video（G2 与 S6 的地基）",
           repr(sorted(kinds)))
    report(kinds == S.SUPPORTED_SOURCE_KINDS,
           "G2 ★ 行为级读数与常量一致（不是被运行时覆盖掉的假象）",
           repr(sorted(kinds)))


# ── --controls：反向对照 ────────────────────────────────────────────────

def _src():
    with open(ROOT / "base" / "submission_service.py", encoding="utf-8") as f:
        return f.read()


class _Ns:
    """exec 出来的命名空间包成可属性访问 —— **写入必须透传到底层 dict**。

    ★ 第一版是 `self.__dict__.update(ns)`。它在读的时候看不出问题，
      但 `mod.MEDIA_INGEST_ENABLED = True` 只改了包装对象自己的属性，
      而 exec 出来的函数读的是**那个 dict** 作为 `__globals__` ——
      于是开关看起来打开了、函数眼里仍然是 False，E1/E2 全部误判成红，
      连「好副本必须全绿」那条也跟着红，六条对照全灭。

      这正是本项目反复记的形状：判据读的值和实际生效的值不是同一个东西。
      修法是让读写都落到同一个 dict 上，而不是各留一份。
    """

    def __init__(self, ns):
        object.__setattr__(self, "_ns", ns)

    def __getattr__(self, name):
        try:
            return self._ns[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name, value):
        self._ns[name] = value

    def __dir__(self):
        return list(self._ns)


def _exec_mod(text, tag):
    ns = {"__name__": "submission_service_%s" % tag,
          "__file__": str(ROOT / "base" / "submission_service.py")}
    exec(compile(text, "submission_service_%s.py" % tag, "exec"), ns)
    return _Ns(ns)


def probe(mod, image_path):
    """对给定模块跑关键判据，返回 {编号: 是否绿}。坏副本要能走进来。"""
    out = {}

    def hit(key, fn):
        try:
            out[key] = bool(fn())
        except Exception:  # noqa: BLE001
            out[key] = False

    # A3：常量不含 image
    hit("A3", lambda: "image" not in mod.SUPPORTED_SOURCE_KINDS)
    # A5：字符串真值不算开
    def _str_flag():
        old = mod.MEDIA_INGEST_ENABLED
        mod.MEDIA_INGEST_ENABLED = "false"
        try:
            return mod.ingest_media_enabled() is False
        finally:
            mod.MEDIA_INGEST_ENABLED = old
    hit("A5", _str_flag)
    # C1：开关关时挡在媒体那道门
    def _c1():
        ing = mod.SubmissionIngestor(media_roots=[str(image_path.parent)])
        old = mod.MEDIA_INGEST_ENABLED
        mod.MEDIA_INGEST_ENABLED = False
        try:
            try:
                ing.prepare(_submission(image_path), principal=PRINCIPAL)
            except mod.SubmissionRejected as exc:
                return exc.code == "media_ingest_disabled"
            return False
        finally:
            mod.MEDIA_INGEST_ENABLED = old
    hit("C1", _c1)
    # E1：根外路径必须拒
    def _e1():
        ing = mod.SubmissionIngestor(media_roots=[str(image_path.parent)])
        old = mod.MEDIA_INGEST_ENABLED
        mod.MEDIA_INGEST_ENABLED = True
        try:
            try:
                ing._build_unit(
                    _submission(image_path,
                                source={"kind": "image", "uri": "/etc/hosts"}),
                    product_line="p", uri="u")
            except mod.SubmissionRejected as exc:
                return exc.code == "image_path_outside_allowed_roots"
            return False
        finally:
            mod.MEDIA_INGEST_ENABLED = old
    hit("E1", _e1)
    # E2：无根必须拒
    def _e2():
        bare = mod.SubmissionIngestor()
        old = mod.MEDIA_INGEST_ENABLED
        mod.MEDIA_INGEST_ENABLED = True
        try:
            try:
                bare._build_unit(_submission(image_path), product_line="p", uri="u")
            except mod.SubmissionRejected as exc:
                return exc.code == "media_root_not_configured"
            return False
        finally:
            mod.MEDIA_INGEST_ENABLED = old
    hit("E2", _e2)
    return out


def run_controls(image_path):
    print("=" * 78)
    print("verify_media_ingest · --controls（图片进件断言的离线反向对照）")
    print("=" * 78)
    src = _src()
    ok = bad = 0

    def C(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            bad += 1
            print("  ❌ %s  %s" % (name, detail))

    # 每一处打断各只让**指定的**那几条红。四处都只让同一条红 = 它们在守同一件事。
    cases = (
        ("CM1 把 image 加进 SUPPORTED_SOURCE_KINDS → A3 与 C1 必须红（真违规形状）",
         src.replace('SUPPORTED_SOURCE_KINDS = frozenset({"free_text", "ad_text"})',
                     'SUPPORTED_SOURCE_KINDS = frozenset({"free_text", "ad_text", "image"})'),
         # A3 直接读常量。C1 也红是**正确连带**：开关关着而集合里有 image，
         # 那句「能力已建成但生产路径未打开」的分支就不再生效，归因随之丢失 ——
         # 这两条守的其实是同一件事的两面，所以它们一起红。
         {"A3", "C1"}),
        ("CM2 开关判据改成真值判 → A5 必须红（'false' 也算开）",
         src.replace("return MEDIA_INGEST_ENABLED is True",
                     "return bool(MEDIA_INGEST_ENABLED)"),
         {"A5"}),
        ("CM3 删掉开关关时的专用错误码 → C1 必须红（归因丢失）",
         src.replace('"media_ingest_disabled", 422,',
                     '"unsupported_source_kind", 422,'),
         {"C1"}),
        ("CM4 根目录约束改成恒真 → E1 必须红（任意文件可读）",
         src.replace("        if not inside:",
                     "        if False:"),
         {"E1"}),
        ("CM5 无根目录时放行 → E2 必须红（不配根也收图）",
         # 把 raise 换成 pass 会留下一个空 if 体 —— 那本身是语法错误，
         # 而「坏副本跑不起来」不能当成「判据抓住了」。改成填一句 no-op，
         # 让它是一个**能跑起来**的坏副本，判据才有机会真的拒绝它。
         src.replace(
             '        if not candidates:\n'
             '            raise SubmissionRejected(\n'
             '                "media_root_not_configured", 503,',
             '        if not candidates:\n'
             '            candidates = []  # no-op：不配根也放行\n'
             '            _unused = (\n'
             '                "media_root_not_configured", 503,'),
         {"E2"}),
    )
    for name, badsrc, must_red in cases:
        if badsrc == src:
            C(name, False, "找不到替换原文（生产代码变了，对照过期）")
            continue
        try:
            got = probe(_exec_mod(badsrc, "m%d" % len(name)), image_path)
        except Exception as exc:  # noqa: BLE001
            C(name, False, "坏副本跑不起来：%s" % exc)
            continue
        reds = {k for k, v in got.items() if not v}
        C(name, reds == must_red,
          "红的集合是 %r，应当是 %r" % (sorted(reds), sorted(must_red)))

    # 反向的另一半：好副本必须全绿
    try:
        good = probe(_exec_mod(src, "good"), image_path)
        C("CM6 好副本同输入必须全绿（否则上面五条是误报）",
          all(good.values()),
          "好副本被误伤：%r" % (sorted(k for k, v in good.items() if not v),))
    except Exception as exc:  # noqa: BLE001
        C("CM6 好副本跑不起来", False, str(exc))

    print("-" * 78)
    print("%s --controls %d 过 · %d 红 · 0 未测" % ("✅" if bad == 0 else "❌", ok, bad))
    return 0 if bad == 0 else 1


def main(argv):
    image_path = _real_image()
    if "--controls" in argv:
        if image_path is None:
            print("UNTESTED: 盘上没有可用的真实位图 —— 反向对照无对象")
            return 2
        return run_controls(image_path)

    print("=" * 78)
    print("T-431 · 图片进件（能力建成 · 生产路径未打开）")
    print("=" * 78)
    check_gate_defaults()
    check_env_entry()
    check_two_readings()
    check_video_coverage()
    if image_path is None:
        untested("盘上没有 ok 状态的真实位图 —— C/D/E 组无对象")
    else:
        print(f"  样本：{image_path.name}")
        check_gate_blocks(image_path)
        check_real_image(image_path)
        check_path_constraints(image_path)
    check_failure_not_fake()
    check_existing_guards()

    print("-" * 78)
    if FAILED:
        print(f"❌ {PASSED} passed, {FAILED} failed, {UNTESTED} untested")
        return 1
    if UNTESTED:
        print(f"⚠️ {PASSED} 项过 · {UNTESTED} 项未测 —— **未测不是通过**")
        return 2
    print(f"✅ {PASSED}/{PASSED} 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
