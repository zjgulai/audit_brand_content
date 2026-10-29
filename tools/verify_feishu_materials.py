#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_feishu_materials.py —— B 档飞书材料的登记表自证。

## 为什么需要它

`tools/feishu_content_materials.json` 里记着 12 份材料的 sha256，并写着一句
「**重取后若变，说明上游改过**」。但如果没有东西去比，那句话就是一句注释 ——
正是 `AGENTS.md` §2.4.2 点名的「承诺没有执行点」。

## 它验什么

  M1 登记项字段齐          key/token/type/title/why_project/data_class/sha256/bytes 一个不许空
  M2 落地根合法            仓外 + 0700（公开仓红线：正文不许进版本库）
  M3 指纹仍与落盘一致       逐份重算 sha256 == 登记值（**上游改过就红**）
  M4 仓内没有正文           登记表里不许出现任何一份正文的片段
  M5 反向对照              改一个字节 → M3 必须红；删一份 → M3 必须红

## 退出码（AGENTS.md §2.1 三态）

  0 = 全过
  1 = 有红
  2 = 未测（落地根不在盘上 —— **不是通过，也不是红**）

用法：
  python3 tools/verify_feishu_materials.py
  python3 tools/verify_feishu_materials.py --controls
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "tools" / "feishu_content_materials.json"
REQUIRED = ("key", "feishu_token", "type", "title", "why_project",
            "data_class", "sha256", "bytes", "status")


def _within_repo(p: Path) -> bool:
    try:
        real = Path(os.path.realpath(str(p)))
        repo = Path(os.path.realpath(str(ROOT)))
    except OSError:
        return False
    return real == repo or repo in real.parents


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 断言（每个都返回错误列表；好样本必须返回 []）─────────────────────

def check_m1(reg: dict) -> list[str]:
    errs = []
    items = reg.get("items") or []
    if len(items) < 12:
        errs.append(f"M1 登记项只有 {len(items)} 条 < 12（B 档清单是 12 份）")
    keys = [it.get("key") for it in items]
    if len(set(keys)) != len(keys):
        errs.append("M1 key 有重复")
    for it in items:
        for f in REQUIRED:
            v = it.get(f)
            if v is None or (isinstance(v, str) and not v.strip()):
                errs.append(f"M1 {it.get('key', '?')}: 字段 {f} 为空")
    return errs


def check_m2(reg: dict) -> list[str]:
    errs = []
    lr = reg.get("landing_root")
    if not lr:
        return ["M2 登记表缺 landing_root"]
    root = Path(os.path.expanduser(lr))
    if _within_repo(root):
        errs.append(f"M2 landing_root 在仓库内（{root}）—— 公开仓，正文不许进")
    if root.exists():
        mode = os.stat(str(root)).st_mode & 0o777
        if mode != 0o700:
            errs.append(f"M2 landing_root 权限 {oct(mode)} ≠ 0o700")
    else:
        errs.append(f"M2 landing_root 不在盘上：{root}")
    return errs


def shell_stat_size(p: Path) -> int | None:
    """**shell 口径**的大小（`stat -f %z`）。取不到 → None（→ 未测，不是 0）。

    ★ 为什么 M3 必须用它而不是 `os.stat().st_size`：2026-10-27 实测，
    这批文件被 +4096 填充时，**`os.stat()` 与 `os.path.getsize()` 都报真实大小
    （50），只有 `stat -f %z` 报 4146**。第一版 M3 全用 Python 口径，
    于是 12 份全被填充却报「全过」—— §2.4.8「同一个量有两个口径，
    而只有一个被看见」在我自己刚写的验证器里重演了一次。

    `AGENTS.md` §2.4.8 的判据：**同一个量能算出两个数时，两个都要报**，
    并写明判定用哪个。这里判定用 shell 口径 —— 因为 nmem / read 工具读到的
    正是填充后的字节流（实测它对 50B 真实内容报 UTF-8/解析错误）。
    """
    try:
        r = subprocess.run(["stat", "-f", "%z", str(p)],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return None
        txt = r.stdout.strip()
        return int(txt) if txt.isdigit() else None
    except Exception:                                       # noqa: BLE001
        return None


def check_m3(reg: dict, root: Path) -> tuple[list[str], list[str], dict]:
    """返回 (errs, readings, tally)。

    ★ 三种 status 必须**长得不一样**（`AGENTS.md` §2.1 三态）：

    | status | 含义 | 处理 |
    |---|---|---|
    | `ok` | 取到内容且指纹一致 | 逐份重算 sha256 |
    | `empty` | **抓取成功但取到 0 条** | 仍要验落盘文件存在、指纹一致（那就是「空」的证据），
          但结论行必须**单独报**它 —— 不许算进「已取到内容」 |
    | `untested` | 取不到 | 落「未测」，不算进任何分子 |

    第一版对 `!= "ok"` 一律 `continue`，于是 `empty` 与 `untested` 在输出里
    长得一模一样，而结论行仍写「12 份材料 · 指纹一致」 —— 实际只验了 11 份。
    这正是 §2.4.8 那个形状落在三态上：两种东西共用一个分支，读数就被摊平了。
    """
    errs, readings = [], []
    tally = {"ok": 0, "empty": 0, "untested": 0}
    for it in reg.get("items") or []:
        st = it.get("status")
        if st not in ("ok", "empty"):
            tally["untested"] += 1
            readings.append(f"{it.get('key')} 未测")
            continue
        fn = root / str(it.get("file") or "")
        if not fn.exists():
            errs.append(f"M3 {it.get('key')}: 落盘文件不在盘上（{fn.name}）")
            continue
        # ── §2.4.8：两个口径都量，都报 ────────────────────────────
        real = os.path.getsize(fn)          # 逻辑视图
        shown = shell_stat_size(fn)         # stat 视图（填充态在这里现形）
        if shown is None:
            errs.append(f"M3 {it.get('key')}: `stat -f %z` 取不到 → **未测**，不许当成一致")
        elif shown != real:
            errs.append(
                f"M3 {it.get('key')}: **被 +{shown - real} 填充**"
                f"（stat={shown} / getsize={real}）—— 外部读取方（nmem / read 工具）"
                f"会读到填充后的字节流。跑 `cp` 往返修掉，再重取 sha256")
        size = shown if shown is not None else real
        if size != it.get("bytes"):
            errs.append(f"M3 {it.get('key')}: 字节数 {size} ≠ 登记 {it.get('bytes')}"
                        f"（stat={shown} getsize={real}）")
        got = sha256_of(fn)
        if got != it.get("sha256"):
            errs.append(
                f"M3 {it.get('key')}: sha256 {got[:12]} ≠ 登记 {str(it.get('sha256'))[:12]} "
                f"—— **上游改过或文件被动过**，要么重取并更新登记，要么说清为什么不动")
        else:
            readings.append(it.get("key"))
            tally["empty" if st == "empty" else "ok"] += 1
    return errs, readings, tally


def check_m5() -> list[str]:
    """M5 抓取脚本仍带着**去填充**这一步。

    ★ 这一条是覆盖登记逼出来的，但它本身是真断言，不是为了让 C 段闭嘴
    （§2.4：「名字出现过」不是「它拦得住」）。

    为什么必须有：2026-10-27 实测，`fetch_feishu_materials.py` 用
    `fn.write_bytes(data)` 落 12 份 `.md`，**仓外路径也全部 +4096 填充**。
    填充的后果不是「文件坏了」，是外部读取方看不到内容 —— nmem 对真实 50 B 的
    文件报 `application/octet-stream`。所以那个脚本的写盘段**必须**含
    `_depad(fn)` 一次 `cp` 往返，且登记字节数必须取**去填充之后**的值。

    判据按 §2.4 的三层来：①源码里 `_depad(fn)` 必须出现在 `write_bytes` 之后；
    ②`_depad` 自己必须用 shell `cp`（不能用 `shutil.copyfile`，它会把填充一起复制）；
    ③登记值取 `os.path.getsize` 而非 `len(data)`。
    """
    errs = []
    src_path = ROOT / "tools" / "fetch_feishu_materials.py"
    if not src_path.exists():
        return ["M5 抓取脚本 tools/fetch_feishu_materials.py 不在盘上"]
    src = src_path.read_text(encoding="utf-8")

    # ① write_bytes 之后必须有 _depad(fn)
    iw = src.find("fn.write_bytes(data)")
    idd = src.find("_depad(fn)")
    if iw < 0:
        errs.append("M5 抓取脚本里找不到 `fn.write_bytes(data)` —— 定位失败，判据失效")
    elif idd < 0:
        errs.append("M5 抓取脚本写盘后**没有** `_depad(fn)` —— "
                    "Python 写 .md 会落 +4096 填充，仓外路径一样触发")
    elif idd < iw:
        errs.append("M5 `_depad(fn)` 出现在 `write_bytes` **之前** —— 那等于没去填充")

    # ② _depad 必须用 shell cp
    if "def _depad(" in src:
        seg = src[src.find("def _depad("):src.find("def _depad(") + 700]
        if 'subprocess.run(["cp"' not in seg:
            errs.append("M5 `_depad` 没有用 shell `cp` —— "
                        "`shutil.copyfile` 会把 +4096 填充一起复制（实测）")
    else:
        errs.append("M5 抓取脚本里没有 `_depad` 函数")

    # ③ 登记字节数取去填充后的值
    if "real = os.path.getsize(fn)" not in src:
        errs.append("M5 抓取脚本没有用 `os.path.getsize(fn)` 记登记字节数 —— "
                    "记 `len(data)` 会把填充前的值当登记值，M3 永远对不上")
    return errs


def check_m4(reg: dict, root: Path) -> list[str]:
    """公开仓红线：登记表里不许出现正文片段。"""
    errs = []
    try:
        text = REG.read_text(encoding="utf-8")
    except Exception as e:                                  # noqa: BLE001
        return [f"M4 读不出登记表：{e}"]
    for it in reg.get("items") or []:
        fn = root / str(it.get("file") or "")
        if not fn.exists():
            continue
        body = fn.read_text(encoding="utf-8", errors="replace")
        # 取中段一截当探针（避开标题行，那里本来就是登记项里的 title）
        probe = body[len(body) // 2: len(body) // 2 + 40].strip()
        if len(probe) >= 12 and probe in text:
            errs.append(f"M4 {it.get('key')}: 正文片段出现在**入库文件**里 —— 公开仓红线")
    return errs


# ── 反向对照 ────────────────────────────────────────────────────────

def controls(reg: dict, root: Path) -> int:
    print("=" * 70)
    print("反向对照：喂已知坏样本，断言必须红")
    print("=" * 70)
    passed = failed = 0

    def one(name, got, want_red: bool):
        nonlocal passed, failed
        red = bool(got)
        ok = red == want_red
        print(f"  {'✓' if ok else '✗'} {name} → {'红了' if red else '没红'}"
              + ("" if ok else f"（期望{'红' if want_red else '不红'}）"))
        if red:
            print(f"       {got[0]}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

    # C1 字段空 → M1 必红
    bad = json.loads(json.dumps(reg))
    bad["items"][0]["why_project"] = ""
    one("C1 某条 why_project 为空", check_m1(bad), True)

    # C2 landing_root 指到仓库内 → M2 必红
    bad = json.loads(json.dumps(reg))
    bad["landing_root"] = str(ROOT / "tools")
    one("C2 landing_root 指向仓库内", check_m2(bad), True)

    # C3 改一个字节 → M3 必红（真改临时副本，不碰真文件）
    import shutil
    import tempfile
    tmpdir = Path(tempfile.mkdtemp(prefix="fmat-"))
    try:
        it = next((x for x in reg["items"] if x.get("status") == "ok"), None)
        if it:
            # ★ C3/C4/C5 都只喂**单条**登记项。
            #   第一版拿整份 reg（12 条）去比 tmpdir（只放 1 个文件）——
            #   C4 好样本当场红，报「另外 11 份不在盘上」。那不是被测的行为，
            #   是**反向对照自己构造错了**（§2.1.1：会误报的检查器比没有更糟）。
            single = {**reg, "items": [it]}
            src = root / str(it["file"])
            if src.exists():
                dst = tmpdir / str(it["file"])

                def _cp(a: Path, b: Path):
                    """★ 必须用 shell `cp`，不能用 `shutil.copyfile`。

                    2026-10-27 实测：`shutil.copyfile` 会把 +4096 填充**一起复制**，
                    于是 C4「原样拷贝的好样本」背着填充进了临时目录，M3 当场红 ——
                    那不是被测行为，是**反向对照自己的构造错了**（§2.1.1）。
                    shell `cp` 是唯一两次都干净的那条路（落盘配方第 ② 步）。

                    ⚠️ 不允许 `cp x x`（源目相同，cp 自己会拒）。需要「原地去填充」时
                    走 `_depad()`：先 cp 到临时名，再 mv 回来。
                    """
                    subprocess.run(["cp", str(a), str(b)], check=True,
                                   capture_output=True)

                def _depad(p: Path):
                    tmp = p.with_suffix(p.suffix + ".depad.tmp")
                    subprocess.run(["cp", str(p), str(tmp)], check=True,
                                   capture_output=True)
                    subprocess.run(["mv", str(tmp), str(p)], check=True,
                                   capture_output=True)

                _cp(src, dst)
                data = bytearray(dst.read_bytes())
                if data:
                    data[-1] = (data[-1] + 1) % 256
                dst.write_bytes(bytes(data))
                _depad(dst)            # 去填充，让 C3 红的是「改了一个字节」
                errs, _, _ = check_m3(single, tmpdir)
                one("C3 落盘文件改一个字节", errs, True)

                # C4 好样本必须闭嘴（用 shell cp 原样拷回来，不带填充）
                _cp(src, dst)
                errs, _, _ = check_m3(single, tmpdir)
                one("C4 好样本（原样拷贝）", errs, False)
        # C5 删一份 → M3 必红
        if it:
            (tmpdir / str(it["file"])).unlink(missing_ok=True)
            errs, _, _ = check_m3(single, tmpdir)
            one("C5 落盘文件被删", errs, True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n反向对照：{passed} 过 / {failed} 红")
    return 0 if failed == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true")
    a = ap.parse_args()

    if not REG.exists():
        print(f"⚠ 未测：登记表不在盘上 {REG} → 退 2", file=sys.stderr)
        return 2
    reg = json.loads(REG.read_text(encoding="utf-8"))
    root = Path(os.path.expanduser(reg.get("landing_root") or ""))

    if a.controls:
        if not root.exists():
            print("⚠ 未测：落地根不在盘上，反向对照无法做 → 退 2", file=sys.stderr)
            return 2
        return controls(reg, root)

    print("=" * 70)
    print("B 档飞书材料登记表 · 自证")
    print("=" * 70)

    errs: list[str] = []
    untested: list[str] = []

    e1 = check_m1(reg)
    print(f"  {'✅' if not e1 else '❌'} M1 登记项字段齐全（{len(reg.get('items') or [])} 条）")
    for e in e1:
        print(f"       {e}")
    errs += e1

    e2 = check_m2(reg)
    print(f"  {'✅' if not e2 else '❌'} M2 落地根：仓外 + 0700")
    for e in e2:
        print(f"       {e}")
    errs += e2

    if not root.exists():
        untested.append(f"落地根不在盘上：{root} —— 指纹无从比对")
        print(f"  ⚠ M3 未测：{root} 不在盘上")
        print(f"  ⚠ M4 未测：同上")
    else:
        e3, readings, tally = check_m3(reg, root)
        print(f"  {'✅' if not e3 else '❌'} M3 指纹仍与落盘一致"
              f"（有内容 {tally['ok']} 份 · **空表 {tally['empty']} 份** · 未测 {tally['untested']} 份，逐份重算）")
        for e in e3:
            print(f"       {e}")
        errs += e3

        e4 = check_m4(reg, root)
        print(f"  {'✅' if not e4 else '❌'} M4 仓内没有正文片段")
        for e in e4:
            print(f"       {e}")
        errs += e4

    # M5 不依赖落地根 —— 它验的是抓取脚本仍在去填充
    e5 = check_m5()
    print(f"  {'✅' if not e5 else '❌'} M5 抓取脚本仍带着去填充（+4096 的唯一修法）")
    for e in e5:
        print(f"       {e}")
    errs += e5

    print()
    if errs:
        print(f"❌ {len(errs)} 项红" + (f" · ⚠ {len(untested)} 项未测" if untested else ""))
        return 1
    if untested:
        print(f"⚠ {len(untested)} 项未测 —— 退 2（不是通过）")
        for u in untested:
            print(f"   ⚠ {u}")
        return 2
    print(f"✅ 全过（{len(reg['items'])} 份登记 / 其中**有内容的 {tally['ok']} 份** · 空表 {tally['empty']} 份 · 正文在仓外 · 指纹一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
