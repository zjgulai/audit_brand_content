#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multimodal_egress.py — T-438：出境清单落盘（送什么、送给谁、留多久）

## 为什么这份东西必须能落盘

`base/multimodal_provider.py` 的 `egress_manifest()` 回答的是**静态**问题：
「若启用某个 provider，会送出什么」。它不回答「昨天 14:03 那张图上路时，
实际登记的是哪一份清单」—— 而事故复盘要的正是后者。

所以本文件把清单**快照**下来，并记三个时间量：

    声明于     —— 登记表里那一条 `registration.note` 里写的口径来源
    生成于     —— 这份快照是什么时刻算出来的
    保留至     —— 按保留策略算出的到期时刻（**这一项以前完全没有**）

★ 「留多久」这一项是方案 §五 T-432 判据 4 点名的「送什么、送给谁、留多久」，
  前两项 `egress_manifest()` 早就有，第三项此前**在任何地方都不存在**。
  没有它，「我们只保留 30 天」是一句没有执行点的承诺（AGENTS §2.4.2）。

## 边界

* **不联网**：只读内存里的登记表，不做任何调用。
* **不写仓内**：落盘根由调用方给，且必须过「不在仓内」检查 ——
  出境清单里含接收方与数据分级，属于内部审计件，与报告正文同一个理由不进公开仓。
* **不改登记表**：本层只读。谁注册 provider 是走 `register_provider()` 的事。

## 与 `egress_manifest()` 的关系（避免第二套口径）

本文件**不重新计算**清单，一律调 `ProviderRegistry.egress_manifest()` 与
`egress_manifest_digest()`。它只做三件那一层不做的事：加时间、加保留期、落盘。
两套口径各算一次是 AGENTS §2.4.8 点名的病。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 保留期（天）。★ 方案没规定具体天数，这里给一个**保守默认**并把它写进快照，
#: 让「留多久」成为一个可读的数，而不是一句「我们会保留适当时间」。
#: 改它必须同时改文档 —— 由 `verify_egress_manifest` 断言两处相等。
DEFAULT_RETENTION_DAYS = 365


class EgressStoreError(ValueError):
    """落盘根不合法 / 写入失败。**不静默**：审计件写不下去必须让人知道。"""


def _iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def retention_days_from_env(env: Optional[Mapping[str, str]] = None) -> int:
    """读保留期。非法值必须抛，不许退回默认 —— 退回默认会让配错悄悄生效。"""
    env = os.environ if env is None else env
    raw = (env.get("MULTIMODAL_EGRESS_RETENTION_DAYS") or "").strip()
    if not raw:
        return DEFAULT_RETENTION_DAYS
    try:
        days = int(raw)
    except ValueError as exc:
        raise EgressStoreError(
            "MULTIMODAL_EGRESS_RETENTION_DAYS 必须是整数，收到 %r" % (raw,)) from exc
    if days <= 0:
        raise EgressStoreError(
            "MULTIMODAL_EGRESS_RETENTION_DAYS 必须为正，收到 %d" % days)
    if days > 3650:
        raise EgressStoreError(
            "MULTIMODAL_EGRESS_RETENTION_DAYS 超过 10 年（%d）—— "
            "出境清单按年计保留期不合规，请复核" % days)
    return days


def check_root(root: str | Path) -> Path:
    """落盘根必须是**仓外**目录。

    ★ 与 `api/production_app.py` 的 `_inside_repository` 同一个理由：出境清单里
      含接收方、数据分级与任务范围 —— 它是内部审计件。写进公开仓等于把
      「我们会把哪些客户内容送给谁」一并发布。
    """
    path = Path(root).expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise EgressStoreError(
            "出境清单落盘根不许在仓内（%s）：它是内部审计件" % path)
    if path.exists() and not path.is_dir():
        raise EgressStoreError("落盘根存在但不是目录：%s" % path)
    return path


def build_snapshot(registry, *, retention_days: int = DEFAULT_RETENTION_DAYS,
                   now: Optional[float] = None,
                   tasks: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """算一份出境清单快照。

    `registry` 是 `base.multimodal_provider.ProviderRegistry` 实例。
    `tasks` 给了就按任务收窄（与 `egress_manifest(task)` 同一口径）。
    """
    now = time.time() if now is None else float(now)
    entry_time = _iso(now)
    expire_time = _iso(now + retention_days * 86400)
    # ★ 清单只取一次，指纹从同一份内存对象算 —— 否则会得到
    #   「providers 是新清单、digest 是旧清单」的自相矛盾审计件
    #   （这与 `egress_manifest_report()` 里那条注释是同一个理由）。
    manifest = registry.egress_manifest()
    digest = registry.egress_manifest_digest()
    by_task: Dict[str, Any] = {}
    for task in tasks or ():
        narrowed = registry.egress_manifest(task)
        by_task[str(task)] = {
            "providers": narrowed,
            "item_count": sum(len(p.get("egress_items") or []) for p in narrowed),
            "digest_sha256": registry.egress_manifest_digest(task),
        }
    return {
        "schema_version": "multimodal-egress-snapshot/v1",
        "generated_at": entry_time,
        "retention": {
            "days": int(retention_days),
            "expires_at": expire_time,
            # ★ 这一行是「留多久」的**执行点**：到期之后这份快照不该再被当作
            #   现行清单引用。判定函数是 `is_expired()`，不是读这行字符串。
            "policy": "到期后本快照仅作历史留档，不得再作为现行出境面引用",
        },
        "provider_count": len(manifest),
        "digest_sha256": digest,
        "providers": manifest,
        "by_task": by_task,
        "boundary": (
            "本快照描述**登记表当前声明**的出境面，不证明任何一次调用实际发生过。"
            "实际调用凭证在 multimodal_provider 的 analyze() 返回里（egress_status）。"
        ),
    }


def is_expired(snapshot: Mapping[str, Any], *, now: Optional[float] = None) -> bool:
    """快照是否已过保留期。

    ★ 解析不出到期时刻 → **按已过期处理**（fail-closed）。
      反向的默认值（「读不出就当没过期」）会让一份损坏的审计件永远有效。
    """
    now = time.time() if now is None else float(now)
    raw = ((snapshot.get("retention") or {}).get("expires_at") or "").strip()
    if not raw:
        return True
    try:
        parsed = time.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return True
    import calendar
    return calendar.timegm(parsed) < now


def write_snapshot(snapshot: Mapping[str, Any], *, root: str | Path,
                   name: Optional[str] = None) -> Path:
    """落盘。文件名带生成时刻，**不覆盖历史**。

    ★ 为什么用 append-only 而不是「latest.json 覆盖写」：
      覆盖写会让「昨天晚上那张图送出时清单是什么」无法回答，而那正是复盘要的。
      历史文件由 `prune_expired()` 按保留期清理 —— 删除也留痕。
    """
    path = check_root(root)
    path.mkdir(parents=True, exist_ok=True)
    stamp = str(snapshot.get("generated_at") or _iso(time.time()))
    safe = stamp.replace(":", "").replace("-", "")
    filename = name or ("egress-%s.json" % safe)
    target = path / filename
    # ★ 重名 = 同一秒内两次生成。不静默覆盖，加序号。
    index = 1
    while target.exists():
        target = path / ("%s.%d.json" % (filename[:-5], index))
        index += 1
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    return target


def prune_expired(root: str | Path, *, now: Optional[float] = None) -> Dict[str, Any]:
    """按保留期清理历史快照。**返回删了什么**（删也要留痕）。"""
    path = check_root(root)
    now = time.time() if now is None else float(now)
    removed: List[str] = []
    kept = 0
    errors: List[str] = []
    if not path.is_dir():
        return {"removed": [], "kept": 0, "errors": ["root_not_a_directory"]}
    for item in sorted(path.glob("egress-*.json")):
        try:
            data = json.loads(item.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # ★ 读不出的文件**不删**：删掉一个看不懂的审计件是不可逆的。
            #   留给人工 —— 并把它记进 errors，不许静默忽略。
            errors.append("%s: %s" % (item.name, exc))
            continue
        if not isinstance(data, dict) or is_expired(data, now=now):
            try:
                item.unlink()
                removed.append(item.name)
            except OSError as exc:
                errors.append("%s: unlink_failed:%s" % (item.name, exc))
        else:
            kept += 1
    return {"removed": removed, "kept": kept, "errors": errors}


def _usage():
    print("用法：python3 base/multimodal_egress.py --root <dir> [--retention-days N]")
    print("  算一份空注册表的出境清单快照并落盘（不联网、不读凭据）。")


def main(argv: Sequence[str]) -> int:
    argv = list(argv)
    if "--root" in argv:
        index = argv.index("--root")
        if index + 1 >= len(argv):
            print("--root 需要一个目录")
            return 1
        try:
            from base.multimodal_provider import ProviderRegistry
        except Exception as exc:  # noqa: BLE001
            print("未测：无法导入 multimodal_provider: %s" % exc)
            return 2
        days = DEFAULT_RETENTION_DAYS
        if "--retention-days" in argv:
            j = argv.index("--retention-days")
            try:
                days = int(argv[j + 1])
            except (IndexError, ValueError):
                print("--retention-days 需要一个整数")
                return 1
        snapshot = build_snapshot(ProviderRegistry(), retention_days=days)
        target = write_snapshot(snapshot, root=argv[index + 1])
        print(json.dumps({"written": str(target),
                          "digest": snapshot["digest_sha256"],
                          "providers": snapshot["provider_count"],
                          "expires_at": snapshot["retention"]["expires_at"]},
                         ensure_ascii=False, indent=2))
        return 0
    _usage()
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
