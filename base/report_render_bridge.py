#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/report_render_bridge.py —— 报告渲染适配层（T-316c）

**它是什么**：把「Python 侧手里有一份冻结的 report_snapshot」翻译成
「跑一次 Node 渲染器，拿回 markdown 或一个明确的失败」。

**它不是什么**：它**不校验** snapshot。`validateSnapshot()` 是渲染器自己的事。
两次校验一定会出现「桥接层放行、渲染器拒了」或反过来的状态，而那时
两个地方各说一套，且**没有任何断言能判断该信谁**。

--------------------------------------------------------------------------
四条硬约束（每条都有对应断言）
--------------------------------------------------------------------------

**一、超时必须显式（30s）**

    没有超时的子进程调用，在渲染器死循环或 stdin 阻塞时会挂住整个结案请求。
    `subprocess.run(..., timeout=...)` 是唯一能保证返回的手段 ——
    一次被切断的渲染，比一条永远不返回的请求好得多。

**二、`node` 不在 PATH 时不抛异常，返回 `{"ok": False, "detail": "node_missing"}`**

    报告模块坏了 ≠ 结案失败。渲染是结案的**下游副作用**：它失败时
    案件仍然已经结案（权威已提交），把异常上浮成 HTTP 500 会让用户以为
    结案没成功，从而重复提交。

**三、snapshot 走 stdin，不走 argv**

    快照可能几十 KB，其中 IR 的 findings/coverage 会更大。argv 有
    `ARG_MAX`（Linux 常见 128KB），超了是 `OSError: E2BIG` ——
    一种随数据量才出现的失败，本地小样本永远看不见。

**四、不做任何重试**

    重试会把「渲染器坏了」变成「结案慢 30 秒 × N 次」。渲染失败要立刻
    可见（`detail` 带原因），而不是被重试掩盖成一次延迟。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

#: 渲染器路径（相对仓库根）。构造时允许覆盖，便于验证器指向别的实现。
DEFAULT_RENDERER = os.path.join("tools", "audit", "report_render.mjs")

_RENDER_TIMEOUT = 30

#: 这个 runner 做的事：import 渲染器 → 从 stdin 读完 → 调 renderReport。
#:
#: ★ 为什么用 `-e` 内联而不是写一个 .mjs 落盘：
#:   落盘就要管临时文件的清理与权限，而渲染器本身是纯函数。
#:   `--input-type=module` 让 `import` 在 `-e` 里可用。
#:
#: ★ 为什么输出包一层 `{ok, errors, markdown}` 而不是原样转发：
#:   渲染器返回里还有 hits/warnings/blocked。原样转发会让「桥接层返回什么」
#:   等于「渲染器今天返回什么」—— 渲染器加一个字段，桥接层的契约就悄悄变了。
#:   这里只留三个键，是**主动收窄**，让下游读的东西是稳定的。
_RUNNER = (
    "import { renderReport } from %s;\n"
    "let buf = '';\n"
    "for await (const chunk of process.stdin) buf += chunk;\n"
    "let out;\n"
    "try {\n"
    "  const r = renderReport(JSON.parse(buf));\n"
    "  out = { ok: r.ok === true, errors: r.errors || [],\n"
    "          markdown: r.markdown || '', hits: r.hits || [],\n"
    "          warnings: r.warnings || [], blocked: r.blocked === true };\n"
    "} catch (err) {\n"
    "  out = { ok: false, errors: [String(err && err.message || err)],\n"
    "          markdown: '', hits: [], warnings: [], blocked: true };\n"
    "}\n"
    "process.stdout.write(JSON.stringify(out));\n"
)


def _normalize(payload):
    """渲染器输出 → 稳定三键 + 可选 detail。**未知形状一律按失败处理。**

    ★ 为什么要判 `ok is True` 而不是 `payload.get("ok")`：
      渲染器万一改成返回 `"ok": "true"`（字符串），truthy 判定会放行，
      而下游 `if not result["ok"]` 也放行 —— 两个宽松判定加起来，
      一份**没渲染出来**的空 markdown 会被当成成功发出去。
    """
    if not isinstance(payload, dict):
        return {"ok": False, "markdown": "", "errors": ["bad_output:not_object"],
                "detail": "bad_output"}
    ok = payload.get("ok") is True
    markdown = payload.get("markdown")
    errors = payload.get("errors")
    if not isinstance(markdown, str):
        markdown = ""
    if not isinstance(errors, list):
        errors = [str(errors)] if errors else []
    # ★ 为什么成功条件是**两条**：说成了 **且** 真的产出了正文。
    #
    #   `ok=True` 但 markdown 为空：渲染器说成了，却什么都没产出。
    #   这种情况**不许**当成功 —— 下游会拿空字符串去 publish，
    #   然后 `_check_r1` 报一个看不出根源的错（「fingeprint 行缺失」），
    #   而真正的原因在渲染器那一侧。
    #
    #   ★ 判据只有这一处。第一版把它拆成了两半 —— 上面 `ok and bool(markdown)`，
    #     下面再 `if ok and not markdown: result["ok"]=False` —— 于是
    #     变异「去掉后一半」**没有红**：前一半已经挡住了。**同一个判据写两遍，
    #     两遍里任意一遍都是冗余的，冗余的那一遍永远测不出东西。**
    if ok and not markdown:
        return {"ok": False, "markdown": "",
                "errors": [str(e) for e in errors] or ["渲染器返回 ok 但 markdown 为空"],
                "detail": "empty_markdown"}
    return {
        "ok": ok,
        "markdown": markdown if ok else "",
        "errors": [str(e) for e in errors],
    }


class ReportRenderBridge:
    """调 Node 渲染器。**无状态、无线程、无重试。**

    `node_path=None` 表示用 `shutil.which("node")` 现场找。允许注入是为了
    验证器能构造「node 不存在」这个形状（把 PATH 清空也行，但那会影响
    同一进程里别的子进程调用）。
    """

    def __init__(self, repo_root, *, renderer=None, node_path=None,
                 timeout=_RENDER_TIMEOUT):
        self.repo_root = os.path.abspath(str(repo_root))
        self.renderer = os.path.abspath(
            renderer or os.path.join(self.repo_root, DEFAULT_RENDERER))
        self._node_path = node_path
        self.timeout = float(timeout)

    def node(self):
        """返回可用的 node 路径；没有则 None。

        ★ 每次现找而不缓存：容器里 `node` 可能在启动后才出现（镜像分层、
          volume 覆盖），缓存会把「刚装好」当成「一直没有」。
        """
        if self._node_path is not None:
            return self._node_path or None
        return shutil.which("node")

    def render(self, snapshot):
        """`snapshot -> {ok, markdown, errors, detail?}`。**任何情况都返回 dict。**"""
        node = self.node()
        if not node:
            return {"ok": False, "markdown": "", "errors": ["node_missing"],
                    "detail": "node_missing"}
        if not os.path.isfile(self.renderer):
            return {"ok": False, "markdown": "", "errors": ["renderer_missing"],
                    "detail": "renderer_missing"}
        if not isinstance(snapshot, dict):
            return {"ok": False, "markdown": "", "errors": ["bad_snapshot"],
                    "detail": "bad_snapshot"}
        code = _RUNNER % json.dumps("file://" + self.renderer)
        try:
            payload = json.dumps(snapshot, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            # 快照里有不可序列化的东西（datetime/自定义对象）。这是**调用方**的错，
            # 不是渲染器的错 —— 报清楚，不要让它以 TypeError 冒到 HTTP 层。
            return {"ok": False, "markdown": "",
                    "errors": ["snapshot_not_serializable"],
                    "detail": "snapshot_not_serializable:%s" % type(exc).__name__}
        try:
            proc = subprocess.run(
                [node, "--input-type=module", "-e", code],
                input=payload, capture_output=True, text=True,
                timeout=self.timeout,
                # ★ 不继承当前环境里的 NODE_OPTIONS：它可能带 --require，
                #   在容器里指向一个不存在的文件，然后渲染器起不来。
                env={"PATH": os.environ.get("PATH",
                                            "/usr/local/bin:/usr/bin:/bin"),
                     "NODE_ENV": "production"},
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "markdown": "", "errors": ["render_timeout"],
                    "detail": "render_timeout:%ss" % self.timeout}
        except OSError as exc:
            # node 存在但起不来（权限/架构不符 —— 沙盒里见过 Exec format error）
            return {"ok": False, "markdown": "",
                    "errors": ["render_spawn_failed"],
                    "detail": "render_spawn_failed:%s" % type(exc).__name__}
        if proc.returncode != 0:
            tail = (proc.stderr or "")[:500]
            return {"ok": False, "markdown": "",
                    "errors": ["render_exit:%d" % proc.returncode, tail],
                    "detail": "render_exit:%d" % proc.returncode}
        try:
            parsed = json.loads(proc.stdout)
        except ValueError:
            return {"ok": False, "markdown": "",
                    "errors": ["render_bad_json", (proc.stdout or "")[:200]],
                    "detail": "render_bad_json"}
        return _normalize(parsed)


def render_snapshot(snapshot, *, repo_root, node_path=None):
    """一次性便利函数。生产请持有 `ReportRenderBridge` 实例。"""
    return ReportRenderBridge(repo_root, node_path=node_path).render(snapshot)
