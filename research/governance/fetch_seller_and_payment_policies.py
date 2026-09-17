#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_seller_and_payment_policies.py — 补齐卖家平台与支付侧的规则结构证据

背景：R7 的任务是回答「真实系统的规则库实际怎么切轴、实际存哪些字段」。
已有的 R7 证据全部来自开放平台（GitHub / Mozilla / npm / PyPI / AWS / Shopify），
**缺失与客户业务直接同构的对象**：电商卖家平台（eBay / Etsy / Walmart / Amazon Seller）
与支付风控（Stripe / Adyen）——后者的「Prohibited and restricted businesses」
是「同一商品在不同国家可否销售」表达方式的最佳公开样本。

本脚本抓取这些页面，逐条记录真实 HTTP 状态，失败的一并记录（不静默丢弃）。
每条证据写成 `<name>.txt`，头部含 SOURCE_URL / FETCHED / HTTP / BYTES 四行，
与既有证据目录约定一致，可直接被 audit_evidence_integrity.py 核验。

用法：
    python3 fetch_seller_and_payment_policies.py
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "_evidence", "R7", "marketplace")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15")

TARGETS = [
    # 电商卖家平台：规则的切轴方式
    ("ebay-seller-code-of-conduct",
     "https://www.ebay.com/help/policies/selling-policies/seller-code-of-conduct?id=4345"),
    ("ebay-prohibited-restricted-items",
     "https://www.ebay.com/help/policies/prohibited-restricted-items/prohibited-restricted-items?id=4207"),
    ("ebay-policy-index",
     "https://www.ebay.com/help/policies/default/ebays-rules-for-sellers?id=4342"),
    ("etsy-seller-policy",
     "https://www.etsy.com/legal/sellers/"),
    ("etsy-prohibited-items",
     "https://www.etsy.com/legal/prohibited/"),
    ("walmart-marketplace-policies",
     "https://marketplace.walmart.com/policies-and-guidelines/"),
    ("walmart-prohibited-products",
     "https://marketplace.walmart.com/help/article/prohibited-products"),
    # 支付风控：同一商品「各国可否」的表达方式
    ("stripe-restricted-businesses",
     "https://stripe.com/legal/restricted-businesses"),
    ("stripe-legal-index",
     "https://stripe.com/legal"),
    ("adyen-prohibited-restricted",
     "https://docs.adyen.com/risk-management/restricted-and-prohibited-products/"),
    ("adyen-risk-index",
     "https://docs.adyen.com/risk-management/"),
    # 广告平台：严重等级与后果的表达
    ("google-ads-policy-index",
     "https://support.google.com/adspolicy/answer/6008942"),
    ("google-ads-misrepresentation",
     "https://support.google.com/adspolicy/answer/6020955"),
    ("meta-ad-standards-index",
     "https://transparency.meta.com/policies/ad-standards/"),
]

TAG_RE = re.compile(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", re.S | re.I)
BLOCK_TAG_RE = re.compile(
    r"</?(p|div|br|li|tr|h[1-6]|section|article|header|footer|table|ul|ol)[^>]*>",
    re.I)
ANY_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    raw = TAG_RE.sub(" ", raw)
    raw = BLOCK_TAG_RE.sub("\n", raw)
    raw = ANY_TAG_RE.sub(" ", raw)
    raw = html.unescape(raw)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch(url: str):
    cmd = ["curl", "-sL", "--compressed", "-m", "30", "-A", UA,
           "-H", "Accept-Language: en-US,en;q=0.9",
           "-H", "Accept: text/html,application/xhtml+xml",
           "-w", "\n__HTTP__%{http_code}", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=45)
    except subprocess.TimeoutExpired:
        return "000", "", "timeout"
    body = r.stdout.decode("utf-8", "replace")
    code = "000"
    m = re.search(r"__HTTP__(\d{3})\s*$", body)
    if m:
        code = m.group(1)
        body = body[:m.start()]
    return code, body, ""


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    log = []
    for name, url in TARGETS:
        code, raw, err = fetch(url)
        text = html_to_text(raw) if raw else ""
        path = os.path.join(OUT, f"{name}.txt")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"SOURCE_URL: {url}\n")
            fh.write(f"FETCHED: {stamp}\n")
            fh.write(f"HTTP: {code}\n")
            fh.write(f"BYTES: {len(raw.encode('utf-8'))}\n")
            fh.write(f"NOTE: {err or 'ok'}\n\n")
            fh.write(text)
        status = "OK " if code == "200" and len(text) > 400 else "FAIL"
        log.append(f"{status} {code} raw={len(raw):>8}B text={len(text):>7}B  {name}")
        print(log[-1], flush=True)
        time.sleep(1.5)   # 对目标站保持礼貌

    ok = sum(1 for l in log if l.startswith("OK"))
    print(f"\n成功 {ok}/{len(TARGETS)}")
    print(f"证据目录：{os.path.relpath(OUT, ROOT)}")
    print("核验：python3 audit_evidence_integrity.py --shard R7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
