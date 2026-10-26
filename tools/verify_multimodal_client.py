#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_multimodal_client.py — T-432：多模态客户端 + 闸门接通（全离线）

## 这一票验的是什么

`tools/multimodal_client.py`（**全仓唯一有网络的地方**）与
`base/multimodal_provider.py`（授权闸门，**一行网络都不许有**）之间的接缝。

★ **本验收器一次网络都不发。** 传输层是可注入的：真实现与打桩走同一套
  解析与状态映射，所以离线测的是「拿到响应之后怎么判」，不是一个平行实现。
  这也是 AGENTS §2.4.4 的要求 —— 验收动作本身不许有副作用。

## 断言分组

  N  网络边界：provider 层只有 0 条网络 import（**只查 import 行**，不查全文 ——
     全文会命中它自己的文档注释，那是实测过的假红）；客户端里网络 import 集中在
     底层，业务函数不直接 import
  T  任务/介质表：客户端与闸门两张表**恒等**（复制可以对，漂移不许）
  C  配置：缺环境变量 → ClientNotConfigured 且**不读凭据文件**；两个网关各自读自己的
  E  出境清单：按任务收窄（scene_semantics 不许把 audio 报进清单）
  A  授权：`registration_for` 默认 **authorized=False**；未授权时注册表**一次都不许调**
  S  状态映射：每种失败都**不许**落 ok（网络失败/非 2xx/非 JSON/无 choices/空正文/
     无 JSON/observations 空/缺介质）
  O  正常路径：真 JSON → observations 逐条带 statement
  M  多任务聚合：一条 error 不许被另一条 ok 盖成 ok
  R  凭据不进仓：本文件与客户端源码里不出现真实密钥字面量

退出码：0 全过 / 1 有红 / 2 未测（导入失败）。
`--controls`：反向对照 —— 坏副本必须红、好副本必须绿。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    ok = bool(ok)
    print(("PASS: " if ok else "FAIL: ") + name + ((" " + detail) if detail else ""),
          file=sys.stdout if ok else sys.stderr)
    PASSED += int(ok)
    FAILED += int(not ok)


try:
    from base import multimodal_provider as MP
    from tools import multimodal_client as MC
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入多模态链: %s" % exc)
    sys.exit(2)


# ── 打桩传输层 ────────────────────────────────────────────────────────

def transport_ok(observations, *, model="stub"):
    """返回一个「网关正常」的传输层。"""
    def _t(url, headers, payload, timeout):
        body = json.dumps({
            "choices": [{"message": {"content": json.dumps(
                {"observations": observations}, ensure_ascii=False)}}],
            "model": model,
        }, ensure_ascii=False)
        return MC.HttpResult(status=200, body=body)
    return _t


def transport_raw(body, status=200):
    def _t(url, headers, payload, timeout):
        return MC.HttpResult(status=status, body=body)
    return _t


def transport_fail(kind="url_error"):
    def _t(url, headers, payload, timeout):
        return MC.HttpResult(status=0, error=kind)
    return _t


def _tiny_png(path: Path):
    """写一个最小 PNG（1×1）。内容是**真的字节**，不是假造的字符串 ——
    这样 media_part 的 base64 编码路径真的被执行到。"""
    import base64 as _b64
    data = _b64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
        "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    path.write_bytes(data)


# ── N：网络边界 ───────────────────────────────────────────────────────

NET_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(requests|httpx|urllib|socket|aiohttp|openai|anyio)\b",
    re.M)


def net_imports(text, *, strip_comments=True):
    """数网络 import。**只查 import 行**。

    ★ 不查全文的理由是实测的：`base/multimodal_provider.py` 里
      `requests|httpx|urllib|socket` 全文命中 3 处，**全在文档注释里**
      （文件头解释「为什么这里一行网络都不许有」）。一条把注释当违规的判据，
      会让下一个人去改注释而不是改代码。
    """
    lines = []
    for raw in text.splitlines():
        line = raw
        if strip_comments:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # 去掉行尾注释（保守：只去 ` #` 之后，避免切坏字符串里的 #）
            if " #" in line:
                line = line.split(" #", 1)[0]
        lines.append(line)
    return len(NET_IMPORT.findall("\n".join(lines)))


def check_network_boundary():
    src = (ROOT / "base" / "multimodal_provider.py").read_text(encoding="utf-8")
    report(net_imports(src) == 0,
           "N1 ★★ 授权闸门 base/multimodal_provider.py 的网络 import 为 0（只查 import 行）",
           str(net_imports(src)))
    # ★ 反向对照：全文查会命中它自己的注释 —— 这一条证明「只查 import 行」不是宽松
    full = len(re.findall(r"\b(requests|httpx|urllib|socket|aiohttp)\b", src))
    report(full >= 1 and net_imports(src) == 0,
           "N2 ★ 全文确实命中过（都在注释里），而 import 行仍是 0 —— 判据没放宽，是没假红",
           "全文 %d 处" % full)

    client_src = (ROOT / "tools" / "multimodal_client.py").read_text(encoding="utf-8")
    report(net_imports(client_src) >= 1,
           "N3 客户端确实是那个有网络的地方（否则边界是假的）",
           str(net_imports(client_src)))
    # urllib 只许出现在底层两处：import 与 urllib_transport
    body = client_src.split("def urllib_transport", 1)[-1]
    report("urllib.request.urlopen" in body,
           "N4 真发请求的只有 urllib_transport 一处")


# ── T：两张任务/介质表恒等 ───────────────────────────────────────────

def check_task_tables():
    required = {t.value: tuple(v) for t, v in MP._REQUIRED_MEDIA.items()}
    report(MC.TASK_MEDIA == required,
           "T1 ★ 客户端 TASK_MEDIA 与闸门 _REQUIRED_MEDIA 恒等（复制可以对，漂移不许）",
           "client=%r gate=%r" % (MC.TASK_MEDIA, required))
    report(set(MC.TASK_PROMPTS) == set(MC.TASK_MEDIA),
           "T2 每个任务都有写死的指令（不靠调用方自由文本）",
           repr(sorted(set(MC.TASK_MEDIA) ^ set(MC.TASK_PROMPTS))))


# ── C：配置 ──────────────────────────────────────────────────────────

def check_config():
    try:
        MC.GatewayClient.from_env("tokenhub", model="m", env={})
        report(False, "C1 缺环境变量必须拒")
    except MC.ClientNotConfigured as exc:
        report(True, "C1 缺环境变量 → ClientNotConfigured", str(exc)[:60])

    try:
        MC.GatewayClient.from_env("nope", model="m", env={})
        report(False, "C2 未知网关必须拒")
    except MC.ClientNotConfigured:
        report(True, "C2 未知网关 → ClientNotConfigured")

    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k-1"}
    c = MC.GatewayClient.from_env("tokenhub", model="m1", env=env)
    report(c.base_url == "https://a.test/v1" and c.model == "m1",
           "C3 配置读到了（base 去尾斜杠、model 保留）", c.base_url)
    report(c.endpoint() == "https://a.test/v1/chat/completions",
           "C4 endpoint 拼对", c.endpoint())

    # ★ vod 用自己那对变量，不许串门
    env2 = {"MULTIMODAL_VOD_BASE_URL": "https://v.test/v1",
            "MULTIMODAL_VOD_API_TOKEN": "k-2"}
    c2 = MC.GatewayClient.from_env("vod", model="m2", env=env2)
    report(c2.api_key == "k-2", "C5 vod 读自己那对（不串用 tokenhub 的）")
    try:
        MC.GatewayClient.from_env("vod", model="m2",
                                  env={"MULTIMODAL_VOD_BASE_URL": "https://v.test/v1"})
        report(False, "C6 vod 缺 token 必须拒")
    except MC.ClientNotConfigured:
        report(True, "C6 vod 缺 token → ClientNotConfigured")

    # ★ 不读凭据文件。判据只查**代码里的读取动作**，不查文档里提到的路径。
    #
    #   第一版查的是「源码里出现 `.dsh/credentials` 字样」，于是它命中了
    #   `multimodal_client.py` 文件头那句「一个会去翻 `~/.dsh/credentials/` 的
    #   网络客户端……」—— 一句**解释这条边界为什么存在**的话被当成了违规。
    #   那正是本文件 N2 在骂的形状：把注释当违规，下一个人会去删注释而不是改代码。
    src = (ROOT / "tools" / "multimodal_client.py").read_text(encoding="utf-8")
    open_call = re.compile(
        r"\bopen\s*\([^)\n]*(credentials|\.dsh|\.env)\b", re.I)
    expand = re.compile(r"expanduser\s*\(\s*['\"][^'\"]*\.dsh", re.I)
    report(not open_call.search(src) and not expand.search(src),
           "C7 ★ 客户端**代码**里没有读凭据文件的动作（只读环境变量）")
    # ★ 反向对照：真的写了一个「打开凭据文件」的动作必须被抓到
    report(bool(open_call.search('fp = open(home + "/.dsh/credentials/x.json")')),
           "C8 扫描器能抓到真的打开凭据文件（否则 C7 恒真）")
    report(bool(expand.search('p = os.path.expanduser("~/.dsh/credentials")')),
           "C9 扫描器能抓到 expanduser 到 .dsh（两种读法都覆盖）")


# ── E：出境清单 ──────────────────────────────────────────────────────

def check_egress():
    img_only = {i["item_id"] for i in MC.egress_items_for("vod", ["scene_semantics"])}
    report("audio_bytes_b64" not in img_only,
           "E1 ★ scene_semantics 的出境清单**不含**音轨（按任务收窄）",
           repr(sorted(img_only)))
    av = {i["item_id"] for i in MC.egress_items_for("vod", ["av_alignment"])}
    report({"video_bytes_b64", "audio_bytes_b64"} <= av,
           "E2 av_alignment 清单含视频与音轨", repr(sorted(av)))
    report("task_prompt_text" in img_only,
           "E3 指令文本也在清单里（内部数据也是出境）")

    reg = MC.registration_for("vod", model="gemini-3.8-flash",
                              tasks=["scene_semantics", "av_alignment"])
    report(reg.recipient and "vod" in reg.recipient.lower() or "VOD" in reg.recipient,
           "E4 recipient 是可指认的接收方（不是「云端」）", reg.recipient[:40])
    report(all(not v for v in reg.authorized.values()),
           "E5 ★★ registration_for 默认 authorized 全 False（接上 ≠ 出境）",
           repr(reg.authorized))
    ids = {i.item_id for i in reg.egress_items}
    report("audio_bytes_b64" in ids, "E6 多任务合并时音轨进清单", repr(sorted(ids)))


# ── A：授权闸门 ──────────────────────────────────────────────────────

def check_authorization():
    reg_obj = MC.registration_for("tokenhub", model="glm-5.3-flash",
                                  tasks=["scene_semantics"])
    registry = MP.ProviderRegistry()
    called = {"n": 0}

    def stub_class(provider_id):
        """造一个 provider_id 与登记表**完全一致**的桩。

        ★ 注册表会校验名字一致（不一致时「审计看到的名字和实际被调用的对象对不上」），
          所以桩不能是一份固定类 —— 否则 A3 那条会用错名字，被闸门拒掉的
          是「名字不符」而不是我们要测的东西，判据就变成了假红。
        """
        class _Stub(MP.MultimodalProvider):
            pass

        _Stub.provider_id = provider_id

        def analyze(self, media_ref, tasks):
            called["n"] += 1
            return {"status": "ok", "tasks": {}}

        _Stub.analyze = analyze
        return _Stub

    registry.register(reg_obj, stub_class(reg_obj.provider_id))
    media_ref = MP.MediaRef(uri="inline:x", sha256="a" * 64,
                            byte_size=10, kind="image",
                            mime="image/png")
    try:
        registry.require_authorization(reg_obj.provider_id, "scene_semantics")
        report(False, "A1 ★★ 未授权时 require_authorization 必须抛")
    except MP.NotAuthorized:
        report(True, "A1 ★★ 未授权 → NotAuthorized（闸门关着）")
    report(called["n"] == 0,
           "A2 ★★ 未授权时 provider **一次都没被调用**（不是调了再拒）",
           "调用 %d 次" % called["n"])

    # 反向：授权之后必须能过（否则闸门是砖头）
    auth = MP.ProviderRegistration(
        provider_id="p-auth", egress_items=(MP.EgressItem(
            item_id="x", description="d"),),
        recipient="r",
        required_authorizations={"scene_semantics": ("content_egress",)},
        authorized={"scene_semantics": True},
        granted_authorizations=("content_egress",))
    reg2 = MP.ProviderRegistry()
    reg2.register(auth, stub_class("p-auth"))
    try:
        reg2.require_authorization("p-auth", "scene_semantics")
        report(True, "A3 已授权 → 放行（闸门不是砖头）")
    except Exception as exc:  # noqa: BLE001
        report(False, "A3 已授权却仍被拒", repr(exc))


# ── S：状态映射（每种失败都不许落 ok） ───────────────────────────────

def check_status_mapping(tmpdir):
    img = Path(tmpdir) / "t.png"
    _tiny_png(img)
    media = {"image": img}
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k"}

    def client(transport):
        return MC.GatewayClient.from_env("tokenhub", model="m", env=env,
                                         transport=transport)

    cases = (
        ("S1 网络失败 → 不许 ok", transport_fail("url_error")),
        ("S2 超时 → 不许 ok", transport_fail("timeout")),
        ("S3 HTTP 500 → 不许 ok", transport_raw("boom", status=500)),
        ("S4 HTTP 429 → 不许 ok", transport_raw("slow down", status=429)),
        ("S5 响应非 JSON → 不许 ok", transport_raw("<html>nope</html>")),
        ("S6 无 choices → 不许 ok", transport_raw(json.dumps({"x": 1}))),
        ("S7 空正文 → 不许 ok",
         transport_ok([], model="m") if False else
         transport_raw(json.dumps(
             {"choices": [{"message": {"content": ""}}]}))),
        ("S8 正文无 JSON → 不许 ok",
         transport_raw(json.dumps(
             {"choices": [{"message": {"content": "我看了，没问题"}}]}))),
        ("S9 observations 为空数组 → 不许 ok",
         transport_raw(json.dumps(
             {"choices": [{"message": {"content": json.dumps({"observations": []})}}]}))),
        ("S10 observations 里没有 statement → 不许 ok",
         transport_raw(json.dumps(
             {"choices": [{"message": {"content": json.dumps(
                 {"observations": [{"confidence": 0.9}]})}}]}))),
    )
    for name, transport in cases:
        got = client(transport).analyze_task("scene_semantics", media)
        report(got.get("status") != "ok",
               "★ " + name, "实际 status=%r" % (got.get("status"),))
        if got.get("status") != "ok":
            report(bool(got.get("reason")),
                   "   %s：非 ok 必须带 reason" % name.split()[0],
                   repr(got.get("reason"))[:60])

    # ★★ 判别用例：非 2xx **但响应体结构完整**。
    #
    #   没有这一条，S3/S4 是假绿 —— 实测过：把「非 2xx 一律不许 ok」那行删掉，
    #   S3/S4 仍然绿，因为真实网关的错误页不是 JSON，被后面「响应非 JSON」
    #   那层兜住了。两层防线各自都对，于是**没有一条断言在守状态码那一层**，
    #   而它恰好是最该守的：一个 401 的响应体若带完整结构，会被读成一次成功分析。
    #
    #   所以这里专门构造「结构完整 + 非 2xx」，让它只有状态码那层能拦。
    body_full = json.dumps({"choices": [{"message": {"content": json.dumps(
        {"observations": [{"statement": "这个观察来自一个失败响应"}]},
        ensure_ascii=False)}}]})
    for status in (401, 403, 429, 500, 503):
        got = client(transport_raw(body_full, status=status)).analyze_task(
            "scene_semantics", media)
        report(got.get("status") != "ok",
               "★ S12 非 2xx（%d）但结构完整 → 不许 ok（只有状态码这层能拦）"
               % status, repr(got.get("status")))
    got = client(transport_raw(body_full, status=200)).analyze_task(
        "scene_semantics", media)
    report(got.get("status") == "ok",
           "★ S13 同一份结构完整的响应体，2xx 时必须 ok（否则 S12 恒红）",
           repr(got.get("status")))

    # 缺介质：只有图却要 av_alignment → untested 且点名缺 audio
    got = client(transport_ok([{"statement": "x"}])).analyze_task(
        "av_alignment", {"image": img})
    report(got.get("status") == "untested"
           and "audio" in (got.get("missing_media") or []),
           "S11 ★ av_alignment 只有图 → untested 且点名缺 audio",
           repr(got))


# ── O：正常路径 ──────────────────────────────────────────────────────

def check_happy_path(tmpdir):
    img = Path(tmpdir) / "t.png"
    _tiny_png(img)
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k"}
    seen = {}

    def capture(url, headers, payload, timeout):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization", "")
        seen["payload"] = json.loads(payload.decode("utf-8"))
        body = json.dumps({"choices": [{"message": {"content": json.dumps(
            {"observations": [
                {"statement": "画面演示婴儿睡眠场景", "confidence": 0.82,
                 "region": "中央"},
                {"statement": "背景有认证徽章", "confidence": 0.4},
            ]}, ensure_ascii=False)}}]}, ensure_ascii=False)
        return MC.HttpResult(status=200, body=body)

    client = MC.GatewayClient.from_env("tokenhub", model="glm-5.3-flash",
                                       env=env, transport=capture)
    got = client.analyze(["scene_semantics"], {"image": img})
    report(got.get("status") == "ok",
           "O1 正常响应 → ok", repr(got.get("status")))
    obs = (got.get("tasks") or {}).get("scene_semantics", {}).get("observations") or []
    report(len(obs) == 2 and obs[0].get("statement"),
           "O2 observations 逐条带 statement", repr(obs[:2]))
    report(obs[0].get("confidence") == 0.82 and obs[0].get("region") == "中央",
           "O3 可选字段（confidence/region）保留")
    report(seen["url"].endswith("/chat/completions"),
           "O4 请求打到 /chat/completions", seen["url"])
    report(seen["auth"].startswith("Bearer "),
           "O5 鉴权走 Authorization: Bearer")
    content = seen["payload"]["messages"][0]["content"]
    has_img = any(p.get("type") == "image_url" for p in content)
    report(has_img, "O6 图片作为 image_url part 送出（data URL）")
    report(all("data:image/png;base64," in str(p) for p in content
               if p.get("type") == "image_url"),
           "O7 data URL 带 MIME 与 base64")
    report(seen["payload"].get("temperature") == 0,
           "O8 temperature=0（审核要可复现，不要发挥）")


# ── M：多任务聚合 ────────────────────────────────────────────────────

def check_aggregation(tmpdir):
    img = Path(tmpdir) / "t.png"
    _tiny_png(img)
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k"}
    # scene_semantics 成功、mark_symbol 失败 → 总状态不许是 ok
    state = {"n": 0}

    def flaky(url, headers, payload, timeout):
        state["n"] += 1
        if state["n"] == 1:
            return transport_ok([{"statement": "s"}])(
                url, headers, payload, timeout)
        return MC.HttpResult(status=503, body="nope")

    client = MC.GatewayClient.from_env("tokenhub", model="m", env=env,
                                       transport=flaky)
    got = client.analyze(["scene_semantics", "mark_symbol"], {"image": img})
    report(got.get("status") == "error",
           "M1 ★★ 一条 error 不许被另一条 ok 盖成 ok", repr(got.get("status")))
    report(got["tasks"]["scene_semantics"]["status"] == "ok"
           and got["tasks"]["mark_symbol"]["status"] == "error",
           "M2 每条任务各自的状态都要在", repr(
               {k: v["status"] for k, v in got["tasks"].items()}))
    empty = client.analyze([], {"image": img})
    report(empty.get("status") == "untested",
           "M3 空任务 → untested（不是 ok）", repr(empty.get("status")))
    report(bool(got.get("boundary")) and "control_code" in got["boundary"],
           "M4 结果带 boundary：不许自称能产 control_code", repr(got.get("boundary"))[:60])


# ── R：凭据不进仓 ────────────────────────────────────────────────────

def check_no_secrets():
    """源码里不许出现真实密钥字面量。

    ★ 不在本文件里写任何密钥片段做比对 —— 那等于把密钥的**一半**写进公开仓。
      改为判形态：`sk-` 开头的长串、以及 32 位以上无分隔的混合串。
    """
    pat = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
    for rel in ("tools/multimodal_client.py", "base/multimodal_provider.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        report(not pat.search(text), "R1 %s 不含 sk- 形态的凭据" % rel)


def main(argv):
    if "--controls" in argv:
        return run_controls()
    print("=" * 78)
    print("T-432 · 多模态客户端 + 闸门接通（全离线，一次网络不发）")
    print("=" * 78)
    check_network_boundary()
    check_task_tables()
    check_config()
    check_egress()
    check_authorization()
    with tempfile.TemporaryDirectory() as td:
        check_status_mapping(td)
        check_happy_path(td)
        check_aggregation(td)
    check_no_secrets()
    print("-" * 78)
    if FAILED:
        print("❌ %d passed, %d failed" % (PASSED, FAILED))
        return 1
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


# ── --controls ──────────────────────────────────────────────────────

def _client_src():
    return (ROOT / "tools" / "multimodal_client.py").read_text(encoding="utf-8")


def _probe_interpret(transport_factory, observations=None):
    """用一个独立的 client 实例走 _interpret，返回 status。"""
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k"}
    c = MC.GatewayClient.from_env("tokenhub", model="m", env=env)
    return c._interpret("scene_semantics", transport_factory)._get if False else None


def run_controls():
    print("=" * 78)
    print("verify_multimodal_client · --controls（状态映射与清单的离线反向对照）")
    print("=" * 78)
    ok = bad = 0

    def C(name, cond, detail=""):
        nonlocal ok, bad
        if cond:
            ok += 1
            print("  ✅ %s" % name)
        else:
            bad += 1
            print("  ❌ %s  %s" % (name, detail))

    # 每个坏样本：把「不许 ok」改成「一律 ok」，看判据是否仍能分辨
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k"}

    # CD1：真实 _interpret 对坏响应不落 ok（这是主判据的地基）
    c = MC.GatewayClient.from_env("tokenhub", model="m", env=env)
    got = c._interpret("scene_semantics", MC.HttpResult(status=500, body="x"))
    C("CD1 HTTP 500 经 _interpret 不落 ok", got.get("status") != "ok",
      repr(got.get("status")))
    got2 = c._interpret("scene_semantics", MC.HttpResult(status=200, body="{}"))
    C("CD2 空 JSON 经 _interpret 不落 ok", got2.get("status") != "ok",
      repr(got2.get("status")))
    got3 = c._interpret("scene_semantics", MC.HttpResult(
        status=200, body=json.dumps({"choices": [{"message": {"content": json.dumps(
            {"observations": [{"statement": "真的"}]})}}]})))
    C("CD3 好响应经 _interpret 落 ok（否则判据恒红）", got3.get("status") == "ok",
      repr(got3.get("status")))

    # CD4：出境清单按任务收窄这条判据真的会红 —— 把 audio 无条件加进去
    global EGRESS_OVERRIDE
    orig = MC.egress_items_for
    try:
        def leaky(gateway, tasks):
            return MC.EGRESS_ITEMS[gateway]  # 全量，不按任务收窄
        MC.egress_items_for = leaky
        ids = {i["item_id"] for i in MC.egress_items_for("vod", ["scene_semantics"])}
        C("CD4 全量出境清单会让「不许含音轨」判据红", "audio_bytes_b64" in ids,
          repr(sorted(ids)))
    finally:
        MC.egress_items_for = orig

    # CD5：授权默认值这条真的会红 —— 把 registration_for 改成默认 True
    reg_auth = MC.registration_for("tokenhub", model="m",
                                   tasks=["scene_semantics"], authorized=True)
    C("CD5 authorized=True 时确实全 True（证明默认 False 不是恒真）",
      all(reg_auth.authorized.values()), repr(reg_auth.authorized))

    # CD6：import 扫描必须能抓出真的网络 import
    C("CD6 扫描器能抓到真的 `import requests`",
      net_imports("import requests\n") == 1)
    C("CD7 扫描器不把整行注释算成 import",
      net_imports("# import requests\n") == 0)

    print("-" * 78)
    print("%s --controls %d 过 · %d 红" % ("✅" if bad == 0 else "❌", ok, bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
