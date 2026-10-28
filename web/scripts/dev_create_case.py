#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev_create_case.py —— 给浏览器写动作测试建一条**真实**案件

## 它为什么存在

`web/scripts/check_review_actions.mjs` 要验「认领 → 存草稿 → 提交复核意见」
这条写链路。但写动作只能对 **authority 里真有的案件**做，而
`seed_fixture` 造的 10 条夹具案件**全部只存在于冻结投影**（实测：
队列 10 条，authority 里有 `ir` 的 0 条）。

于是对冻结案件做写动作时，reducer 会为本库没有的案件造一个 `ir=None` 的空壳，
之后每个裁决动作都报 `finding_not_found` —— 而详情里明明有 finding。
现在这条已经在 reducer 的 claim 处被拒（`case_not_in_authority`），
所以测试必须**真建一条**。

## 为什么正文是那句广告词

写动作测试需要案件里**有 finding**：它的核心断言之一是
「有 confirmed finding 时，界面上不该出现裁决按钮」。
空案件会让那条断言恒真（0 个按钮，永远通过）。

★ 这条正文命中的是**规则**，产出 `confirmed`。
  `candidate` 只由 `base/semantic_judge.py` 产出，而
  `base/judge_entry.py:286` 把它写死成 `untested`（实测）——
  所以经 HTTP 新建的案件不会有 candidate。这件事已如实登记，
  测试也据此改了断言，不假装验过。

## 用法

    python3 web/scripts/dev_create_case.py --api-port 51097 --cookie <session>

成功时 stdout 只输出 `case_id`（供 bash `$( )` 取用），
诊断信息一律走 stderr —— 否则会被当成 case_id 拼进 URL。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

#: 故意命中一条规则（品牌极限词），确保案件里有 finding。
#: ★ 换掉它会让「有没有裁决按钮」那条断言退化成恒真。
PROBE_TEXT = (
    "本品采用专利级双频吸乳技术，是母婴行业唯一同时获得三项资质的产品。"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-port", required=True)
    ap.add_argument("--cookie", required=True, help="session cookie 值")
    args = ap.parse_args()

    origin = "http://127.0.0.1:%s" % args.api_port
    body = json.dumps({
        "submission_id": "devup-write-case-1",
        "content_type": "文本",
        "content_stage": "final_content",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
        "product_line": "pump",
        "text": PROBE_TEXT,
    }).encode("utf-8")

    req = urllib.request.Request(
        origin + "/api/v1/submissions",
        data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Cookie": "session=" + args.cookie,
            "Idempotency-Key": "devup-write-case-key-1",
            "Origin": origin,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        sys.stderr.write("建案失败 HTTP %s：%s\n" % (exc.code, detail))
        return 1
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("建案失败：%s: %s\n" % (type(exc).__name__, exc))
        return 1

    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        # ★ 「没拿到 case_id」与「建案失败」必须说得不一样 ——
        #   前者说明响应形状变了，后者说明请求没成。
        sys.stderr.write("响应里没有 case_id：%s\n" % (json.dumps(payload, ensure_ascii=False)[:300],))
        return 1

    # ★ stdout 只放 case_id：调用方用 `$( )` 取它。
    print(case_id.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
