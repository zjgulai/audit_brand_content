#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/skill_registry.py —— skill 的**唯一**加载点（T-453）

## 它为什么存在

回执里有三个字段：`skill_id` / `skill_version` / `skill_hash`。
2026-10-27 实测：**生产链路一个都没传** ——

    judgment = self.judge_fn(unit, authority_query=..., kb_snapshot=...)   # 就这两个

于是 `base/judge_entry.py:181-182` 的默认值生效，回执永远写着：

    skill_id    = "content-review"
    skill_version = "1"
    skill_hash  = "local"        ← 这是硬编码字面量

**"local" 比"没实现"更该修**：没有加载器只是缺功能，而它是在**声称**一个自己
并不知道的版本 —— 回执读起来像"查过了"，实际什么都没查。这正是
AGENTS.md §2.4.1 那个病（接口调通了、看着正常、但口径是假的）。

## 口径

* **指纹 = 文件字节的 sha256**。不是 mtime、不是大小、不是 git blob 的 hash。
  理由：回执要能回答"这次跑的是哪一版规程"，而**内容**才是那一版的身份
  （§2.1.1 说过：用 (mtime, size) 当判据会被两个数相等骗过去）。
* **注册表里登记了但文件不在 → 红**；**文件在但没登记 → 红**。
  两个方向都要：只查一个方向，另一个方向永远绿。
* **触发词重复 → 红**。否则"该用哪个 skill"无解，而那种错不会自己暴露。
* **加载失败不抛** —— 返回 None + 原因，由调用方决定落 untested 还是拒绝。
  与 `base/media_ingest.ocr_file()` 同一口径：失败**不许**伪装成成功。

## 不做什么

* 不解释 SKILL.md 的内容（那是给人看的规程；本模块只算指纹、按 id 取文本）。
* 不决定"该用哪个 skill"（触发词重叠只会被**报出来**，不做自动选择 ——
  自动选择需要先有"选错了会怎样"的判据，那是另一张票）。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: 注册表路径（相对仓库根）
REGISTRY_PATH = "agent-skills/registry.json"

#: 指纹算法。★ 换算法必须同时改这里与 `$fingerprint` 说明，否则验证器会红。
FINGERPRINT_ALGO = "sha256(文件字节)"


class SkillRegistryError(RuntimeError):
    """注册表坏了 / 读不出来。与"某个 skill 加载失败"分开：那是两件事。"""


def load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    """读注册表。**失败抛** —— 注册表本身坏掉时不该安静返回空表。

    ★ 返回空表会让"零个 skill"与"注册表读不出"长得一样，
      而后者是配置问题、前者是设计问题，处理方式完全不同。
    """
    p = Path(path) if path is not None else (REPO_ROOT / REGISTRY_PATH)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillRegistryError("注册表读不出：%s（%s）" % (p, exc)) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SkillRegistryError("注册表不是合法 JSON：%s" % (exc,)) from exc
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise SkillRegistryError("注册表缺 skills 数组")
    return data


def fingerprint(path: Path) -> str:
    """文件的 sha256（字节级）。回执里的 `skill_hash` 就是这个值。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(skill_id: str, *, registry: Optional[Dict[str, Any]] = None,
            root: Optional[Path] = None) -> Tuple[Optional[Dict[str, Any]], str]:
    """按 id 取 skill 的**运行时描述**。返回 (descriptor | None, 失败原因)。

    descriptor 的键正是回执要的三样：

        {"skill_id", "skill_version", "skill_hash", "path", "text"}

    ★ 取不到时返回 `(None, 原因)` 而**不是**抛，也**不是**给默认值 ——
      给默认值就等于继续撒谎（那正是 `skill_hash="local"` 的老毛病）。
    """
    base = Path(root) if root is not None else REPO_ROOT
    if not isinstance(skill_id, str) or not skill_id.strip():
        return None, "skill_id 为空"
    try:
        reg = registry if registry is not None else load_registry(base / REGISTRY_PATH)
    except SkillRegistryError as exc:
        return None, str(exc)

    hits = [s for s in reg.get("skills") or []
            if isinstance(s, dict) and s.get("id") == skill_id]
    if not hits:
        return None, "注册表里没有 skill_id=%r" % (skill_id,)
    if len(hits) > 1:
        # 同一个 id 登记两次 → 不知道该用哪一份，不许随便取第一个
        return None, "skill_id=%r 登记了 %d 次（id 必须唯一）" % (skill_id, len(hits))

    entry = hits[0]
    rel = entry.get("path")
    if not isinstance(rel, str) or not rel.strip():
        return None, "skill_id=%r 没有 path" % (skill_id,)
    target = (base / rel).resolve()
    if not target.is_file():
        return None, "skill_id=%r 的规程文件不在盘上：%s" % (skill_id, rel)
    try:
        text = target.read_text(encoding="utf-8")
        digest = fingerprint(target)
    except OSError as exc:
        return None, "skill_id=%r 读不出：%s" % (skill_id, exc)

    return {
        "skill_id": entry.get("id"),
        "skill_version": str(entry.get("version") or ""),
        "skill_hash": digest,
        "path": rel,
        "text": text,
    }, ""


def receipt_fields(skill_id: str, *, registry: Optional[Dict[str, Any]] = None,
                   root: Optional[Path] = None) -> Tuple[Dict[str, str], str]:
    """给回执用的三个字段。取不到时**返回空 dict + 原因**，不编默认值。

    ★ 调用方拿到空 dict 时应当把 `skill_hash` 写成 `untested` 之类**不可冒充**的值，
      而不是继续写 `"local"` —— 那是本模块存在的原因。
    """
    desc, why = resolve(skill_id, registry=registry, root=root)
    if desc is None:
        return {}, why
    return {
        "skill_id": desc["skill_id"],
        "skill_version": desc["skill_version"],
        "skill_hash": desc["skill_hash"],
    }, ""


def validate(registry: Dict[str, Any], *, root: Optional[Path] = None) -> List[str]:
    """校验注册表。返回问题清单（空 = 全过）。供验证器复用。

    ★ 判据全部是**双向**的：登记↔文件、id 唯一、触发词不重叠。
      只查一个方向会让另一个方向永远绿。
    """
    base = Path(root) if root is not None else REPO_ROOT
    problems: List[str] = []
    skills = registry.get("skills")
    if not isinstance(skills, list):
        return ["registry.skills 不是数组"]

    seen_ids: Dict[str, int] = {}
    trigger_owner: Dict[str, str] = {}
    for index, entry in enumerate(skills):
        tag = "skills[%d]" % index
        if not isinstance(entry, dict):
            problems.append("%s 不是对象" % tag)
            continue
        sid = entry.get("id")
        if not isinstance(sid, str) or not sid.strip():
            problems.append("%s 没有 id" % tag)
            continue
        seen_ids[sid] = seen_ids.get(sid, 0) + 1
        # version 必须是非空字符串（回执里要能逐字说出是哪一版）
        if not isinstance(entry.get("version"), str) or not entry["version"].strip():
            problems.append("%s（%s）version 缺失或不是字符串" % (tag, sid))
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel.strip():
            problems.append("%s（%s）path 缺失" % (tag, sid))
            continue
        target = (base / rel).resolve()
        if not target.is_file():
            problems.append("%s（%s）文件不在盘上：%s" % (tag, sid, rel))
        for word in entry.get("trigger_words") or []:
            if not isinstance(word, str) or not word.strip():
                problems.append("%s（%s）触发词为空或不是字符串" % (tag, sid))
                continue
            key = word.strip().lower()
            if key in trigger_owner:
                # ★ 两个 skill 抢同一个触发词 → 该用哪个无解
                problems.append("触发词 %r 同时属于 %r 与 %r（会无法选择）"
                                % (word, trigger_owner[key], sid))
            else:
                trigger_owner[key] = sid

    for sid, count in seen_ids.items():
        if count > 1:
            problems.append("id %r 登记了 %d 次" % (sid, count))

    # ★ 反向：盘上有 SKILL.md 但注册表没登记 —— 那个 skill 永远不会被加载到
    skills_dir = base / "agent-skills"
    if skills_dir.is_dir():
        on_disk = {str(p.relative_to(base)) for p in skills_dir.rglob("SKILL.md")}
        registered = {str(e.get("path")) for e in skills if isinstance(e, dict)}
        for miss in sorted(on_disk - registered):
            problems.append("盘上有规程但没登记：%s（它永远不会被加载）" % miss)
    return problems
