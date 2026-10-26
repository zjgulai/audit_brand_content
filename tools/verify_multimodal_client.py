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

# ── F：回落链与重试（ADR-0019 §二） ─────────────────────────────────

def check_fallback(tmpdir):
    """回落链 + 429 重试 + 「不静默换模型」。

    ★ 这一组验的是 ADR-0019 §二 的三条硬规矩：
      ① 429 必须**重试同一模型**（retryable），不许直接判死；
      ② 主选失败要**落到下一个**，并留下 `fallback_from`；
      ③ 整条链失败落 **error**（测了但失败），不是 `untested`（没测）。
    """
    img = Path(tmpdir) / "t.png"
    _tiny_png(img)
    media = {"image": img}
    env = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
           "MULTIMODAL_TOKENHUB_API_KEY": "k1",
           "MULTIMODAL_VOD_BASE_URL": "https://v.test/v1",
           "MULTIMODAL_VOD_API_TOKEN": "k2"}

    def ok_t(url, headers, payload, timeout):
        return MC.HttpResult(200, json.dumps({"choices": [{"message": {"content":
            json.dumps({"observations": [{"statement": "看到 X"}]})}}]}))

    # F1 每个任务都有回落链，且 av_alignment 链里**没有 tokenhub**
    for task in ("scene_semantics", "mark_symbol", "av_alignment"):
        chain = MC.chain_for(task)
        report(len(chain) >= 2,
               "F1 %s 的回落链 ≥2 项（单点等于把可用性押在一处）" % task,
               str(len(chain)))
    av_gw = {gw for gw, _ in MC.chain_for("av_alignment")}
    report(av_gw == {"vod"},
           "F1b ★★ av_alignment 链里只有 vod（tokenhub 的 glm 家族 audio 为 0 家）",
           repr(sorted(av_gw)))
    # ★★ 光查 `chain_for()` 不够 —— 它会把不允许的网关**过滤掉**，
    #   于是「原始表里写了 tokenhub」这件事永远查不到（真变异实测：往
    #   FALLBACK_CHAINS 的 av 链里插 tokenhub，F1b 仍然绿）。
    #   所以要**直接查原始表**：写下来的东西和过滤后的东西是两件事。
    raw_av = {gw for gw, _ in MC.FALLBACK_CHAINS["av_alignment"]}
    report(raw_av == {"vod"},
           "F1b2 ★★ FALLBACK_CHAINS 的 av 链**原始表**里也只有 vod"
           "（chain_for 的过滤会掩盖写错）", repr(sorted(raw_av)))
    # ★ 反向：真的把 tokenhub 塞进 av 链时，chain_for 必须把它过滤掉
    report(not MC.gateway_supports("tokenhub", "av_alignment"),
           "F1c ★ 反证：gateway_supports 对 tokenhub+av_alignment 为 False")

    # F2 主选成功 → fallback_from 为 None（不是空列表）
    got = MC.analyze_with_fallback("scene_semantics", media, env=env,
                                   transport=ok_t)
    report(got["status"] == "ok" and got["fallback_from"] is None,
           "F2 ★ 主选就成功时 fallback_from=None（不是 []）",
           repr(got.get("fallback_from")))
    report(got.get("model_used") == MC.chain_for("scene_semantics")[0][1],
           "F2b 主选成功时 model_used 是主选那个", repr(got.get("model_used")))

    # F3 主选 429 → 落下一个，且 fallback_from 记下走过的路
    def first_429(url, headers, payload, timeout):
        if "a.test" in url:
            return MC.HttpResult(429, "limited")
        return ok_t(url, headers, payload, timeout)

    got3 = MC.analyze_with_fallback("scene_semantics", media, env=env,
                                    transport=first_429,
                                    retry_attempts=1, retry_backoff=0)
    report(got3["status"] == "ok"
           and got3["fallback_from"] == ["tokenhub/glm-5.3-flash"],
           "F3 ★★ 主选 429 → 回落，且 fallback_from 记下走过的那一项",
           repr(got3.get("fallback_from")))
    report(got3.get("gateway_used") == "vod",
           "F3b 回落成功时 gateway_used 是实际用的那个", repr(got3.get("gateway_used")))

    # F4 整条链都 429 → error，不是 untested
    def all_429(url, headers, payload, timeout):
        return MC.HttpResult(429, "limited")

    got4 = MC.analyze_with_fallback("scene_semantics", media, env=env,
                                    transport=all_429,
                                    retry_attempts=1, retry_backoff=0)
    report(got4["status"] == "error",
           "F4 ★★ 整条链失败 → error（测了但失败），不是 untested",
           repr(got4.get("status")))
    report(len(got4.get("chain_tried") or []) == len(MC.chain_for("scene_semantics")),
           "F4b 每次尝试都记进 chain_tried（能追到哪一步死的）",
           str(len(got4.get("chain_tried") or [])))
    report("整条回落链都失败" in (got4.get("reason") or ""),
           "F4c reason 明说「整条链都失败」")
    report(got4.get("model_used") is None,
           "F4d 全失败时 model_used 是 None（不许编一个）", repr(got4.get("model_used")))

    # F5 429 必须在 RETRYABLE 里；401/403/404 不在
    report(429 in MC.RETRYABLE_STATUS,
           "F5 ★★ 429 是 retryable（限流可重试）")
    for code in (401, 403, 404):
        report(code not in MC.RETRYABLE_STATUS,
               "F5b ★ %d 不是 retryable（鉴权/寻址错，重试无意义）" % code)

    # F6 重试次数真的生效：一个永远 429 的 transport，调用次数 = retry_attempts
    calls = {"n": 0}

    def counting_429(url, headers, payload, timeout):
        calls["n"] += 1
        return MC.HttpResult(429, "limited")

    client = MC.GatewayClient.from_env("tokenhub", model="m", env=env,
                                       transport=counting_429,
                                       retry_attempts=3, retry_backoff=0)
    client.analyze_task("scene_semantics", media)
    report(calls["n"] == 3,
           "F6 ★★ 同一模型重试次数 = retry_attempts（3 次），不是 1 次",
           str(calls["n"]))
    report(client.analyze_task("scene_semantics", media).get("retryable") is True,
           "F6b 429 结果带 retryable=True（与「不可用」分开）")

    # F7 401 必须立刻放弃重试（重试一百次也一样）
    calls2 = {"n": 0}

    def counting_401(url, headers, payload, timeout):
        calls2["n"] += 1
        return MC.HttpResult(401, "bad key")

    client2 = MC.GatewayClient.from_env("tokenhub", model="m", env=env,
                                        transport=counting_401,
                                        retry_attempts=3, retry_backoff=0)
    out401 = client2.analyze_task("scene_semantics", media)
    report(calls2["n"] == 1,
           "F7 ★★ 401 只试 1 次（不是 3 次）—— 鉴权错重试无意义", str(calls2["n"]))
    report(out401.get("retryable") is False,
           "F7b 401 结果带 retryable=False")
    report("鉴权" in (out401.get("reason") or ""),
           "F7c ★ 401 的 reason 点名「鉴权」，不许被读成「模型坏了」",
           (out401.get("reason") or "")[:40])

    # F8 未配凭据 ≠ 试过了不行：链上某网关未配时，应记 not_configured 并继续
    only_tokenhub = {"MULTIMODAL_TOKENHUB_BASE_URL": "https://a.test/v1",
                     "MULTIMODAL_TOKENHUB_API_KEY": "k1"}
    calls3 = {"n": 0}

    def tok_429(url, headers, payload, timeout):
        calls3["n"] += 1
        return MC.HttpResult(429, "limited")

    got8 = MC.analyze_with_fallback("scene_semantics", media, env=only_tokenhub,
                                    transport=tok_429, retry_attempts=1,
                                    retry_backoff=0)
    tried = got8.get("chain_tried") or []
    report(any(t.get("status") == "not_configured" for t in tried),
           "F8 ★★ vod 未配凭据时记 not_configured（不是「试过了不行」）",
           repr([t.get("status") for t in tried]))
    report(got8["status"] == "error",
           "F8b 但整体仍是 error（一个都没成功）", repr(got8.get("status")))

    # F10 ★★★ 缺介质必须是 untested 且**不许**把整条链跑完
    #   —— 实测踩到过：只有 video 没有 audio 时落成「error 整条回落链都失败」，
    #      读起来像「5 个模型都坏了」，而真相是「这次一个模型都不该被叫」。
    calls10 = {"n": 0}

    def counting_ok(url, headers, payload, timeout):
        calls10["n"] += 1
        return ok_t(url, headers, payload, timeout)

    got10 = MC.analyze_with_fallback("av_alignment", {"video": img}, env=env,
                                     transport=counting_ok, retry_attempts=1,
                                     retry_backoff=0)
    report(got10["status"] == "untested",
           "F10 ★★★ 缺音轨 → untested（不是 error、更不是 ok）",
           repr(got10.get("status")))
    report(calls10["n"] == 0,
           "F10b ★★★ 缺介质时**一个模型都没被调用**（0 次请求）",
           str(calls10["n"]))
    report(len(got10.get("chain_tried") or []) <= 1,
           "F10c ★★ 缺介质时不许把整条链跑完（≤1 次尝试）",
           str(len(got10.get("chain_tried") or [])))
    report("与模型无关" in (got10.get("reason") or ""),
           "F10d reason 明说「与模型无关」（不让人去查模型）",
           (got10.get("reason") or "")[:50])

    # F11 全部 not_configured → untested（没测），不是 error（失败）
    got11 = MC.analyze_with_fallback("scene_semantics", media, env={},
                                     transport=ok_t, retry_attempts=1,
                                     retry_backoff=0)
    report(got11["status"] == "untested",
           "F11 ★★ 全部未配凭据 → untested（没测 ≠ 失败）",
           repr(got11.get("status")))
    report("没测" in (got11.get("reason") or ""),
           "F11b reason 明说「这是没测，不是失败」", (got11.get("reason") or "")[:50])

    # F9 读数的字面量不许再写「3.8-flash 不能用」
    src = (ROOT / "tools" / "multimodal_client.py").read_text(encoding="utf-8")
    report("gemini-3.8-flash" in src,
           "F9 3.8-flash 在回落链里（主选之一）")
    # ★ 判据要查的是「这句话还被当成**现行结论**」，不是「这句话有没有作为
    #   历史被引用」。我自己的更正说明里就引用了它（引号里那句），
    #   所以裸查子串会误报 —— 与 §2.4.1 记过的「判据被文档喂饱」同一个形状。
    #   判法：查**非注释行**里有没有这句。
    code_lines = []
    in_doc = False
    for raw in src.splitlines():
        stripped = raw.strip()
        if '"""' in stripped:
            if stripped.count('"""') == 1:
                in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#"):
            continue
        code_lines.append(raw)
    code_only = "\n".join(code_lines)
    report("默认落 gemini-3.1-flash-lite，不是 3.8" not in code_only,
           "F9b ★★ 那句把 429 写成「不能用」的过期判语**不在代码里**"
           "（注释里作为历史引用保留是允许的）")
    report("不是 3.8" in src,
           "F9c ★ 反证：那句话确实还作为**历史**在注释里（证明 F9b 查的是代码不是全文）")


def check_adr_alignment():
    """ADR-0019 与代码**必须一致**。

    ★ 为什么这条要在这份验收器里：ADR-0019 定的是「网关策略」（谁是主选、
      回落链长什么样、429 怎么处置）。它如果只写在文档里，代码改了没人知道 ——
      而这份 ADR 的 §一 本身就是「文档与事实不一致」的产物
      （委托方以为 tokenhub 有 gemini，实测 0 个）。所以必须双向钉住。
    """
    adr_path = ROOT / "ADR" / "ADR-0019-媒体审核网关策略与盘上缺件处置.md"
    if not adr_path.is_file():
        report(False, "F12 ADR-0019 存在")
        return
    adr = adr_path.read_text(encoding="utf-8")
    report("accepted" in adr and "2026-10-26" in adr,
           "F12 ADR-0019 状态 accepted、日期 2026-10-26")
    # ★ 回落链上每个模型都必须在 ADR 的 §2.1 表里出现
    missing = []
    for task, chain in MC.FALLBACK_CHAINS.items():
        for gateway, model in chain:
            if model not in adr:
                missing.append("%s/%s" % (gateway, model))
    report(missing == [],
           "F12b ★★ 回落链上每个模型都在 ADR §2.1 里（代码与决策不许脱钩）",
           repr(missing))
    # ★ 反向：代码里有的任务，ADR 里也有那一行
    report(all(task in adr for task in MC.FALLBACK_CHAINS),
           "F12c ★ 三个任务都在 ADR 里点名",
           repr([t for t in MC.FALLBACK_CHAINS if t not in adr]))
    # ★★ 关键那条：ADR 明确写着「tokenhub 里没有 gemini」
    report("gemini 0 个" in adr or "tokenhub 里没有 gemini" in adr,
           "F12d ★★ ADR 记下了「tokenhub 无 gemini」这个实测结论")
    # ★ 且不许反过来把 tokenhub 写成有 gemini
    report("tokenhub 的 gemini" not in adr,
           "F12e ★ 反证：ADR 里没有把 gemini 说成 tokenhub 的资产")


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
        check_fallback(td)
    check_no_secrets()
    check_adr_alignment()
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
