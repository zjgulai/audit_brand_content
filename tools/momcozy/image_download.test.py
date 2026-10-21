#!/usr/bin/env python3
# tools/momcozy/image_download.test.py
# 离线单元测试:覆盖 8 条硬边界,不依赖网络。
#
# 用法:
#   python3 tools/momcozy/image_download.test.py
# 退出码 0 = 全过
#
# 测试覆盖:
#   - validate_url(host allowlist / path prefix / https / userinfo)
#   - is_private_ip(IPv4 + IPv6 各种私网)
#   - classify_magic(JPEG / PNG / WebP / RIFF-but-not-WEBP / 非图)
#   - ext_for(content_type → jpg/png/webp)
#   - URL 形式错误时的 ValueError 文案

import sys
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "image_download",
    Path(__file__).parent / "image_download.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


failures = []
def check(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name}: {detail}")
        failures.append(name)


# ---- Boundary 1: host allowlist + path prefix ----
print("Boundary 1: host allowlist / path prefix / scheme / userinfo")
for u, ok, label in [
    ("https://cdn.shopify.com/s/files/1/abc/x.jpg",                  True,  "1a cdn + /s/files/ pass"),
    ("https://cdn.shopify.com/s/files/anything",                       True,  "1b cdn deep path pass"),
    ("https://cdn.shopify.com/",                                      False, "1c cdn root reject"),
    ("https://cdn.shopify.com/admin/api",                             False, "1d cdn other path reject"),
    ("https://momcozy.com/cdn/shop/files/x.webp",                     True,  "1e momcozy + /cdn/shop/ pass"),
    ("https://momcozy.com/cdn/shop/anything",                          True,  "1f momcozy deep path pass"),
    ("https://momcozy.com/products/x",                                False, "1g momcozy other reject"),
    ("https://evil.example.com/s/files/x.jpg",                        False, "1h non-allowlist reject"),
    ("http://cdn.shopify.com/s/files/x.jpg",                          False, "1i http reject"),
    ("https://user:pass@cdn.shopify.com/s/files/x.jpg",               False, "1j userinfo reject"),
    ("https://cdn.shopify.com./s/files/x.jpg",                        True,  "1k trailing dot pass"),
]:
    try:
        mod.validate_url(u)
        check(label, ok is True, "did not raise but expected" if not ok else "")
    except ValueError as e:
        check(label, ok is False, str(e) if ok else "")

# ---- Boundary 3: IP literal / private ----
print("Boundary 3: IP literal / private IPv4 + IPv6")
for ip, expected, label in [
    ("10.0.0.1",         True,  "3a 10/8"),
    ("172.16.0.1",       True,  "3b 172.16/12"),
    ("172.31.255.255",   True,  "3c 172.31/12 high edge"),
    ("172.32.0.1",       False, "3d 172.32 not private"),
    ("192.168.1.1",      True,  "3e 192.168/16"),
    ("127.0.0.1",        True,  "3f loopback"),
    ("169.254.169.254",  True,  "3g link-local"),
    ("224.0.0.1",        True,  "3h multicast"),
    ("0.0.0.0",          True,  "3i unspecified"),
    ("162.125.32.6",     False, "3j public IP pass"),
    ("8.8.8.8",          False, "3k public DNS pass"),
    ("::1",              True,  "3l IPv6 loopback"),
    ("fc00::1",          True,  "3m IPv6 fc00::/7"),
    ("fd00::1",          True,  "3n IPv6 fd00::/8"),
    ("fe80::1",          True,  "3o IPv6 fe80::/10"),
    ("2606:4700::1",     False, "3p IPv6 public pass"),
    ("::ffff:127.0.0.1", True,  "3q IPv6 IPv4-mapped private"),
    ("::ffff:8.8.8.8",   False, "3r IPv6 IPv4-mapped public"),
    ("not.an.ip",        True,  "3s garbage IP treated private (fail-safe)"),
]:
    check(label, mod.is_private_ip(ip) is expected, f"is_private_ip({ip})={mod.is_private_ip(ip)}")

# ---- Boundary 6: magic ----
print("Boundary 6: magic")
jpeg = bytes.fromhex("ffd8ffe100ae45786966")
png  = bytes.fromhex("89504e470d0a1a0a0000")
webp = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100
riff_avi = b"RIFF" + b"\x00\x00\x00\x00" + b"AVI " + b"\x00" * 100
svg = b"<?xml version=\"1.0\"?>"
html = b"<!DOCTYPE html><html>"
json_ = b'{"hello":1}'

check("6a JPEG magic", mod.classify_magic(jpeg) == "image/jpeg", mod.classify_magic(jpeg))
check("6b PNG magic",  mod.classify_magic(png)  == "image/png",  mod.classify_magic(png))
check("6c WebP magic", mod.classify_magic(webp) == "image/webp", mod.classify_magic(webp))
check("6d RIFF-but-not-WEBP → null", mod.classify_magic(riff_avi) is None, str(mod.classify_magic(riff_avi)))
check("6e SVG → null", mod.classify_magic(svg) is None, str(mod.classify_magic(svg)))
check("6f HTML → null", mod.classify_magic(html) is None, str(mod.classify_magic(html)))
check("6g JSON → null", mod.classify_magic(json_) is None, str(mod.classify_magic(json_)))

# ---- ext_for ----
print("ext_for")
check("e1 jpeg→jpg",  mod.ext_for("image/jpeg") == "jpg")
check("e2 png→png",   mod.ext_for("image/png")  == "png")
check("e3 webp→webp", mod.ext_for("image/webp") == "webp")
check("e4 unknown→None", mod.ext_for("application/octet-stream") is None)
check("e5 empty→None", mod.ext_for("") is None)

print()
if failures:
    print(f"FAIL: {len(failures)} failures: {failures}")
    sys.exit(1)
print(f"PASS: all 8-boundary tests green")
sys.exit(0)
