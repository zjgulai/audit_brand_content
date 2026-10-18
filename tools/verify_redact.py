#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_redact.py —— `redact.py` 的判据（T0-09 外发最小化 / PII）

## 它验什么

三条，缺一条都不算「外发最小化」成立：

  A **必拦**：凭据形态 / 身份证·护照 / 手机·邮箱 / 内部绝对路径 / tool_call_id·栈帧
    —— 每类都有正样本，断言**至少产出一条对应类型**的 finding，且**原文不回显**。
  B **必放**：普通营销文案里的价格 / 尺寸 / 月龄 / 型号 / 日期 / URL 商品 ID
    —— 每类都有负样本，断言 **0 条 finding**。这一条防的是「全拦」：
    一个把什么都标红的脱敏器，等于把外发内容全变成 `[REDACTED]`，业务没法用。
  C **规则是承重的**：把某条规则单独禁用 → 对应正样本必须**不再**产出该类型 finding。
    没有这一条，A 可能只是在验一个与被测规则无关的兜底。

## 退出码

  0 全过 · 1 有红 · 2 未测（样本表为空 / 导入失败之外的不可测条件）

## 口径（照实写）

  - **纯离线**：不联网、不读仓内日志、不写任何文件。
  - finding 只带 `type / start / end / sha256[:16]`，**不回显原文**；
    本脚本用输入切片自行验证「原文不在 safe_text 里」，而不是信 finding 自报。
  - 规则是**文本形态**匹配（正则），不是语义判断：故意把手机号写进 URL 的样本
    不在必拦范围内（见 redact.py 的边界说明）。
"""
from __future__ import annotations

import hashlib
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
try:
    import redact as R
except Exception as e:  # noqa: BLE001
    print("❌ 导入 redact.py 失败：%s" % e)
    sys.exit(1)

# ── A 必拦样本：(id, 文本, 期望命中类型之一) ──────────────────────────────
POSITIVE = [
    ("A1 凭据键值", "配置里写着 api_key=AbCdEf1234567890 ，别外发", "credential_kv"),
    ("A1b 凭据键值（冒号）", "secret: SuperSecretValue123", "credential_kv"),
    ("A2 Bearer", "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", "bearer"),
    ("A3 sk 密钥", "key=sk-abcdefghijklmnop123456", "api_key_sk"),
    ("A4 飞书 wbk", "tenant token wbk_AbCdEf1234567890", "feishu_wbk"),
    ("A5 邮箱", "请联系 someone@example.com 处理", "email"),
    ("A6 身份证", "身份证 110101199003071234", "cn_id"),
    ("A6b 身份证 X 尾", "证件号 11010119900307123X", "cn_id"),
    ("A7 护照", "护照号 E12345678", "passport"),
    ("A8 手机号", "联系电话 13800138000", "phone_cn"),
    ("A8b 手机号 +86", "电话 +86 13800138000", "phone_cn"),
    # ★ 国际号不能选 +1 415…：`14155552671` 同时符合 phone_cn（1 后跟 4 属 [3-9]），
    #   禁用 phone_e164 后会被 phone_cn 兜住 —— C 段就测不出 e164 规则承重。
    ("A9 国际号", "call +33612345678", "phone_e164"),
    ("A10 绝对路径", "/Users/lute/Project/audit_multi_content/tools/agent/config.mjs", "abs_path"),
    ("A10b 家目录凭据路径", "~/.dsh/credentials/shouheng-lark.json", "home_secret_path"),
    ("A11 tool_call_id", "tool_call_id=call_abc123def456ghi789", "tool_call_id"),
    # ★ 裸 call_ 规则（RULES 里第二条 tool_call_id）必须有自己的正样本：
    #   上面那条自带 `tool_call_id=` 前缀，只有第一条规则接得住；删掉第二条仍全绿（实测过）。
    ("A11b 裸 call_ id", "日志里出现 call_abc123def456ghi789 ，请按 id 查", "tool_call_id"),
    # ★ 栈帧样本刻意用**相对路径**：绝对路径会被 abs_path 规则兜住，
    #   于是「删掉 stack_frame_* 规则」仍被另一条规则脱敏 —— C 段就测不出承重。
    ("A12 栈帧（File）", '  File "src/main.py", line 12, in handler\n    raise X', "stack_frame_file"),
    ("A13 栈帧（at）", "    at Object.<anonymous> (src/main.py:12:5)", "stack_frame_at"),
]

# ── B 必放样本：普通营销文案，0 条 finding ────────────────────────────────
NEGATIVE = [
    ("B1 价格/容量/月龄", "新品上市：售价 $199.99，容量 240ml，适合 0-6 个月宝宝。"),
    ("B2 型号/日期", "Momcozy S12 Pro 吸奶器，型号 M5，2026-09-24 发布。"),
    # ★ 必须是 11 位、以 138 开头（形态与国内手机号完全相同），否则这条负样本
    #   根本不会触发 phone_cn —— 删掉 no_url 守卫也全绿（实测过）。
    ("B3 URL 商品 ID（11 位、形态同手机号）", "https://shop.example.com/item/13800138000?sku=BM04"),
    # ★ 同一个守卫也挂在 phone_e164 上：只测 phone_cn 的话，删掉 e164 的 no_url 仍全绿。
    ("B3b URL 里的国际号形态", "https://shop.example.com/call/+33612345678"),
    ("B4 订单号", "产品编号 1234567890，批次 2026-09"),
    ("B5 功效数字", "对比 28.2% Faster / 292 mmHg Strong Suction"),
    ("B6 英文文案", "Clinically proven, 18% more milk on average."),
    ("B7 促销日期", "Amazon Prime Big Days 2026-10-08 至 2026-10-09"),
    ("B8 尺寸", "尺寸 1280×720，重量 1.2kg，电压 110V"),
]


def main() -> int:
    if not POSITIVE or not NEGATIVE:
        print("⚠ 未测：样本表为空 —— 空样本表不是「全过」")
        return 2

    fails: list[str] = []
    checks = 0

    # A 必拦 + 不回显 + 位置合法
    for sid, text, want in POSITIVE:
        checks += 1
        safe, findings = R.redact(text)
        types = [f["type"] for f in findings]
        if want not in types:
            fails.append("%s：期望命中 %s，实际 %s" % (sid, want, types or "（无）"))
            continue
        # 原文不回显：用输入切片验证，而不是信 finding 自报
        for f in findings:
            checks += 1
            if not (0 <= f["start"] < f["end"] <= len(text)):
                fails.append("%s：位置非法 %s" % (sid, f))
            elif text[f["start"]:f["end"]] in safe:
                fails.append("%s：原文仍在 safe_text 里（%s）" % (sid, f["type"]))
        # finding 不许带原文
        for f in findings:
            checks += 1
            if "text" in f or "raw" in f or "match" in f:
                fails.append("%s：finding 带回了原文（%s）" % (sid, sorted(f)))

    # B 必放（防「全拦」）
    for sid, text in NEGATIVE:
        checks += 1
        safe, findings = R.redact(text)
        if findings:
            fails.append("%s：干净文本被误拦 —— %s" % (sid, [(f["type"], text[f["start"]:f["end"]]) for f in findings]))
        if safe != text:
            fails.append("%s：干净文本被改写" % sid)

    # C 规则承重：禁用某类型 → **原敏感切片必须重新出现在 safe_text 里**
    # ★ 旧写法「禁用后不再命中该类型」是恒真的：被禁规则根本不会产出 finding，
    #   所以它证明不了这条规则在任何样本上真的干了活。现在要求阳性证据：
    #   ① 未禁用时该类型确实切出了片段；② 禁用后至少有一个原片段原样回到输出里。
    #   若另一个类型/同类型另一条规则把它兜住了，就说明「这条规则对这一样本不承重」。
    for sid, text, want in POSITIVE:
        checks += 1
        safe0, findings0 = R.redact(text)
        want_slices = [text[f["start"]:f["end"]] for f in findings0 if f["type"] == want]
        if not want_slices:
            fails.append("%s：未禁用时就没命中 %s —— C 无法判定承重" % (sid, want))
            continue
        checks += 1
        safe1, _ = R.redact(text, disabled={want})
        if not any(sl in safe1 for sl in want_slices):
            fails.append("%s：禁用 %s 后原切片仍被脱敏（被另一条规则兜住）—— 该规则对这一样本不承重"
                         % (sid, want))

    for m in fails:
        print("  ❌ " + m)
    ok = len(fails) == 0
    print("\n%s verify_redact %d 项检查 · %d 项红 · 样本 正 %d / 负 %d"
          % ("✅" if ok else "❌", checks, len(fails), len(POSITIVE), len(NEGATIVE)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
