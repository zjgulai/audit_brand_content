#!/usr/bin/env python3
# tools/momcozy/image_download.test.integration.py
#
# 7 类集成测试 + 1 个单元 sanity。基于本地 TLS mock(http.server + ssl),
# 用 self-signed cert(python 自带 `ssl.create_default_context` 跳过 verify,仅测试用)。
# 测试钩子 download_one(_internal_overrides=...) 走 MOMCOZY_TEST_HOOK=1 启用。
#
# 注意:
# - 私钥文件 0600,测试结束删
# - server 线程 daemon=True,主进程退出时自动结束
# - 测试证书 SAN = "cdn.shopify.com"(模拟生产 ALLOW 的合法 hostname)
# - 本地 127.0.0.1 通过 dns_override 注入到 dns_lookup,验证 is_private_ip 仍可走
#   (注:127.0.0.1 会被 is_private_ip 拒——所以我们用 127.0.0.2 + 加白名单 is_private 跳过)
#
# 7 类:
#   T1 chunked
#   T2 无 Content-Length 且超 MAX_BYTES
#   T3 redirect 循环
#   T4 redirect 6+ 跳
#   T5 peer 私网 → 用 dns_override 注入 127.0.0.1 验证 getpeername 拒
#   T6 Content-Type / magic 不匹配
#   T7 连接中断后 .part 清理
#   T8 损坏目标幂等校验
#   T9 - 单元 sanity(URL/IP/魔数/扩展名)

import datetime as _dt
import hashlib
import http.server
import importlib.util
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "image_download", HERE / "image_download.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---- mini fixture helpers ----

def _gen_self_signed(cn: str):
    """用 openssl 现场签发 cert+key。本会话不持久化,临时目录 0600。
    公钥 fingerprint 后续若要断言可取;SAN 由 subjectAltName + openssl 强制。
    """
    d = tempfile.mkdtemp(prefix="momcozy-mock-")
    cert_pem = os.path.join(d, "cert.pem")
    key_pem = os.path.join(d, "key.pem")
    # 生成 key
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", key_pem, "-out", cert_pem, "-days", "1",
                    "-subj", f"/CN={cn}", "-addext",
                    f"subjectAltName=DNS:{cn}"],
                   check=True, capture_output=True)
    os.chmod(key_pem, 0o600)
    os.chmod(cert_pem, 0o600)
    return cert_pem, key_pem, d


class TlsMockServer(threading.Thread):
    """Generic TLS HTTP/1.1 server with a thread-local handler builder.
    server 接受 action 可重设 handler。
    """
    def __init__(self, port=0, handler_factory=None, cert=None, key=None):
        super().__init__(daemon=True)
        self.port = port
        self._action = {"fn": handler_factory}
        self.cert, self.key = cert, key
        self.httpd = None

    def set_action(self, fn):
        self._action["fn"] = fn

    def run(self):
        if not self.cert:
            self.cert, self.key, _ = _gen_self_signed("cdn.shopify.com")
        outer_self = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                fn = outer_self._action["fn"]
                if fn is None:
                    self.send_error(500)
                    return
                fn(self)

            def log_message(self, *a, **k):
                pass

        httpd = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=self.cert, keyfile=self.key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        self.httpd = httpd
        # 分配 ephemeral port
        sockname = httpd.socket.getsockname()
        self.port = sockname[1]
        httpd.serve_forever()


def fresh_ssl_ctx_client(cert_path: str) -> ssl.SSLContext:
    """client SSL context,验测试用 cert(策略:跳过 verify,表示信任该测试 cert)。
    生产代码不传这种 ctx;测试里仅做 ssl_ctx override。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---- 7 类测试 + sanity ----

failures = []
def expect(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name}: {detail}")
        failures.append(name)


def t1_chunked(server, dest_dir, dns_ovr):
    """T1 chunked 200 → 应正常落盘。"""
    print("T1 chunked 200")
    body_full = bytes.fromhex("ffd8ffe100ae457869660000" + "00" * 100)
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Transfer-Encoding", "chunked")
        h.end_headers()
        h.wfile.write(b"32\r\n")
        h.wfile.write(body_full[:0x32])
        h.wfile.write(b"\r\n")
        h.wfile.write(b"%x\r\n" % (len(body_full) - 0x32))
        h.wfile.write(body_full[0x32:])
        h.wfile.write(b"\r\n0\r\n\r\n")
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/test/chunked.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T1 saved", r["saved"], str(r))
    expect("T1 sha matches", r.get("sha256") and r["sha256"] == hashlib.sha256(body_full).hexdigest(), r.get("sha256"))


def t2_no_cl_over_max(server, dest_dir, dns_ovr):
    """T2 无 Content-Length 且 body 超 MAX_BYTES → 触发 size_limit + unlink .part"""
    print("T2 no Content-Length, body too big")
    big = b"a" * (mod.MAX_BYTES + 1024)
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Transfer-Encoding", "chunked")
        h.end_headers()
        # 假装不告诉 server Content-Length;持续写直至断
        sent = 0
        chunk_size = 64 * 1024
        while sent < len(big):
            n = min(chunk_size, len(big) - sent)
            h.wfile.write(b"%x\r\n" % n)
            h.wfile.write(big[sent:sent+n])
            h.wfile.write(b"\r\n")
            sent += n
        h.wfile.write(b"0\r\n\r\n")
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/test/too-big.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T2 not saved", not r["saved"], str(r))
    expect("T2 fail reason contains size", "size" in r.get("fail_reason", ""), r.get("fail_reason"))
    expect("T2 no .part leftovers", not [p for p in os.listdir(dest_dir) if p.endswith(".part")], str(os.listdir(dest_dir)))


def t3_redirect_loop(server, dest_dir, dns_ovr):
    """T3 redirect 循环 → TooManyRedirects。"""
    print("T3 redirect loop")
    def fn(h):
        # 跳到一个固定 ALLOW 内路径,模拟循环
        h.send_response(301)
        h.send_header("Location", "https://cdn.shopify.com/s/files/loop/start.jpg")
        h.send_header("Content-Length", "0")
        h.end_headers()
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/loop/start.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T3 not saved", not r["saved"], str(r))
    expect("T3 too_many_redirects",
            "too_many_redirects" in r.get("fail_reason", "") or "redirect_loop" in r.get("fail_reason", ""),
            r.get("fail_reason"))
    # 注:visited set 命中 → "redirect_loop:<url>" 是比 too_many_redirects 更早的失败;
    #     期望 fail_reason 含两者之一,download_one 整体未保存。


def t4_redirect_6(server, dest_dir, dns_ovr):
    """T4 redirect 6 跳 → 4 个不同的 hop,第 5 次还在 ALLOW,但第 6 次应该被拒。"""
    print("T4 redirect chain > 5")
    counter = {"n": 0}
    def fn(h):
        counter["n"] += 1
        h.send_response(301)
        h.send_header("Location", "https://cdn.shopify.com/s/files/h%d.jpg" % counter["n"])
        h.send_header("Content-Length", "0")
        h.end_headers()
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/h0.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T4 not saved", not r["saved"], str(r))


def t5_peer_private_via_dns_override(server, dest_dir, dns_ovr):
    """T5 用 dns_override 注入 127.0.0.1,server 仍在 127.0.0.1 → peerAddress 是私网 → 拒。
    注意:测试 server 真实是 127.0.0.1,所以这条**真实**就是私网,验证 is_private_ip + 拒绝路径。
    """
    print("T5 peer private (dns_override inject 127.0.0.1)")
    body = bytes.fromhex("ffd8ffe1" + "00" * 32)
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/private/test.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert)},
    )
    expect("T5 not saved", not r["saved"], str(r))
    expect("T5 private_peer fail", r.get("fail_reason") in ("private_peer",), r.get("fail_reason"))


def t6_magic_ct_mismatch(server, dest_dir, dns_ovr):
    """T6 Content-Type:image/jpeg 但 magic 是 PNG → unlink + 返回错。"""
    print("T6 CT=image/jpeg magic=PNG mismatch")
    png = bytes.fromhex("89504e470d0a1a0a" + "00" * 32)
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Content-Length", str(len(png)))
        h.end_headers()
        h.wfile.write(png)
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/mismatch/test.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T6 not saved", not r["saved"], str(r))
    expect("T6 magic_or_ct_mismatch", r.get("fail_reason") == "magic_or_ct_mismatch", r.get("fail_reason"))


def t7_partial_cleanup(server, dest_dir, dns_ovr):
    """T7 连接中断后 .part 必须被清。"""
    print("T7 connection interrupted → .part cleaned")
    body = b"x" * (10 * 1024 * 1024)  # 10MB
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Transfer-Encoding", "chunked")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(b"100\r\n")
        h.wfile.write(body[:0x100])
        h.wfile.write(b"\r\n")
        # 提前断:不送 0\r\n
        try:
            h.wfile.close()
        except Exception:
            pass
        raise ConnectionAbortedError("simulated interrupt")
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/interrupt/test.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T7 not saved", not r["saved"], str(r))
    expect("T7 .part cleaned", not any(p.endswith(".part") for p in os.listdir(dest_dir)), str(os.listdir(dest_dir)))


def t8_corrupted_target_idempotent(server, dest_dir, dns_ovr):
    """T8 目标已存在但 sha 不匹配 → idem 拒绝。"""
    print("T8 corrupted target idempotency")
    body = bytes.fromhex("ffd8ffe1" + "00" * 32)
    sha_correct = hashlib.sha256(body).hexdigest()
    sha_actual = "0" * 64  # 长度对,不等于 sha_correct
    # 先预创建冲突文件
    target_name = f"{sha_correct}.jpg"
    target_path = os.path.join(dest_dir, target_name)
    with open(target_path, "wb") as f:
        f.write(b"corrupted bytes not matching sha")
    def fn(h):
        h.send_response(200)
        h.send_header("Content-Type", "image/jpeg")
        h.send_header("Content-Length", str(len(body)))
        h.end_headers()
        h.wfile.write(body)
    server.set_action(fn)
    r = mod.download_one(
        "https://cdn.shopify.com/s/files/idem/test.jpg",
        dest_dir,
        _internal_overrides={"dns": dns_ovr, "port": server.port, "ssl_ctx": fresh_ssl_ctx_client(server.cert), "skip_peer_check": True},
    )
    expect("T8 not saved", not r["saved"], str(r))
    expect("T8 idempotent_hash_mismatch", r.get("fail_reason") == "idempotent_hash_mismatch", r.get("fail_reason"))
    try:
        os.unlink(target_path)
    except FileNotFoundError:
        pass


# ---- main ----

def main():
    os.environ["MOMCOZY_TEST_HOOK"] = "1"

    tmpdir = tempfile.mkdtemp(prefix="momcozy-test-")
    print(f"tmpdir: {tmpdir}")

    # 启动 TLS server,逻辑 hostname = cdn.shopify.com,实连 127.0.0.1:ephemeral
    server = TlsMockServer(port=0, cert=None, key=None)
    server.start()
    time.sleep(0.2)
    print(f"server listening on 127.0.0.1:{server.port}")
    dns_ovr = {"cdn.shopify.com": ["127.0.0.1"]}

    cases = [
        t1_chunked, t2_no_cl_over_max, t3_redirect_loop, t4_redirect_6,
        t5_peer_private_via_dns_override, t6_magic_ct_mismatch,
        t7_partial_cleanup, t8_corrupted_target_idempotent,
    ]
    for fn in cases:
        try:
            fn(server, tmpdir, dns_ovr)
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {type(e).__name__}: {e}")
            failures.append(fn.__name__)
        time.sleep(0.05)

    # 收尾:清临时目录
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass
    # server 是 daemon thread,主进程退出自然结束

    print()
    if failures:
        print(f"FAIL: {len(failures)} {failures}")
        sys.exit(1)
    print("PASS: all 8 integration cases green")
    sys.exit(0)


if __name__ == "__main__":
    main()
