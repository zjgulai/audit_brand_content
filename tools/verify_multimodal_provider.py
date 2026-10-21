#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_multimodal_provider.py —— `base/multimodal_provider.py` 的自证（**零网络**）

验的是那一层的三条硬承诺：

  1. **没接能力 != 通过**：空注册表、空任务、任务不支持、`ok` 却没有可复核观察
     —— 全都必须落成 `untested`，不许是 `ok`、`[]`、`None`。
  2. **先授权，后出境**：未授权时**一次 provider 都不许调**。不是「先调了再报告」。
  3. **出境清单只描述「若启用会送出什么」**，且 `actual_egress_status`
     只有 `none` / `untested` 两个值 —— 不许写成「没有出境」。

--------------------------------------------------------------------------
★ 为什么要做变异测试（E 段）
--------------------------------------------------------------------------
A–D 段是「喂样本看结果」。它们有一个共同的盲点：**把守卫删掉，样本可能照样过**，
只要样本没走到那条分支。本项目 §2.4 的原话是「名字出现过 != 拦得住」。

所以 E 段对源码做 **12 次单点删除**（每次只改一个锚点，锚点唯一性先断言），
在子进程里重新 import 被改过的副本，然后检查**那个缺陷是不是真的出现了**：

  * 缺陷出现了  → 这条守卫是真的在执行点上，✓
  * 缺陷没出现  → 我改的地方跟那条断言无关，**这条断言是假的**，✗

反向对照本身也有反面对照：`--selftest-of-selftest` 会喂一个**什么都没改**的副本，
此时 12 条必须**全部报「缺陷没出现」**，否则说明探针恒真。

退出码：0 全过 / 1 有红 / 2 未测（导入失败或子进程不可用）
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "base" / "multimodal_provider.py"

sys.path.insert(0, str(ROOT))

try:
    from base import multimodal_provider as M
except Exception as exc:  # noqa: BLE001
    print("⚠ 未测：import base.multimodal_provider 失败（%s: %s）"
          % (type(exc).__name__, exc), file=sys.stderr)
    sys.exit(2)


# ══════════════════════════════════════════════════════════════════════════
# 变异表：锚点 → 替换成什么 → 探针（缺陷出现时返回 True）
#
# ★ 每个锚点在源码里必须**恰好出现一次**。出现 0 次 = 源码变了，我的断言失锚；
#   出现 >1 次 = 替换会波及别处，读数不可归因。两种情况都直接红。
# ══════════════════════════════════════════════════════════════════════════

MUTATIONS = [
    (
        "M1",
        "空注册表返回 untested",
        "    return _base_result(\n"
        "        status=STATUS_UNTESTED,\n"
        "        reason=reason,\n"
        "        reason_code=reason_code,",
        "    return _base_result(\n"
        "        status=STATUS_OK,\n"
        "        reason=reason,\n"
        "        reason_code=reason_code,",
        """
reg = m.ProviderRegistry()
r = reg.analyze(m.MediaRef(uri="x://a"), ["scene_semantics"])
defect = (r.get("status") == m.STATUS_OK)
""",
    ),
    (
        "M2",
        "没有任务状态时不返回 ok",
        "        # 没有任务状态时绝不能返回 ok —— 那等于「什么都没做，但我宣布通过」。\n"
        "        return STATUS_UNTESTED",
        "        # 没有任务状态时绝不能返回 ok —— 那等于「什么都没做，但我宣布通过」。\n"
        "        return STATUS_OK",
        """
defect = (m._worst_status() == m.STATUS_OK)
""",
    ),
    (
        "M3",
        "authorized 键集合必须等于 required",
        "        if set(required) != set(authorized):",
        "        if False:",
        """
# ★ 探「多出键」而不是「缺键」。两个方向都试过，只有前者是干净的判据：
#   删掉这道守卫后，缺键会抛 KeyError —— 那是意外崩溃，不是被设计成拒绝，
#   用它当判据等于把「崩了」记成「守住了」。而多出的键会被**静默接受**，
#   并且真的进到 egress_manifest 的 authorized 里，是一个会对外说谎的登记项。
defect = False
try:
    reg = m.ProviderRegistration(
        provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
        recipient="r", required_authorizations={"scene_semantics": ("s",)},
        authorized={"scene_semantics": False, "av_alignment": True},
    )
    defect = "av_alignment" in reg.to_manifest_entry()["authorized"]
except ValueError:
    defect = False
""",
    ),
    (
        "M4",
        "authorized=True 时 granted 必须真有那些 scope",
        "                if absent:",
        "                if False:",
        """
defect = False
try:
    m.ProviderRegistration(
        provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
        recipient="r", required_authorizations={"scene_semantics": ("egress:audio",)},
        authorized={"scene_semantics": True}, granted_authorizations=(),
    )
    defect = True               # 声明已授权但一项都没授，却构造成功
except ValueError:
    defect = False
""",
    ),
    (
        "M5",
        "纵深防御：authorized 被绕过时仍查 granted",
        "        if missing:",
        "        if False:",
        """
reg = m.ProviderRegistration(
    provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"scene_semantics": ("egress:frames",)},
    authorized={"scene_semantics": True}, granted_authorizations=("egress:frames",),
)
# 绕过 frozen 直接改内部：构造时校验通过，调用时必须再拦一次
object.__setattr__(reg, "granted_authorizations", ())
registry = m.ProviderRegistry()
registry.register(reg, type("P", (), {"provider_id": "p",
                                      "analyze": lambda self, media, tasks: {}})())
defect = False
try:
    registry.require_authorization("p", "scene_semantics")
    defect = True               # 守卫没了，篡改过的登记项被放行
except m.NotAuthorized:
    defect = False
""",
    ),
    (
        "M6",
        "sha256 必须真是 64 位十六进制",
        "    if len(candidate) != 64:\n        return None",
        "    if False:\n        return None",
        """
defect = False
try:
    ref = m.MediaRef(uri="x://a", sha256="abc")
    defect = (ref.sha256 == "abc")   # 长度不对却当成内容指纹收下了
except ValueError:
    defect = False
""",
    ),
    (
        "M7",
        "占位词不许当接收方 / 标识",
        "    if value.strip().lower() in _PLACEHOLDERS:",
        "    if False:",
        """
defect = False
try:
    m.EgressItem(item_id="系统", description="d")
    defect = True               # 「系统」这种假登记被收下了
except ValueError:
    defect = False
""",
    ),
    (
        "M8",
        "ok 没有 observations 必须降级为 untested",
        "    if status == STATUS_OK and not isinstance(observations_raw, list):",
        "    if False:",
        """
reg = m.ProviderRegistration(
    provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"scene_semantics": ("s",)},
    authorized={"scene_semantics": True}, granted_authorizations=("s",),
)
class P:
    provider_id = "p"
    def analyze(self, media, tasks):
        return {"tasks": {"scene_semantics": {"status": "ok"}}}   # 没有任何观察
registry = m.ProviderRegistry()
registry.register(reg, P())
# ★ 必须带 kind：不带的话会先被介质闸门挡成 untested，
#   探针就永远走不到 observations 那条路径（假红）。
r = registry.analyze(m.MediaRef(uri="x://a", kind="image/png"), ["scene_semantics"])
defect = (r["results"]["scene_semantics"]["status"] == "ok")
""",
    ),
    (
        "M9",
        "重复注册必须拒",
        "        if provider_id in self._providers:",
        "        if False:",
        """
reg = m.ProviderRegistration(
    provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"scene_semantics": ("s",)},
    authorized={"scene_semantics": True}, granted_authorizations=("s",),
)
class P:
    provider_id = "p"
    def analyze(self, media, tasks): return {"tasks": {}}
registry = m.ProviderRegistry()
registry.register(reg, P())
defect = False
try:
    registry.register(reg, P())
    defect = (len(registry.egress_manifest()) == 2) or True
except ValueError:
    defect = False
""",
    ),
    (
        "M10",
        "注册时不收空壳（必须有 analyze）",
        '        analyze = getattr(provider, "analyze", None)',
        "        analyze = lambda *a, **k: {}",
        """
reg = m.ProviderRegistration(
    provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"scene_semantics": ("s",)},
    authorized={"scene_semantics": True}, granted_authorizations=("s",),
)
registry = m.ProviderRegistry()
defect = False
try:
    registry.register(reg, object())     # 没有 analyze
    defect = True
except TypeError:
    defect = False
""",
    ),
    (
        "M11",
        "actual_egress_status 只有 none / untested",
        '    if actual_egress_status not in ("none", STATUS_UNTESTED):',
        "    if False:",
        """
defect = False
try:
    b = m._policy_boundary("ok")     # 一个不存在的状态被接受了
    defect = (b["actual_egress_status"] == "ok")
except ValueError:
    defect = False
""",
    ),
    (
        "M12",
        "授权闸门必须在 provider 调用之前",
        "        for task in executed:\n"
        "            self.require_authorization(provider_id, task)",
        "        pass",
        """
called = {"n": 0}
reg = m.ProviderRegistration(
    provider_id="p", egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"scene_semantics": ("s",)},
    authorized={"scene_semantics": False},     # 未授权
)
class P:
    provider_id = "p"
    def analyze(self, media, tasks):
        called["n"] += 1
        return {"tasks": {"scene_semantics": {"status": "ok", "observations": []}}}
registry = m.ProviderRegistry()
registry.register(reg, P())
try:
    # ★ 带 kind，理由同 M8：介质闸门在授权闸门**之后**，
    #   但不带 kind 会让「删掉授权闸门」之后仍被介质挡住，探针假红。
    registry.analyze(m.MediaRef(uri="x://a", kind="image/png"), ["scene_semantics"])
except m.NotAuthorized:
    pass
defect = (called["n"] > 0)      # 未授权却先出境了
""",
    ),
    (
        "M13",
        "出境清单按任务收窄",
        "        if task is None:\n"
        "            return self.egress_items\n"
        "        return tuple(item for item in self.egress_items if item.applies_to(task))",
        "        return self.egress_items",
        """
# 删掉收窄后，只跑静图的部署也会在清单里看到音轨。
reg = m.ProviderRegistration(
    provider_id="p",
    egress_items=(
        m.EgressItem(item_id="frames", description="帧", data_class="internal"),
        m.EgressItem(item_id="audio_track", description="音轨", data_class="pii",
                     tasks=("av_alignment",)),
    ),
    recipient="r",
    required_authorizations={"scene_semantics": ("s",), "av_alignment": ("s",)},
    authorized={"scene_semantics": True, "av_alignment": True},
    granted_authorizations=("s",),
)
registry = m.ProviderRegistry()
class P:
    provider_id = "p"
    def analyze(self, media, tasks): return {"tasks": {}}
registry.register(reg, P())
entry = registry.egress_manifest("scene_semantics")[0]
defect = any(i["item_id"] == "audio_track" for i in entry["egress_items"])
""",
    ),
    (
        "M14",
        "介质闸门在调用前拦截",
        "        lacking = {\n"
        "            task: _missing_media(task, media)\n"
        "            for task in executed\n"
        "            if _missing_media(task, media)\n"
        "        }\n"
        "        if lacking:",
        "        lacking = {}\n"
        "        if False:",
        """
# 删掉介质闸门后，缺音轨的请求会被放行给 provider。
called = {"n": 0}
reg = m.ProviderRegistration(
    provider_id="p",
    egress_items=(m.EgressItem(item_id="f", description="d"),),
    recipient="r", required_authorizations={"av_alignment": ("s",)},
    authorized={"av_alignment": True}, granted_authorizations=("s",),
)
class P:
    provider_id = "p"
    def analyze(self, media, tasks):
        called["n"] += 1
        return {"tasks": {t.value: {"status": "ok", "observations": []} for t in tasks}}
registry = m.ProviderRegistry()
registry.register(reg, P())
r = registry.analyze(m.MediaRef(uri="x://a", kind="video/mp4"), ["av_alignment"])
defect = (called["n"] > 0 and r.get("status") != m.STATUS_UNTESTED)
""",
    ),
    (
        "M15",
        "kind/mime 都空时按「缺」处理",
        "    required = task.required_media\n"
        "    if not required:\n"
        "        return ()\n"
        "    declared = set(_declared_media(media))\n"
        "    return tuple(medium for medium in required if medium not in declared)",
        "    return ()",
        """
# 删掉判据后，「什么都没声明」会被当成「什么都不缺」——
# 正是「没测被读成通过」的那一步。
media = m._describe_media_ref(m.MediaRef(uri="x://a"))     # kind/mime 全空
defect = (m._missing_media(m.MultimodalTask.AV_ALIGNMENT, media) == ())
""",
    ),
    (
        "M16",
        "data_class 只接受四个分级",
        "        if data_class not in DATA_CLASSES:",
        "        if False:",
        """
# 删掉这道守卫后，任意字符串都能当分级收下 ——
# 审计读到的「这一项是 internal 还是 pii」就变成调用方随手写的字。
defect = False
try:
    m.EgressItem(item_id="x", description="d", data_class="weird")
    defect = True
except ValueError:
    defect = False
""",
    ),
]

PROBE_TEMPLATE = '''\
import importlib.util, json, sys
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("mutmod", path)
m = importlib.util.module_from_spec(spec)
sys.modules["mutmod"] = m
spec.loader.exec_module(m)
defect = False
try:
%s
except Exception:
    defect = False
print(json.dumps({"defect": bool(defect)}))
sys.exit(0 if defect else 1)
'''


def _probe(src_path: Path, body: str) -> bool:
    """在子进程里 import 一份源码副本，返回「那个缺陷是否真的出现了」。"""
    code = PROBE_TEMPLATE % "\n".join("    " + ln if ln.strip() else ln
                                      for ln in body.strip().splitlines())
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as fh:
        probe_path = Path(fh.name)
        fh.write(code)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(probe_path), str(src_path)],
            capture_output=True, text=True, timeout=90,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError("探针异常退出 rc=%d：%s"
                               % (proc.returncode, (proc.stderr or "")[-300:]))
        line = (proc.stdout or "").strip().splitlines()
        if not line:
            raise RuntimeError("探针没有输出（stderr：%s）"
                               % (proc.stderr or "")[-300:])
        return bool(json.loads(line[-1])["defect"])
    finally:
        probe_path.unlink(missing_ok=True)


def main() -> int:
    results = []

    def add(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    def expect_raise(name, fn, exc_type, detail=""):
        try:
            fn()
        except exc_type as exc:
            add(name, True, "%s: %s" % (type(exc).__name__, str(exc)[:56]))
        except Exception as exc:  # noqa: BLE001
            add(name, False, "抛了别的 %s：%s（要的是 %s）"
                % (type(exc).__name__, str(exc)[:40], exc_type.__name__))
        else:
            add(name, False, "**没有拒** —— 这条断言是假的 " + detail)

    src = SRC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # ══════════════════════════════════════════════════════════════════
    # A. 零网络 / 零副作用（静态）
    # ══════════════════════════════════════════════════════════════════
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    NET = {"requests", "httpx", "aiohttp", "urllib", "urllib3", "socket",
           "openai", "anyio", "http", "websocket", "ftplib", "smtplib"}
    FS = {"os", "sys", "pathlib", "subprocess", "shutil", "tempfile", "io"}

    add("A1 ★ 不 import 任何网络库", not (imported & NET),
        "命中 %s" % sorted(imported & NET))
    add("A2 ★ 不 import 任何文件/环境通道（本层不碰盘）", not (imported & FS),
        "命中 %s" % sorted(imported & FS))

    urls = [n.value[:40] for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and ("http://" in n.value or "https://" in n.value)]
    add("A3 ★ 源码里没有 URL 字面量", not urls, "命中 %s" % urls[:3])

    # ══════════════════════════════════════════════════════════════════
    # B. 「没接能力 != 通过」
    # ══════════════════════════════════════════════════════════════════
    empty = M.ProviderRegistry()

    r = empty.analyze(M.MediaRef(uri="x://a"), ["scene_semantics"])
    add("B1 ★ 空注册表 → status=untested（不是 ok / [] / None）",
        r.get("status") == M.STATUS_UNTESTED, "status=%r" % r.get("status"))
    add("B2 ★ untested 必须带非空 reason",
        isinstance(r.get("reason"), str) and bool(r["reason"].strip()),
        repr(r.get("reason"))[:52])
    add("B3 ★ untested 的每个任务结果也不许是 ok",
        all(t.get("status") != M.STATUS_OK for t in r["results"].values()),
        str({k: v.get("status") for k, v in r["results"].items()})[:60])

    r2 = empty.analyze(M.MediaRef(uri="x://a"), [])
    add("B4 ★ 空任务集 → untested（不是「没有任务所以通过」）",
        r2.get("status") == M.STATUS_UNTESTED,
        "status=%r reason_code=%r" % (r2.get("status"), r2.get("reason_code")))

    add("B5 ★ 三态互异：ok / untested / error",
        len({M.STATUS_OK, M.STATUS_UNTESTED, M.STATUS_ERROR}) == 3, "")

    expect_raise("B6 ★ 未知任务 → ValueError（不许静默忽略）",
                 lambda: M.normalize_tasks(["no_such_task"]), ValueError)
    expect_raise("B7 ★ tasks=None → TypeError（不是「没有任务」）",
                 lambda: M.normalize_tasks(None), TypeError)

    # 重复任务去重（否则同一任务算两次、重复出境）
    add("B8 重复任务去重", len(M.normalize_tasks(
        ["scene_semantics", "scene_semantics"])) == 1, "")

    # ══════════════════════════════════════════════════════════════════
    # C. 授权闸门
    # ══════════════════════════════════════════════════════════════════
    def reg_of(pid, tasks, authorized, granted=(), items=None):
        return M.ProviderRegistration(
            provider_id=pid,
            egress_items=items or (M.EgressItem(
                item_id="frames", description="抽帧画面", data_class="confidential"),),
            recipient="example-provider（测试用，未接任何真实地址）",
            required_authorizations={t: ("egress:frames",) for t in tasks},
            authorized={t: authorized for t in tasks},
            granted_authorizations=granted,
        )

    reg_denied = reg_of("p-denied", ["scene_semantics"], False)
    reg_allowed = reg_of("p-allowed", ["scene_semantics"], True, ("egress:frames",))

    # C1 默认未授权 → 拒，且点名缺什么
    try:
        M.ProviderRegistry().register(reg_denied, type("P", (), {
            "provider_id": "p-denied",
            "analyze": lambda self, media, tasks: {"tasks": {}}})())
        g = M.ProviderRegistry()
        g.register(reg_denied, type("P", (), {
            "provider_id": "p-denied",
            "analyze": lambda self, media, tasks: {"tasks": {}}})())
        g.require_authorization("p-denied", "scene_semantics")
        add("C1 ★ 默认未授权 → NotAuthorized", False, "**没有拒**")
    except M.NotAuthorized as exc:
        add("C1 ★ 默认未授权 → NotAuthorized", True,
            "缺 %s" % (list(exc.missing),))

    # C2 缺键构造即拒
    expect_raise("C2 ★ authorized 缺键 → 构造期 ValueError（缺键不许默认放行）",
                 lambda: M.ProviderRegistration(
                     provider_id="p", egress_items=(
                         M.EgressItem(item_id="f", description="d"),),
                     recipient="r",
                     required_authorizations={"scene_semantics": ("s",)},
                     authorized={}), ValueError)

    # C3 授权齐全 → 放行，且返回登记项本身
    try:
        got = M.ProviderRegistry.__new__(M.ProviderRegistry)
        got._providers = {}
        got.register(reg_allowed, type("P", (), {
            "provider_id": "p-allowed",
            "analyze": lambda self, media, tasks: {"tasks": {}}})())
        out = got.require_authorization("p-allowed", "scene_semantics")
        add("C3 授权齐全 → 放行且回登记项", out is reg_allowed, "")
    except Exception as exc:  # noqa: BLE001
        add("C3 授权齐全 → 放行且回登记项", False,
            "%s: %s" % (type(exc).__name__, exc))

    # C4 纵深防御：绕过 frozen 篡改 granted 后仍拒
    tampered = reg_of("p-tampered", ["scene_semantics"], True, ("egress:frames",))
    object.__setattr__(tampered, "granted_authorizations", ())
    g4 = M.ProviderRegistry()
    g4.register(tampered, type("P", (), {
        "provider_id": "p-tampered",
        "analyze": lambda self, media, tasks: {"tasks": {}}})())
    expect_raise("C4 ★ 纵深防御：登记项被篡改后仍拒（不是只靠构造期校验）",
                 lambda: g4.require_authorization("p-tampered", "scene_semantics"),
                 M.NotAuthorized)

    # C5 未登记的任务不许借用别的任务的授权
    expect_raise("C5 ★ 没为某任务登记授权 → 不许借用别的任务",
                 lambda: g4.require_authorization("p-tampered", "av_alignment"),
                 M.NotConfigured)

    # C6 「没配」与「没授权」是两个异常，不许合并
    add("C6 ★ NotConfigured 与 NotAuthorized 互不继承",
        not issubclass(M.NotConfigured, M.NotAuthorized)
        and not issubclass(M.NotAuthorized, M.NotConfigured), "")

    # C7 授权项为空 → 拒（否则闸门变装饰）
    expect_raise("C7 ★ required_authorizations 值为空 → 拒（闸门不许是装饰）",
                 lambda: M.ProviderRegistration(
                     provider_id="p", egress_items=(
                         M.EgressItem(item_id="f", description="d"),),
                     recipient="r",
                     required_authorizations={"scene_semantics": ()},
                     authorized={"scene_semantics": False}), ValueError)

    # ══════════════════════════════════════════════════════════════════
    # D. 出境清单
    # ══════════════════════════════════════════════════════════════════
    gm = M.ProviderRegistry()
    gm.register(reg_allowed, type("P", (), {
        "provider_id": "p-allowed",
        "analyze": lambda self, media, tasks: {"tasks": {}}})())

    man = gm.egress_manifest()
    add("D1 清单能列出 provider", len(man) == 1, "%d 条" % len(man))
    # ★ 2026-10-21 改：这条原先断言「清单里每项的 data_class 都合法」——
    #   而 `EgressItem.__post_init__` 在**构造期**就拒掉了非法值，
    #   所以清单里永远不可能出现非法 data_class。**它是一条恒真的断言**，
    #   从来没拦住过任何东西（§2.4「名字出现过 ≠ 拦得住」的又一例）。
    #
    #   现在改成断言「清单**忠实传递**每项的分级」：造两项分属不同分级的数据，
    #   看清单是不是原样带出去、有没有被默认值抹平。
    #   这条能红 —— 把 `to_dict()` 里的 data_class 换成常量就会红。
    graded = M.ProviderRegistration(
        provider_id="p-graded",
        egress_items=(
            M.EgressItem(item_id="frames", description="帧", data_class="internal"),
            M.EgressItem(item_id="audio", description="音轨", data_class="pii"),
        ),
        recipient="graded-vendor.example",
        required_authorizations={"av_alignment": ("s",)},
        authorized={"av_alignment": True}, granted_authorizations=("s",),
    )
    graded_entry = graded.to_manifest_entry()
    add("D2 ★ 清单忠实传递每项 data_class（不被默认值抹平）",
        {i["item_id"]: i["data_class"] for i in graded_entry["egress_items"]}
        == {"frames": "internal", "audio": "pii"}
        and graded_entry["data_classes"] == ["internal", "pii"], "")
    add("D3 ★ 接收方可指认（不是「云端」这类空话）",
        all(p.get("recipient") and p["recipient"].strip()
            and p["recipient"].strip().lower() not in M._PLACEHOLDERS for p in man), "")

    d1 = gm.egress_manifest_digest()
    add("D4 ★ 清单指纹稳定（同一配置两次相同）",
        d1 == gm.egress_manifest_digest() and len(d1) == 64, d1[:16])

    # 指纹不许受书写顺序影响
    ra = M.ProviderRegistration(
        provider_id="p-order",
        egress_items=(M.EgressItem(item_id="b", description="乙"),
                      M.EgressItem(item_id="a", description="甲")),
        recipient="r", required_authorizations={"scene_semantics": ("s",)},
        authorized={"scene_semantics": False})
    rb = M.ProviderRegistration(
        provider_id="p-order",
        egress_items=(M.EgressItem(item_id="a", description="甲"),
                      M.EgressItem(item_id="b", description="乙")),
        recipient="r", required_authorizations={"scene_semantics": ("s",)},
        authorized={"scene_semantics": False})
    add("D5 ★ 出境项书写顺序不影响指纹",
        ra.to_manifest_entry() == rb.to_manifest_entry(), "")

    add("D6 ★ 未授权 → would_egress=False（清单描述「若启用」）",
        man[0].get("would_egress") is True
        and reg_denied.to_manifest_entry().get("would_egress") is False,
        "denied would_egress=%r" % reg_denied.to_manifest_entry().get("would_egress"))

    # D7 actual_egress_status 只有两个合法值
    expect_raise("D7 ★ actual_egress_status 不许是 'ok' / 'none-sent' 等自造值",
                 lambda: M._policy_boundary("ok"), ValueError)

    rep = gm.egress_manifest_report()
    add("D8 ★ 报告里 manifest 与 digest 出自同一份对象（不会自相矛盾）",
        rep["digest_sha256"] == M._manifest_digest(rep["providers"]), "")

    # ══════════════════════════════════════════════════════════════════
    # E. 变异测试：把每道守卫单点删掉，缺陷必须真的出现
    # ══════════════════════════════════════════════════════════════════
    tmpdir = Path(tempfile.mkdtemp(prefix="mm-mut-"))
    try:
        for mid, label, anchor, replacement, body in MUTATIONS:
            n = src.count(anchor)
            if n != 1:
                add("%s ★ %s" % (mid, label), False,
                    "锚点出现 %d 次（应为 1）—— 断言已失锚" % n)
                continue
            # ★ 变异副本写进本次的临时目录，**不写进 base/**。
            #   写进 base/ 有两个后果：并发跑两次会互相覆盖（读到的可能是对方的变异体），
            #   中途被杀会在仓库里留下一个被改过的 .py。自证不许有副作用。
            mutated = tmpdir / ("_mut_%s.py" % mid)
            mutated.write_text(src.replace(anchor, replacement, 1), encoding="utf-8")
            try:
                present = _probe(mutated, body)
            except Exception as exc:  # noqa: BLE001
                add("%s ★ %s" % (mid, label), False,
                    "探针不可用（%s: %s）" % (type(exc).__name__, str(exc)[:70]))
                continue
            finally:
                mutated.unlink(missing_ok=True)
            add("%s ★ %s" % (mid, label), present,
                "删掉后缺陷出现 → 守卫在执行点上" if present
                else "**删掉后缺陷没出现 → 这条断言是假的**")

        # E 段自己的反向对照：一份什么都没改的副本，12 条必须全部「缺陷没出现」
        control = tmpdir / "_mut_control.py"
        control.write_text(src, encoding="utf-8")
        false_positives = []
        for mid, label, _a, _r, body in MUTATIONS:
            try:
                if _probe(control, body):
                    false_positives.append(mid)
            except Exception:  # noqa: BLE001
                false_positives.append(mid)
        # ★ 条数**算出来**，不写死。写死的数字一定过期 ——
        #   §2.2 第 1 条：文档里的数字要算出来。这里是同一个规矩，只是对象是断言而不是文档。
        #   本行原先写死「12 个」，加 M13–M15 之后它就成了假的。
        add("E0 ★ 反向对照：未改动的源码里 %d 个缺陷都不许出现" % len(MUTATIONS),
            not false_positives,
            "恒真的探针：%s" % false_positives if false_positives
            else "%d/%d 干净" % (len(MUTATIONS), len(MUTATIONS)))
    finally:
        for leftover in tmpdir.glob("*"):
            leftover.unlink(missing_ok=True)
        tmpdir.rmdir()

    # ══════════════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════════════
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 78)
    print("多模态契约自证（离线 · 零网络 · %d 项，含 %d 条变异对照）"
          % (total, len(MUTATIONS)))
    print("=" * 78)
    group = None
    for name, p, detail in results:
        g = name[0]
        if g != group:
            group = g
            print()
        print("  %s %-58s %s" % ("✓" if p else "✗", name, detail))
    print()
    if passed == total:
        print("✅ %d/%d 项全过（红项 0，未测 0）" % (passed, total))
        return 0
    reds = [n for n, p, _ in results if not p]
    print("✗ %d/%d 通过；红项 %d 条：%s" % (passed, total, len(reds), reds),
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print("⚠ 未测：验收器自身异常 %s: %s" % (type(exc).__name__, exc),
              file=sys.stderr)
        sys.exit(2)
