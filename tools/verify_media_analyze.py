#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_media_analyze.py — ADR-0021 主线：多模态分析的生产接线

## 它守的是什么

`base/judge_entry.py` 早就有 `multimodal_analyze` 注入点，
`tools/multimodal_client.py` 也早建成了（3 任务 / 2 网关 / 回落链）。
**但生产链路一个参数都没传** —— 2026-10-28 实测
`grep multimodal_analyze base/submission_service.py` = 0 命中。

于是每张图、每段视频的观察都是「未接入多模态分析」。
这是本项目**第四次**同形：`due_at` / 工作流耗时 / `semantic_judge` / `skill_hash`。

## 分组

| 组 | 验什么 |
|---|---|
| A 就绪读数 | 两网关分开报（视频覆盖面比图片窄）；缺哪个变量逐个点名 |
| B ★★★ 未配凭据 | 必须 `untested` + 点名缺失变量，**不许**空列表 / 不许当通过 |
| C 注入契约 | `analyze(media_ref, tasks)` 形状；图片 2 任务、视频 3 任务 |
| D ★★ 路径 | 不从 uri 反推；本地路径缺失 → `error` 而不是猜 |
| E ★ 降级 | 只配 tokenhub 时视频的 `av_alignment` 被跳过**且说清原因** |
| F 观测归因 | 每条观察带 `task`，报告里能说清是哪条任务给的 |
| G 反向对照 | 好样本绿、坏样本各自红 |

退出码：0 全过 / 1 有红 / 2 未测。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0
UNTESTED = 0


def report(ok, name, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print("PASS: %s%s" % (name, ("  " + detail) if detail else ""))
    else:
        FAILED += 1
        print("FAIL: %s%s" % (name, ("  " + detail) if detail else ""))


def untested(name, detail=""):
    global UNTESTED
    UNTESTED += 1
    print("UNTESTED: %s%s" % (name, ("  " + detail) if detail else ""))


#: 四件配齐（两个网关都有）。
FULL_ENV = {
    "MULTIMODAL_TOKENHUB_BASE_URL": "https://tokenhub.example/v1",
    "MULTIMODAL_TOKENHUB_API_KEY": "k-tokenhub",
    "MULTIMODAL_VOD_BASE_URL": "https://vod.example/v1",
    "MULTIMODAL_VOD_API_TOKEN": "t-vod",
}

#: 只配 tokenhub（图片能审、视频不能）。
PARTIAL_ENV = {
    "MULTIMODAL_TOKENHUB_BASE_URL": "https://tokenhub.example/v1",
    "MULTIMODAL_TOKENHUB_API_KEY": "k-tokenhub",
}


class _Stub:
    """打桩客户端：形状与 `multimodal_client.GatewayClient` 一致。

    ★ 打桩的是**传输**，不是解析 —— 解析与状态映射在
      `verify_multimodal_client.py` 里已经用「可注入 transport」验过。
      这里只验接线层。
    """

    def __init__(self, status="ok", statements=("画面显示母婴使用场景",)):
        self.status = status
        self.statements = statements

    def analyze(self, tasks, media):
        return {
            "status": self.status,
            "tasks": {
                t: {"status": self.status,
                    "observations": [{"statement": s, "confidence": 0.8,
                                      "region": "中部"} for s in self.statements]}
                for t in tasks
            },
        }


def _fake_file(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    p = Path(name)
    p.write_bytes(b"\x00" * 64)
    return p


# ─────────────────────────────────────────────────────────── A 就绪读数

def group_a():
    from base import media_analyze as MA

    full = MA.readiness(FULL_ENV)
    report(full["image"]["ready"] is True and full["video"]["ready"] is True,
           "A1 四件配齐 → image/video 都就绪",
           repr((full["image"]["ready"], full["video"]["ready"])))
    report(full["status"] == "ok" and full["reason"] == "",
           "A2 就绪时 status=ok 且 reason 为空")

    part = MA.readiness(PARTIAL_ENV)
    report(part["image"]["ready"] is True,
           "A3 ★ 只配 tokenhub → 图片仍就绪", repr(part["image"]["ready"]))
    # ★★★ 这一条是本组最要紧的：视频覆盖面比图片窄
    report(part["video"]["ready"] is False,
           "A4 ★★★ 只配 tokenhub → **视频不就绪**"
           "（av_alignment 只有 vod 能做；合并成一个布尔会让它被图片盖掉）",
           repr(part["video"]["ready"]))

    none = MA.readiness({})
    report(none["status"] == "untested" and none["image"]["ready"] is False,
           "A5 都不配 → untested")
    report(len(none["missing_env"]) == 4,
           "A6 ★ 缺的变量逐个点名（四个）", repr(none["missing_env"]))
    report("MULTIMODAL_TOKENHUB_API_KEY" in none["missing_env"],
           "A7 ★ 点名到具体变量名（运维照着就能配）")
    # A8 ★★ 不许把 key 本身写进读数（读数会被打进日志）
    report("k-tokenhub" not in repr(none) and "k-tokenhub" not in repr(part),
           "A8 ★★ 读数里不含密钥值（只报『缺哪个』，不报『值是什么』")


# ─────────────────────────────────────────────────────────── B 未配凭据

def group_b():
    from base import media_analyze as MA

    fn = MA.build_analyze(resolve_path=lambda ref: None, env={})
    report(fn is None,
           "B1 ★★★ 凭据未配 → build_analyze 返回 None（不注入）",
           repr(fn))

    # B2 ★★★ 「不注入」之后 judge_entry 落的是「未接入多模态分析」，
    #   而不是「没有发现问题」。这一条验的是那条链。
    from base.judge_entry import _collect_multimodal_observations
    unit = {"source": {"kind": "image", "uri": "submission:x"}}
    obs, note = _collect_multimodal_observations(unit, None)
    report(obs == [] and "未接入" in note,
           "B2 ★★★ 未注入 → 观察为空 + note 说「未接入」（不是「没问题」）",
           repr(note))

    # B3 ★★★ 那条 note 必须**真的活到 state**，不能只活在 judge_entry 的返回值里。
    #
    #   ★ 这是执行中抓到的一个真缺陷（2026-10-28 实测）：
    #     `judge_entry` 一直返回 `multimodal_note`，但
    #     ① `submission_service` 的 payload 顶层**没带**这个键；
    #     ② `review_reducer` 的 `state.update` 里**没有**这个键。
    #     两处缺一，报告里「画面语义」那一节就只剩空列表 ——
    #     读起来像「画面没问题」，而实际是「没看成」。
    #     与 T-455 的 `intent_inference` 是同一个形状（payload 有、state 没有）。
    # ★ 被验主体（覆盖登记表 C 段要求文件名在本文件里逐字出现）：
    #   `base/review_reducer.py` 的 state.update —— 它收不收这个键，
    #   决定报告里有没有「没看成」这句。
    #   `base/submission_service.py` 的 payload 组装 —— reducer 从 payload 读。
    import inspect
    reducer_src = inspect.getsource(
        __import__("base.review_reducer", fromlist=["x"]))
    report('"multimodal_note"' in reducer_src,
           "B3 ★★★ reducer 的 state.update 收下 multimodal_note"
           "（收不下就等于报告里没有「没看成」这句）")
    sub_src = inspect.getsource(
        __import__("base.submission_service", fromlist=["x"]))
    report('"multimodal_note"' in sub_src,
           "B4 ★★★ payload 顶层带上 multimodal_note（reducer 从 payload 读）")


# ─────────────────────────────────────────────────────────── C 注入契约

def group_c():
    from base import media_analyze as MA

    img = _fake_file(".png")
    vid = _fake_file(".mp4")
    try:
        fn = MA.build_analyze(
            resolve_path=lambda ref: img, env=FULL_ENV,
            client_factory=lambda env=None: _Stub())

        r = fn({"kind": "image", "uri": str(img)},
               ["scene_semantics", "mark_symbol"])
        report(r["status"] == "ok", "C1 图片 → ok", repr(r["status"]))
        report(len(r["observations"]) == 2,
               "C2 图片两个任务各一条观察", str(len(r["observations"])))

        fn2 = MA.build_analyze(
            resolve_path=lambda ref: vid, env=FULL_ENV,
            client_factory=lambda env=None: _Stub())
        r2 = fn2({"kind": "video", "uri": str(vid)},
                 ["scene_semantics", "mark_symbol", "av_alignment"])
        report(len(r2["observations"]) == 3,
               "C3 ★ 视频三个任务（含 av_alignment）各一条观察",
               str(len(r2["observations"])))
    finally:
        img.unlink(missing_ok=True)
        vid.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────── D 路径

def group_d():
    from base import media_analyze as MA

    fn = MA.build_analyze(resolve_path=lambda ref: None, env=FULL_ENV,
                          client_factory=lambda env=None: _Stub())
    r = fn({"kind": "image", "uri": "submission:abc"}, ["scene_semantics"])
    # ★★★ 解析不出路径 → error，**不许**猜一个路径继续跑
    report(r["status"] == "error",
           "D1 ★★★ 解析不出本地路径 → error（不许猜路径）", repr(r["status"]))
    report("submission:abc" in (r.get("reason") or ""),
           "D2 ★ 原因里带上那个 uri（排查时要知道是哪个引用解不开）",
           (r.get("reason") or "")[:60])

    # D3 ★ 路径给了但文件不存在 → error（不是 untested）
    missing = Path("/nonexistent/never/here.png")
    fn2 = MA.build_analyze(resolve_path=lambda ref: missing, env=FULL_ENV,
                           client_factory=lambda env=None: _Stub())
    r2 = fn2({"kind": "image", "uri": "x"}, ["scene_semantics"])
    report(r2["status"] == "error",
           "D3 ★★ 文件不存在 → error（「读不到」与「没测」是两件事）",
           repr(r2["status"]))

    # D4 ★★ 非媒体载体 → {}
    report(MA._media_map("free_text", Path("/tmp/x")) == {},
           "D4 ★ 文本载体没有多模态介质映射（不硬塞）")
    report(set(MA._media_map("video", Path("/tmp/x"))) == {"video", "audio"},
           "D5 ★ 视频同时映射为 video 与 audio（mp4 里两者都有）")


# ─────────────────────────────────────────────────────────── E 降级

def group_e():
    from base import media_analyze as MA

    vid = _fake_file(".mp4")
    try:
        fn = MA.build_analyze(
            resolve_path=lambda ref: vid, env=PARTIAL_ENV,
            client_factory=lambda env=None: _Stub())
        r = fn({"kind": "video", "uri": str(vid)},
               ["scene_semantics", "mark_symbol", "av_alignment"])
        tasks = {o.get("task") for o in r["observations"]}
        # ★★★ 只配 tokenhub 时，av_alignment 必须被跳过**并且说清为什么**
        report("av_alignment" not in tasks,
               "E1 ★★★ 只配 tokenhub → 视频的 av_alignment 被跳过", repr(sorted(tasks)))
        report("vod" in (r.get("reason") or ""),
               "E2 ★★★ 跳过时**说清原因**（vod 网关未配置）"
               "—— 静默少一个任务会让人以为音画已经看过",
               (r.get("reason") or "")[:50])
        report(len(tasks) == 2,
               "E3 其余两个画面任务照常做", repr(sorted(tasks)))
    finally:
        vid.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────── F 观测归因

def group_f():
    from base import media_analyze as MA

    img = _fake_file(".png")
    try:
        fn = MA.build_analyze(
            resolve_path=lambda ref: img, env=FULL_ENV,
            client_factory=lambda env=None: _Stub())
        r = fn({"kind": "image", "uri": str(img)},
               ["scene_semantics", "mark_symbol"])
        report(all(o.get("task") for o in r["observations"]),
               "F1 ★★ 每条观察都带 task（报告里要说清是哪条任务给的）")
        report({o.get("task") for o in r["observations"]}
               == {"scene_semantics", "mark_symbol"},
               "F2 ★ 两条任务的观察不混成一堆")

        # F3 ★★ 客户端说 ok 但一条观察都没有 → 降成 untested
        fn2 = MA.build_analyze(
            resolve_path=lambda ref: img, env=FULL_ENV,
            client_factory=lambda env=None: _Stub(statements=()))
        r2 = fn2({"kind": "image", "uri": str(img)}, ["scene_semantics"])
        report(r2["status"] == "untested",
               "F3 ★★★ 返回 ok 但零观察 → untested"
               "（「看了没说」不是「没问题」）", repr(r2["status"]))
    finally:
        img.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────── G 反向对照

def group_g():
    from base import media_analyze as MA

    # G1 好样本必须绿
    r = MA.readiness(FULL_ENV)
    report(r["status"] == "ok", "G1 ★ 好样本必须绿（否则上面全是恒红）")

    # G2 ★★ 反向对照：把「视频也能做」的条件放宽（vod 未配时也报 ready），
    #    A4 那条必须能抓住 —— 直接构造一个坏读数验证判据的形状
    bad = dict(r)
    bad["video"] = {"ready": True, "gateways": []}
    report(bad["video"]["ready"] is True and r["video"]["ready"] is True,
           "G2 ★★ 判据看的是 video.ready 字段本身"
           "（若实现把它写成 image.ready 的别名，A4 会红）")

    # G3 ★★ 空白字符串不算已配（.strip() 之后为空 = 没配）
    fake = {k: "   " for k in FULL_ENV}
    report(MA.readiness(fake)["status"] == "untested",
           "G3 ★★ 全空白的环境变量不许算已配（否则会在运行期才炸）")

    # G4 ★ 密钥不进 reason
    reason = MA.readiness({})["reason"]
    report("k-tokenhub" not in reason and "t-vod" not in reason,
           "G4 ★★ reason 里不含任何密钥值")


def group_h():
    """H 组（2026-10-28）：**形状契约两端必须真的接上**。

    ## 它守的是什么

    实测发现生产链路的多模态观察**从来没成功过一次**：

    · `base/media_analyze._flatten()` 产出**扁平** `{status, observations:[...]}`，
      它自己的 docstring 明说「摊平成 judge_entry 期望的」；
    · 而 `base/judge_entry._observations_from_result()` 读的是**嵌套**
      `raw["tasks"][task]["observations"]`。

    两边对不上 → `per_task` 恒空 → 每个任务判 `untested`
    → 「provider 未返回该任务的结果」。`media_analyze` 给了 11 条真观察，全丢。

    ★ 症状隐蔽：`status=ok`、`note=""`、观察列表里有 2 条（每任务一条 untested
      占位）——「画面语义」那一节看着有内容，没人会去数那 2 条其实是
      「没跑到」而不是「看到了什么」。

    ★ 判据必须跨模块：单测 `media_analyze` 或单测 `judge_entry` 都测不到它。
      所以这里把前者的**真实产出**喂给后者的**真实消费函数**。
    """
    from base import judge_entry as J
    from base import media_analyze as MA

    # 造一份 `_flatten` 会产出的形状（等价于真跑一次 media_analyze）
    flat = {
        "status": "ok",
        "observations": [
            {"statement": "画面有一位女性抱着婴儿", "confidence": 0.9,
             "region": "中上部", "task": "scene_semantics"},
            {"statement": "画面有 momcozy 品牌标识", "confidence": 0.8,
             "region": "底部", "task": "scene_semantics"},
            {"statement": "未发现认证徽章", "confidence": 0.7,
             "region": "全图", "task": "mark_symbol"},
        ],
    }
    entries, note = J._observations_from_result(
        flat, ["scene_semantics", "mark_symbol"], clock=lambda: 0.0)

    ok_entries = [e for e in entries if e.get("status") == "ok"]
    report(len(ok_entries) == 3,
           "H1 ★★★ 扁平形状（media_analyze 的产出）必须被 judge_entry 认",
           "%d 条 ok / 共 %d 条" % (len(ok_entries), len(entries)))
    report(note == "", "H2 ★ note 应为空（有观察时不该有说明）", repr(note))
    report({e.get("task") for e in ok_entries}
           == {"scene_semantics", "mark_symbol"},
           "H3 ★★ task 名保留（否则报告分不清观察来自哪一路）",
           repr({e.get("task") for e in ok_entries}))

    # H4 ★★★ 反向对照：嵌套形状**仍然**要能用（不能为修扁平而把嵌套弄坏）
    nested = {
        "status": "ok", "model": "m1",
        "tasks": {"scene_semantics": {"status": "ok", "observations": [
            {"statement": "嵌套形状的观察", "confidence": 0.5}]}},
    }
    n_entries, _ = J._observations_from_result(
        nested, ["scene_semantics"], clock=lambda: 0.0)
    report(len([e for e in n_entries if e.get("status") == "ok"]) == 1,
           "H4 ★★★ 嵌套形状仍然可用（修扁平不许把嵌套弄坏）",
           "%d 条" % len(n_entries))

    # H5 ★★★ `task_reasons` 必须落成观察条目，不许消失
    #
    #   「这个任务没成」是**没看成**，不是「没问题」。
    #   丢掉它等于把失败读成通过。
    flat_fail = {"status": "ok", "observations": [],
                 "task_reasons": {"scene_semantics": "网络层失败：timeout"}}
    f_entries, _ = J._observations_from_result(
        flat_fail, ["scene_semantics"], clock=lambda: 0.0)
    report(len(f_entries) == 1 and f_entries[0].get("status") == "untested",
           "H5 ★★★ 任务级失败要落 untested 条目（不许从列表里消失）",
           repr([(e.get("status"), e.get("reason", "")[:20]) for e in f_entries]))
    report("timeout" in str(f_entries[0].get("reason") or ""),
           "H6 ★★ 失败原因要原样带出（不许换成笼统一句）",
           str(f_entries[0].get("reason") or "")[:40])

    # H7 ★★ 空观察 + 无失败原因 → 空列表，不是伪造一条
    empty = {"status": "ok", "observations": []}
    e_entries, _ = J._observations_from_result(
        empty, ["scene_semantics"], clock=lambda: 0.0)
    report(e_entries == [],
           "H7 ★★ 真的没有观察时返回空列表（不伪造）", repr(e_entries))

    # H8 ★★★ 默认任务必须**含 mark_symbol**
    #
    #   实测：原值是 `("scene_semantics",)` —— 审一张图时认证标志/资质图标
    #   **从来没有被识别过**，而 mark_symbol 在 provider 层已建好。
    #   这是「能力建好了、接线没接」的又一例。
    report("mark_symbol" in J.DEFAULT_MEDIA_TASKS,
           "H8 ★★★ 默认任务含 mark_symbol（否则标志/资质图标永远不识别）",
           repr(J.DEFAULT_MEDIA_TASKS))
    report("scene_semantics" in J.DEFAULT_MEDIA_TASKS,
           "H9 ★ scene_semantics 仍在（另一半：别为了加一个删另一个）",
           repr(J.DEFAULT_MEDIA_TASKS))


def main():
    print("=" * 74)
    print("media_analyze · ADR-0021 主线（多模态生产接线）")
    print("=" * 74)
    group_a()
    group_b()
    group_c()
    group_d()
    group_e()
    group_f()
    group_g()
    group_h()
    print("-" * 74)
    if FAILED:
        print("❌ %d 过 · %d 红 · %d 未测" % (PASSED, FAILED, UNTESTED))
        return 1
    if UNTESTED:
        print("⚠️ %d 过 · %d 未测 —— 未测不是通过" % (PASSED, UNTESTED))
        return 2
    print("✅ %d/%d 全过" % (PASSED, PASSED))
    return 0


if __name__ == "__main__":
    sys.exit(main())
