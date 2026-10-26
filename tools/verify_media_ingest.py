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
    """临时改开关；用 try/finally 复原，避免把后面所有用例带歪。"""
    class _Flag:
        def __enter__(self):
            self.old = S.MEDIA_INGEST_ENABLED
            S.MEDIA_INGEST_ENABLED = value
            return self

        def __exit__(self, *exc):
            S.MEDIA_INGEST_ENABLED = self.old
            return False
    return _Flag()


def check_gate_defaults():
    """A 组：开关的语义。"""
    report(S.MEDIA_INGEST_ENABLED is False,
           "A1 开关默认关（MEDIA_INGEST_ENABLED is False）",
           repr(S.MEDIA_INGEST_ENABLED))
    report(S.ingest_media_enabled() is False,
           "A2 未打开时 ingest_media_enabled() 为 False（判据读一处）")
    report("image" not in S.SUPPORTED_SOURCE_KINDS,
           "A3 ★ SUPPORTED_SOURCE_KINDS 不含 image（ADR-0018 §6.2 的静态那一半）",
           repr(sorted(S.SUPPORTED_SOURCE_KINDS)))
    report(S.MEDIA_SOURCE_KINDS == frozenset({"image"}),
           "A4 媒体载体集合今天只有 image（视频要 T-435 抽帧，不提前收）",
           repr(sorted(S.MEDIA_SOURCE_KINDS)))
    # ★ 反例：字符串真值不算打开。用真值判的写法会让 "false"/"0"/1 都算开。
    with _with_flag("false"):
        report(S.ingest_media_enabled() is False,
               "A5 ★ 字符串 'false' 不许算打开（用 is True 判，不用真值判）")
    with _with_flag(1):
        report(S.ingest_media_enabled() is False,
               "A6 ★ 整数 1 不许算打开（同上）")
    with _with_flag(True):
        report(S.ingest_media_enabled() is True,
               "A7 显式 True → 算打开（否则开关是砖头，永远开不了）")


def check_two_readings():
    """B 组：两个读数不许混用。"""
    with _with_flag(False):
        now = S.supported_source_kinds_now()
        report("image" not in now,
               "B1 关时不接受 image", repr(sorted(now)))
        report(now == S.SUPPORTED_SOURCE_KINDS,
               "B2 关时「此刻」与「声明」相等（关闭状态两者不该分叉）")
    with _with_flag(True):
        now = S.supported_source_kinds_now()
        report(now == S.SUPPORTED_SOURCE_KINDS | S.MEDIA_SOURCE_KINDS,
               "B3 ★ 开时「此刻」= 声明 ∪ 媒体载体", repr(sorted(now)))
        report("image" in now and "image" not in S.SUPPORTED_SOURCE_KINDS,
               "B4 ★ 打开后声明常量**仍未变**（能力与生产路径是两件事）",
               repr(sorted(S.SUPPORTED_SOURCE_KINDS)))


def check_gate_blocks(image_path):
    """C 组：开关关时挡在哪一道门 —— 必须点名是媒体那道，不是别的。"""
    ing = S.SubmissionIngestor(media_roots=[str(image_path.parent)])
    with _with_flag(False):
        code = _expect_reject(ing.prepare, _submission(image_path),
                              principal=PRINCIPAL)
    report(code == "media_ingest_disabled",
           "C1 ★ 开关关 → media_ingest_disabled（不是 unsupported_source_kind）",
           repr(code))
    # ★ 反向：别的载体被挡时**不许**借用媒体那个码，否则两者分不开
    with _with_flag(False):
        code2 = _expect_reject(
            ing.prepare,
            _submission(image_path, source={"kind": "video", "uri": "x"}),
            principal=PRINCIPAL)
    report(code2 != "media_ingest_disabled",
           "C2 ★ video 被挡不许用媒体的码（它连能力都还没有）", repr(code2))
    # 媒体门开着时，文本链路不许受影响
    with _with_flag(True):
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
    with _with_flag(True):
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
    with _with_flag(True):
        got = _expect_reject(ing.prepare, _submission(image_path),
                             principal=PRINCIPAL)
    report(got != "media_ingest_disabled" and got != "image_ingest_failed",
           "D7 ★ 开关开时 prepare 不再被媒体门挡（后续失败与进件无关）",
           repr(got))


def check_path_constraints(image_path):
    """E 组：路径约束 —— 不能让这个端点变成任意文件的读取器。"""
    root = image_path.parent
    ing = S.SubmissionIngestor(media_roots=[str(root)])
    with _with_flag(True):
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
        report(code4 == "bad_image_uri",
               "E4 source.uri 为空 → 422", repr(code4))

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
        with _with_flag(True):
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
    check_two_readings()
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
