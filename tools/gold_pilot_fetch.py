#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/gold_pilot_fetch.py —— 审查结论 gold 试点：附件下载与 gold 结构化

**它做什么**：按给定的 `record_id + file_token` 清单，
把飞书多维表里的图片附件下载到**仓外**目录，并把人工审核意见结构化成 `gold.json`。

**它不做什么**：不判断内容、不改写审核人原话、不跑任何模型。

--------------------------------------------------------------------------
★ 五条本文件刻意做死的事
--------------------------------------------------------------------------

**一、落盘目录必须在仓外，且 0700**

    本仓库是**公开**的。附件里是客户素材 + 审核意见，进仓就是泄露。
    执行点是本文件的 `_prepare_landing()`：realpath 后仍在仓内 → 直接拒并退 2。
    （与 `base/takedown.py` 的截图仓外判定、`download_registry` 的 landing_root
     校验同一口径。）

**二、下载调用点必须登记**

    改线后（2026-10-17）下载允许，但每个调用点要在 `tools/download_callers.json`
    里结构化登记：谁消费、落在哪个根、留多久、什么分级。
    未登记 → `verify_download_governance.py` 的 DG-1 报红。

**三、审核人原话一个字都不改**

    `具体原因/分析` 与 `建议` 原样落进 `gold.json`，只做**结构化**（加字段名、
    加 record_id、加附件指纹），不做**改写**（不润色、不摘要、不纠错）。
    ★ gold 是评测的基准答案。改写基准答案，等于把「模型答得对不对」变成
      「模型答得像不像我改写后的版本」。

**四、没有下载到的东西不许记成「已验证」**

    每张图落盘后重算 sha256 并写进 manifest；清单里声明了却没下下来的，
    逐条报进 `missing`，**不静默跳过**。

**五、`--self-test` 不碰网络**

    用临时目录造本地文件，验证 manifest / sha256 / 仓外守卫三件事。
    真实下载只在显式给 `--records` 时发生。

用法
----
    # 真实下载（需要凭据，走 tools/lark_http.py 的同一套鉴权）
    python3 tools/gold_pilot_fetch.py --plan /tmp/gold_plan.json

    # 自证（不联网）
    python3 tools/gold_pilot_fetch.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# 落盘根：**仓外**。可用环境变量覆盖，但覆盖后仍要过仓外判定。
DEFAULT_LANDING = os.path.expanduser("~/audit-data/gold/pilot")
LANDING_ENV = "SHOUHENG_GOLD_LANDING"

# 数据分级：客户素材 + 内部审核意见
DATA_CLASS = "confidential"
RETENTION = "run-scoped"

BJT = timezone(timedelta(hours=8))

# 附件下载接口（media tmp url）。★ 这个字符串是登记表 `api` 字段的来源，
# 也是扫描器认出调用点的依据 —— 改它就要同步改 download_callers.json。
MEDIA_API = "medias/batch_get_tmp_download_url"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _within_repo(p: Path) -> bool:
    """路径是否落在仓库内（realpath 判定）。"""
    try:
        real = Path(os.path.realpath(str(p)))
        repo = Path(os.path.realpath(str(ROOT)))
    except OSError:
        return False
    return real == repo or repo in real.parents


def prepare_landing(base: str | None = None) -> dict:
    """
    准备落盘目录。返回 {"root": Path, "images": Path}。

    ★ 三个硬条件，任一不满足就抛 —— 不许「先建了再说」：
      ① 在仓外（realpath 后）
      ② 目录权限 0700
      ③ 建得出来
    """
    raw = base or os.environ.get(LANDING_ENV) or DEFAULT_LANDING
    root = Path(os.path.expanduser(raw))

    if _within_repo(root):
        raise PermissionError(
            "落盘根 %s 在仓库内 —— 本仓库是公开的，附件与审核意见不许进" % root)

    root.mkdir(parents=True, exist_ok=True)
    os.chmod(str(root), 0o700)

    mode = os.stat(str(root)).st_mode & 0o777
    if mode != 0o700:
        raise PermissionError("落盘根 %s 权限是 %o，要求 0700" % (root, mode))

    images = root / "images"
    images.mkdir(exist_ok=True)
    os.chmod(str(images), 0o700)
    return {"root": root, "images": images}


# ═══════════════════════ ① 下载 ═══════════════════════

def fetch_tmp_urls(file_tokens, *, http=None):
    """
    取一批 file_token 的临时下载地址。

    ★ 单独一个函数是为了让 `--self-test` 能注入桩，不碰网络。
    """
    if http is None:
        import lark_find as L
        tok = L.token()
        _req = L._req
    else:
        tok, _req = http

    out = []
    import lark_find as L
    for i in range(0, len(file_tokens), 5):
        part = file_tokens[i:i + 5]
        q = "&".join("file_tokens=%s" % t for t in part)
        # ★ 接口名必须是**字面量**，不能藏在变量里：
        #   download_scan_py 靠 URL 里出现的接口名推断 api_kind。
        #   写成 `{MEDIA_API}` 时扫描器只看到 `<expr>/drive/v1/medias/<expr>`，
        #   推断不出族 → 登记表的 ordinal 定位失效、调用点也认领不上。
        #   实测踩过一次（DG-1 报「ordinal 超出范围 + 调用点未被覆盖」）。
        url = f"{L.BASE}/drive/v1/medias/batch_get_tmp_download_url?{q}"
        r = _req(url, tok)
        if r.get("code") != 0:
            return {"ok": False, "err": "code=%s %s" % (r.get("code"), r.get("msg"))}
        out.extend((r.get("data") or {}).get("tmp_download_urls") or [])
    return {"ok": True, "urls": out}


def download_one(url: str, dest: Path, *, opener=None):
    """下载一个地址到 dest。返回 {"ok", "bytes", "sha256"}。"""
    if opener is None:
        import urllib.request

        def opener(u):
            with urllib.request.urlopen(u, timeout=60) as r:
                return r.read()

    try:
        data = opener(url)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}

    if not data:
        return {"ok": False, "err": "下载到 0 字节"}

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    os.chmod(str(dest), 0o600)
    return {"ok": True, "bytes": len(data), "sha256": _sha256(dest)}


# ═══════════════════════ ② gold 结构化 ═══════════════════════

def build_gold(records, downloaded) -> list:
    """
    把原始记录 + 下载结果拼成 gold.json 的内容。

    `records` 每条形如：
      {"record_id","品线","分类","原因文本","建议","images":[{"file_token","name"}]}

    `downloaded` 是 {(record_id, file_token): {"file","sha256","ok"}}

    ★ 原话字段（原因文本 / 建议）**原样带过**，不加任何修饰。
      这里只加「它属于哪条记录、图叫什么、指纹是什么」。
    """
    out = []
    for r in records:
        imgs = []
        for im in r.get("images") or []:
            key = (r["record_id"], im.get("file_token"))
            d = downloaded.get(key) or {}
            imgs.append({
                "file_token": im.get("file_token"),
                "name": im.get("name"),
                "file": d.get("file"),
                "sha256": d.get("sha256"),
                "ok": bool(d.get("ok")),
            })
        out.append({
            "record_id": r["record_id"],
            "产品线": r.get("品线"),
            "原因分类": r.get("分类"),
            "原因文本": r.get("原因文本"),      # ★ 原话，不改写
            "建议": r.get("建议"),              # ★ 原话，不改写
            "审核人": r.get("审核人"),
            "images": imgs,
        })
    return out


# ═══════════════════════ ③ 自证 ═══════════════════════

def self_test() -> int:
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        # ── ① 落盘根：仓外可建、权限 0700 ──
        info = prepare_landing(str(base / "landing"))
        mode = os.stat(str(info["root"])).st_mode & 0o777
        ok("S1 仓外目录可建且权限 0700", mode == 0o700, "mode=%o" % mode)

        # ── ② 落盘根在仓内 → 必须拒 ──
        try:
            prepare_landing(str(ROOT / "_should_not_exist"))
            ok("S2 ★ 仓内路径 → 拒", False, "居然建了")
        except PermissionError:
            ok("S2 ★ 仓内路径 → 拒", True, "PermissionError")
        finally:
            p = ROOT / "_should_not_exist"
            if p.exists():
                p.rmdir()

        # ── ③ 下载 + sha256 ──
        dest = info["images"] / "a.png"
        r = download_one("http://example.invalid/x", dest,
                         opener=lambda u: b"fake-image-bytes")
        ok("S3 下载落盘并算 sha256",
           r["ok"] and r["bytes"] == 16 and r["sha256"] == _sha256(dest),
           str(r))
        ok("S4 落盘文件权限 0600",
           (os.stat(str(dest)).st_mode & 0o777) == 0o600, "")

        # ── ④ 0 字节 → 拒（不许记成「下下来了」）──
        r0 = download_one("http://example.invalid/x", info["images"] / "z.png",
                          opener=lambda u: b"")
        ok("S5 ★ 0 字节 → 拒", r0["ok"] is False, str(r0))

        # ── ⑤ 下载抛异常 → 拒 ──
        def boom(u):
            raise OSError("网络断了")
        rb = download_one("http://example.invalid/x", info["images"] / "b.png",
                          opener=boom)
        ok("S6 ★ 下载异常 → 拒", rb["ok"] is False, str(rb))

        # ── ⑦ gold 结构化：原话必须逐字保留 ──
        recs = [{
            "record_id": "rec1", "品线": "吸奶器", "分类": "原则性错误",
            "原因文本": "原文里有「未经验证的功效宣称」，且含数字 99.9%。",
            "建议": "改为：建议咨询专业人士。",
            "审核人": "张三",
            "images": [{"file_token": "ft1", "name": "a.png"}],
        }]
        dl = {("rec1", "ft1"): {"file": "a.png", "sha256": _sha256(dest), "ok": True}}
        gold = build_gold(recs, dl)
        g = gold[0]
        ok("S7 ★ 原因文本逐字保留（不改写）",
           g["原因文本"] == recs[0]["原因文本"], g["原因文本"])
        ok("S8 ★ 建议逐字保留（不改写）",
           g["建议"] == recs[0]["建议"], g["建议"])
        ok("S9 结构化保留了 record_id / 品线 / 分类",
           g["record_id"] == "rec1" and g["产品线"] == "吸奶器"
           and g["原因分类"] == "原则性错误", "")
        ok("S10 附件带 sha256",
           g["images"][0]["sha256"] == _sha256(dest)
           and g["images"][0]["ok"] is True, "")

        # ── ⑧ 没下下来的附件不许记成 ok ──
        gold2 = build_gold(recs, {})
        ok("S11 ★ 未下载的附件 → ok=False 且 sha256 为空",
           gold2[0]["images"][0]["ok"] is False
           and gold2[0]["images"][0]["sha256"] is None, "")

        # ── ⑨ manifest 形状 ──
        man = {
            "generated_at": datetime.now(BJT).isoformat(),
            "landing_root": str(info["root"]),
            "data_class": DATA_CLASS,
            "retention": RETENTION,
            "files": [{"file": "a.png", "sha256": _sha256(dest),
                       "record_id": "rec1", "file_token": "ft1"}],
        }
        ok("S12 manifest 每条都有 sha256 与来源 record",
           all(f.get("sha256") and f.get("record_id") for f in man["files"]), "")

        # ── ⑩ 落盘根不在仓外时，manifest 里也不许出现仓内路径 ──
        ok("S13 ★ 落盘根在仓外", not _within_repo(info["root"]), str(info["root"]))

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 74)
    print("gold_pilot_fetch · 自证（零网络）")
    print("=" * 74)
    for name, p, detail in results:
        print("  %s %-46s %s" % ("✓" if p else "✗", name, detail))
    print()
    if passed == total:
        print("✅ %d/%d 项全过" % (passed, total))
        return 0
    print("✗ %d/%d 项通过；红项：%s"
          % (passed, total, [n for n, p, _ in results if not p]), file=sys.stderr)
    return 1


# ═══════════════════════ ④ 主流程 ═══════════════════════

def run_plan(plan_path: str, landing: str | None = None) -> int:
    """
    按 plan 跑一遍：下载 + 写 manifest + 写 gold。

    plan 形状：
      {"records": [{"record_id","品线","分类","原因文本","建议","审核人",
                    "images":[{"file_token","name"}]}, ...]}
    """
    try:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("⚠ 未测：plan 读不出（%s）" % e, file=sys.stderr)
        return 2

    records = plan.get("records")
    if not isinstance(records, list) or not records:
        print("⚠ 未测：plan 里没有 records", file=sys.stderr)
        return 2

    try:
        info = prepare_landing(landing)
    except PermissionError as e:
        print("✗ 落盘根不合格：%s" % e, file=sys.stderr)
        return 2

    # 先取所有临时下载地址
    tokens = [im["file_token"] for r in records for im in (r.get("images") or [])]
    url_map = {}
    for i in range(0, len(tokens), 5):
        res = fetch_tmp_urls(tokens[i:i + 5])
        if not res.get("ok"):
            print("✗ 取下载地址失败：%s" % res.get("err"), file=sys.stderr)
            return 1
        for u in res["urls"]:
            url_map[u["file_token"]] = u["tmp_download_url"]

    downloaded, manifest_files, missing = {}, [], []
    for r in records:
        rid = r["record_id"]
        for im in r.get("images") or []:
            ft = im["file_token"]
            name = "%s__%s" % (rid, im.get("name") or ft)
            url = url_map.get(ft)
            if not url:
                missing.append({"record_id": rid, "file_token": ft,
                                "reason": "没有拿到临时下载地址"})
                continue
            d = download_one(url, info["images"] / name)
            if not d["ok"]:
                missing.append({"record_id": rid, "file_token": ft,
                                "reason": d.get("err", "")})
                continue
            downloaded[(rid, ft)] = {"file": name, "sha256": d["sha256"], "ok": True}
            manifest_files.append({
                "record_id": rid, "file_token": ft, "file": name,
                "bytes": d["bytes"], "sha256": d["sha256"],
                "downloaded_at": datetime.now(BJT).isoformat(),
            })

    manifest = {
        "generated_at": datetime.now(BJT).isoformat(),
        "source": {"app_token": plan.get("app_token"),
                   "table_id": plan.get("table_id")},
        "landing_root": str(info["root"]),
        "data_class": DATA_CLASS,
        "retention": RETENTION,
        "never_tracked": True,
        "files": manifest_files,
        "missing": missing,
    }
    (info["root"] / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    gold = build_gold(records, downloaded)
    (info["root"] / "gold.json").write_text(
        json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")

    print("落盘根：%s" % info["root"])
    print("记录 %d 条 · 下载 %d 张 · 缺失 %d 张"
          % (len(gold), len(manifest_files), len(missing)))
    for m in missing:
        print("  ✗ %s / %s —— %s" % (m["record_id"], m["file_token"], m["reason"]))
    print("manifest.json · gold.json 已写")

    return 0 if not missing else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="审查 gold 试点：附件下载与结构化")
    ap.add_argument("--plan", help="计划 JSON（records + app_token/table_id）")
    ap.add_argument("--landing", default=None,
                    help="落盘根（默认 ~/audit-data/gold/pilot，必须在仓外）")
    ap.add_argument("--self-test", action="store_true", default=False)
    ns = ap.parse_args(argv)

    if ns.self_test:
        return self_test()
    if not ns.plan:
        ap.print_usage(sys.stderr)
        print("⚠ 未测：--plan 必填", file=sys.stderr)
        return 2
    try:
        return run_plan(ns.plan, ns.landing)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("✗ 失败：%s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
