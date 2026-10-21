#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4-② 图片接线验收：media row → ContentUnit → RuleJudge/Orchestrator。

直接主体：base/media.py、base/normalizer.py、base/judge_entry.py、base/orchestrator.py。
ReviewIR schema 的真实产物对拍由 tools/verify_contracts.py B-8 负责，不在本器冒充。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import contract as C
    if os.environ.get("IMAGE_MEDIA_MODULE"):
        spec = importlib.util.spec_from_file_location(
            "image_media_under_test", os.environ["IMAGE_MEDIA_MODULE"])
        media = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(media)
        media.MEDIA = ROOT / "research" / "landing" / "_evidence" / "media"
    else:
        from base import media
    from base.judge_entry import judge_unit
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入图片判定链: %s" % exc)
    sys.exit(2)


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    rows = media.load_rows()
    if not rows:
        print("UNTESTED: 盘上没有图片样本")
        return 2

    # C0 真实样本全量走链；报告只出计数，不输出 OCR 正文或 URL。
    result = media.judge_rows(rows)
    report(result["rows"] == len(rows)
           and result["image_units"] == len(rows)
           and not result["failures"],
           "C0 盘上图片逐条产 ContentUnit", repr(result))
    report(result["entered_judgment"] == result["parse_status"].get("ok", 0),
           "C1 ok 图片全部进入 RuleJudge/Orchestrator", repr(result))
    report(result["parse_status"].get("failed", 0) >= 1
           and result["labels"].get("未审查", 0) >= 1,
           "C2 OCR 失败观测显式落 failed → 未审查", repr(result))
    report(set(result["labels"]) <= {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"},
           "C3 输出只用五标签", repr(result["labels"]))

    ok_row = next((r for r in rows if r.get("status") == "ok"), None)
    failed_row = next((r for r in rows if r.get("status") != "ok"), None)
    if ok_row is None or failed_row is None:
        print("UNTESTED: 样本缺成功或失败对照")
        return 2

    try:
        ok_result = media.judge_row(ok_row, "sample:image")
        failed_result = media.judge_row(failed_row, "sample:image")
    except Exception as exc:  # noqa: BLE001
        report(False, "C4/C5 成功与失败样本可走 judge_row",
               "%s: %s" % (type(exc).__name__, exc))
        ok_result = failed_result = None
    ok_unit = ok_result["unit"] if ok_result else {}
    failed_unit = failed_result["unit"] if failed_result else {}
    report(ok_result is not None
           and ok_unit["source"]["kind"] == "image"
           and ok_unit["parse_status"] == "ok"
           and ok_result["judgment"]["steps"] ==
           ["normalize", "judge", "dispose", "output", "evaluate"],
           "C4 成功样本 from_media → 五步固定顺序")
    report(failed_result is not None
           and failed_unit["parse_status"] == "failed"
           and failed_unit["failure_kind"] in C.FAILURE_KINDS
           and failed_result["judgment"]["label"] == "未审查"
           and failed_result["judgment"]["layer"] == "DP0"
           and failed_result["judgment"]["ir"]["content_unit_ref"]["failure_kind"]
           == failed_unit["failure_kind"],
           "C5 失败 unit/ReviewIR/decision 三层失败字段一致")
    report(ok_result is not None
           and "画面语义" in " ".join(ok_unit["textification"]["does_not_cover"])
           and ok_result["judgment"]["ir"]["coverage"]["coverage_state"] == "partial",
           "C6 图片只覆盖 OCR 文字，画面语义仍 partial")

    # R1 行为反向对照：断开 row_to_unit，judge_rows 必须报告失败而非假装 0 unit。
    original = media.row_to_unit
    try:
        media.row_to_unit = lambda _row, _uri: None
        broken = media.judge_rows([ok_row])
    finally:
        media.row_to_unit = original
    report(broken["image_units"] == 0 and len(broken["failures"]) == 1,
           "R1 断开 row_to_unit 接线 → 验收必红形状", repr(broken))

    # R2 源码执行点：judge_row 必须调用 row_to_unit，不能复制 builder 绕过。
    tree = ast.parse((ROOT / "base/media.py").read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "judge_row":
            calls = [n.func.id for n in ast.walk(node)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    report("row_to_unit" in calls,
           "R2 judge_row 源码真的调用 row_to_unit", repr(calls))

    # C7 judge_entry 必须使用唯一 RuleJudge，不得 import skeleton/judge。
    entry_tree = ast.parse((ROOT / "base/judge_entry.py").read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(entry_tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    report(any(name.endswith("rule_judge") for name in imported)
           and any(name.endswith("orchestrator") for name in imported)
           and not any("skeleton" in name or "judge_adapter" in name for name in imported),
           "C7 生产判定入口只 import RuleJudge/Orchestrator", repr(imported))

    # C8 from_media 显式空 does_not_cover 合法，但省略仍拒绝。
    empty = C.from_media(
        "image", b"x", "", uri="inline:empty", extractor="test",
        covers=["失败观测"], does_not_cover=[])
    try:
        C.from_media("image", b"x", "", uri="inline:missing", extractor="test",
                     covers=["失败观测"])
        omitted_denied = False
    except TypeError:
        omitted_denied = True
    report(empty["textification"]["does_not_cover"] == [] and omitted_denied,
           "C8 does_not_cover 显式空可用，省略仍拒绝")

    # C9 CLI/文件入口：直接接受实时附件临时路径，不要求 agent 拼 sample row。
    with tempfile.TemporaryDirectory(prefix="image-judge-") as td:
        path = Path(td) / "unit.json"
        path.write_text(json.dumps(ok_unit, ensure_ascii=False), encoding="utf-8")
        report(bool(ok_result) and path.is_file() and not C.validate(ok_unit),
               "C9 单图 unit 可序列化且契约合法")
        image_path = Path((ok_row.get("fetch") or {})["path"])
        try:
            file_result = media.judge_image_file(image_path, uri="inline:file-test")
        except Exception as exc:  # noqa: BLE001
            report(False, "C9b 实时图片文件路径可直接 OCR→判定",
                   "%s: %s" % (type(exc).__name__, exc))
            file_result = None
        report(file_result is not None
               and file_result["unit"]["source"]["kind"] == "image"
               and file_result["unit"]["source"]["uri"] == "inline:file-test"
               and file_result["judgment"]["label"] in
               {"BLOCK", "REVIEW", "未审查", "待自决", "PASS"},
               "C9b 实时图片文件路径可直接 OCR→判定")

    # M1 源码变异：临时副本断开 judge_row→row_to_unit，整份 verifier 必须 rc=1。
    if os.environ.get("IMAGE_MUTANT_CHILD") != "1":
        with tempfile.TemporaryDirectory(prefix="image-mutant-") as td:
            source = (ROOT / "base/media.py").read_text(encoding="utf-8")
            needle = "unit = row_to_unit(row, page_uri)"
            mutant = source.replace(needle, "unit = None", 1)
            mutant_path = Path(td) / "media_mutant.py"
            mutant_path.write_text(mutant, encoding="utf-8")
            env = os.environ.copy()
            env["IMAGE_MUTANT_CHILD"] = "1"
            env["IMAGE_MEDIA_MODULE"] = str(mutant_path)
            env["PYTHONPATH"] = os.pathsep.join(
                [str(ROOT), str(ROOT / "base"), env.get("PYTHONPATH", "")])
            child = subprocess.run(
                [sys.executable, __file__], cwd=str(ROOT), env=env,
                capture_output=True, text=True, timeout=300)
            report(needle in source and child.returncode == 1,
                   "M1 断开源码接线 → 同一 verifier rc=1（不是 0/2）",
                   "rc=%s" % child.returncode)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
