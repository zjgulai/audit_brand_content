#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_media_upload.py —— ADR-0021 主线：上传端点的安全边界

## 它守的是什么

后端能用多模态审图片/视频，但要的是**服务器可达的路径**。
网页拖一张图时文件只在浏览器内存里 —— 所以加了一个上传端点。
**上传是「写」，比读更需要边界**：写错一个位置就是漏洞。

## 四道边界（缺一条都能被打穿）

| # | 边界 | 打穿后果 |
|---|---|---|
| ① | 落盘只在 `REVIEW_MEDIA_ROOTS` 内 | 一个请求就能写到 `~/.ssh/` |
| ② | 文件名**不用**客户端给的 | `../../etc/x` 直穿目录 |
| ③ | 大小**两道**拦（声明 + 实际） | 声明 1KB 传 1GB 打满磁盘 |
| ④ | 类型按**内容**判（魔数），不信后缀 | `.png` 里装任意内容 |

## 为什么每条都要正反两面

只验「坏样本被拒」会让 `raise UploadRejected` 一个无条件抛出就全绿；
只验「好样本通过」则什么都拦不住。**两面成对**。

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


#: 1x1 PNG（真实魔数，用来验「好样本必须过」）
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db4"
    "0000000049454e44ae426082")

#: 最小 mp4 头
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 128


def _root():
    return tempfile.mkdtemp(prefix="upload-")


def _try(**kwargs):
    """跑一次，返回 (结果 | None, 异常 code | None)。"""
    from base import media_upload as MU
    try:
        return MU.save_upload(**kwargs), None
    except MU.UploadRejected as exc:
        return None, exc.code
    except Exception as exc:  # noqa: BLE001
        return None, "UNEXPECTED:%s" % (type(exc).__name__,)


# ─────────────────────────────────────────────── ① 落盘位置

def group_a():
    root = _root()
    try:
        out, err = _try(filename="a.png", stream=io.BytesIO(PNG), media_roots=[root])
        report(err is None and out is not None,
               "A1 ★ 好样本：PNG 上传成功（否则下面全是恒红）", repr(err))
        if out:
            p = Path(out["path"])
            r = Path(root).resolve()
            report(r in p.parents,
                   "A2 ★★★ 落盘路径在允许的根之内", str(p.relative_to(r)))
            report(p.is_file() and p.read_bytes() == PNG,
                   "A3 ★ 落盘内容与上传内容逐字节相同")

        # A4 ★★★ 未配置根 → 一律拒（不许默认写到某个「合理」位置）
        _, err = _try(filename="a.png", stream=io.BytesIO(PNG), media_roots=[])
        report(err == "media_root_not_configured",
               "A4 ★★★ 未配置 media_roots → 拒（不许默认写到某处）", repr(err))

        # A5 ★★ 多个根时只写第一个（不猜、不轮询）
        root2 = _root()
        try:
            out2, err2 = _try(filename="b.png", stream=io.BytesIO(PNG),
                              media_roots=[root, root2])
            report(err2 is None and out2 is not None
                   and Path(root).resolve() in Path(out2["path"]).parents,
                   "A5 ★★ 多个根时写在第一个根里（不猜）")
            report(not any(Path(root2).rglob("*")),
                   "A6 ★ 第二个根里一个文件都没有（没撒出去）")
        finally:
            _rm(root2)
    finally:
        _rm(root)


# ─────────────────────────────────────────────── ② 文件名

def group_b():
    root = _root()
    try:
        # B1 ★★★ 路径穿越的文件名：落盘必须仍在根内
        out, err = _try(filename="../../etc/passwd.png",
                        stream=io.BytesIO(PNG), media_roots=[root])
        report(err is None and out is not None,
               "B1 ★★★ 带 ../ 的文件名不报错（但也不许真穿出去）", repr(err))
        if out:
            p = Path(out["path"]).resolve()
            report(Path(root).resolve() in p.parents,
                   "B2 ★★★ 落盘仍在根内（路径穿越被挡住）", str(p))
            report(p.parent.name == "_uploads",
                   "B3 ★ 落在 _uploads 子目录（与业务素材分开）", p.parent.name)
            report(out["display_name"] == "passwd.png",
                   "B4 ★ 客户端名只留最后一段（供人读）", repr(out["display_name"]))

        # B5 ★★ 落盘名由服务端生成，不是客户端给的
        out2, _ = _try(filename="我的图.png", stream=io.BytesIO(PNG),
                       media_roots=[root])
        report(out2 and "我的图" not in out2["stored_name"],
               "B5 ★★ 落盘名由服务端生成（不用客户端名，避免编码/穿越问题）",
               repr(out2["stored_name"] if out2 else None))
        report(out2 and out2["display_name"].endswith(".png"),
               "B6 ★ 但显示名保留可读信息", repr(out2["display_name"] if out2 else None))

        # B7 ★★ 两个同名上传不许互相覆盖
        o1, _ = _try(filename="same.png", stream=io.BytesIO(PNG), media_roots=[root])
        o2, _ = _try(filename="same.png", stream=io.BytesIO(PNG), media_roots=[root])
        report(o1 and o2 and o1["path"] != o2["path"],
               "B7 ★★ 同名文件两次上传落到两个不同路径（不覆盖）")

        # B8 ★★ 控制字符被剥掉
        o3, _ = _try(filename="a\x00b\x07.png", stream=io.BytesIO(PNG),
                     media_roots=[root])
        report(o3 and "\x00" not in o3["display_name"],
               "B8 ★★ 显示名里没有控制字符", repr(o3["display_name"] if o3 else None))
    finally:
        _rm(root)


# ─────────────────────────────────────────────── ③ 大小

def group_c():
    from base import media_upload as MU
    root = _root()
    try:
        # C1 ★★★ 声明就超限 → 立刻拒，连流都不读
        class _NeverRead:
            def __init__(self):
                self.read_called = False

            def read(self, n=-1):
                self.read_called = True
                return b""

        probe = _NeverRead()
        _, err = _try(filename="big.png", stream=probe, media_roots=[root],
                      declared_size=MU.MAX_IMAGE_BYTES + 1)
        report(err == "upload_too_large",
               "C1 ★★★ 声明超限 → 拒", repr(err))
        report(probe.read_called is False,
               "C2 ★★★ 声明超限时不读流（省带宽，也不给别人打满内存的机会）")

        # C3 ★★★ 声明没问题但实际超限 → 也要拒（第二道拦）
        class _Flood:
            def __init__(self, total):
                self.left = total

            def read(self, n=-1):
                take = min(n if n > 0 else 1024, self.left, MU.CHUNK)
                if take <= 0:
                    return b""
                self.left -= take
                return b"\x00" * take

        # 用很小的上限跑，避免真写 20MB
        saved = MU.MAX_IMAGE_BYTES
        MU.MAX_IMAGE_BYTES = 4096
        try:
            _, err = _try(filename="flood.png",
                          stream=_Flood(64 * 1024), media_roots=[root])
            report(err == "upload_too_large",
                   "C3 ★★★ 实际字节超限 → 也拒"
                   "（声明 1KB 传 1GB 靠这道拦）", repr(err))
            # C4 ★★ 被拒后不留残件
            leftovers = [p for p in (Path(root) / "_uploads").glob("*")]
            report(not leftovers,
                   "C4 ★★ 超限被拒后不留半截文件（否则磁盘会被残件打满）",
                   repr([p.name for p in leftovers][:3]))
        finally:
            MU.MAX_IMAGE_BYTES = saved

        # C5 ★ 0 字节 → 拒（不是「成功但空」）
        _, err = _try(filename="empty.png", stream=io.BytesIO(b""),
                      media_roots=[root])
        report(err == "upload_empty", "C5 ★ 0 字节 → 拒", repr(err))
    finally:
        _rm(root)


# ─────────────────────────────────────────────── ④ 类型

def group_d():
    root = _root()
    try:
        # D1 ★★★ 后缀不在白名单 → 拒
        _, err = _try(filename="x.exe", stream=io.BytesIO(b"MZ\x90\x00" + b"\x00" * 64),
                      media_roots=[root])
        report(err == "upload_type_not_allowed",
               "D1 ★★★ 后缀不在白名单 → 拒（白名单，不是黑名单）", repr(err))

        # D2 ★★★ 后缀是 .png 但内容不是图片 → 拒
        _, err = _try(filename="fake.png", stream=io.BytesIO(b"MZ\x90\x00" + b"\x00" * 64),
                      media_roots=[root])
        report(err == "upload_content_unrecognized",
               "D2 ★★★ 后缀 .png 但魔数不匹配 → 拒"
               "（不信后缀，按内容判）", repr(err))

        # D3 ★★★ 后缀说图片、内容是视频 → 拒（两者不一致）
        _, err = _try(filename="sneaky.png", stream=io.BytesIO(MP4),
                      media_roots=[root])
        report(err == "upload_type_mismatch",
               "D3 ★★★ 后缀图片 / 内容视频 → 拒（不一致时不许猜）", repr(err))

        # D4 ★ 视频好样本必须过（否则 D 组全是恒红）
        out, err = _try(filename="v.mp4", stream=io.BytesIO(MP4), media_roots=[root])
        report(err is None and out and out["kind"] == "video",
               "D4 ★ 真视频 → 通过且 kind=video", repr(err))

        # D5 ★★ RIFF 但不是 WebP → 拒（只认确定的子类型）
        _, err = _try(filename="x.webp", stream=io.BytesIO(b"RIFF" + b"\x00"*4 + b"WAVE" + b"\x00"*64),
                      media_roots=[root])
        report(err == "upload_content_unrecognized",
               "D5 ★★ RIFF 但不是 WebP → 拒（不许「像就放」）", repr(err))
    finally:
        _rm(root)


# ─────────────────────────────────────────────── E 反向对照

def group_e():
    from base import media_upload as MU

    # E1 好样本必须绿
    report(MU.sniff_kind(PNG) == "image",
           "E1 ★ 好样本：PNG 魔数 → image（否则上面全是恒红）")
    report(MU.sniff_kind(MP4) == "video", "E2 ★ 好样本：mp4 魔数 → video")
    # E3 ★★ 反向对照：乱码不许被认成任何类型
    report(MU.sniff_kind(b"just some text here") is None,
           "E3 ★★ 反向对照：乱码 → None（不许默认成 image）")
    # E4 ★ 空 head → None
    report(MU.sniff_kind(b"") is None, "E4 ★ 空内容 → None")

    # E5 ★★ 后缀白名单：每一个都真的被认
    bad = [s for s in MU.ALLOWED_SUFFIXES if MU.ALLOWED_SUFFIXES[s] not in ("image", "video")]
    report(not bad, "E5 ★ 白名单里每项都映射到 image/video", repr(bad))
    # E6 ★★ 白名单里没有可执行/脚本后缀
    for risky in (".exe", ".sh", ".js", ".svg", ".phtml", ".php"):
        report(risky not in MU.ALLOWED_SUFFIXES,
               "E6 ★★ 白名单不含 %s（SVG 也算：它能内嵌脚本）" % risky)

    # E7 ★★ `Path.suffix` 的坑：x.png.exe 的 suffix 是 .exe
    try:
        MU.safe_suffix("x.png.exe")
        ok = False
    except MU.UploadRejected:
        ok = True
    report(ok, "E7 ★★ x.png.exe → 取到的后缀是 .exe，必须拒（不许被前面的 .png 骗）")


def _rm(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def main():
    print("=" * 74)
    print("media_upload · ADR-0021 主线（上传端点安全边界）")
    print("=" * 74)
    try:
        import base.media_upload  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        untested("导入 base/media_upload", str(exc))
        return 2
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    print("-" * 74)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
