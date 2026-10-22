#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_asr_no_diarization.py —— 行 124：ASR 不做说话人分离（依赖侧）

## 行 124 四条与覆盖（结论：三条无对象）

| 要求 | 状态 |
|---|---|
| ① 多人音频跑 ASR，所有语音片段都在输出里（对照人工转写片段数） | ❌ **无对象**：无 ASR 后端、无音频素材、无人工转写基线 |
| ② 每段带 `start`/`end` | ❌ 无对象：`tools/benchmark_media.py:274` 把 segments 拼成扁平串，接口无分段位 |
| ③ `speaker` 存在且为 `unknown` | ❌ 无对象：`speaker` 在可执行代码里 0 命中；`normalizer.py:440-443` 只判 `asr.timecodes` 真值 |
| 全仓无 diarization 依赖 | ✅ **A124**：扫 pyproject / uv.lock / 可执行 import |

**五类通道（为什么 ①②③ 是无对象）**：
1. 直接 import：`faster_whisper / whisper / pyannote / torch` 的 `find_spec` 全为 None。
2. 传递依赖：`tools/benchmark_media.py` 调的是外部 CLI 约定，不是仓内模块。
3. 代码实现：`base/media.py:824 video_stage()` 恒 `cannot_measure`，没有转写分支。
4. 数据：`git ls-files` 的音视频文件 0 个（全盘同样 0）。
5. 运行时：`normalizer.py` 只读 `asr.timecodes` 的真值；`speaker` 传进来会被静默忽略。

所以 #124 不映射。本文件只把**有对象的**那一条（依赖侧无 diarization）做成执行点。
等 ASR 后端与音频素材到位，①②③ 才有可断言的对象。

退出码：0 / 1 / 2（文件读不出）。
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PYPROJECT = ROOT / "pyproject.toml"
UVLOCK = ROOT / "uv.lock"
SCAN_DIRS = (ROOT / "base", ROOT / "api", ROOT / "tools")
#: 说话人分离（diarization）相关依赖特征。逐个点名，不用模糊匹配。
DIARIZATION = (
    "pyannote", "pyannote.audio", "speaker-diarization", "speaker_diarization",
    "resemblyzer", "wespeaker", "nemo_toolkit", "nemo", "diarization",
)
EXCLUDE_PARTS = {"__pycache__", "node_modules", "skills-inventory", ".venv"}


class Untested(Exception):
    pass


def read_pyproject() -> str:
    if not PYPROJECT.is_file():
        raise Untested(f"没有 pyproject.toml：{PYPROJECT}")
    return PYPROJECT.read_text(encoding="utf-8")


def check_pyproject(text: str) -> list[str]:
    """A124a：pyproject 的依赖组里不许出现 diarization 包。"""
    try:
        d = tomllib.loads(text)
    except Exception as e:  # noqa: BLE001
        return [f"A124a pyproject.toml 解析失败：{e}"]
    problems = []
    groups = {}
    project = d.get("project") or {}
    groups["dependencies"] = project.get("dependencies") or []
    groups["optional-dependencies"] = project.get("optional-dependencies") or {}
    groups["dependency-groups"] = d.get("dependency-groups") or {}
    flat = []
    for k, v in groups.items():
        if isinstance(v, list):
            flat += [(k, x) for x in v if isinstance(x, str)]
        elif isinstance(v, dict):
            for g, items in v.items():
                flat += [(f"{k}.{g}", x) for x in (items or []) if isinstance(x, str)]
    for where, dep in flat:
        low = dep.lower()
        if any(tok in low for tok in DIARIZATION):
            problems.append(f"A124a {where} 里出现 diarization 依赖：{dep!r}")
    return problems


def check_lock(text: str) -> list[str]:
    """A124b：uv.lock 里不许有 diarization 包。"""
    hits = [tok for tok in DIARIZATION if re.search(rf'(?i)\b{re.escape(tok)}\b', text)]
    return [f"A124b uv.lock 里出现 diarization 包特征：{hits}"] if hits else []


def strip_comments(src: str) -> str:
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln for ln in src.splitlines() if not ln.strip().startswith("#"))


def check_imports(sources: dict[str, str]) -> list[str]:
    """A124c：可执行源码的 import 行里不许出现 diarization 包。"""
    problems = []
    pat = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", re.M)
    for rel, src in sources.items():
        for m in pat.finditer(strip_comments(src)):
            mod = m.group(1).lower()
            if any(mod == tok or mod.startswith(tok + ".") for tok in DIARIZATION):
                problems.append(f"A124c {rel} 导入了 diarization 模块：{m.group(1)}")
    return problems


def collect_sources() -> dict[str, str]:
    out = {}
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            if any(part in EXCLUDE_PARTS for part in p.parts):
                continue
            try:
                out[str(p.relative_to(ROOT))] = p.read_text(encoding="utf-8")
            except OSError:
                continue
    return out


def assess(pyproject: str, lock_text: str, sources: dict[str, str]) -> list[str]:
    return check_pyproject(pyproject) + check_lock(lock_text) + check_imports(sources)


def controls() -> int:
    good_py = '[project]\nname="x"\ndependencies=["fastapi>=0.1"]\n'
    bad_py = '[project]\nname="x"\ndependencies=["pyannote.audio==3.1"]\n'
    good_src = {"base/x.py": "from fastapi import FastAPI\n# from pyannote.audio import Pipeline 注释不算\n"}
    bad_src = {"base/x.py": "from pyannote.audio import Pipeline\n"}

    def red(frag, py=good_py, lock="", src=None):
        return any(frag in p for p in assess(py, lock, src or good_src))

    cases = [
        ("正样本：依赖里没有 diarization → 必须绿",
         lambda: not assess(good_py, "", good_src)),
        ("★ A124a 坏样本：pyproject 加 pyannote.audio → 必须红",
         lambda: red("A124a", py=bad_py)),
        ("★ A124c 坏样本：源码 import pyannote → 必须红",
         lambda: red("A124c", src=bad_src)),
        ("★ A124b 坏样本：lock 里出现 pyannote → 必须红",
         lambda: red("A124b", lock='name = "pyannote.audio"\n')),
        ("反向对照：只出现在整行注释里 → 不许误报",
         lambda: not check_imports({"base/x.py": "# from pyannote.audio import X\nimport json\n"})),
    ]
    bad = 0
    print("=" * 78)
    print("行 124 · ASR 无说话人分离（依赖侧，离线）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            bad += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if bad:
        print(f"❌ {len(cases)} 项中 {bad} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    try:
        py = read_pyproject()
        lock = UVLOCK.read_text(encoding="utf-8") if UVLOCK.is_file() else ""
        sources = collect_sources()
        problems = assess(py, lock, sources)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 124 · ASR 无说话人分离（依赖侧）")
    print("=" * 78)
    print(f"  扫描：pyproject.toml + uv.lock{'（缺失）' if not lock else ''} + {len(sources)} 个 .py")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：依赖与 import 层没有 diarization。")
    print("   ⚠️ 行 124 的片段完整性 / start-end / speaker=unknown 三条**无对象**")
    print("      （无 ASR 后端、无音频素材、接口无分段位），#124 不映射。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
