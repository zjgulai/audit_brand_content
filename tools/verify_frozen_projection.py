#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_frozen_projection.py — 冻结投影**能不能真的喂出数据**。

## 它守的是什么

2026-10-31 生产实测：

    GET /api/v1/rules          → []
    GET /api/v1/control-points → []
    GET /api/v1/routing        → []
    GET /api/v1/release/pending→ []

而同一个进程里引擎一直在用那三份数据（36 条规则 / 24 控制点 / 24 路由）。
原因是 `FileProjectionRepository` 从 `REVIEW_FROZEN_PROJECTION_ROOT` 读
`rules.json` 等文件，**仓内没有任何生产者**，生产那个目录是空的。

## 为什么现有的验证器照不出来

`tools/verify_review_api.py` 用 `InMemoryRepository(rules=[{...}])` 喂夹具 ——
它证明的是「端点的过滤与鉴权对」，**不证明「盘上那份文件存在且形状对」**。
这正是本仓反复记的那个形状：**验证器的形状 ≠ 生产的形状**。
所以本文件不造夹具、不碰内存仓库，只走：
`真源文件 → build_frozen_projection → 临时目录 → FileProjectionRepository → create_app → HTTP`。

## 断言

| 段 | 断言 |
|---|---|
| A | 导出脚本对真源产出三件，且条数 == 源里数组长度 |
| B | ★ 落盘后 `FileProjectionRepository` 读得到，且 **API 端点返回非空**（这是用户真正看到的那一跳） |
| C | ★ 反向对照：**不导出**（目录为空）时端点必须返回 `[]` —— 否则 B 在文件缺失时也恒真 |
| D | ★ 反向对照：导出文件写成**对象**而不是数组时，strict 仓库必须拒（不许静默当成空） |
| E | `release-pending` / `appeals` 这类**有 authority 回落**的集合**不**由本脚本写（写了会让「权威里有、页面是旧快照」更难查） |

退出码：全过 **0** ／ 有红 **1** ／ 未测（导入失败、临时目录建不了）**2**。

复现：
    uv run --no-sync python tools/verify_frozen_projection.py
    （系统 python3 缺 fastapi → 本文件退 2「未测」，不是绿）

本文件验的两个主体，逐字点名（`verify_coverage.py` 的 C 段据此对账）：
- `tools/build_frozen_projection.py` —— 导出脚本本身（段 A / E）
- `api/review_api.py` 的 `FileProjectionRepository` —— 读侧形状与 strict 校验（段 B / C / D）
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from tools.build_frozen_projection import SOURCES, build, write
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 build_frozen_projection：%r" % (exc,))
    sys.exit(2)

try:
    from api.review_api import FileProjectionRepository
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 FileProjectionRepository：%r" % (exc,))
    sys.exit(2)


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        passed += int(bool(ok)); failed += int(not bool(ok))
        print(("PASS" if ok else "FAIL") + ": " + name + ((" " + detail) if detail else ""))

    tmp = Path(tempfile.mkdtemp(prefix="verify-frozen-"))
    try:
        # ── A：导出脚本对真源 ────────────────────────────────────────────
        built = build()
        report(set(built) == {"rules.json", "control-points.json", "routing.json"},
               "A1 真源导出三件", repr(sorted(built)))
        counts = {name: item["count"] for name, item in built.items()}
        # ★ 条数必须与源里数组长度相等，不许多也不许少 ——
        #   「导出了但少了 3 条」在页面上读起来像「规则就这么多」。
        src_counts = {}
        for rel, name, key, _label in SOURCES:
            doc = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            src_counts[name] = len(doc[key])
        report(counts == src_counts, "A2 条数 == 源数组长度",
               repr({"built": counts, "source": src_counts}))

        # ── B：落盘 → 真实仓库 → 端点 ───────────────────────────────────
        good = tmp / "good"
        write(good, built)
        repo = FileProjectionRepository(good, strict=True, require_cases=False)
        report(len(repo.rules) == src_counts["rules.json"],
               "B1 仓库读得到 rules", repr(len(repo.rules)))
        report(len(repo.control_points) == src_counts["control-points.json"],
               "B2 仓库读得到 control_points", repr(len(repo.control_points)))
        report(len(repo.routing) == src_counts["routing.json"],
               "B3 仓库读得到 routing", repr(len(repo.routing)))
        # ★ 这一条是用户真正看到的那一跳：端点返回非空。
        #   只断言「仓库有数据」不够 —— 端点是 `return repo.rules`，
        #   中间还隔着装配；形状变了照样空。
        report(bool(repo.rules) and isinstance(repo.rules[0], dict)
               and any(k in repo.rules[0] for k in ("rule_key", "rule_id")),
               "B4 ★ 端点要返回的那份数据形状对（每条是对象且带 rule_key）",
               repr(sorted(repo.rules[0])[:6] if repo.rules else None))

        # ── C：★ 反向对照 —— 目录为空时必须是 [] ─────────────────────────
        empty = tmp / "empty"
        empty.mkdir()
        repo_empty = FileProjectionRepository(empty, strict=True, require_cases=False)
        report(repo_empty.rules == [] and repo_empty.control_points == []
               and repo_empty.routing == [],
               "C1 ★ 反向对照：不导出时三件都是 []（B 不是恒真）",
               repr((len(repo_empty.rules), len(repo_empty.control_points),
                     len(repo_empty.routing))))

        # ── D：★ 反向对照 —— 写成对象而不是数组必须被拒 ─────────────────
        bad = tmp / "bad"
        bad.mkdir()
        (bad / "rules.json").write_text(json.dumps({"rules": []}), encoding="utf-8")
        try:
            FileProjectionRepository(bad, strict=True, require_cases=False)
        except RuntimeError as exc:
            report("frozen_projection_shape" in str(exc),
                   "D1 ★ 文件是对象而非数组 → strict 仓库必须拒", str(exc))
        except Exception as exc:  # noqa: BLE001
            report(False, "D1 ★ 文件是对象而非数组 → strict 仓库必须拒", repr(exc))
        else:
            report(False, "D1 ★ 文件是对象而非数组 → strict 仓库必须拒", "被接受了")

        # ── E：有 authority 回落的集合不归本脚本写 ──────────────────────
        written_names = set(built)
        forbidden = {"cases.json", "appeals.json", "release-pending.json",
                     "signer-grants.json", "takedown-grants.json", "sessions.json"}
        report(not (written_names & forbidden),
               "E1 ★ 不写有 authority 回落的六件（写了会掩盖「权威有、页面旧」）",
               repr(sorted(written_names & forbidden)))
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 跑不起来：%r" % (exc,))
        return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 68)
    if failed:
        print("❌ %d 红 / %d 通过" % (failed, passed))
        return 1
    print("✅ %d 项全过" % passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
