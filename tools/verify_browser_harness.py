#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_browser_harness.py —— `web/scripts/lib/browser_harness.mjs` 的判据

## 这个文件为什么存在

`browser_harness.mjs` 是前后端接线联调（pairing）的驱动。它是**工具的工具**：
一旦它悄悄坏了，坏法不是「报错」，而是**联调结果不可信** ——
比如 Chrome 起不来时返回空文本，而空文本与「页面确实是空的」长得一样。
那正是 AGENTS §2.4.1 第 4 行的形状：否定结论的输入比它说出口的小。

所以这一份断言不验「页面长什么样」（那是 `pairing_check.mjs` 的事），
只验驱动本身的三条硬约束 + CLI 三态退出码：

    H1  Chrome 不存在 → 抛 **HarnessUntested**（不是普通 Error）
        —— 调用方据此退 2（未测），不是退 1（红）
    H2  每个 CDP 调用都有超时；超时抛 HarnessFailed 且**不挂住**
    H3  `close()` 幂等；关掉之后再用必须明确失败（不是静默成功）
    H4  ★ CLI 三态：好页面 → rc=0；坏选择器 → rc=1；无 Chrome → rc=2
        —— 这一条是「未测 ≠ 红 ≠ 通过」在**进程退出码**上的执行点
    H5  `goto` 等到 `readyState=complete` 才返回；页内 JS 抛错必须变成
        HarnessFailed（不是静默返回 undefined）
    H6  后台进程/临时 profile 在 close 之后不残留（读了 profile 路径再验它没了）

## 为什么 H1/H4 要分开测

H1 测的是**模块 API**（`launch()` 抛什么类），H4 测的是**CLI 退出码**。
两者可以各自正确而合起来错：`launch()` 抛对了类，而 CLI 的 catch 分支
把它当普通错误退 1 —— 那时 API 层全绿，而实际操作得到「红」。
本仓已有的教训（§2.4.5「两个各自都对的部件，合起来必然撞车」）。

## 退出码

  0 全过 · 1 有红 · 2 未测（node 不可用 / Chrome 不可用 —— 本文件自己也守这条）

用法：
  python3 tools/verify_browser_harness.py
  python3 tools/verify_browser_harness.py --controls   # 喂坏样本必须红
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(ROOT, "web", "scripts", "lib", "browser_harness.mjs")

PASS = []
FAIL = []
UNTESTED = []


def ok(label, detail=""):
    PASS.append(label)
    print("PASS: %s%s" % (label, (" " + detail) if detail else ""))


def no(label, detail=""):
    FAIL.append((label, detail))
    print("FAIL: %s%s" % (label, (" " + detail) if detail else ""),
          file=sys.stderr)


if not os.path.isfile(HARNESS):
    print("UNTESTED: 找不到 %s" % HARNESS)
    sys.exit(2)

try:
    NODE = shutil.which("node")
    if not NODE:
        raise RuntimeError("node 不在 PATH")
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: %s" % exc)
    sys.exit(2)


CHROME = (os.environ.get("CHROME_BIN")
          or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_OK = os.path.isfile(CHROME)


def node(script, args=None, env=None, timeout=90):
    """跑一段 node 脚本，返回 (rc, stdout, stderr)。

    ★ 不接管道：`$?` 在管道后面取的是最后一个命令的状态（§2.2 第 6 条）。
      这里直接取 subprocess 的 returncode。
    """
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [NODE, "--input-type=module", "-e", script] + list(args or []),
        cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        env=full_env)
    return proc.returncode, proc.stdout, proc.stderr


def cli(args, env=None, timeout=120):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run([NODE, HARNESS] + args, cwd=ROOT,
                          capture_output=True, text=True, timeout=timeout,
                          env=full_env)
    return proc.returncode, proc.stdout, proc.stderr


def check_h1_no_chrome():
    """H1：Chrome 不存在时必须抛 HarnessUntested。"""
    script = """
import { launch, HarnessUntested } from %s;
try {
  await launch();
  console.log("LAUNCHED");
} catch (e) {
  console.log(e instanceof HarnessUntested ? "UNTESTED_CLASS" : "OTHER:" + e.name);
}
""" % json.dumps(HARNESS)
    rc, out, err = node(script, env={"CHROME_BIN": "/nonexistent/chrome-xyz"})
    out = out.strip()
    if rc != 0:
        no("H1 无 Chrome 时必须抛 HarnessUntested（脚本本身崩了）",
           (err or out)[:200])
    elif out == "UNTESTED_CLASS":
        ok("H1 ★ 无 Chrome → HarnessUntested（调用方据此退 2，不是退 1）")
    elif out == "LAUNCHED":
        no("H1 指定不存在的 CHROME_BIN 却起来了（环境变量没生效？）", out)
    else:
        no("H1 无 Chrome 时抛了错误的异常类型", out)


def check_h2_timeout_and_h3_close():
    """H2 超时 / H3 close 幂等 + 关闭后调用必须失败。"""
    if not CHROME_OK:
        print("⚠ 未测：H2/H3 需要本机 Chrome（%s）" % CHROME)
        UNTESTED.append("H2/H3")
        return
    script = """
import { launch, HarnessFailed } from %s;
const s = await launch();
const out = {};
try {
  await s.goto("data:text/html,<p>ok</p>");

  // H2：必须让一个**真的慢**的调用超时。
  //   ★ 两版都错了，两次都是「判据没测到它要说的事」：
  //     第一版超时给 1ms → elapsed=0，看着像「秒超时」，其实是 CDP 返回太快，
  //     计时器根本没触发，断言证的是「调用成功」。
  //     第二版给 60ms 时也还是 NO_THROW —— 因为 CDP 往返只有 1ms。
  //     真正的做法是让**页面内**自己挂住：evaluate 一个 5 秒的 Promise
  //     （awaitPromise: true 会让 CDP 等它），再给 120ms 超时。
  //     这时超时必然触发，而 elapsed 会落在 [120, 3000) 之间 ——
  //     它既证明「超时抛对了」，也证明「它没有把 5 秒等完」。
  const t0 = Date.now();
  try {
    await s.send("Runtime.evaluate", {
      expression: "new Promise((r) => setTimeout(() => r(1), 5000))",
      awaitPromise: true,
      returnByValue: true,
    }, 120);
    out.timeout = "NO_THROW";
  } catch (e) {
    out.timeout = e instanceof HarnessFailed ? "FAILED_CLASS" : "OTHER:" + e.name;
  }
  out.timeout_ms = Date.now() - t0;

  // H3：close 两次都不许抛
  await s.close();
  try { await s.close(); out.close_twice = "OK"; }
  catch (e) { out.close_twice = "THREW:" + e.message; }

  // H3：关闭后再 eval 必须明确失败（不是静默 undefined）
  try {
    const v = await s.eval("1+1");
    out.after_close = "SILENT:" + JSON.stringify(v);
  } catch (e) {
    out.after_close = e instanceof HarnessFailed ? "FAILED_CLASS" : "OTHER:" + e.name;
  }
} finally {
  try { await s.close(); } catch {}
}
console.log(JSON.stringify(out));
""" % json.dumps(HARNESS)
    rc, out, err = node(script)
    if rc != 0:
        no("H2/H3 脚本本身出错", (err or out)[:300])
        return
    try:
        d = json.loads(out.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        no("H2/H3 输出不是 JSON", out[-300:])
        return

    # ★ 双向判据，缺一条这一条就退化成假绿：
    #   下界 elapsed ≥ 100  → 超时**真的触发过**（不是响应太快蒙混过关）；
    #   上界 elapsed < 3000 → 它**没有**把页面里那个 5 秒的 Promise 等完
    #                         （等到 5 秒说明超时没生效，只是恰好在 5 秒后抛错）。
    elapsed = d.get("timeout_ms", 0)
    if d.get("timeout") == "FAILED_CLASS" and 100 <= elapsed < 3000:
        ok("H2 ★ 超时抛 HarnessFailed：等了 %dms（超时设 120ms，页面里挂 5000ms）"
           % elapsed)
    else:
        no("H2 超时判据不成立（elapsed=%sms，期望 [100, 3000) 区间）" % elapsed,
           json.dumps(d, ensure_ascii=False))
    if d.get("close_twice") == "OK":
        ok("H3 ★ close() 幂等（连调两次不抛）")
    else:
        no("H3 close() 不幂等", d.get("close_twice", ""))
    if d.get("after_close") == "FAILED_CLASS":
        ok("H3 ★ 关闭后调用明确失败（不是静默返回 undefined）")
    else:
        no("H3 关闭后的调用没有明确失败", d.get("after_close", ""))


def check_h4_cli_three_states():
    """H4：CLI 三态退出码 —— 0 通过 / 1 红 / 2 未测。"""
    if not CHROME_OK:
        print("⚠ 未测：H4 需要本机 Chrome")
        UNTESTED.append("H4")
        return
    # 好样本：能取到文本 → 0
    rc, out, _ = cli(["goto", "data:text/html,<p id=x>PAIRING-OK</p>"])
    if rc == 0 and "PAIRING-OK" not in out:
        # goto 只打印 url，不打印文本 —— 再跑一次 text 取值
        rc2, out2, _ = cli(["text"])
        rc = rc2 if rc2 != 0 else rc
        detail = out2.strip()[:60]
        ok("H4 ★ CLI 好样本 rc=0") if rc == 0 and "PAIRING-OK" in out2 else no(
            "H4 CLI 好样本没取到页面文本", detail)
    elif rc == 0:
        ok("H4 ★ CLI 好样本 rc=0")
    else:
        no("H4 CLI 好样本应为 rc=0", str(rc))

    # 坏样本：等一个不存在的选择器 → 1（不是 2，也不是 0）
    rc, out, err = cli(["wait", "#definitely-not-there", "1200"])
    if rc == 1:
        ok("H4 ★ CLI 坏样本（选择器等不到）rc=1 —— 「测了不符合预期」")
    else:
        no("H4 CLI 坏样本应为 rc=1", "rc=%s %s" % (rc, (err or out)[:120]))

    # 未测：无 Chrome → 2（不是 1）
    rc, out, err = cli(["text"], env={"CHROME_BIN": "/nonexistent/chrome-xyz"})
    if rc == 2:
        ok("H4 ★ CLI 无 Chrome rc=2 —— 「未测 ≠ 红」在执行码上成立")
    else:
        no("H4 CLI 无 Chrome 应为 rc=2（不是 1/0）",
           "rc=%s %s" % (rc, (err or out)[:120]))


def check_h5_goto_and_js_error():
    """H5：goto 等 readyState；页内 JS 抛错 → HarnessFailed。"""
    if not CHROME_OK:
        print("⚠ 未测：H5 需要本机 Chrome")
        UNTESTED.append("H5")
        return
    script = """
import { launch, HarnessFailed } from %s;
const s = await launch();
const out = {};
try {
  // goto 返回后 readyState 必须已经是 complete（不是停在 loading）
  await s.goto("data:text/html,<div id=ready>R</div>", 0);
  out.ready = await s.eval("document.readyState");

  // 页内抛错必须变成 HarnessFailed，不许静默返回 undefined
  try {
    const v = await s.eval("(() => { throw new Error('boom'); })()");
    out.js_error = "SILENT:" + JSON.stringify(v);
  } catch (e) {
    out.js_error = e instanceof HarnessFailed ? "FAILED_CLASS" : "OTHER:" + e.name;
  }
} finally {
  await s.close();
}
console.log(JSON.stringify(out));
""" % json.dumps(HARNESS)
    rc, out, err = node(script)
    if rc != 0:
        no("H5 脚本本身出错", (err or out)[:300])
        return
    try:
        d = json.loads(out.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        no("H5 输出不是 JSON", out[-300:])
        return
    if d.get("ready") == "complete":
        ok("H5 ★ goto 返回时 readyState=complete")
    else:
        no("H5 goto 返回时页面还没 load 完", repr(d.get("ready")))
    if d.get("js_error") == "FAILED_CLASS":
        ok("H5 ★ 页内 JS 抛错 → HarnessFailed（不是静默 undefined）")
    else:
        no("H5 页内 JS 抛错没有明确失败", d.get("js_error", ""))


def check_h6_no_residue():
    """H6：close 之后临时 profile 目录被删。

    ★ 第一版扫的是 `/tmp/browser_harness_*`，而 node 的 `os.tmpdir()` 是
      `/var/folders/.../T`（macOS 上每个用户不同）—— 于是它扫了一个
      **本来就没有东西的目录**，得到 `0 → 0`，恒真。
      现在改为：从 harness 自己声明的 `_profileDir` 读真实路径
      （它是唯一真相），close 前必须存在、close 后必须不存在。
    """
    if not CHROME_OK:
        print("⚠ 未测：H6 需要本机 Chrome")
        UNTESTED.append("H6")
        return
    script = """
import { launch } from %s;
import fs from "node:fs";
const s = await launch();
const out = { profile: s._profileDir };
out.existed_before = fs.existsSync(s._profileDir);
await s.goto("data:text/html,<p>x</p>");
await s.close();
await new Promise((r) => setTimeout(r, 300));
out.exists_after = fs.existsSync(s._profileDir);
console.log(JSON.stringify(out));
""" % json.dumps(HARNESS)
    rc, out, err = node(script)
    if rc != 0:
        no("H6 脚本本身出错", (err or out)[:300])
        return
    try:
        d = json.loads(out.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        no("H6 输出不是 JSON", out[-300:])
        return
    prof = d.get("profile") or ""
    # ★ 三个方向都要查：路径真实存在过（否则「删掉了」是假象）、
    #   它是本次的临时目录（不是误指到别处）、关了之后它真的没了。
    if not prof or "browser_harness_" not in prof:
        no("H6 harness 没有可读的 profile 路径（判据无法成立）", repr(prof))
        return
    if not d.get("existed_before"):
        no("H6 close 之前 profile 就不存在 —— 「删掉了」无从谈起", prof)
        return
    if d.get("exists_after"):
        no("H6 close 后 profile 仍残留", prof)
    else:
        ok("H6 ★ close 后临时 profile 被删（%s）" % prof.split("/")[-1])


def check_h7_keep_flag():
    """H7：`dev-up.sh --keep` 的两个方向。

    ★ 为什么这一条属于**本文件**：`--keep` 是为联调存在的（见它的注释），
      而联调的唯一入口是 `pairing_check.mjs`。若 `--keep` 没生效，
      联调拿不到端口与 PID，只能自己去猜 —— 那时联调会报「连不上」，
      而读的人会去查前端。所以「启动脚本的联调开关」与「联调驱动」
      是同一个失效面。

    两个方向缺一不可：
      a) `--help` 必须列出 `--keep`（开关存在且自述）
      b) 未知参数必须在**启动任何东西之前**退 2（不是跑一半才失败）
    """
    devup = os.path.join(ROOT, "web", "scripts", "dev-up.sh")
    if not os.path.isfile(devup):
        no("H7 找不到 web/scripts/dev-up.sh")
        return
    proc = subprocess.run(["bash", devup, "--help"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode == 0 and "--keep" in proc.stdout:
        ok("H7 ★ dev-up.sh --help 自述 --keep（联调开关存在）")
    else:
        no("H7 dev-up.sh --help 没提到 --keep",
           "rc=%s %s" % (proc.returncode, proc.stdout[:120]))

    # b) 未知参数：必须早退 2，且**不许**在 stdout 里出现任何阶段标记
    proc = subprocess.run(["bash", devup, "--no-such-flag"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
    staged = "[1/11]" in (proc.stdout or "")
    if proc.returncode == 2 and not staged:
        ok("H7 ★ 未知参数 → rc=2 且在任何阶段之前退出（未测，不是红）")
    else:
        no("H7 未知参数没有早退",
           "rc=%s staged=%s %s" % (proc.returncode, staged,
                                   (proc.stdout or "")[:120]))


def run_controls():
    """反向对照：H1/H4 的判据自己会不会红。"""
    print("=" * 70)
    print("反向对照：判据自己会不会红")
    print("=" * 70)
    results = []

    # C1：把源码里的 HarnessUntested 改名 —— H1 与 H4 的 rc=2 必须红。
    #   ★ 这是唯一能证明「未测」不是巧合的办法：如果 H1 只看「没起来」，
    #     改成普通 Error 它照样绿。
    saved = None
    try:
        with open(HARNESS, encoding="utf-8") as f:
            saved = f.read()
        mutated = saved.replace("class HarnessUntested extends Error",
                                "class HarnessNotReallyUntested extends Error")
        mutated = mutated.replace("new HarnessUntested(", "new HarnessNotReallyUntested(")
        with open(HARNESS, "w", encoding="utf-8") as f:
            f.write(mutated)
        before = len(FAIL)
        check_h1_no_chrome()
        went_red = len(FAIL) > before
        while len(FAIL) > before:
            FAIL.pop()
        results.append(("C1 改名 HarnessUntested → H1 必须红", went_red, True))
    finally:
        if saved is not None:
            with open(HARNESS, "w", encoding="utf-8") as f:
                f.write(saved)

    # C2：把 CLI 的「未测退 2」改成退 1 —— H4 必须红。
    try:
        with open(HARNESS, encoding="utf-8") as f:
            saved = f.read()
        mutated = saved.replace(
            'if (e instanceof HarnessUntested) {\n      console.error("⚠ 未测：" + e.message);\n      process.exit(2);\n    }',
            'if (e instanceof HarnessUntested) {\n      console.error("⚠ 未测：" + e.message);\n      process.exit(1);\n    }')
        changed = mutated != saved
        with open(HARNESS, "w", encoding="utf-8") as f:
            f.write(mutated)
        before = len(FAIL)
        if changed:
            check_h4_cli_three_states()
        went_red = (len(FAIL) > before) if changed else False
        while len(FAIL) > before:
            FAIL.pop()
        results.append(("C2 未测退 2 改成退 1 → H4 必须红", went_red, True))
    finally:
        if saved is not None:
            with open(HARNESS, "w", encoding="utf-8") as f:
                f.write(saved)

    print("=" * 70)
    bad = 0
    for name, red, want in results:
        good = red == want
        bad += 0 if good else 1
        print("%s %s（红了=%s，期望红=%s）" % ("✅" if good else "❌", name, red, want))
    if bad == 0:
        print("✅ 反向对照 %d/%d 全过" % (len(results), len(results)))
        return 0
    print("❌ 反向对照 %d/%d 通过" % (len(results) - bad, len(results)),
          file=sys.stderr)
    return 1


def main():
    print("=" * 70)
    print("verify_browser_harness · 联调驱动的三条硬约束 + CLI 三态")
    print("=" * 70)
    check_h1_no_chrome()
    check_h2_timeout_and_h3_close()
    check_h4_cli_three_states()
    check_h5_goto_and_js_error()
    check_h6_no_residue()
    check_h7_keep_flag()

    print("-" * 70)
    print("通过 %d 项 · 红 %d 项 · 未测 %d 项"
          % (len(PASS), len(FAIL), len(UNTESTED)))
    if FAIL:
        for label, detail in FAIL:
            print("  ✗ %s %s" % (label, detail), file=sys.stderr)
        print("❌ 有红", file=sys.stderr)
        return 1
    if UNTESTED:
        print("⚠ 有未测（本机没有 Chrome）—— 未测不是通过", file=sys.stderr)
        return 2
    print("✅ 全过")
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(run_controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常：%s" % exc, file=sys.stderr)
        sys.exit(2)
