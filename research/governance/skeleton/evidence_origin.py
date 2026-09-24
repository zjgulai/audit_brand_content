#!/usr/bin/env python3
"""
evidence_origin.py —— 证据来源分级（T19 · C2 移植）

## 这个模块治的病

PRD §5.2 说图片走「OCR + 基础视觉识别」、视频走「字幕/旁白 + 关键帧 + OCR」，
**但没说 OCR 出来的字在证据链里比正文低一档。**
于是「图片里写着 FDA approved」与「正文里写着 FDA approved」在判定里是同一件事。

本模块把那句话补上：**每一条证据都要声明它是怎么来的，而且弱的那些不能单独把结论推到 PASS。**

## ★★ 本文件里有两个 `origin`，它们不是一回事

这是本模块存在时**当场撞到的**一件事，必须写在最前面：

| 名字 | 说的是 | 取值 | 住在哪 |
|---|---|---|---|
| `receipt["origin"]` | **回执来源**：这次判定是谁发起的 | `cli` / `batch` / `shouheng` / `test` | 回执顶层 |
| `input["evidence_origin"]` | **证据来源**：被审的材料是怎么读到的 | `stated` / `ocr` / `transcribed` / `described` | 判定输入块 |

两者都叫 origin，都在同一份回执里，**但一个字节也不重叠**。
危险在于它们看起来可以互换：把 `origin="stated"` 写进回执顶层，
`push_receipts.py` 那道「`origin=test` 不许进生产账本」的闸门会照常放行；
反过来把 `evidence_origin="test"` 填进输入块，则没有任何东西会红。

所以本模块**不新增一个叫 origin 的字段**，而是：

* 证据来源一律叫 **`evidence_origin`**（输入块）或写在 `evidence_ref.origin` 里（结构化地址内部）；
* 并给出 `receipt_origin_problems()` —— 它断言**两个取值域互不相交**，
  谁把 `stated` 写进回执顶层、或把 `test` 写进证据来源，都会红。

> 这正是 `AGENTS.md` §2.4.5 的形状：**两个各自都对的部件，合起来必然撞车。**
> 修法不是给其中一个改措辞了事，是把两者的取值域钉成互斥的，并让判据盯着。

## 四档

| 档 | 什么意思 | 能不能单独把结论推到 PASS |
|---|---|---|
| `stated` | 原文照读（网页正文 / API 文本 / 文档原话） | ✅ |
| `ocr` | 图片里的文字，经 OCR 取出 | ❌ |
| `transcribed` | 音视频转写 | ❌ |
| `described` | 模型对画面的**转述**（不是画面里的字） | ❌ |

蓝本 `extraction.rs:97` 的 `DESCRIBED_CEILING = LOW_CONFIDENCE_BELOW - 0.05`
是同一个判断的更细版本（`described` 连「关掉一条旧事实」都不许，只开冲突且压到人看）。
本模块只实现 PRD 缺的那一档。

## 接线状态

* **W1（本模块 + 判据）已完成**：四档枚举、`may_finalize_pass()`、反例与正例对照。
* **W3（接线）未完成**：`evidence_ref` 目前由回执侧**还没产出**（T4）。
  今天真正在跑的是 `input.evidence_origin` —— 文字输入的判定一律 `stated`，
  所以收窄**今天不会触发**；它触发的那一天，是图片/视频第一次进审查的那一天。
"""

ORIGINS = ("stated", "ocr", "transcribed", "described")
ORIGIN_MEANING = {
    "stated": "原文照读（网页正文 / API 文本 / 文档原话）",
    "ocr": "图片里的文字，经 OCR 取出",
    "transcribed": "音视频转写",
    "described": "模型对画面的转述（不是画面里的字）",
}
# ★ 「只有 stated 能单独支撑 PASS」是**唯一**一处定义。
PASS_ORIGINS = ("stated",)

# 回执来源 —— 与证据来源**互不相交**，见模块抬头那张表。
RECEIPT_ORIGINS = ("cli", "batch", "shouheng", "test")


def evidence_problems(refs, where=""):
    """每条证据必带来源，且在那四档内（枚举，不许自由字符串）。"""
    bad = []
    for i, r in enumerate(refs or [], 1):
        tag = f"{where}#{i}" if where else f"证据#{i}"
        if not isinstance(r, dict):
            bad.append(f"{tag}: 不是结构化证据：{r!r}")
            continue
        o = r.get("origin")
        if o is None:
            bad.append(f"{tag}: 没有 origin —— 一条证据不许不声明它是怎么来的")
        elif o not in ORIGINS:
            bad.append(f"{tag}: origin={o!r} 不在四档内（{list(ORIGINS)}）")
        elif o in RECEIPT_ORIGINS:
            bad.append(f"{tag}: origin={o!r} 是**回执来源**，不是证据来源 —— 两个 origin 不许混")
    return bad


def may_finalize_pass(refs):
    """**一条判定能不能被这些证据单独推到 PASS。** 返回 `(bool, 为什么)`。

    ★ 这是 T19 判据 ② 的**唯一**实现处。有 `stated` 在场时，
      OCR/转写/画面转述可以当**补充**证据（结论不靠它们单独支撑）。

    ★ 空证据集返回 False：**没有证据不等于无需证据。**
      这一条挡的是「零命中自动算通过」——本仓真有这个形状（`catch_all`）。
    """
    if not refs:
        return False, "没有任何证据 —— 没有证据不等于无需证据"
    stated = [r for r in refs
              if isinstance(r, dict) and r.get("origin") in PASS_ORIGINS]
    if stated:
        return True, (f"有 {len(stated)} 条 origin=stated 的证据在场（其余 "
                      f"{len(refs) - len(stated)} 条只能算补充）")
    kinds = sorted({(r or {}).get("origin") for r in refs if isinstance(r, dict)})
    return False, (f"证据里没有一条 origin=stated（只有 {kinds}）——"
                   f"OCR/转写/画面转述可以补充，但不能单独把结论推到 PASS")


def receipt_origin_problems(rc):
    """回执里两个 `origin` 不许混。这是本模块抬头那张表的执行点。"""
    bad = []
    if not isinstance(rc, dict):
        return [f"回执不是 dict：{type(rc).__name__}"]
    o = rc.get("origin")
    if o not in RECEIPT_ORIGINS:
        bad.append(f"回执 origin={o!r} 不在回执来源取值域 {list(RECEIPT_ORIGINS)} —— "
                   f"若写的是 {list(ORIGINS)} 里的值，那是**证据来源**，写错字段了")
    eo = rc.get("evidence_origin")
    if eo is not None and eo not in ORIGINS:
        bad.append(f"evidence_origin={eo!r} 不在证据来源取值域 {list(ORIGINS)} —— "
                   f"若写的是 {list(RECEIPT_ORIGINS)} 里的值，那是**回执来源**，写错字段了")
    return bad


def main():
    print("证据来源四档：")
    for o in ORIGINS:
        ok = "✅" if o in PASS_ORIGINS else "❌"
        print(f"  {ok} {o:<12}{ORIGIN_MEANING[o]}")
    print(f"回执来源（另一件事）：{list(RECEIPT_ORIGINS)}")
    print(f"两者交集：{sorted(set(ORIGINS) & set(RECEIPT_ORIGINS))}　← 必须为空")
    return 0 if not (set(ORIGINS) & set(RECEIPT_ORIGINS)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
