#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/media_upload.py —— 浏览器上传 → 落盘 → 可进件的本地路径（ADP-0021 主线）

## 它为什么存在

后端已经能用多模态审图片/视频（`base/media_analyze.py`），但它要的是
**服务器上可达的文件路径**（`source.uri`）。而网页上拖一张图时，
文件只在浏览器内存里 —— 2026-10-28 实测：`grep UploadFile|multipart api/` = 0，
后端**没有任何上传端点**。于是界面只能往正文里塞一句
「【上传图片文件：xxx.png】请核查」，而那张图从来没被任何人看过。

## ★★ 三条安全边界（缺一条就变成漏洞）

### ① 落盘位置**只能**在 `REVIEW_MEDIA_ROOTS` 之内

`media_roots` 存在的理由就是「不许对机器上任意路径做提取」
（见 `submission_service._build_media_unit` 的注释）。
上传端点是**写**，比读更需要这道边界：否则一个请求就能把文件写到
`~/.ssh/` 或者覆盖应用代码。

所以本模块**只接受已配置的根**，且落盘后的路径仍要过
`media_roots` 的包含性检查 —— 两道，不是一道（路径拼接与真实路径可能不同）。

### ② 文件名**绝不用客户端给的名字**

客户端可以传 `../../etc/passwd` 或者 `a.png\x00.sh`。
落盘名一律由服务端生成（`uuid4 + 白名单后缀`），客户端给的名字
只作为**记录字段**（写进 unit 的 source，供人读）。
这不是洁癖：用客户端文件名拼路径，等于把写位置交给请求方。

### ③ 类型与大小都必须**按内容**判，不能只看声明的 MIME

浏览器给的 `Content-Type` 可以随便伪造。所以：
· 类型按**后缀白名单** + **魔数**（magic bytes）双重确认；
· 大小在**读流之前**按 `Content-Length` 拦一次、读的时候再按实际字节拦一次
  —— 只拦一次的话，声明 1KB 实际传 1GB 依然能打满磁盘。

## 不做什么

* 不删除文件。清理是另一件事（且有「审到一半被删」的风险），
  本模块只在文件名里带上时间戳，由运维按目录策略清。
* 不做病毒扫描 / 图片解码校验 —— 那是更深的一层，不在本轮。
* 不把文件内容读进内存再落盘（大视频会 OOM）：按块流式写。
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

#: 允许的上传后缀 → 声明的媒体种类。
#: ★ 白名单，不是黑名单：黑名单永远漏（`phtml` / `svgz` / `phar`…）。
ALLOWED_SUFFIXES: Dict[str, str] = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".mp4": "video",
    ".mov": "video",
    ".webm": "video",
    ".m4v": "video",
}

#: 魔数 → 媒体种类。★ 只认**确定的**几个；认不出就拒。
#: 宁可拒掉一个合法文件（用户换格式重传），也不放一个伪装进来。
_MAGIC: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image"),
    (b"\xff\xd8\xff", "image"),           # JPEG
    (b"GIF87a", "image"),
    (b"GIF89a", "image"),
    (b"RIFF", "image"),                   # WebP 也是 RIFF；下面再看子类型
    (b"\x00\x00\x00\x18ftyp", "video"),
    (b"\x00\x00\x00\x20ftyp", "video"),
    (b"\x00\x00\x00\x1cftyp", "video"),
    (b"\x1a\x45\xdf\xa3", "video"),       # matroska / webm
)

#: 单个文件上限。★ 视频比图片大得多，所以两个档。
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024

#: 读流时的块大小。
CHUNK = 1024 * 1024

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class UploadRejected(Exception):
    """上传被拒。`code` 供 API 层翻译成 HTTP 状态。"""

    def __init__(self, code: str, status: int, detail: str = ""):
        self.code = code
        self.status = int(status)
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def _roots(media_roots: Iterable[str]) -> Tuple[Path, ...]:
    out = []
    for root in media_roots or ():
        try:
            out.append(Path(root).expanduser().resolve())
        except OSError:
            continue
    return tuple(out)


def sniff_kind(head: bytes) -> Optional[str]:
    """按魔数判媒体种类。认不出 → None（调用方必须拒，不许猜）。"""
    if not head:
        return None
    for magic, kind in _MAGIC:
        if head.startswith(magic):
            # RIFF 可能是 WebP 也可能是别的；再看第 8-12 字节
            if magic == b"RIFF":
                return "image" if head[8:12] == b"WEBP" else None
            return kind
    return None


def safe_suffix(filename: str) -> str:
    """取后缀并规范化。**只返回白名单里的后缀**，否则抛。

    ★ 不用 `Path(filename).suffix` 直接拼：客户端可以传
      `x.png.exe`（suffix 是 `.exe`，会被白名单拒 —— 好），
      也可以传 `x.png/../../y`（`Path` 会把它当嵌套路径）。
      所以先只取**最后一段里的**后缀，再做白名单判定。
    """
    base = str(filename or "").replace("\\", "/").split("/")[-1]
    # 去掉控制字符（含 \x00），它们会让文件名在某些系统上截断
    base = "".join(ch for ch in base if ch.isprintable() and ch not in "\x00")
    suffix = os.path.splitext(base)[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadRejected(
            "upload_type_not_allowed", 415,
            "不支持的文件类型 %r（允许：%s）"
            % (suffix or "(无后缀)", "、".join(sorted(ALLOWED_SUFFIXES))))
    return suffix


def display_name(filename: str) -> str:
    """给**人看**的名字。已剥离路径与控制字符，长度上限 120。"""
    base = str(filename or "").replace("\\", "/").split("/")[-1]
    cleaned = _SAFE_NAME.sub("_", "".join(
        ch for ch in base if ch.isprintable() and ch not in "\x00"))
    return (cleaned or "upload")[:120]


def save_upload(
    *,
    filename: str,
    stream,
    media_roots: Iterable[str],
    declared_size: Optional[int] = None,
    prefix: str = "upload",
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """把上传流写到 `media_roots[0]` 下的 `_uploads/` 目录，返回落盘信息。

    返回：

        {
          "path": 绝对路径（字符串）,
          "kind": "image" | "video",
          "byte_size": int,
          "sha256": str,
          "display_name": 客户端给的名字（已清洗）,
          "stored_name": 服务端生成的名字,
        }

    ## 为什么写在 `_uploads/` 子目录

    根目录里可能已有业务素材。混在一起会让「哪些是用户刚传的」看不出来，
    清理时就容易误删业务文件。子目录名带下划线前缀，一眼可辨。
    """
    suffix = safe_suffix(filename)
    kind = ALLOWED_SUFFIXES[suffix]
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES

    roots = _roots(media_roots)
    if not roots:
        raise UploadRejected(
            "media_root_not_configured", 503,
            "未配置 REVIEW_MEDIA_ROOTS —— 不配根目录就不收上传，"
            "否则这个端点会把文件写到任意位置。")
    root = roots[0]

    # ★ 第一道拦：声明的长度就超限时，连读都不读。
    if isinstance(declared_size, int) and declared_size > limit:
        raise UploadRejected(
            "upload_too_large", 413,
            "文件 %d 字节，上限 %d" % (declared_size, limit))

    stem = uuid.uuid4().hex
    stamp = time.strftime("%Y%m%d", time.gmtime(now if now is not None else time.time()))
    stored_name = "%s-%s%s" % (prefix, stamp, "-") + stem[:16] + suffix
    target_dir = root / "_uploads"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UploadRejected(
            "upload_dir_unwritable", 500,
            "落盘目录不可写：%s" % (type(exc).__name__,)) from exc

    target = (target_dir / stored_name).resolve()

    # ★★ 第二道拦：真实路径必须仍在根之内。
    #   第一道（拼路径）在正常情况下已经够了，但符号链接、`..`、
    #   以及「根本身就是个软链」都能绕过去。这里用 resolve 之后的结果再判一次。
    if not (target == root or root in target.parents):
        raise UploadRejected(
            "upload_path_outside_roots", 403,
            "落盘路径不在允许的根目录内（拒绝写入）")

    digest = hashlib.sha256()
    written = 0
    head = b""
    try:
        with open(target, "wb") as fh:
            while True:
                chunk = stream.read(CHUNK) if hasattr(stream, "read") else None
                if not chunk:
                    break
                written += len(chunk)
                # ★ 第三道拦：实际字节超限 —— 声明 1KB 实际传 1GB 时靠这条。
                if written > limit:
                    raise UploadRejected(
                        "upload_too_large", 413,
                        "实际写入超过上限 %d 字节" % limit)
                if len(head) < 64:
                    head += chunk[: 64 - len(head)]
                digest.update(chunk)
                fh.write(chunk)
    except UploadRejected:
        _unlink_quiet(target)
        raise
    except Exception as exc:  # noqa: BLE001
        _unlink_quiet(target)
        raise UploadRejected(
            "upload_write_failed", 500,
            "%s: %s" % (type(exc).__name__, exc)) from exc

    if written == 0:
        _unlink_quiet(target)
        raise UploadRejected("upload_empty", 400, "上传内容为空（0 字节）")

    # ★★ 第四道：按**内容**判类型，与后缀白名单互相印证。
    #   只信后缀的话，一个 `.png` 里塞可执行内容照样能进；
    #   只信魔数的话，`.png` 里装 mp4 会被当成图片送去做 OCR。
    sniffed = sniff_kind(head[:64])
    if sniffed is None:
        _unlink_quiet(target)
        raise UploadRejected(
            "upload_content_unrecognized", 415,
            "内容不是可识别的图片/视频（魔数不匹配）—— 后缀是 %r，但不采信后缀" % suffix)
    if sniffed != kind:
        _unlink_quiet(target)
        raise UploadRejected(
            "upload_type_mismatch", 415,
            "后缀声明 %r，但内容看起来是 %r —— 两者不一致时拒绝" % (kind, sniffed))

    return {
        "path": str(target),
        "kind": kind,
        "byte_size": written,
        "sha256": digest.hexdigest(),
        "display_name": display_name(filename),
        "stored_name": stored_name,
    }


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
