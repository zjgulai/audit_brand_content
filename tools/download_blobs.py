#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""download_blobs.py —— 仓内二进制 / PII 内容检测（下载治理漏洞 4）

## 为什么不能按扩展名扫

旧实现只拿 `git ls-files` 的扩展名和一张 `MEDIA_EXTS` 比对，实测把同一份
PNG 字节改名成 `evil.txt` / `evil.dat` / `evil.bin` / `evil` 就全部放行。
扩展名是文件名的一部分，是**声明**；护栏必须看**内容**。所以本模块先用
magic bytes 嗅探，再决定这个文件能不能被跟踪。

红线（2026-10-17 起）：飞书内容允许下载，但**下载物不许进公开仓**。
判据不是「是不是二进制」，而是「这个二进制 / 数据文件能不能说清来源」：

| 类别 | 判据 | 结果 |
|---|---|---|
| 自有素材 | `asset_baseline.json` 里有登记，**且 sha256 与盘上内容一致** | 放行 |
| 未登记二进制 | magic bytes / NUL 判定为二进制 | 红 |
| 未登记 PII 文本 | CSV / JSON / TXT 里出现身份证、手机号、邮箱批量 | 红 |
| 源码 / 文档 / 配置 | 扩展名白名单 + 内容确实是文本 | 放行 |

## 为什么资产基线必须带 sha256

攻击轮指出：旧基线只有 `source` / `note` / `approved_by`，把任意文件塞进
`assets` 就能放行 —— 基线是一条**字符串**，与文件内容没有任何连接。
现在每条必须有 `sha256`，实际文件哈希对不上就红；缺哈希同样红（fail-closed）。
sha256 用 Python `open().read()` 计算，不用 `stat` / `shasum`：本机填充态下
`stat` 与 macOS `shasum` 会虚报 +4096B（ENV-001），只有读真内容才可信。
基线里的 `prefixes`（目录级放行）**不参与放行** —— 目录级放行等于没有哈希，
任何一个文件塞进该目录都会被一起放行；要么逐条登记 sha256，要么就是未登记二进制。

★ 明着承认：sha256 只能证明「盘上这份字节就是登记过的那份」，不能证明
「这份文件真的是自有素材」。任何人仍然可以算出任意文件的 sha256 并写进基线。
`source` / `approved_by` 是声明，不是可验证凭据。本模块把门槛从「写个路径」
提高到「写对内容哈希 + 填出来源与批准人」，但**没有**解决来源伪造。

## ★ 明着承认的残余漏洞（本轮不假装拦住）

1. **base64 / hex 编码载荷**：落盘后就是 ASCII 文本，magic 与 NUL 都看不见。
   做熵检测会误伤 minified JS / lock 文件，本轮不做。
2. **文本头 + 尾部二进制**：大文件只嗅探前 64KB；64KB 之后才出现的二进制
   对非 PII 文件不可见。PII 文件最多读前 16MB，超出部分落「未测」。
3. **PII 正则只认常见格式**：18 位大陆身份证（含校验位）、11 位大陆手机号、
   常规邮箱。15 位旧身份证、境外号码、脱敏/变形写法不认。
4. **Git LFS**：LFS 指针文件本身是文本，本模块不会去拉 LFS 内容（也不该拉）。
5. **历史扫描里的基线旧版本**：基线只批准当前版本的 sha256。历史里的同一路径
   会重新计算内容 sha256 并与基线比对：相符则放行；不同则落「未测」而不是假绿
   （旧版本可能是同一个自有素材的早期版本，直接判红会制造无法消除的历史噪音）。
6. **不可达的 dangling blob**：`git log --all --raw` 只覆盖 refs 可达的提交，
   `git fsck` 才能看到的悬空对象不在范围内。
7. **PII 扫描按扩展名豁免源码 / 文档 / 配置**（`.py` / `.md` / `.yaml` / `.xml` /
   `.html` 等）：这是为了满足「不能误伤」，代价是伪装成这些扩展名的数据导出
   不会被 PII 规则抓到；但二进制内容仍会被 magic 规则抓到。

## 接口

- `sniff_kind(data: bytes) -> str`
  返回 `png` / `jpeg` / `pdf` / `zip` / `mp4` / `text` / `binary` / `unknown`。
  GIF / WEBP / MP3 等同类二进制映射为 `binary`（返回值集合是定死的；
  具体格式可用 `detect_magic()` 取）。
- `scan_tracked_blobs(repo_root, tracked, baseline) -> {"reds": [...], "untested": [...]}`
  `reds` / `untested` 都是**字符串**（与兄弟模块 download_registry.py 一致）。
- `scan_history_blobs(repo_root, baseline, already_red_paths=None, timeout=60)`
  单独跑历史提交扫描；`scan_tracked_blobs` 默认会带上它。

未测绝不等于通过：读不出、超时、超上限一律进 `untested`，调用方应把
`untested` 非空当成退出码 2，而不是当成绿。

`--scan` 的退出码：0 无红无未测 / 1 有红 / 2 只有未测（与项目其他 verifier 同口径）。
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Dict, List, Optional, Sequence, Set, Tuple

__all__ = [
    "sniff_kind",
    "detect_magic",
    "scan_tracked_blobs",
    "scan_history_blobs",
]

# 大文件只读头部：magic bytes 与 UTF-16 判别都在头部完成，读全文件只是浪费。
# 64KB 足够覆盖常见文件头，也给「文本头 + 尾部二进制」留下明着承认的盲区。
HEAD_BYTES = 64 * 1024

# PII 文本最多读 16MB：导出表可能很大，但再大就落「未测」，不许静默只扫一半。
PII_SCAN_BYTES = 16 * 1024 * 1024

# 历史扫描的整体预算。git log + cat-file 在本仓约 2s；60s 是给大仓的
# 上限，超时落「未测」而不是假装扫完。
HISTORY_TIMEOUT = 60.0
HISTORY_MAX_OBJECTS = 20000
HISTORY_DISCARD_CHUNK = 1 << 20

_HEX_OID = re.compile(r"^[0-9a-f]{40,64}$")
# `git log --raw -z` 的记录形如 `:100644 100644 <old> <new> M\0<path>\0`。
_RAW_RECORD = re.compile(
    br"^:\d{6} \d{6} ([0-9a-f]{40,64}) ([0-9a-f]{40,64}) ([A-Z][0-9]*)$")
_ZERO_OID = re.compile(r"^0+$")


# ================================================================ 内容嗅探

# 已知二进制魔数。命中即二进制；其中 png/jpeg/pdf/zip/mp4 另外给精确 kind。
_NAMED_MAGICS: Tuple[Tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\x89PNG", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"GIF8", "gif"),
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),
    (b"PK\x05\x06", "zip"),
    (b"PK\x07\x08", "zip"),
)

# 其余已知二进制格式统一返回 binary，但 detect_magic 会保留具体名字，
# 这样报告能写「magic=gif」而不是只有一句「二进制」。
_OTHER_MAGICS: Tuple[Tuple[bytes, str], ...] = (
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
    (b"\x00\x00\x01\x00", "ico"),
    (b"\x1f\x8b\x08", "gzip"),
    (b"7z\xbc\xaf\x27\x1c", "7z"),
    (b"Rar!\x1a\x07", "rar"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "ole"),
    (b"\x7fELF", "elf"),
    (b"SQLite format 3\x00", "sqlite"),
    (b"\x00asm\x01\x00\x00\x00", "wasm"),
    (b"\xca\xfe\xba\xbe", "class"),
    (b"8BPS", "psd"),
    (b"OggS", "ogg"),
    (b"fLaC", "flac"),
)


def detect_magic(data: bytes) -> Optional[str]:
    """返回具体格式名；认不出返回 None。比 sniff_kind 的返回值更细。"""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("detect_magic() 需要 bytes")
    if not data:
        return None
    data = bytes(data)
    for magic, name in _NAMED_MAGICS:
        if data.startswith(magic):
            return name

    # WEBP / WAV / AVI 共用 RIFF 容器，必须看 offset 8 的四个字节。
    if len(data) >= 12 and data[:4] == b"RIFF":
        tag = data[8:12]
        if tag == b"WEBP":
            return "webp"
        if tag == b"WAVE":
            return "wav"
        if tag == b"AVI ":
            return "avi"
        if tag == b"ACON":
            return "ani"

    # MP4 / MOV / HEIC 共用 ISO BMFF：offset 4 是 'ftyp'。
    # 先判它再判 NUL，否则以 00 00 00 xx 开头的 MP4 会被 NUL 规则误判。
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "mp4"

    # MP3：ID3v2 标签，或 MPEG 音频帧同步（0xFF 后三位为 1）。
    # ID3 只认合法头（版本 2/3/4 + syncsafe 长度）：文本文件以 "ID3," 开头
    # 也会命中三个字母，不能只比前缀。
    if data.startswith(b"ID3"):
        if (len(data) >= 10 and data[3] in (2, 3, 4) and data[4] != 0xFF
                and all(byte < 0x80 for byte in data[6:10])):
            return "mp3"
    # ★ UTF-16 的 BOM 是 FF FE / FE FF，第二字节同样满足 111xxxxx，
    #   不先排除的话，所有 UTF-16 文本都会被当成 MP3。
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return None
    if len(data) >= 4 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        version = (data[1] >> 3) & 0x03
        layer = (data[1] >> 1) & 0x03
        bitrate_index = (data[2] >> 4) & 0x0F
        sample_rate_index = (data[2] >> 2) & 0x03
        if (version != 0x01 and layer != 0x00
                and bitrate_index not in (0x00, 0x0F)
                and sample_rate_index != 0x03):
            return "mp3"

    # BMP 的 "BM" 只有两个字节，文本 "BMW..." 也会命中；用保留字段全零收紧。
    if len(data) >= 14 and data[:2] == b"BM" and data[6:10] == b"\x00\x00\x00\x00":
        return "bmp"

    for magic, name in _OTHER_MAGICS:
        if data.startswith(magic):
            return name
    return None


def _utf16_encoding(data: bytes) -> Optional[str]:
    """判 UTF-16/32（含 BOM 与无 BOM 的 ASCII 型 UTF-16），返回编码名。

    为什么必须单独判：UTF-16 文本天然充满 NUL 字节；先判 NUL 会把正常文本
    误判成二进制。反过来，二进制里的 NUL 也不能因为「可能像 UTF-16」就放行，
    所以无 BOM 的情况要求一半字节为 NUL、另一半以可打印字符为主。
    """
    if data.startswith(b"\xff\xfe\x00\x00") or data.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32"
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return "utf-16"

    sample = data[:4096]
    if len(sample) < 16:
        return None
    even = sample[0::2]
    odd = sample[1::2]
    if not even or not odd:
        return None
    ez = even.count(0) / float(len(even))
    oz = odd.count(0) / float(len(odd))
    if ez >= 0.55 and oz <= 0.10:
        return "utf-16-be"
    if oz >= 0.55 and ez <= 0.10:
        return "utf-16-le"
    return None


def _control_ratio_text(text: str) -> float:
    """解码后的控制字符比例。ESC 不算：终端日志里的 ANSI 颜色很常见。"""
    if not text:
        return 0.0
    bad = 0
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in "\t\n\r\f\b" and code != 0x1B:
            bad += 1
        elif code == 0x7F:
            bad += 1
    return bad / float(len(text))


def _control_ratio_bytes(data: bytes) -> float:
    if not data:
        return 0.0
    bad = 0
    for b in data:
        if b < 32 and b not in (9, 10, 11, 12, 13, 8, 27):
            bad += 1
        elif b == 127:
            bad += 1
    return bad / float(len(data))


def _looks_like_utf16(data: bytes) -> bool:
    enc = _utf16_encoding(data)
    if not enc:
        return False
    try:
        text = data.decode(enc)
    except UnicodeDecodeError:
        return False
    return _control_ratio_text(text) <= 0.02


def sniff_kind(data: bytes) -> str:
    """按内容返回 png/jpeg/pdf/zip/mp4/text/binary/unknown。

    判定顺序是刻意的：先认 magic（最硬的证据），再判 UTF-16（NUL 是它的正常
    组成部分），最后才用 NUL/控制字符判定「像不像二进制」。
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    if not isinstance(data, bytes):
        raise TypeError("sniff_kind() 需要 bytes")
    if not data:
        return "text"

    magic = detect_magic(data)
    if magic in ("png", "jpeg", "pdf", "zip", "mp4"):
        return magic
    if magic is not None:
        return "binary"

    if _looks_like_utf16(data):
        return "text"

    # 含 NUL 且不是 UTF-16：按二进制处理。不做「比例高才算」的宽松判定 ——
    # 一个 NUL 已经足以说明这不是普通 UTF-8/GBK 文本，fail-closed 更安全。
    if b"\x00" in data:
        return "binary"

    if _control_ratio_bytes(data) > 0.02:
        return "binary"

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("gb18030")
        except UnicodeDecodeError:
            # 只读了前 64KB 时，文件很可能在 UTF-8 多字节序列中间被截断。
            # 一两个 U+FFFD 是截断的证据，不是二进制证据；替换率高了才算
            # 「无法判定」。没有这一步，所有超过 64KB 的中文 Markdown 都会被
            # 误判成二进制（实测 10 个文件）。
            tolerant = data.decode("utf-8", "replace")
            bad = tolerant.count("�")
            if (bad <= max(1, len(tolerant) // 200)
                    and _control_ratio_text(tolerant) <= 0.02):
                return "text"
            return "unknown"

    if _control_ratio_text(text) > 0.02:
        return "binary"
    return "text"


# ================================================================ PII 判定

# 18 位大陆身份证：先正则框形状，再用 ISO 7064 校验位确认。
# 不加校验位的话，任意 18 位数字（订单号、时间戳拼接）都会误报。
_RE_ID18 = re.compile(
    r"(?<![0-9A-Za-z])([1-9]\d{5}(?:18|19|20)\d{2}"
    r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])(?![0-9A-Za-z])",
    re.ASCII,
)
_RE_PHONE = re.compile(r"(?<![0-9A-Za-z])(1[3-9]\d{9})(?![0-9A-Za-z])", re.ASCII)
_RE_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"(?![A-Za-z0-9-])"
)

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"


def _valid_id18(value: str) -> bool:
    if len(value) != 18:
        return False
    body, check = value[:17], value[17].upper()
    if not body.isdigit():
        return False
    try:
        datetime.date(int(value[6:10]), int(value[10:12]), int(value[12:14]))
    except ValueError:
        return False
    total = sum(int(ch) * weight for ch, weight in zip(body, _ID_WEIGHTS))
    return _ID_CHECK[total % 11] == check


# 源码 / 文档 / 配置一律不扫 PII。理由不是「它们不可能有 PII」，而是项目要求
# 这三类必须绿：测试夹具、文档示例、配置里的示例号码一旦触发批量阈值，
# 检查器就会开始误报，而误报比不报更糟（AGENTS.md §2.1.1）。
_SOURCE_EXTS = {
    ".py", ".pyi", ".pyx", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".vue", ".svelte", ".astro", ".go", ".rs", ".java", ".kt", ".kts",
    ".scala", ".groovy", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs",
    ".fs", ".vb", ".rb", ".php", ".swift", ".m", ".mm", ".lua", ".pl", ".pm",
    ".r", ".jl", ".ex", ".exs", ".erl", ".hrl", ".clj", ".cljs", ".cljc",
    ".edn", ".dart", ".sol", ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".psm1", ".bat", ".cmd", ".sql", ".graphql", ".gql", ".proto", ".thrift",
    ".css", ".scss", ".sass", ".less", ".styl", ".html", ".htm", ".xhtml",
    ".xml", ".svg", ".ipynb", ".rmd", ".qmd", ".map",
}
_DOC_EXTS = {".md", ".markdown", ".mdx", ".rst", ".adoc", ".asciidoc", ".org", ".tex"}
_CONFIG_EXTS = {
    ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".config",
    ".properties", ".lock", ".plist", ".desktop", ".service", ".editorconfig",
}
_EXEMPT_BASENAMES = {
    # 无扩展名的文档 / 构建入口
    "makefile", "gnumakefile", "dockerfile", "containerfile", "procfile",
    "gemfile", "rakefile", "pipfile", "license", "licence", "copying",
    "notice", "authors", "contributors", "changelog", "readme",
    "contributing", "codeowners", "version", "vagrantfile",
    # 点文件（os.path.splitext 对它们返回空扩展名）
    ".gitignore", ".gitattributes", ".gitmodules", ".dockerignore",
    ".npmignore", ".npmrc", ".yarnrc", ".prettierrc", ".eslintrc",
    ".babelrc", ".flake8", ".pylintrc", ".coveragerc", ".editorconfig",
    ".env", ".env.example", ".env.local",
    # 明确是配置而不是数据导出的 JSON
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "tsconfig.json", "jsconfig.json", "composer.json", "composer.lock",
    "manifest.json", "deno.json", "deno.lock", "babel.config.json",
    ".eslintrc.json", ".prettierrc.json", "renovate.json",
    "dependabot.json", "appsettings.json",
}
# 表格型 / 纯文本数据按「一行一条记录」看，阈值可以低；其它未知文本用高阈值，
# 避免把文档里顺手写的一个联系方式当成 PII 批量。`.txt` / `.log` 也算数据面：
# 它们没有源码/文档的豁免，正是「纯文本但含明显 PII」要覆盖的形态。
_TABULAR_EXTS = {
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".txt", ".log",
}


def _pii_eligible(rel: str) -> bool:
    """这个路径要不要扫 PII。二进制检测不受此函数影响。"""
    base = os.path.basename(rel).lower()
    ext = os.path.splitext(base)[1].lower()
    if base in _EXEMPT_BASENAMES:
        return False
    if ext in _SOURCE_EXTS or ext in _DOC_EXTS or ext in _CONFIG_EXTS:
        return False
    return True


def _pii_tabular(rel: str) -> bool:
    return os.path.splitext(rel)[1].lower() in _TABULAR_EXTS


def _decode_for_pii(data: bytes) -> str:
    enc = _utf16_encoding(data)
    if enc:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    # 解不出也要继续扫 ASCII 部分：PII 号码本身是 ASCII，替换坏字节不影响它们。
    return data.decode("utf-8", "replace")


def _mask_id(value: str) -> str:
    return value[:6] + "********" + value[-4:]


def _mask_phone(value: str) -> str:
    return value[:3] + "****" + value[-4:]


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return (local[:1] or "*") + "***@" + domain


def _pii_hits(text: str, tabular: bool) -> Optional[Dict[str, List[str]]]:
    ids = sorted({m.group(1).upper() for m in _RE_ID18.finditer(text)
                  if _valid_id18(m.group(1))})
    phones = sorted({m.group(1) for m in _RE_PHONE.finditer(text)})
    emails = sorted({m.group(1).lower().rstrip(".") for m in _RE_EMAIL.finditer(text)})

    if tabular:
        hit = bool(ids) or len(phones) >= 2 or len(emails) >= 3
    else:
        hit = len(ids) >= 2 or len(phones) >= 4 or len(emails) >= 8
    if not hit:
        return None
    return {"ids": ids, "phones": phones, "emails": emails}


def _pii_summary(hits: Dict[str, List[str]]) -> str:
    parts = []
    if hits["ids"]:
        parts.append("身份证 %d 个（如 %s）" % (len(hits["ids"]), _mask_id(hits["ids"][0])))
    if hits["phones"]:
        parts.append("手机号 %d 个（如 %s）" % (len(hits["phones"]), _mask_phone(hits["phones"][0])))
    if hits["emails"]:
        parts.append("邮箱 %d 个（如 %s）" % (len(hits["emails"]), _mask_email(hits["emails"][0])))
    return "、".join(parts)


# ================================================================ 路径 / 文件

def _norm_rel(value) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if not isinstance(value, str):
        return ""
    value = value.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value


def _bad_rel(rel: str) -> bool:
    if not rel or rel.startswith("/") or "\x00" in rel:
        return True
    return any(part == ".." for part in rel.split("/"))


def _within(child: str, parent: str) -> bool:
    child = os.path.normpath(child)
    parent = os.path.normpath(parent)
    if child == parent:
        return True
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_limited(path: str, limit: int) -> Tuple[bytes, bool]:
    with open(path, "rb") as handle:
        data = handle.read(limit)
        truncated = bool(handle.read(1))
    return data, truncated


# ================================================================ 基线

_PLACEHOLDERS = {
    "", "-", "—", "--", "n/a", "na", "none", "null", "todo", "tbd",
    "unknown", "system", "系统", "待定", "待补", "?",
}


def _meaningful(value) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() not in _PLACEHOLDERS


def _norm_sha(value) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text.startswith("sha256:"):
        text = text[7:].strip()
    if re.fullmatch(r"[0-9a-f]{64}", text):
        return text
    return None


def _normalise_assets(baseline: dict) -> Dict[str, dict]:
    raw = baseline.get("assets", {})
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        rel = _norm_rel(key)
        if rel:
            out[rel] = value
    return out


def _never_tracked_patterns(baseline: dict) -> List[str]:
    """收集 never_tracked 路径。

    为什么单独存在：旧实现把 never_tracked 的 path 加进「允许的二进制」集合，
    等于把「禁止入仓」的清单读成了「可以入仓」的清单，源代码路径也能被塞进去。
    本模块把它当**禁止清单**：命中就红，而且永远不会用去放行任何文件。
    """
    out: List[str] = []
    raw = baseline.get("never_tracked")
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            rel = _norm_rel(item)
            if rel:
                out.append(rel)
    for key in ("download_callers", "download_registry", "registry"):
        registry = baseline.get(key)
        if not isinstance(registry, dict):
            continue
        for entry in registry.get("entries", []) or []:
            if isinstance(entry, dict) and entry.get("never_tracked") is True:
                rel = _norm_rel(entry.get("path", ""))
                if rel:
                    out.append(rel)
    return out


def _matches_never(rel: str, patterns: Sequence[str]) -> Optional[str]:
    for pattern in patterns:
        if rel == pattern or rel.startswith(pattern.rstrip("/") + "/"):
            return pattern
    return None


def _baseline_problem(real: str, entry) -> Tuple[str, bool]:
    """返回 (问题描述, 是否属于未测)。空描述表示哈希与来源都通过。"""
    if not isinstance(entry, dict):
        return "基线条目不是对象 —— 无法核对哈希与来源", False

    sha = _norm_sha(entry.get("sha256"))
    problems = []
    if sha is None:
        problems.append("基线缺 sha256（或格式非法）—— 内容哈希无法核对")
    if not _meaningful(entry.get("source")):
        problems.append("基线 source 缺失或为占位词")
    if not _meaningful(entry.get("approved_by")):
        problems.append("基线 approved_by 缺失或为占位词")
    if problems:
        return "；".join(problems), False

    try:
        actual = _sha256_file(real)
    except OSError as exc:
        return "基线文件读不出，无法核对哈希（%s）—— 未测" % exc, True

    if actual != sha:
        return ("基线 sha256 不符（登记 %s…，实际 %s…）"
                % (sha[:12], actual[:12])), False
    return "", False


# ================================================================ 当前工作区

def scan_tracked_blobs(repo_root, tracked, baseline,
                       include_history: bool = True,
                       history_timeout: float = HISTORY_TIMEOUT) -> dict:
    """扫 git 已跟踪文件的内容。

    `tracked` 来自 `git ls-files`；`baseline` 是 asset_baseline.json 的 dict。
    默认顺带扫历史提交（漏洞 5）。历史扫描代价高 / 不是 git 仓库时，结果会
    落进 `untested`，调用方应报「未测」而不是「通过」。
    """
    reds: List[str] = []
    untested: List[str] = []
    red_paths: Set[str] = set()

    if baseline is None:
        baseline = {}
    if not isinstance(baseline, dict):
        untested.append("baseline 不是对象 —— 基线放行未测，不是通过")
        baseline = {}

    root = os.path.realpath(os.fspath(repo_root))
    if isinstance(root, bytes):
        root = root.decode("utf-8", "replace")
    if not os.path.isdir(root):
        return {"reds": [], "untested": ["仓库根不存在或不是目录：%s —— 未测" % repo_root]}

    assets = _normalise_assets(baseline)
    if "assets" in baseline and not isinstance(baseline.get("assets"), dict):
        untested.append("baseline.assets 不是对象 —— 所有基线放行未测，不是通过")
    never = _never_tracked_patterns(baseline)

    if isinstance(tracked, (str, bytes)) or not isinstance(tracked, (list, tuple, set)):
        untested.append("tracked 不是列表 —— 当前工作区未测，不是通过")
        tracked = []

    seen: Set[str] = set()
    for raw in tracked:
        rel = _norm_rel(raw)
        if not rel or rel in seen:
            continue
        seen.add(rel)

        if _bad_rel(rel):
            reds.append("%s: 路径越界或非法（绝对路径 / ..）" % rel)
            red_paths.add(rel)
            continue

        pattern = _matches_never(rel, never)
        if pattern:
            reds.append(
                "%s: 被登记为 never_tracked（%s）却仍被 git 跟踪 —— "
                "never_tracked 是禁止入仓清单，不是放行名单" % (rel, pattern)
            )
            red_paths.add(rel)
            continue

        full = os.path.join(root, rel)
        if not os.path.exists(full):
            untested.append("%s: 工作区文件缺失（可能是 sparse checkout）—— 未测，不是通过" % rel)
            continue

        real = os.path.realpath(full)
        if not _within(real, root):
            reds.append("%s: 符号链接指向仓外（%s）" % (rel, real))
            red_paths.add(rel)
            continue
        if os.path.isdir(real):
            untested.append("%s: 是目录或子模块，无法按文件扫描 —— 未测" % rel)
            continue
        if not os.path.isfile(real):
            untested.append("%s: 不是普通文件（FIFO / 设备等）—— 未测" % rel)
            continue

        if rel in assets:
            problem, is_untested = _baseline_problem(real, assets[rel])
            if problem:
                if is_untested:
                    untested.append("%s: %s" % (rel, problem))
                else:
                    reds.append("%s: %s" % (rel, problem))
                    red_paths.add(rel)
            continue

        eligible = _pii_eligible(rel)
        limit = PII_SCAN_BYTES if eligible else HEAD_BYTES
        try:
            data, truncated = _read_limited(real, limit)
        except OSError as exc:
            untested.append("%s: 读不出（%s）—— 未测，不是通过" % (rel, exc))
            continue

        kind = sniff_kind(data)
        magic = detect_magic(data)

        if kind != "text":
            if kind == "unknown":
                reds.append(
                    "%s: 内容无法判定为文本（kind=unknown）—— 按二进制处理，"
                    "且未在 asset_baseline.json 登记 sha256" % rel
                )
            else:
                detail = "kind=%s" % kind
                if magic and magic != kind:
                    detail += "，magic=%s" % magic
                reds.append(
                    "%s: 检出二进制内容（%s）—— 未在 asset_baseline.json 登记 sha256"
                    % (rel, detail)
                )
            red_paths.add(rel)
            continue

        if eligible:
            hits = _pii_hits(_decode_for_pii(data), _pii_tabular(rel))
            if hits:
                reds.append(
                    "%s: 检出 PII（%s）—— 公开仓不许放个人数据"
                    % (rel, _pii_summary(hits))
                )
                red_paths.add(rel)
                continue
            if truncated:
                untested.append(
                    "%s: 文件超过 %d 字节，PII 只扫了前 %d 字节 —— 尾部未测"
                    % (rel, PII_SCAN_BYTES, PII_SCAN_BYTES)
                )

    if include_history:
        history = scan_history_blobs(
            root, baseline, already_red_paths=red_paths, timeout=history_timeout
        )
        reds.extend(history["reds"])
        untested.extend(history["untested"])

    return {"reds": reds, "untested": untested}


# ================================================================ 历史提交

def _read_exact(stream, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            raise EOFError("cat-file 流提前结束")
        chunks.extend(chunk)
    return bytes(chunks)


def _discard_exact(stream, size: int) -> None:
    remaining = size
    while remaining > 0:
        chunk = stream.read(min(remaining, HISTORY_DISCARD_CHUNK))
        if not chunk:
            raise EOFError("cat-file 流提前结束")
        remaining -= len(chunk)


def _read_keep_and_hash(stream, size: int, keep_limit: int,
                        hash_all: bool) -> Tuple[bytes, Optional[str]]:
    """读一个 blob：只保留前 keep_limit 字节，但可以顺手把全文哈希完。

    为什么哈希要单独算：git 的 blob oid 是 SHA-1（`blob <len>\\0<content>`），
    基线里的 sha256 是内容 SHA-256，两者**永远不可能相等**。历史版本要与基线
    逐字节核对，必须在读流时把内容重新哈希，不能拿 blob oid 去比。
    """
    keep = min(size, keep_limit)
    data = _read_exact(stream, keep)
    hasher = hashlib.sha256()
    hasher.update(data)
    remaining = size - keep
    if hash_all:
        while remaining > 0:
            chunk = stream.read(min(remaining, HISTORY_DISCARD_CHUNK))
            if not chunk:
                raise EOFError("cat-file 流提前结束")
            hasher.update(chunk)
            remaining -= len(chunk)
        return data, hasher.hexdigest()
    _discard_exact(stream, remaining)
    return data, None


def scan_history_blobs(repo_root, baseline, already_red_paths=None,
                       timeout: float = HISTORY_TIMEOUT) -> dict:
    """扫 `git log --all --raw` 里出现过的每个历史 blob。

    为什么不是只扫 `git log --diff-filter=A --name-only` 的路径：
    改名后的二进制、以及「先提交二进制、再删掉」的泄漏，只看当前扩展名都会
    漏掉。这里直接拿历史 blob 的内容嗅探。

    为什么用 `--raw` 而不是 `rev-list --objects`：后者按对象 OID 去重，
    同一份内容出现在两个路径时只会列出一个路径（实测漏了 9 个基线路径），
    而 `--raw` 每个变更路径各有一条记录。`-m` 让 merge commit 也展开，
    避免合并时带进来的文件漏扫。
    """
    reds: List[str] = []
    untested: List[str] = []
    already_red_paths = set(already_red_paths or ())

    if baseline is None or not isinstance(baseline, dict):
        baseline = {}
    assets = _normalise_assets(baseline)
    never = _never_tracked_patterns(baseline)
    root = os.path.realpath(os.fspath(repo_root))
    if isinstance(root, bytes):
        root = root.decode("utf-8", "replace")
    if not os.path.isdir(root):
        return {"reds": [], "untested": ["history: 仓库根不存在 —— 未测"]}

    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--git-dir"], cwd=root,
            capture_output=True, timeout=min(timeout, 10.0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"reds": [], "untested": ["history: git 不可用（%s）—— 历史提交未测" % exc]}
    if probe.returncode != 0:
        return {"reds": [], "untested": ["history: 不是 git 仓库 —— 历史提交未测，不是通过"]}

    deadline = time.monotonic() + timeout
    try:
        listing = subprocess.run(
            ["git", "-c", "core.quotepath=false",
             "log", "--all", "-m", "--raw", "--no-abbrev", "--format=%H", "-z"],
            cwd=root, capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"reds": [], "untested": ["history: git log 超时（%.0fs）—— 历史提交未测" % timeout]}
    except OSError as exc:
        return {"reds": [], "untested": ["history: git log 起不来（%s）—— 历史提交未测" % exc]}
    if listing.returncode != 0:
        return {"reds": [], "untested": [
            "history: git log 失败（rc=%d）—— 历史提交未测，不是通过"
            % listing.returncode]}

    oid_paths: Dict[str, List[str]] = {}
    oid_order: List[str] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    bad_paths = 0
    over_limit = False
    pair_count = 0

    tokens = listing.stdout.split(b"\x00")
    index = 0
    while index < len(tokens):
        token = tokens[index].lstrip(b"\n")
        match = _RAW_RECORD.match(token)
        if not match or index + 1 >= len(tokens):
            index += 1
            continue
        old_oid = match.group(1).decode("ascii")
        new_oid = match.group(2).decode("ascii")
        path_raw = tokens[index + 1]
        index += 2

        # 删除记录的新 oid 是全零，被删掉的 blob 在 old_oid；其它记录取新 oid。
        oid = new_oid if not _ZERO_OID.match(new_oid) else old_oid
        if _ZERO_OID.match(oid) or not path_raw:
            continue
        path = path_raw.decode("utf-8", "replace")
        if not path or "�" in path or any(ord(ch) < 32 for ch in path):
            bad_paths += 1
            continue
        path = _norm_rel(path)
        if not path or _bad_rel(path):
            bad_paths += 1
            continue
        pair = (oid, path)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        pair_count += 1
        if pair_count > HISTORY_MAX_OBJECTS:
            over_limit = True
            break
        if oid not in oid_paths:
            oid_paths[oid] = []
            oid_order.append(oid)
        oid_paths[oid].append(path)

    if bad_paths:
        untested.append("history: %d 个历史路径含不可解析字符 —— 未测" % bad_paths)
    if over_limit:
        untested.append(
            "history: 对象数超过上限 %d，只扫描了前 %d 个 —— 未测"
            % (HISTORY_MAX_OBJECTS, HISTORY_MAX_OBJECTS)
        )
    if not oid_order:
        return {"reds": reds, "untested": untested}

    hist_red_seen: Set[str] = set()
    missing = 0
    stream_broken = False
    pii_truncated: Set[str] = set()
    baseline_unverified: Set[str] = set()
    baseline_other_versions: Set[str] = set()

    try:
        process = subprocess.Popen(
            ["git", "cat-file", "--batch"], cwd=root,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {"reds": reds, "untested": untested + [
            "history: git cat-file 起不来（%s）—— 历史提交未测" % exc]}

    try:
        for oid in oid_order:
            if time.monotonic() > deadline:
                untested.append(
                    "history: 扫描超时（%.0fs），只看了部分历史 —— 未测" % timeout)
                break

            paths = oid_paths[oid]
            baseline_sha_by_path: Dict[str, str] = {}
            for candidate in paths:
                entry = assets.get(candidate)
                if isinstance(entry, dict):
                    sha = _norm_sha(entry.get("sha256"))
                    if (sha and _meaningful(entry.get("source"))
                            and _meaningful(entry.get("approved_by"))):
                        baseline_sha_by_path[candidate] = sha
            want_full = any(_pii_eligible(path) for path in paths)
            try:
                process.stdin.write((oid + "\n").encode("ascii"))
                process.stdin.flush()
                header = process.stdout.readline()
                if not header:
                    stream_broken = True
                    break
                parts = header.split()
                if len(parts) >= 2 and parts[1] == b"missing":
                    missing += 1
                    continue
                if len(parts) < 3:
                    stream_broken = True
                    break
                obj_type = parts[1].decode("ascii", "replace")
                size = int(parts[2])
                keep_limit = PII_SCAN_BYTES if want_full else HEAD_BYTES
                data, blob_sha256 = _read_keep_and_hash(
                    process.stdout, size, keep_limit, bool(baseline_sha_by_path))
                process.stdout.read(1)
            except (EOFError, BrokenPipeError, OSError, ValueError):
                stream_broken = True
                break

            if obj_type != "blob":
                continue

            kind = sniff_kind(data)
            magic = detect_magic(data)
            pii_text = _decode_for_pii(data) if (want_full and kind == "text") else None
            truncated = want_full and size > PII_SCAN_BYTES

            for path in paths:
                if path in already_red_paths or path in hist_red_seen:
                    continue

                entry = assets.get(path)
                if entry is not None:
                    sha = _norm_sha(entry.get("sha256")) if isinstance(entry, dict) else None
                    provenance_ok = (isinstance(entry, dict)
                                     and _meaningful(entry.get("source"))
                                     and _meaningful(entry.get("approved_by")))
                    if sha is None or not provenance_ok:
                        baseline_unverified.add(path)
                    elif blob_sha256 is None:
                        # 有合法 sha 的路径会让 hash_all=True；这里只是防御。
                        baseline_unverified.add(path)
                    elif blob_sha256 != sha:
                        # 旧版本与当前基线不符：不判红（可能是同一素材的早期版本），
                        # 但也不能说它被基线批准过 —— 落「未测」。
                        baseline_other_versions.add(path)
                    continue

                if _matches_never(path, never):
                    reds.append(
                        "%s: 历史提交里有 never_tracked 的文件（blob=%s）—— "
                        "它已经进入公开仓历史" % (path, oid[:12])
                    )
                    hist_red_seen.add(path)
                    continue

                if kind != "text":
                    if kind == "unknown":
                        reds.append(
                            "%s: 历史提交内容无法判定（kind=unknown，blob=%s）—— "
                            "按二进制处理" % (path, oid[:12])
                        )
                    else:
                        detail = "kind=%s" % kind
                        if magic and magic != kind:
                            detail += "，magic=%s" % magic
                        reds.append(
                            "%s: 历史提交里有未登记二进制（%s，blob=%s）—— "
                            "删除工作区文件不够，内容仍在公开仓历史里"
                            % (path, detail, oid[:12])
                        )
                    hist_red_seen.add(path)
                    continue

                if pii_text is not None and _pii_eligible(path):
                    hits = _pii_hits(pii_text, _pii_tabular(path))
                    if hits:
                        reds.append(
                            "%s: 历史提交里有 PII 文本（%s，blob=%s）—— "
                            "内容仍在公开仓历史里"
                            % (path, _pii_summary(hits), oid[:12])
                        )
                        hist_red_seen.add(path)
                    elif truncated:
                        pii_truncated.add(path)
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=5.0)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    if stream_broken:
        untested.append("history: cat-file 输出流中断，剩余历史 blob 未测")
    if missing:
        untested.append("history: %d 个历史 blob 读不出 —— 未测" % missing)
    if pii_truncated:
        untested.append(
            "history: %d 个历史文本超过 %d 字节，PII 只扫了前 %d 字节 —— 未测"
            % (len(pii_truncated), PII_SCAN_BYTES, PII_SCAN_BYTES)
        )
    if baseline_unverified:
        untested.append(
            "history: %d 个基线历史路径缺 sha256 或来源/批准人 —— "
            "这些历史版本无法核对，未测" % len(baseline_unverified)
        )
    if baseline_other_versions:
        untested.append(
            "history: %d 个基线路径存在与当前基线 sha256 不同的历史版本 —— "
            "不判红（可能是同一素材的早期版本），但也不视为已批准（未测）"
            % len(baseline_other_versions)
        )

    return {"reds": reds, "untested": untested}


# ================================================================ 自证 fixture

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 24
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 24
_GIF = b"GIF89a" + b"\x01\x00\x01\x00" + b"\x00" * 16
_WEBP = b"RIFF" + b"\x24\x00\x00\x00" + b"WEBP" + b"VP8 " + b"\x00" * 16
_PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n" + b"\x00" * 8
_ZIP = b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 24
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 24
_MP3_ID3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 16
_MP3_FRAME = b"\xff\xfb\x90\x64" + b"\x00" * 24


def _write_file(root: str, rel: str, data: bytes) -> None:
    path = os.path.join(root, rel)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def _make_valid_id(body17: str) -> str:
    total = sum(int(ch) * weight for ch, weight in zip(body17, _ID_WEIGHTS))
    return body17 + _ID_CHECK[total % 11]


def _check_case(name: str, root: str, tracked, baseline,
                want_reds: Sequence[str] = (),
                want_untested: Sequence[str] = (),
                red_count: Optional[int] = None,
                clean: bool = False,
                include_history: bool = False) -> bool:
    result = scan_tracked_blobs(root, tracked, baseline,
                                include_history=include_history)
    problems: List[str] = []

    if set(result.keys()) != {"reds", "untested"}:
        problems.append("返回值键必须是 reds/untested，实际 %r" % sorted(result.keys()))
    reds = result.get("reds", [])
    untested = result.get("untested", [])

    if clean:
        if reds:
            problems.append("期望绿，实际红 %d 条：%s" % (len(reds), reds[:3]))
        if untested:
            problems.append("期望无未测，实际 %d 条：%s" % (len(untested), untested[:3]))
    else:
        for needle in want_reds:
            if not any(needle in item for item in reds):
                problems.append("红里找不到 %r；实际红：%s" % (needle, reds[:4]))
        for needle in want_untested:
            if not any(needle in item for item in untested):
                problems.append("未测里找不到 %r；实际未测：%s" % (needle, untested[:4]))
        if not want_untested and untested:
            problems.append("不期望未测，实际 %d 条：%s" % (len(untested), untested[:3]))
        if red_count is not None and len(reds) != red_count:
            problems.append("期望 %d 条红，实际 %d 条：%s" % (red_count, len(reds), reds[:5]))

    if problems:
        print("❌ %s" % name)
        for problem in problems:
            print("     - %s" % problem)
        return False
    print("✅ %s" % name)
    return True


def _check_sniff_matrix() -> Tuple[bool, int, List[str]]:
    cases = [
        ("png", _PNG, "png", "png"),
        ("jpeg", _JPEG, "jpeg", "jpeg"),
        ("gif→binary", _GIF, "binary", "gif"),
        ("webp→binary", _WEBP, "binary", "webp"),
        ("pdf", _PDF, "pdf", "pdf"),
        ("zip", _ZIP, "zip", "zip"),
        ("mp4", _MP4, "mp4", "mp4"),
        ("mp3-id3→binary", _MP3_ID3, "binary", "mp3"),
        ("mp3-frame→binary", _MP3_FRAME, "binary", "mp3"),
        ("plain-text", b"hello world\n", "text", None),
        ("empty-text", b"", "text", None),
        ("utf16-text", "手机号 13800138000".encode("utf-16"), "text", None),
        ("nul-binary", b"plain prefix\x00binary tail", "binary", None),
        ("unknown-bytes", b"\x80\x80\x80", "unknown", None),
        ("gzip-binary", b"\x1f\x8b\x08\x00" + b"\x00" * 8, "binary", "gzip"),
    ]
    problems: List[str] = []
    for name, data, want_kind, want_magic in cases:
        got_kind = sniff_kind(data)
        got_magic = detect_magic(data)
        if got_kind != want_kind:
            problems.append("%s: sniff_kind=%r，期望 %r" % (name, got_kind, want_kind))
        if got_magic != want_magic:
            problems.append("%s: detect_magic=%r，期望 %r" % (name, got_magic, want_magic))
    if problems:
        print("❌ sniff matrix")
        for problem in problems:
            print("     - %s" % problem)
        return False, len(cases), problems
    print("✅ sniff matrix（%d 项）" % len(cases))
    return True, len(cases), problems


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True)


def _init_git(root: str) -> bool:
    os.makedirs(root, exist_ok=True)
    result = _git(root, "init", "-q")
    if result.returncode != 0:
        print("     - git init 失败：%s" % (result.stderr.strip()[:200]))
        return False
    _git(root, "config", "user.email", "selftest@example.invalid")
    _git(root, "config", "user.name", "download-blobs selftest")
    return True


def _commit_all(root: str, message: str) -> bool:
    if _git(root, "add", "-A").returncode != 0:
        return False
    result = _git(root, "-c", "commit.gpgsign=false", "commit", "-qm", message)
    return result.returncode == 0


def _selftest() -> int:
    failures = 0
    total = 0

    sniff_ok, sniff_total, _ = _check_sniff_matrix()
    if not sniff_ok:
        failures += 1

    with tempfile.TemporaryDirectory(prefix="download_blobs_selftest_") as temp:
        base = temp

        # ---- 坏样本 1：PNG 字节改名成 .txt（旧实现实测放行的那一类）----
        total += 1
        root = os.path.join(base, "f01")
        _write_file(root, "evil.txt", _PNG)
        ok = _check_case(
            "bad-01 png-in-txt", root, ["evil.txt"], {"assets": {}},
            want_reds=("evil.txt", "png", "未在 asset_baseline.json 登记"),
            red_count=1,
        )

        # ---- 坏样本 2：JPEG 改名 + 无 magic 的 NUL 二进制 + unknown ----
        total += 1
        root = os.path.join(base, "f02")
        _write_file(root, "evil.dat", _JPEG)
        _write_file(root, "nul.dat", b"looks like text" + b"\x00" * 8)
        _write_file(root, "unknown.bin", b"\x80\x80\x80")
        ok2 = _check_case(
            "bad-02 jpeg-in-dat / nul-binary / unknown", root,
            ["evil.dat", "nul.dat", "unknown.bin"], {"assets": {}},
            want_reds=("evil.dat", "jpeg", "nul.dat", "binary",
                       "unknown.bin", "unknown"),
            red_count=3,
        )
        ok2 = ok2 and any("nul.dat" in r and "binary" in r
                          for r in scan_tracked_blobs(root, ["nul.dat"], {"assets": {}})["reds"])
        if not ok2:
            failures += 1

        # ---- 坏样本 3：ZIP 系（docx/xlsx/pptx 都是 zip）改名成 .bin ----
        total += 1
        root = os.path.join(base, "f03")
        _write_file(root, "evil.bin", _ZIP)
        ok3 = _check_case(
            "bad-03 zip-in-bin", root, ["evil.bin"], {"assets": {}},
            want_reds=("evil.bin", "zip"), red_count=1,
        )

        # ---- 坏样本 4：其余魔数 + 错误扩展名 ----
        total += 1
        root = os.path.join(base, "f04")
        files = {
            "evil": _MP4,
            "audio.bin": _MP3_ID3,
            "doc.md": _PDF,
            "img.txt": _GIF,
            "pic.dat": _WEBP,
        }
        for rel, data in files.items():
            _write_file(root, rel, data)
        ok4 = _check_case(
            "bad-04 magic-in-wrong-ext", root, sorted(files), {"assets": {}},
            want_reds=("evil", "mp4", "audio.bin", "mp3", "doc.md", "pdf",
                       "img.txt", "gif", "pic.dat", "webp"),
            red_count=5,
        )

        # ---- 坏样本 5：基线缺哈希 / 哈希不符 / 来源占位 / prefixes / never_tracked ----
        total += 1
        root = os.path.join(base, "f05")
        _write_file(root, "assets/no_sha.png", _PNG)
        _write_file(root, "assets/bad_hash.jpg", _JPEG)
        _write_file(root, "assets/no_provenance.png", _PNG + b"2")
        _write_file(root, "evil_prefix/prefix.png", _PNG + b"3")
        _write_file(root, "tools/sneaky.py", b"print('hello')\n")
        _write_file(root, "tools/sneaky2.py", b"print('hello again')\n")
        baseline5 = {
            "assets": {
                "assets/no_sha.png": {
                    "source": "项目自有素材", "note": "x", "approved_by": "委托方",
                },
                "assets/bad_hash.jpg": {
                    "source": "项目自有素材", "note": "x", "approved_by": "委托方",
                    "sha256": hashlib.sha256(b"different bytes").hexdigest(),
                },
                "assets/no_provenance.png": {
                    "source": "", "note": "x", "approved_by": "",
                    "sha256": hashlib.sha256(_PNG + b"2").hexdigest(),
                },
            },
            "prefixes": ["evil_prefix/"],
            "never_tracked": ["tools/sneaky.py"],
            # 真实调用方会把 download_callers.json 的 entries 一起传进来；
            # 这里证明嵌套形态也能识别，而不是只认顶层的 never_tracked。
            "download_callers": {"entries": [
                {"path": "tools/sneaky2.py", "never_tracked": True},
            ]},
        }
        tracked5 = ["assets/no_sha.png", "assets/bad_hash.jpg",
                    "assets/no_provenance.png", "evil_prefix/prefix.png",
                    "tools/sneaky.py", "tools/sneaky2.py"]
        ok5 = _check_case(
            "bad-05 baseline-integrity / never_tracked", root, tracked5, baseline5,
            want_reds=("no_sha.png", "缺 sha256", "bad_hash.jpg", "hash",
                       "no_provenance.png", "source",
                       "prefix.png", "未在 asset_baseline.json 登记",
                       "sneaky.py", "never_tracked", "sneaky2.py"),
            red_count=6,
        )

        # ---- 坏样本 6：CSV 里的身份证 + 手机号批量 ----
        total += 1
        root = os.path.join(base, "f06")
        csv_text = (
            "name,id,phone,email\n"
            "张三,11010519491231002X,13800138000,alice@example.com\n"
            "李四,310101199001011234,13900139000,bob@example.com\n"
        )
        _write_file(root, "data/people.csv", csv_text.encode("utf-8"))
        ok6 = _check_case(
            "bad-06 pii-csv", root, ["data/people.csv"], {"assets": {}},
            want_reds=("people.csv", "PII", "身份证"), red_count=1,
        )

        # ---- 坏样本 7：JSON / TXT 里的 PII ----
        total += 1
        root = os.path.join(base, "f07")
        json_text = json.dumps([
            {"email": "alice@example.com", "phone": "13800138000"},
            {"email": "bob@example.com", "phone": "13900139000"},
            {"email": "carol@example.com", "phone": "13700137000"},
        ], ensure_ascii=False)
        _write_file(root, "data/users.json", json_text.encode("utf-8"))
        id1 = _make_valid_id("11010519491231002")
        id2 = _make_valid_id("31010119900101123")
        _write_file(root, "data/ids.txt",
                    ("证件一：%s\n证件二：%s\n" % (id1, id2)).encode("utf-8"))
        ok7 = _check_case(
            "bad-07 pii-json / pii-txt", root,
            ["data/users.json", "data/ids.txt"], {"assets": {}},
            want_reds=("users.json", "PII", "邮箱", "ids.txt", "身份证"),
            red_count=2,
        )

        # ---- 坏样本 8：历史提交里出现过、当前工作区已删除的二进制 ----
        total += 1
        hist_root = os.path.join(base, "f08hist")
        clean_root = os.path.join(base, "f08clean")
        if not _init_git(hist_root) or not _init_git(clean_root):
            print("❌ bad-08 history-deleted-binary（git 不可用）")
            failures += 1
            ok8 = False
        else:
            _write_file(hist_root, "history/evil.txt", _PNG)
            _write_file(hist_root, "history/notes.md", b"# clean\n")
            committed = _commit_all(hist_root, "add evil")
            os.unlink(os.path.join(hist_root, "history/evil.txt"))
            committed = committed and _commit_all(hist_root, "remove evil")

            _write_file(clean_root, "docs/notes.md", b"# clean history\n")
            committed = committed and _commit_all(clean_root, "clean")

            if not committed:
                print("❌ bad-08 history-deleted-binary（git commit 失败）")
                failures += 1
                ok8 = False
            else:
                result8 = scan_tracked_blobs(
                    hist_root, [], {"assets": {}}, include_history=True)
                clean8 = scan_tracked_blobs(
                    clean_root, [], {"assets": {}}, include_history=True)
                problems8 = []
                if not any("evil.txt" in item and "历史" in item
                           for item in result8["reds"]):
                    problems8.append(
                        "历史里删除的 evil.txt 没红；实际红：%s" % result8["reds"][:4])
                if result8["untested"]:
                    problems8.append("历史扫描不应未测：%s" % result8["untested"][:3])
                if clean8["reds"]:
                    problems8.append(
                        "干净历史应绿，实际红：%s" % clean8["reds"][:3])
                if clean8["untested"]:
                    problems8.append(
                        "干净历史不应未测：%s" % clean8["untested"][:3])

                # 基线历史版本必须按内容 sha256 核对：git blob oid 是 SHA-1，
                # 拿它去比基线的 SHA-256 会永远不等（开发时真踩过）。
                hash_ok_root = os.path.join(base, "f08hash_ok")
                hash_bad_root = os.path.join(base, "f08hash_bad")
                if not _init_git(hash_ok_root) or not _init_git(hash_bad_root):
                    problems8.append("基线哈希历史用例的 git 初始化失败")
                else:
                    _write_file(hash_ok_root, "assets/logo.png", _PNG)
                    _write_file(hash_bad_root, "assets/logo.png", _PNG)
                    hash_committed = (_commit_all(hash_ok_root, "add logo")
                                      and _commit_all(hash_bad_root, "add logo"))
                    if not hash_committed:
                        problems8.append("基线哈希历史用例的 git commit 失败")
                    else:
                        good_baseline = {"assets": {"assets/logo.png": {
                            "source": "项目自有素材",
                            "note": "自证用固定样本",
                            "approved_by": "委托方 2026-10-17",
                            "sha256": hashlib.sha256(_PNG).hexdigest(),
                        }}}
                        wrong_baseline = {"assets": {"assets/logo.png": {
                            "source": "项目自有素材",
                            "note": "自证用固定样本",
                            "approved_by": "委托方 2026-10-17",
                            "sha256": hashlib.sha256(b"other bytes").hexdigest(),
                        }}}
                        hash_ok = scan_tracked_blobs(
                            hash_ok_root, [], good_baseline, include_history=True)
                        hash_bad = scan_tracked_blobs(
                            hash_bad_root, [], wrong_baseline, include_history=True)
                        if hash_ok["reds"] or hash_ok["untested"]:
                            problems8.append(
                                "基线哈希相符的历史版本应绿，实际红=%s 未测=%s"
                                % (hash_ok["reds"][:2], hash_ok["untested"][:2]))
                        if hash_bad["reds"]:
                            problems8.append(
                                "基线哈希不符的历史版本不应判红（应按未测）：%s"
                                % hash_bad["reds"][:2])
                        if not any("不同" in item for item in hash_bad["untested"]):
                            problems8.append(
                                "基线哈希不符的历史版本没有落未测：%s"
                                % hash_bad["untested"][:3])

                if problems8:
                    print("❌ bad-08 history-deleted-binary")
                    for problem in problems8:
                        print("     - %s" % problem)
                    failures += 1
                    ok8 = False
                else:
                    print("✅ bad-08 history-deleted-binary"
                          "（正向 + 干净历史反向对照 + 基线哈希核对）")
                    ok8 = True

        # ---- 好样本 9：源码里的示例 PII + UTF-16 文本 ----
        total += 1
        root = os.path.join(base, "f09")
        _write_file(root, "src/app.py",
                    b'PHONE = "13800138000"\n'
                    b'EMAILS = ["a@example.com", "b@example.com"]\n'
                    b'ID_EXAMPLE = "11010519491231002X"\n')
        _write_file(root, "src/utf16.txt",
                    "你好 13800138000".encode("utf-16"))
        _write_file(root, "src/tool",
                    b'#!/usr/bin/env python\nPHONE = "13800138000"\n')
        ok9 = _check_case(
            "good-09 source / utf16 / never_tracked-nonmatch", root,
            ["src/app.py", "src/utf16.txt", "src/tool"],
            {"assets": {}, "never_tracked": ["downloads/evil.bin"]},
            clean=True,
        )

        # ---- 好样本 10：Markdown 与普通 TXT 的单条联系方式 ----
        total += 1
        root = os.path.join(base, "f10")
        md = (
            "# 文档\n\n"
            "示例身份证 11010519491231002X，示例手机 13800138000。\n\n"
            + "\n".join("联系 user%d@example.com" % i for i in range(10)) + "\n"
        )
        _write_file(root, "docs/README.md", md.encode("utf-8"))
        _write_file(root, "docs/notes.txt",
                    "支援电话 13800138000，邮箱 help@example.com\n".encode("utf-8"))
        ok10 = _check_case(
            "good-10 markdown / single-contact-txt", root,
            ["docs/README.md", "docs/notes.txt"], {"assets": {}}, clean=True,
        )

        # ---- 好样本 11：配置 JSON / YAML 的示例联系方式 ----
        total += 1
        root = os.path.join(base, "f11")
        settings = {
            "support_phone": "13800138000",
            "support_email": "help@example.com",
            "features": ["a", "b"],
        }
        _write_file(root, "config/settings.json",
                    json.dumps(settings, ensure_ascii=False).encode("utf-8"))
        package = {"name": "x", "authors": ["a@example.com"] * 10}
        _write_file(root, "config/package.json",
                    json.dumps(package, ensure_ascii=False).encode("utf-8"))
        yaml_text = "contacts:\n" + "\n".join(
            "  - user%d@example.com" % i for i in range(10)) + "\n"
        _write_file(root, "config/app.yaml", yaml_text.encode("utf-8"))
        ok11 = _check_case(
            "good-11 config-json/yaml", root,
            ["config/settings.json", "config/package.json", "config/app.yaml"],
            {"assets": {}}, clean=True,
        )

        # ---- 好样本 12：基线登记正确 sha256 的自有素材 ----
        total += 1
        root = os.path.join(base, "f12")
        _write_file(root, "assets/logo.png", _PNG)
        baseline12 = {
            "assets": {
                "assets/logo.png": {
                    "source": "项目自有素材",
                    "note": "自证用固定样本",
                    "approved_by": "委托方 2026-10-17",
                    "sha256": hashlib.sha256(_PNG).hexdigest(),
                },
            },
        }
        ok12 = _check_case(
            "good-12 baseline-approved-with-sha", root,
            ["assets/logo.png"], baseline12, clean=True,
        )

        if not ok:
            failures += 1
        if not ok3:
            failures += 1
        if not ok4:
            failures += 1
        if not ok5:
            failures += 1
        if not ok6:
            failures += 1
        if not ok7:
            failures += 1
        if not ok9:
            failures += 1
        if not ok10:
            failures += 1
        if not ok11:
            failures += 1
        if not ok12:
            failures += 1

    if failures:
        print("\n✗ 自证失败：%d 项没过（fixture %d 个，另含 sniff matrix）"
              % (failures, total))
        return 1
    print("\n✅ %d 个 fixture 全过（8 坏 / 4 好）+ sniff matrix %d 项"
          % (total, sniff_total))
    return 0


# ================================================================ CLI

def _scan_repo(repo: str, no_history: bool, as_json: bool) -> int:
    root = os.path.realpath(repo)
    baseline_path = os.path.join(root, "tools", "asset_baseline.json")
    try:
        with open(baseline_path, encoding="utf-8") as handle:
            baseline = json.load(handle)
    except OSError as exc:
        print("✗ 读不到 %s（%s）—— 未测，不是通过" % (baseline_path, exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print("✗ %s 不是合法 JSON（%s）—— 未测，不是通过"
              % (baseline_path, exc), file=sys.stderr)
        return 2

    try:
        listing = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
            cwd=root, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print("✗ git ls-files 跑不了（%s）—— 未测，不是通过" % exc, file=sys.stderr)
        return 2
    if listing.returncode != 0:
        print("✗ git ls-files 退出码 %d —— 未测，不是通过"
              % listing.returncode, file=sys.stderr)
        return 2
    tracked = [item for item in listing.stdout.decode("utf-8", "replace").split("\x00")
               if item]

    result = scan_tracked_blobs(root, tracked, baseline,
                                include_history=not no_history)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("=" * 66)
        print("download_blobs · 仓内二进制 / PII 内容检测")
        print("=" * 66)
        print("  已跟踪文件 %d 个，红 %d 条，未测 %d 条"
              % (len(tracked), len(result["reds"]), len(result["untested"])))
        for item in result["reds"]:
            print("  ❌ %s" % item)
        for item in result["untested"]:
            print("  ⚠ %s" % item)

    if result["reds"]:
        return 1
    if result["untested"]:
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="仓内二进制 / PII 内容检测（下载治理漏洞 4）")
    parser.add_argument("--selftest", action="store_true", help="跑内嵌 fixture 与反向对照")
    parser.add_argument("--scan", action="store_true", help="扫当前仓库")
    parser.add_argument("--repo", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), help="仓库根（默认本文件上一级）")
    parser.add_argument("--no-history", action="store_true",
                        help="--scan 时跳过历史提交扫描")
    parser.add_argument("--json", action="store_true", help="--scan 时输出 JSON")
    args = parser.parse_args(argv)

    if args.scan:
        return _scan_repo(args.repo, args.no_history, args.json)
    return _selftest()


if __name__ == "__main__":
    sys.exit(main())
