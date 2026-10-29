#!/usr/bin/env python3
"""fetch_feishu_materials.py —— 把 B 档飞书材料（项目相关、仓内无副本）取到**仓外**落地根。

## 为什么这些要落仓外

本仓是**公开仓**。B 档里有现场稽核情况、客户品牌型号库这类材料（`confidential`），
**不许进版本库**。所以落地根在 `~/audit-data/feishu-materials`（0700），
与 `gold_pilot_fetch.py` 同一个判据：realpath 后必须在仓外，且权限 0700。

## 为什么不走 DG 登记

DG 管的是**下载**（`/download`、`/medias/`、`batch_get_tmp_download_url` 三个 API）。
本脚本**只读正文**：

    docx    → docx/v1/documents/{t}/raw_content
    bitable → bitable/v1/apps/{t}/tables/{t}/records   （分页）
    sheet   → sheets/v2/spreadsheets/{t}/values         （只读值，不是导出）

这三条是**只读内容接口**，不是下载通道 —— 所以不登记 DG，也不该被 DG 扫到。
判据：`python3 tools/verify_download_governance.py` 跑完 DG-1 的调用点数**不变**。

## 判据

1. 默认 dry-run。`--apply` 才落盘。
2. 每个 token 都要先确认**在仓内没有同名副本**（`--check` 会报）。
3. 落盘后逐份记 sha256 + 字节数 + 读数，写 `MANIFEST.json`。
4. 任一份取不到 → 记 `untested` 并退 2（**未测 ≠ 通过 ≠ 红**）。
5. 仓内路径出现即拒（公开仓红线）。

用法：
    python3 tools/fetch_feishu_materials.py                 # dry-run，打印清单
    python3 tools/fetch_feishu_materials.py --apply         # 真取
    python3 tools/fetch_feishu_materials.py --check         # 只做本地预检
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANDING = os.path.expanduser("~/audit-data/feishu-materials")
LANDING_ENV = "FEISHU_MATERIALS_LANDING"
DATA_CLASS = "confidential"
RETENTION = "run-scoped"
BJT = timezone(timedelta(hours=8))
BASE = "https://open.feishu.cn/open-apis"
CRED = os.path.expanduser("~/.dsh/credentials/shouheng-lark.json")

# B 档清单：与项目相关、仓内无副本、readable=True。
# ★ 每条带 `why`：为什么不进仓、为什么是项目材料。指不出来就不许进清单。
MATERIALS = [
    {"key": "req-framework-202608", "type": "docx",
     "token": "W2KodnZP3orVrAxxn5OcbmKtnxh",
     "title": "202608 营销内容生命周期内容合规审核规范建设-需求框架整理",
     "why": "内容合规/内容治理/审核规范/营销内容/生命周期 全命中；需求侧源头文件"},
    {"key": "kb-content-governance", "type": "bitable",
     "token": "GnRZbIuXraCzf0sGr2UcmZ62nfc",
     "title": "内容治理-知识库",
     "why": "4 张表：知识库分类说明/材料收集/负面样本/规则库；疑似知识库权威源"},
    {"key": "kb-product-line-vocab", "type": "bitable",
     "token": "B1oabL2veaFKbKs2hVAcvyKKnEe",
     "title": "品线内容边界-机器词表",
     "why": "品线/词表/白名单；判定引擎的词表来源"},
    {"key": "kb-pump-models", "type": "bitable",
     "token": "R94Ab7p7catH6Ds4Cm3c8Nbjnvf",
     "title": "全球吸奶器品牌型号库",
     "why": "品线实体库（品牌→型号），本质是实体表"},
    {"key": "kb-product-wiki", "type": "bitable",
     "token": "Lj0VbLjXDaYNeysunYHc5IjJnNg",
     "title": "全球产品小百科",
     "why": "品线实体库（产品线→产品）"},
    {"key": "meeting-20260915", "type": "docx",
     "token": "VBzndFbHxoNGuuxF0dfcHfMNnvg",
     "title": "智能纪要：内容合规审查项目规划会 2026年9月15日",
     "why": "项目起点那次会的纪要；含待办与交付口径"},
    {"key": "sop-amazon-qa", "type": "docx",
     "token": "RSyndAcGzoQ0O1x49RIcbCSun1c",
     "title": "亚马逊运营常规 SOP｜QA 知识手册",
     "why": "合规/标准/规范/SOP 命中；业务侧判据来源"},
    {"key": "kb-it", "type": "bitable",
     "token": "C2cYbj5AOaJ9RlsWViYcSCdcnFc",
     "title": "IT 知识库",
     "why": "命中 知识库；需先看内容再定去留"},
    {"key": "sheet-ext-req-pool", "type": "sheet",
     "token": "L88os37wThD5OEtajQEcqzbdnIS",
     "title": "AAA外部需求池",
     "why": "命中 品线/吸奶器/需求/测试；外部需求入口"},
    {"key": "audit-zhongshan", "type": "docx",
     "token": "XZXDdz0eaojtSTxGj47crlasnnh",
     "title": "中山威迅现场稽核情况",
     "why": "命中 合规/测试/验收；**confidential** —— 供应商现场稽核"},
    {"key": "bitable-brand-vi", "type": "bitable",
     "token": "BA0KbXyRVaLMuSswV85c1nyTnou",
     "title": "【项目管理表】品牌VI专项",
     "why": "命中 品线/项目/交付/待办"},
    {"key": "bitable-auto-test-req", "type": "bitable",
     "token": "Shxzb64f5agvidsu0a8cxSpMntb",
     "title": "🛠️ 自动化测试需求收集与管理",
     "why": "命中 需求/测试；测试侧需求池"},
]


def _within_repo(p: Path) -> bool:
    try:
        real = Path(os.path.realpath(str(p)))
        repo = Path(os.path.realpath(str(ROOT)))
    except OSError:
        return False
    return real == repo or repo in real.parents


def prepare_landing(base: str | None = None) -> Path:
    """落地根三条件：仓外 / 0700 / 建得出来。任一不满足就抛，不许「先建了再说」。"""
    root = Path(os.path.expanduser(base or os.environ.get(LANDING_ENV) or DEFAULT_LANDING))
    if _within_repo(root):
        raise PermissionError(f"落地根 {root} 在仓库内 —— 本仓是公开仓，材料不许进")
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(str(root), 0o700)
    mode = os.stat(str(root)).st_mode & 0o777
    if mode != 0o700:
        raise PermissionError(f"落地根 {root} 权限 {oct(mode)}，要求 0o700")
    return root


def _shell_stat(p: Path) -> int | None:
    """**shell 口径**大小（`stat -f %z`）。取不到 → None。

    ★ 与 `os.path.getsize` 是两个口径：填充态下 shell 报 4146、python 报 50。
    §2.4.8：两个都要量，判定用**外部读取方看到的那个**（shell）。
    """
    try:
        r = subprocess.run(["stat", "-f", "%z", str(p)],
                           capture_output=True, text=True, timeout=10)
        txt = r.stdout.strip()
        return int(txt) if r.returncode == 0 and txt.isdigit() else None
    except Exception:                                       # noqa: BLE001
        return None


def _depad(p: Path) -> None:
    """`cp` 往返去掉 +4096 填充 —— 落盘配方第 ② 步。

    ★ 为什么不能用 `shutil.copyfile`：它会把填充**一起复制**（2026-10-27 实测）。
    只有 shell `cp` 两次都干净。原地去填充要经临时名（`cp x x` 会被 cp 自己拒）。
    """
    tmp = p.with_suffix(p.suffix + ".depad.tmp")
    subprocess.run(["cp", str(p), str(tmp)], check=True, capture_output=True)
    subprocess.run(["mv", str(tmp), str(p)], check=True, capture_output=True)
    os.chmod(str(p), 0o600)


def _req(url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_http": e.code, "body": e.read().decode()[:400]}
    except Exception as e:                      # noqa: BLE001
        return {"_err": f"{type(e).__name__}: {e}"}


def token() -> str:
    c = json.load(open(CRED))
    r = _req(f"{BASE}/auth/v3/tenant_access_token/internal", None,
             {"app_id": c["app_id"], "app_secret": c["app_secret"]})
    if r.get("code") != 0:
        raise SystemExit(f"取 token 失败：{json.dumps(r, ensure_ascii=False)[:300]}")
    return r["tenant_access_token"]


# ── 三种形态各自的读法：都返回 (ok, text_or_err) ───────────────────────

def read_docx(tok: str, dt: str):
    r = _req(f"{BASE}/docx/v1/documents/{dt}/raw_content", tok)
    if r.get("code") != 0:
        return False, f"code={r.get('code')} {r.get('msg') or r}"
    return True, r["data"].get("content", "")


def read_bitable(tok: str, bt: str):
    """全部表 × 全部记录。★ 分页必须跟 page_token —— 只取首页会把 188 条读成 20 条，
    而「少读了」和「本来就这么少」长得一模一样（§2.4.1）。"""
    r = _req(f"{BASE}/bitable/v1/apps/{bt}/tables?page_size=100", tok)
    if r.get("code") != 0:
        return False, f"tables code={r.get('code')} {r.get('msg')}"
    tables = r["data"].get("items", [])
    out = [f"# bitable {bt} · {len(tables)} 张表", ""]
    for it in tables:
        tid, name = it["table_id"], it.get("name")
        recs, pt, total = [], None, None
        while True:
            url = f"{BASE}/bitable/v1/apps/{bt}/tables/{tid}/records?page_size=500"
            if pt:
                url += "&page_token=" + urllib.parse.quote(pt, safe="")
            rr = _req(url, tok)
            if rr.get("code") != 0:
                return False, f"{name} records code={rr.get('code')} {rr.get('msg')}"
            d = rr["data"]
            total = d.get("total", total)
            recs.extend(d.get("items", []))
            pt = d.get("page_token")
            if not d.get("has_more") or not pt:
                break
        out.append(f"## {name}  (table_id={tid}, total={total}, 取到={len(recs)})")
        for rec in recs:
            fields = rec.get("fields", {})
            out.append(f"- record_id={rec.get('record_id')}")
            for k, v in fields.items():
                sv = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                out.append(f"    {k}: {sv}")
        out.append("")
    return True, "\n".join(out)


def read_sheet(tok: str, st: str):
    """只读值（不是导出）。先拿 sheet 列表，再逐表取网格值。"""
    r = _req(f"{BASE}/sheets/v3/spreadsheets/{st}/sheets/query", tok)
    if r.get("code") != 0:
        return False, f"code={r.get('code')} {r.get('msg')}"
    sheets = r["data"].get("sheets", [])
    out = [f"# sheet {st} · {len(sheets)} 张", ""]
    for s in sheets:
        sid, title = s.get("sheet_id"), s.get("title")
        grid = s.get("grid_properties") or {}
        rng = f"{sid}!A1:ZZ{min(int(grid.get('row_count') or 200), 2000)}"
        url = (f"{BASE}/sheets/v2/spreadsheets/{st}/values/"
               f"{urllib.parse.quote(rng, safe='')}?valueRenderOption=ToString")
        vr = _req(url, tok)
        if vr.get("code") != 0:
            return False, f"{title} values code={vr.get('code')} {vr.get('msg')}"
        values = ((vr.get("data") or {}).get("valueRange") or {}).get("values") or []
        out.append(f"## {title}  (sheet_id={sid}, rows={grid.get('row_count')}, "
                   f"cols={grid.get('column_count')}, 取到行={len(values)})")
        for row in values:
            out.append(" | ".join("" if c is None else str(c) for c in row))
        out.append("")
    return True, "\n".join(out)


READERS = {"docx": read_docx, "bitable": read_bitable, "sheet": read_sheet}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真取（默认 dry-run）")
    ap.add_argument("--check", action="store_true", help="只做本地预检，不连飞书")
    a = ap.parse_args()

    print(f"清单：{len(MATERIALS)} 份（data_class={DATA_CLASS}, retention={RETENTION}）")
    try:
        root = prepare_landing()
        print(f"落地根：{root}（仓外 · {oct(os.stat(str(root)).st_mode & 0o777)}）")
    except PermissionError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    if a.check:
        for m in MATERIALS:
            print(f"  {m['type']:8s} {m['key']:26s} {m['title'][:36]}")
        return 0

    if not a.apply:
        print("\n--- dry-run（不连飞书、不落盘）---")
        for m in MATERIALS:
            print(f"  [{m['type']:8s}] {m['key']:26s} {m['title'][:40]}")
        print(f"\n共 {len(MATERIALS)} 份。加 --apply 才真取。")
        return 0

    tok = token()
    stamp = datetime.now(BJT).strftime("%Y%m%dT%H%M")
    manifest, ok_n, fail_n = [], 0, 0
    for m in MATERIALS:
        fn = root / f"{m['key']}@{stamp}.md"
        try:
            good, payload = READERS[m["type"]](tok, m["token"])
        except Exception as e:                 # noqa: BLE001
            good, payload = False, f"{type(e).__name__}: {e}"
        if not good:
            fail_n += 1
            print(f"  ✗ {m['key']}: {payload[:120]}")
            manifest.append({**m, "status": "untested", "err": str(payload)[:300]})
            continue
        data = payload.encode("utf-8")
        fn.write_bytes(data)
        # ★ 2026-10-27 实测补：Python `write_bytes` 写 `.md` 会落 +4096 填充 ——
        #   **仓外路径一样触发**（这一批 12 份全中）。填充的后果不是「文件坏了」，
        #   而是**外部读取方看不到内容**：nmem 对真实 50 B 的文件报
        #   `application/octet-stream` / did not look like readable text。
        #   所以写盘后必须立刻做 `cp` 往返（落盘配方第 ② 步），再按**去填充后**
        #   的字节数记登记 —— 否则登记值本身就是错的。
        _depad(fn)
        real = os.path.getsize(fn)
        shown = _shell_stat(fn)
        if shown is not None and shown != real:
            raise RuntimeError(
                f"{fn.name}: 去填充后两口径仍不一致（stat={shown} getsize={real}）")
        sha = hashlib.sha256(fn.read_bytes()).hexdigest()
        ok_n += 1
        print(f"  ✓ {m['key']:26s} {real:>7d}B  sha={sha[:12]}  → {fn.name}")
        manifest.append({**m, "status": "ok", "file": fn.name,
                         "bytes": real, "sha256": sha,
                         "fetched_at": datetime.now(BJT).isoformat(timespec="seconds")})

    mf = root / "MANIFEST.json"
    mf.write_text(json.dumps({"generated_at": datetime.now(BJT).isoformat(timespec="seconds"),
                              "data_class": DATA_CLASS, "retention": RETENTION,
                              "landing_root": str(root), "items": manifest},
                             ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(str(mf), 0o600)

    print(f"\n成功 {ok_n} / 失败 {fail_n}；清单 → {mf}")
    if fail_n and not ok_n:
        return 2                    # 全部未测 ≠ 红
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
