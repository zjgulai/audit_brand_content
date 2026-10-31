#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `research/governance/*.json` 导出成 `REVIEW_FROZEN_PROJECTION_ROOT` 下
API 直接返回的三个数组文件。

## 它补的是什么缺口

`api/review_api.py` 的 `FileProjectionRepository` 从冻结投影目录读九个文件
（`rules.json` / `control-points.json` / `routing.json` / `metrics.json` /
`appeals.json` / `release-pending.json` / `signer-grants.json` /
`takedown-grants.json` / `sessions.json`）。问题是：**仓内没有任何生产者**。
唯一会写投影的是 `web/scripts/seed_projection.py`，它只写
reports / notifications / takedown-tasks 三个。

后果（2026-10-31 生产实测）：

    GET /api/v1/rules          → []      规则词典「规则库」页签空
    GET /api/v1/control-points → []      控制点名册空
    GET /api/v1/routing        → []      处置路由表空

而引擎**一直在用**这三份数据（`base/rule_judge.py:39` 读
`research/governance/skeleton/rules-v1.json`，36 条规则 / 24 控制点 /
24 路由）。也就是说：同一个进程里，判定在跑，页面在空。

## 为什么是「导出」而不是「让 API 直接读源文件」

ADR/Playbook 要求规则可以独立于代码更新 —— 规则库是**运维可替换的投影**，
不是写死在镜像里的常量。让 API 直读 `research/` 会把「换规则」变成「重建镜像」，
而镜像里的 `research/` 是发版时固化的（见 Dockerfile 注释）。

所以这条边界保持不变：源文件在镜像里，导出产物在 `/data/projection`（可挂载、
可替换），API 只读后者。

## 用法

    python3 tools/build_frozen_projection.py --out /path/to/projection
    python3 tools/build_frozen_projection.py --out ... --dry-run
    python3 tools/build_frozen_projection.py --selftest

★ 不写 `cases.json`（新案件由 authority 提供）、不写 `appeals.json` /
`release-pending.json` / 名单三件（它们有 authority 回落，写死副本反而会
让「权威里明明有、页面却是旧快照」这种更难查的错）。只写**纯静态**的三件。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 源文件 → (导出文件名, 取哪个键)
SOURCES = (
    ("research/governance/skeleton/rules-v1.json", "rules.json", "rules",
     "规则库（P0/P1 字面与语义规则）"),
    ("research/governance/control-points-v1.json", "control-points.json",
     "control_points", "控制点名册（24 个控制点，含空族登记）"),
    ("research/governance/routing-v1.json", "routing.json", "routes",
     "处置路由表（控制点 → 谁接 / 谁结 / 到期 / 升级 / 申诉）"),
)


class BuildError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def _load(path):
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BuildError("source_unreadable", "%s (%s)" % (path, type(exc).__name__)) from exc
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise BuildError("source_not_json", str(path)) from exc
    if not isinstance(doc, dict):
        raise BuildError("source_shape", "%s 顶层必须是对象" % path)
    return doc, hashlib.sha256(raw).hexdigest()


def build(sources=SOURCES, root=ROOT):
    """返回 {文件名: (字节内容, 条数, 源 sha256)}。

    ★ 空列表**不许**当成成功：一个空数组写出去，页面上显示的是
      「当前分类下暂无记录」，与「还没有这条数据」长得一样。
      源文件里 `rules` 是空数组，说明源坏了，不是「今天没有规则」。
    """
    out = {}
    for rel, name, key, _label in sources:
        doc, src_sha = _load(Path(root) / rel)
        rows = doc.get(key)
        if not isinstance(rows, list):
            raise BuildError("source_key_missing", "%s 里没有数组 %r" % (rel, key))
        if not rows:
            raise BuildError(
                "source_empty",
                "%s 的 %r 是空数组 —— 源坏了，不许导出一份空名册出去" % (rel, key))
        body = (json.dumps(rows, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        out[name] = {
            "body": body,
            "count": len(rows),
            "source": rel,
            "source_sha256": src_sha,
            "key": key,
        }
    return out


def write(out_dir, built, *, dry_run=False):
    out_dir = Path(out_dir)
    written = []
    for name, item in sorted(built.items()):
        target = out_dir / name
        if dry_run:
            written.append((str(target), item["count"], "would_write"))
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        # 原子替换：先写临时文件再 rename，避免半截文件被 API 读到。
        fd, tmp = tempfile.mkstemp(dir=str(out_dir), prefix=".%s-" % name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(item["body"])
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
            tmp = None
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        written.append((str(target), item["count"], "written"))
    return written


def selftest():
    """离线自证：好样本必须能建、坏样本必须拒。跑一遍即见读数。"""
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        passed += int(bool(ok)); failed += int(not bool(ok))
        print(("PASS" if ok else "FAIL") + ": " + name + ((" " + detail) if detail else ""))

    tmp = Path(tempfile.mkdtemp(prefix="build-frozen-"))
    try:
        # S1 好样本：真源文件必须导出三个文件，条数非零
        built = build()
        report(set(built) == {"rules.json", "control-points.json", "routing.json"},
               "S1 真源导出三件", repr(sorted(built)))
        report(all(v["count"] > 0 for v in built.values()),
               "S2 三个文件都非空",
               repr({k: v["count"] for k, v in built.items()}))
        # S3 导出的内容必须能 JSON 解析回数组（不是包一层的对象）
        for name, item in built.items():
            parsed = json.loads(item["body"].decode("utf-8"))
            report(isinstance(parsed, list) and len(parsed) == item["count"],
                   "S3 %s 是数组且条数对" % name, repr(len(parsed) if isinstance(parsed, list) else type(parsed)))

        # S4 落盘后逐字读回
        written = write(tmp / "good", built)
        report(len(written) == 3, "S4 三个文件都写了", repr(len(written)))
        for name, item in built.items():
            on_disk = (tmp / "good" / name).read_bytes()
            report(on_disk == item["body"], "S4b %s 落盘逐字相同" % name)

        # S5 ★ 反向对照：源里 key 是空数组 → 必须拒（不许导出一份空名册）
        bad = tmp / "bad_empty.json"
        bad.write_text(json.dumps({"rules": []}), encoding="utf-8")
        try:
            build(sources=(("bad_empty.json", "rules.json", "rules", "x"),), root=tmp)
        except BuildError as exc:
            report(exc.code == "source_empty",
                   "S5 ★ 空数组源 → 拒（不是「今天没有规则」）", exc.code)
        else:
            report(False, "S5 ★ 空数组源 → 拒", "被接受了")

        # S6 ★ 反向对照：源里没有那个 key → 必须拒
        bad2 = tmp / "bad_key.json"
        bad2.write_text(json.dumps({"other": [1]}), encoding="utf-8")
        try:
            build(sources=(("bad_key.json", "rules.json", "rules", "x"),), root=tmp)
        except BuildError as exc:
            report(exc.code == "source_key_missing", "S6 ★ 缺 key → 拒", exc.code)
        else:
            report(False, "S6 ★ 缺 key → 拒", "被接受了")

        # S7 ★ 反向对照：文件不存在 → 拒（不是静默跳过）
        try:
            build(sources=(("nope.json", "rules.json", "rules", "x"),), root=tmp)
        except BuildError as exc:
            report(exc.code == "source_unreadable", "S7 ★ 源不存在 → 拒", exc.code)
        else:
            report(False, "S7 ★ 源不存在 → 拒", "被接受了")

        # S8 dry-run 不落盘
        written = write(tmp / "dry", built, dry_run=True)
        report(not (tmp / "dry").exists() and len(written) == 3,
               "S8 dry-run 不落盘", repr((tmp / "dry").exists()))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 68)
    if failed:
        print("❌ %d 红 / %d 通过" % (failed, passed))
        return 1
    print("✅ %d 项全过" % passed)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="导出冻结投影三件（规则/控制点/路由）")
    ap.add_argument("--out", help="投影目录，通常 REVIEW_FROZEN_PROJECTION_ROOT")
    ap.add_argument("--dry-run", action="store_true", help="只打印将写什么")
    ap.add_argument("--selftest", action="store_true", help="离线自证（不落盘）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.out:
        ap.error("必须给 --out（或 --selftest）")

    try:
        built = build()
    except BuildError as exc:
        print("❌ %s：%s" % (exc.code, exc.detail), file=sys.stderr)
        return 1
    print("源 → 导出（%s）" % ("dry-run" if args.dry_run else "写入"))
    for rel, name, key, label in SOURCES:
        item = built[name]
        print("  %-22s %3d 条  sha256:%s  %s" % (
            name, item["count"], item["source_sha256"][:12], label))
    for path, count, status in write(args.out, built, dry_run=args.dry_run):
        print("  %-11s %s  (%d 条)" % (status, path, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
