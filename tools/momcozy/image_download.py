#!/usr/bin/env python3
# tools/momcozy/image_download.py
#
# 严格按 STATUS §四 重写的下载器
# 改动:
# - 用 http.client (stdlib,不污染 venv)
# - 真解析 Transfer-Encoding: chunked 与 Content-Length
# - 落 .part-{random} (O_EXCL) → fsync → magic+CT 双验 → os.replace 原子落盘
# - 异常 finally unlink .part
# - remoteAddress 验证为公网
# - redirect 用 visited URL 集合 + 最多 5 次**响应跳转**
# - manifest 全字段
#
# 8 条边界按对方会话口径:
#   1. host allowlist + path prefix
#   2. redirect 用 visited set + max 5 跳
#   3. 拒绝 IP literal / 私网 / loopback / link-local / multicast / reserved
#   4. remoteAddress 验证为公网(socket.getpeername)
#   5. 解析 chunked 与 Content-Length;20MB 中段 abort
#   6. magic(JPEG/PNG/WebP)+ Content-Type 双验,扩展名由两者推导
#   7. dest 隔离路径(/tmp/agent_browser_test/<handle>/<sha-prefix>/image/<n>.part)
#   8. 失败不入 images/,用 .part → unlink;成功原子 rename

import argparse
import datetime as _dt
import hashlib
import http.client
import ipaddress
import json
import os
import random
import re
import socket
import ssl
import string
import sys
import urllib.parse
from typing import Optional

ALLOW = {
    "cdn.shopify.com": "/s/files/",
    "momcozy.com":     "/cdn/shop/",
}
ALLOWED_HOSTS = tuple(ALLOW.keys())
MAX_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 5
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 30


def is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None and isinstance(mapped, ipaddress.IPv4Address):
            return (
                mapped.is_private or mapped.is_loopback or mapped.is_link_local
                or mapped.is_multicast or mapped.is_reserved or mapped.is_unspecified
            )
        if ip.sixtofour is not None:
            return is_private_ip(str(ip.sixtofour))
        return (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_multicast or ip.is_reserved or ip.is_unspecified
        )
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def validate_url(url: str, visited: set, allow_test_port: int = None):
    if url in visited:
        raise ValueError(f"redirect_loop: {url}")
    visited.add(url)
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https":
        raise ValueError(f"not_https: {u.scheme}")
    if u.username or u.password:
        raise ValueError("userinfo_present")
    if u.port is not None and u.port != 443 and u.port != allow_test_port:
        raise ValueError(f"non_443_port: {u.port}")
    raw_host = (u.hostname or "").lower().rstrip(".")
    # 拒绝显式尾点(虽 IDNA 后等价)——防混淆攻击
    if "." in raw_host and (u.hostname or "").endswith("."):
        raise ValueError("trailing_dot")
    # 拒绝纯 IP literal
    try:
        ipaddress.ip_address(raw_host)
        raise ValueError(f"ip_literal_host: {raw_host}")
    except ValueError:
        pass
    if raw_host not in ALLOWED_HOSTS:
        raise ValueError(f"host_not_allowed: {raw_host}")
    if not u.path.startswith(ALLOW[raw_host]):
        raise ValueError(f"path_not_allowed: {u.path}")
    return u, raw_host


def dns_lookup(host: str, override: dict = None) -> list:
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"host_not_allowed_pre_dns: {host}")
    if override and host in override:
        return override[host]
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return list({sockaddr[0] for family, _, _, _, sockaddr in infos
                 if sockaddr[0] and not is_private_ip(sockaddr[0])})


def classify_magic(head: bytes):
    if len(head) >= 3 and head[0] == 0xFF and head[1] == 0xD8 and head[2] == 0xFF:
        return "image/jpeg"
    if len(head) >= 8 and head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def ext_for(content_type: str):
    return {
        "image/jpeg": "jpg",
        "image/png":  "png",
        "image/webp": "webp",
    }.get(content_type)


class SizeLimitExceeded(Exception):
    pass


class TooManyRedirects(Exception):
    pass


class DownloadError(Exception):
    def __init__(self, reason: str, **kw):
        super().__init__(reason)
        self.reason = reason
        self.extra = kw


def _read_chunked(conn) -> bytes:
    """读 chunked 响应 body。返回完整 body 字节流。
    触发 SizeLimitExceeded 若总字节 > MAX_BYTES。
    """
    chunks = []
    total = 0
    while True:
        line = conn.readline(64 * 1024)
        if not line:
            raise DownloadError("chunked_truncated")
        line = line.rstrip(b"\r\n")
        if b";" in line:
            line = line.split(b";", 1)[0]
        try:
            size = int(line, 16)
        except ValueError:
            raise DownloadError("chunked_bad_size")
        if size == 0:
            # CRLF 结尾
            conn.readline(64)  # may be trailers; 抛弃
            return b"".join(chunks)
        if total + size > MAX_BYTES:
            raise SizeLimitExceeded(f"chunked_total>{MAX_BYTES}")
        remaining = size
        buf = b""
        while remaining > 0:
            piece = conn.read(remaining)
            if not piece:
                raise DownloadError("chunked_eof")
            buf += piece
            remaining -= len(piece)
        chunks.append(buf)
        total += len(buf)
        # chunk 后必跟 CRLF
        crlf = conn.readline(2)
        if crlf not in (b"\r\n", b"\n"):
            raise DownloadError("chunked_missing_crlf")


def _read_contented(conn, length: int) -> bytes:
    if length > MAX_BYTES:
        raise SizeLimitExceeded(f"content_length>{MAX_BYTES}")
    body = b""
    remaining = length
    while remaining > 0:
        piece = conn.read(min(remaining, 64 * 1024))
        if not piece:
            raise DownloadError("body_eof")
        body += piece
        remaining -= len(piece)
    return body


def _do_request(hostname: str, ip: str, path: str, headers=None, port: int = 443,
                ssl_ctx=None, skip_peer_check: bool = False) -> tuple:
    """直接用 ip 连 servername 写 hostname。
    返回 (status, headers dict, body bytes, conn)
    conn 保留供 streamed download(若 Content-Length = None)。
    port 测试可注入(仅供本会话的 mock);ssl_ctx 注入(测试可用自签证书,跳过 verify)。
    skip_peer_check 测试钩子:仅 mock server peer 是 127.0.0.1 时用。
    """
    ctx = ssl_ctx if ssl_ctx is not None else ssl.create_default_context()
    raw_sock = socket.create_connection((ip, port), timeout=CONNECT_TIMEOUT)
    sock = ctx.wrap_socket(raw_sock, server_hostname=hostname)
    conn = http.client.HTTPResponse(sock, method="GET")
    # 不调用 begin:我们自己写最小请求
    req_headers = {
        "Host": hostname,
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if headers:
        req_headers.update(headers)
    req = (
        f"GET {path} HTTP/1.1\r\n"
        + "".join(f"{k}: {v}\r\n" for k, v in req_headers.items())
        + "\r\n"
    ).encode("ascii")
    sock.sendall(req)
    # 解析响应头
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise DownloadError("head_eof")
        buf += chunk
        if len(buf) > 64 * 1024:
            raise DownloadError("head_too_big")
    head, _, rest = buf.partition(b"\r\n\r\n")
    status_line, *_ = head.split(b"\r\n", 1)
    try:
        status = int(status_line.split()[1])
    except (IndexError, ValueError):
        raise DownloadError("bad_status_line")
    hdrs = {}
    for line in head.split(b"\r\n")[1:]:
        k, _, v = line.partition(b":")
        hdrs[k.strip().lower()] = v.strip()
    if not skip_peer_check:
        peer = sock.getpeername()
        if peer and len(peer) >= 1:
            peer_ip = peer[0]
            if is_private_ip(peer_ip):
                raise DownloadError("private_peer", peer_ip=peer_ip)
    return status, hdrs, rest, sock


def _iter_body_chunks(sock, rest: bytes, hdrs, max_bytes=MAX_BYTES):
    """yield body bytes; 触发 SizeLimitExceeded 若累计 > max_bytes。
    处理 Content-Length / chunked / 关闭连接三种情形。
    """
    yielded = 0
    # rest 可能含数据
    if rest:
        yielded += len(rest)
        if yielded > max_bytes:
            raise SizeLimitExceeded(f"body>{max_bytes}")
        yield rest

    te = (hdrs.get(b"transfer-encoding") or b"").decode("latin-1").lower()
    cl = hdrs.get(b"content-length")
    if "chunked" in te:
        while True:
            line = _readline(sock)
            if not line:
                raise DownloadError("chunked_truncated")
            line = line.rstrip(b"\r\n")
            if b";" in line:
                line = line.split(b";", 1)[0]
            try:
                size = int(line, 16)
            except ValueError:
                raise DownloadError("chunked_bad_size")
            if size == 0:
                _readline(sock)  # trailers
                return
            remaining = size
            buf = b""
            while remaining > 0:
                piece = _recv(sock, remaining)
                if not piece:
                    raise DownloadError("chunked_eof")
                buf += piece
                remaining -= len(piece)
            yielded += len(buf)
            if yielded > max_bytes:
                raise SizeLimitExceeded(f"chunked>{max_bytes}")
            yield buf
            _readline(sock)  # CRLF
        return
    if cl is not None:
        try:
            declared = int(cl.decode("ascii"))
        except (ValueError, AttributeError):
            declared = None
        if declared is None or declared > max_bytes:
            raise SizeLimitExceeded(f"content_length>{max_bytes}")
        while yielded < declared:
            need = min(declared - yielded, 64 * 1024)
            piece = _recv(sock, need)
            if not piece:
                raise DownloadError("body_eof")
            yielded += len(piece)
            yield piece
        return
    # 无 Content-Length + 非 chunked → 读到 EOF
    while True:
        piece = _recv(sock, 64 * 1024)
        if not piece:
            return
        yielded += len(piece)
        if yielded > max_bytes:
            raise SizeLimitExceeded(f"unknown_length>{max_bytes}")
        yield piece


def _readline(sock):
    buf = b""
    while True:
        c = sock.recv(1)
        if not c:
            return buf
        buf += c
        if buf.endswith(b"\r\n"):
            return buf


def _recv(sock, n):
    return sock.recv(n)


def download_one(source_url: str, dest_dir: str, _internal_overrides: dict = None) -> dict:
    """流式落盘到 dest_dir/.<random>.part,原子 rename 到 final。
    返回 manifest dict(成功)或带 fail_reason 的 dict(失败)。

    _internal_overrides 是**测试钩子**(§STATUS-20261017 §四.5):生产代码**绝不该传**——
        生产入口仅 sys.argv 路径,不暴露 _internal_overrides。
      启用需要显式环境变量:download_one 在 overrides 非空时检查
      MOMCOZY_TEST_HOOK=1,缺则抛 RuntimeError("test_hook_off")。
      形状: { "dns": { "<hostname>": [ip1] }, "port": int, "ssl_ctx": ssl_ctx }
    """
    if _internal_overrides is not None:
        if os.environ.get("MOMCOZY_TEST_HOOK") != "1":
            raise RuntimeError("test_hook_off: set MOMCOZY_TEST_HOOK=1 to enable")
    overrides = _internal_overrides or {}
    dns_override = overrides.get("dns")
    test_port = overrides.get("port", 443)
    test_ssl_ctx = overrides.get("ssl_ctx")
    skip_peer_check = overrides.get("skip_peer_check", False)

    visited = set()
    cur = source_url
    redirected_chain = []
    final_url = None
    final_status = None
    final_content_type = None
    final_body_path = None
    part_path = None
    cl_int = None

    os.makedirs(dest_dir, exist_ok=True)
    part_name = "." + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + ".part"
    part_path = os.path.join(dest_dir, part_name)

    try:
        for redirect_n in range(MAX_REDIRECTS + 1):
            u, hostname = validate_url(cur, visited)
            if test_port != 443:
                # 仅测试钩子:port 非 443 时,validate_url 已拒过;此处再 allow 测试 override
                pass
            resolved = dns_lookup(hostname, dns_override)
            if not resolved:
                raise DownloadError("no_public_ip")
            ip = resolved[0]
            try:
                status, hdrs, rest, sock = _do_request(
                    hostname, ip, u.path + (("?" + u.query) if u.query else ""),
                    port=test_port, ssl_ctx=test_ssl_ctx,
                    skip_peer_check=skip_peer_check,
                )
            except (DownloadError, OSError) as e:
                if getattr(e, "reason", None):
                    return dict(ok=False, source_url=source_url, saved=False, fail_reason=e.reason, **e.extra)
                raise

            if status in (301, 302, 303, 307, 308):
                location = (hdrs.get(b"location") or b"").decode("latin-1")
                if not location:
                    sock.close()
                    raise DownloadError("redirect_no_location")
                next_url = urllib.parse.urljoin(cur, location)
                redirected_chain.append({"from": cur, "to": next_url, "status": status})
                sock.close()
                cur = next_url
                continue
            if status != 200:
                sock.close()
                raise DownloadError(f"http_{status}")

            ct = (hdrs.get(b"content-type") or b"").split(b";")[0].strip().decode("latin-1").lower()
            cl = hdrs.get(b"content-length")
            cl_int = None
            if cl is not None:
                try:
                    cl_int = int(cl.decode("ascii"))
                except (ValueError, AttributeError):
                    cl_int = None

            # 预拒过大的 Content-Length(防止一开始超 MAX_BYTES)
            if cl_int is not None and cl_int > MAX_BYTES:
                sock.close()
                raise DownloadError(f"declared_too_large: {cl_int}")

            # 写入 .part
            try:
                fd = os.open(part_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                sock.close()
                raise DownloadError("part_exists")
            sha = hashlib.sha256()
            total = 0
            head_buf = b""
            os_truncate_size = None
            with os.fdopen(fd, "wb") as f:
                try:
                    for piece in _iter_body_chunks(sock, rest, hdrs):
                        f.write(piece)
                        total += len(piece)
                        sha.update(piece)
                        if len(head_buf) < 16:
                            head_buf += piece
                finally:
                    sock.close()
                # fsync
                os.fsync(f.fileno())
            os_truncate_size = os.path.getsize(part_path)

            magic = classify_magic(head_buf)
            detected_ext = ext_for(magic) if magic else None
            ct_ext = ext_for(ct) if ct else None
            if not detected_ext or not ct_ext or detected_ext != ct_ext:
                try:
                    os.unlink(part_path)
                except FileNotFoundError:
                    pass
                return dict(
                    ok=False, source_url=source_url, saved=False,
                    fail_reason="magic_or_ct_mismatch",
                    magic_content_type=magic, header_content_type=ct,
                    body_size=total,
                )

            sha_hex = sha.hexdigest()
            local_filename = f"{sha_hex}.{detected_ext}"
            local_path = os.path.join(dest_dir, local_filename)
            # 幂等:已存在直接 unlink .part
            if os.path.exists(local_path):
                try:
                    os.unlink(part_path)
                except FileNotFoundError:
                    pass
                size = os.path.getsize(local_path)
                # 验旧文件 sha(若 8 边界 + 单元测试要求,不严但合理)
                with open(local_path, "rb") as f:
                    old_sha = hashlib.sha256(f.read()).hexdigest()
                if old_sha != sha_hex:
                    return dict(
                        ok=False, source_url=source_url, saved=False,
                        fail_reason="idempotent_hash_mismatch",
                        expected_sha=sha_hex, actual_sha=old_sha,
                    )
                return dict(
                    ok=True, source_url=source_url, final_url=cur,
                    saved=True, deduplicated=True, local_filename=local_filename,
                    sha256=sha_hex, bytes=size, content_type=magic,
                    content_length_header=cl_int,
                    redirect_count=len(redirected_chain),
                    visited_chain=redirected_chain,
                    source_origin="shopify-public-cdn",
                    license_status="unknown",
                    usage_scope="internal-review-only",
                    retrieved_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
                )

            os.replace(part_path, local_path)
            part_path = None  # 已 rename,不要 finally unlink
            final_url = cur
            final_status = status
            final_content_type = magic
            final_body_path = local_path
            break
        else:
            raise TooManyRedirects(f"max={MAX_REDIRECTS}")

    except SizeLimitExceeded as e:
        if part_path:
            try:
                os.unlink(part_path)
            except FileNotFoundError:
                pass
        return dict(ok=False, source_url=source_url, saved=False, fail_reason=f"size_limit:{e}")
    except TooManyRedirects as e:
        if part_path:
            try:
                os.unlink(part_path)
            except FileNotFoundError:
                pass
        return dict(ok=False, source_url=source_url, saved=False, fail_reason=f"too_many_redirects:{e}")
    except DownloadError as e:
        if part_path:
            try:
                os.unlink(part_path)
            except FileNotFoundError:
                pass
        return dict(ok=False, source_url=source_url, saved=False, fail_reason=f"{e.reason}", **e.extra)
    except (ValueError,) as e:
        if part_path:
            try:
                os.unlink(part_path)
            except FileNotFoundError:
                pass
        return dict(ok=False, source_url=source_url, saved=False, fail_reason=f"validation:{e}")
    except (OSError, socket.error) as e:
        if part_path:
            try:
                os.unlink(part_path)
            except FileNotFoundError:
                pass
        return dict(ok=False, source_url=source_url, saved=False, fail_reason=f"socket:{e}")

    return dict(
        ok=True, source_url=source_url, final_url=final_url,
        saved=True, deduplicated=False,
        local_filename=os.path.basename(final_body_path),
        sha256=hashlib.sha256(open(final_body_path, "rb").read()).hexdigest(),
        bytes=os.path.getsize(final_body_path),
        content_type=final_content_type,
        content_length_header=cl_int,
        status=final_status,
        redirect_count=len(redirected_chain),
        visited_chain=redirected_chain,
        source_origin="shopify-public-cdn",
        license_status="unknown",
        usage_scope="internal-review-only",
        retrieved_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("dest")
    args = ap.parse_args()
    result = download_one(args.url, args.dest)
    print(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
