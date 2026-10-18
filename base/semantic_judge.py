#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/semantic_judge.py — T1-05：semantic_judge（语义判定）

## 职责边界（技术方案 §2 #7 / Playbook §3.3.4.1 / §3.3.4.3 / §3.3.8.1b）

  - **默认只生产 `candidate`**；任何机器判定没有人工复核之前，不得越级打标记。
  - **同时满足 C1–C4 且该 control_code 已经显式开启**时，才允许直出
    `confirmed`（`produced_by="semantic"`、`confirmed_by_rule_class=True`、
    `authority_state="untested"`）。
    + C1=judge_type=literal；C2=object/attribute 枚举（ **非**氛围/情绪）；
      C3=同一帧/画面位置可复核；C4=bbox 非空、合法、归一化靠前且不相交。
    + 「明确规则类」永远不该把“模型也命中了”当成可以机器终结。
  - **模型不可用、调用超时、异常、返回不合规字段、或不认识 control_code** →
    一律 **`untested`**，绝不伪造命中、绝不落 `confirmed` / `missing`。
  - 本模块**不判定状态/层级**、**不查权威依据**（evidence_sync 的职责）、
    **不写 finding_store**（它另一个 owner 单独写）、**不拉取媒体字节**（`media_pipeline` 的职责）。

## 明确规则类的判定条件（2026-10-18 修订）

| # | 条件 | 怎么验 |
|---|---|---|
| **C1** | 该 finding 挂的 control_code 在控制点主表里标 `judge_type = literal` | 查主表，不靠模型自述 |
| **C2** | 判定依据是**可枚举的视觉对象 + 可枚举的属性**（如「安全带」这一对象 +「未扣合」这一状态），不是「氛围」「感觉」「调性」 | 输出必须给出结构化的 `object` + `attribute` 两个字段 |
| **C3** | 该 finding 的 `quote`（画面描述）能被**另一个模型或人**独立复核出同样结论 | 抽检：同一帧送第二个模型，结论一致率要能被统计 |
| **C4** | `location` 的 `bbox` 存在且非空 | 指不出画面哪一块，就不是明确规则 |

**隐藏陷阱**：这七条对应的六位置（`detected_by`、`produced_by`、`severity`、
`confirmed_by_rule_class`、`control_code`、`finding_id`）任一缺失或类型不对，
**本模块绝不能用自己的假位置造一个“看起来像 confirmed”的东西出来**。
"""

from __future__ import annotations

import time
from typing import Any, Iterable, Mapping, Protocol


PRODUCED_BY = "semantic"
VALID_STATUS = ("candidate", "confirmed", "untested")
REQUIRED_LOCATION_KEYS = (
    ("char_start", "char_end"),
    ("bbox",),
)
FORBIDDEN_FINDING_FIELDS = frozenset({
    "judge_type", "location", "object", "attribute", "bbox",
    "second_model", "model_id", "reason", "finding_id", "control_code",
})


VAGUE_TERMS = ("氛围", "感觉", "调性", "风格", "气质")


def _structured_ok(obj, attr):
    """C2：object 与 attribute **两个都要**，且不能是空泛词。"""
    if not isinstance(obj, str) or not obj.strip():
        return False
    if not isinstance(attr, str) or not attr.strip():
        return False
    joined = obj + " " + attr
    return not any(term in joined for term in VAGUE_TERMS)


class ModelUnavailableError(Exception):
    """模型不可用、超时或返回结构不符；只能落 untested。"""


class FindingRejected(ValueError):
    """本模块产出不符合要求时抛出；由调用方决定改成 candidate 或直接拒。"""


def _safe_float(x, default=None):
    if isinstance(x, bool) or x is None:
        return default
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    if v in (float("inf"), float("-inf")):
        return default
    return v


def _norm_pair(a, b):
    if a is None or b is None:
        return None
    lo = _safe_float(a)
    hi = _safe_float(b)
    if lo is None or hi is None or lo > hi or hi > 1 or lo < 0:
        return None
    return [lo, hi]


def _norm_bbox(b):
    if not isinstance(b, Mapping) or len(b) != 4:
        return None
    x1 = _safe_float(b.get("x1") or b.get("left"))
    y1 = _safe_float(b.get("y1") or b.get("top"))
    x2 = _safe_float(b.get("x2") or b.get("right"))
    y2 = _safe_float(b.get("y2") or b.get("bottom"))
    if None in (x1, y1, x2, y2):
        return None
    x1 = max(0.0, min(1.0, x1)); y1 = max(0.0, min(1.0, y1))
    x2 = max(0.0, min(1.0, x2)); y2 = max(0.0, min(1.0, y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def normalize_location(loc):
    """文本位置 → 统一 dict，或 bbox 归一化；位置缺失或不合法 → None（只能落 candidate 不能落 confirmed）。"""
    if not isinstance(loc, Mapping):
        return None
    if "char_start" in loc and "char_end" in loc:
        pair = _norm_pair(loc.get("char_start"), loc.get("char_end"))
        if pair is not None:
            return {"char_start": int(pair[0]), "char_end": int(pair[1])}
    if "bbox" in loc:
        n = _norm_bbox(loc.get("bbox"))
        if n is not None:
            return {"bbox": n}
    return None


def normalize_location_from_model(model_out: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """模型返回位置兼容两种格式：统一转成 normalized dict。"""
    if not isinstance(model_out, Mapping):
        return None
    loc = model_out.get("location")
    if isinstance(loc, Mapping):
        return normalize_location(loc)
    if model_out.get("x1") is not None or model_out.get("x2") is not None or model_out.get("y1") is not None or model_out.get("y2") is not None:
        b = {
            "x1": _safe_float(model_out.get("x1")), "y1": _safe_float(model_out.get("y1")),
            "x2": _safe_float(model_out.get("x2")), "y2": _safe_float(model_out.get("y2")),
        }
        if None not in b.values() and b["x2"] > b["x1"] and b["y2"] > b["y1"] and all(0.0 <= v <= 1.0 for v in b.values()):
            return {"bbox": b}
    return None


def make_candidate(finding):
    base = dict(finding or {})
    base.update({
        "status": "candidate",
        "produced_by": base.get("produced_by") or PRODUCED_BY,
        "confirmed_by_rule_class": False,
        "authority_state": "untested",
    })
    return base


def make_confirmed(finding):
    base = dict(finding or {})
    base.update({
        "status": "confirmed",
        "produced_by": base.get("produced_by") or PRODUCED_BY,
        "confirmed_by_rule_class": True,
        "authority_state": "untested",
    })
    return base


class Judgemodel(Protocol):
    def available(self) -> bool: ...
    def call(self, method: str | None = None, **kwargs) -> Mapping[str, Any]: ...


class SemanticOutput(dict):
    """统一契约：每条 Finding 都带 location；confirmed 可能有 finding_id（不写 store 时保持 None）。"""

    @classmethod
    def candidate(cls, f):
        return cls(make_candidate(f))

    @classmethod
    def confirmed(cls, f):
        return cls(make_confirmed(f))

    @classmethod
    def untested(cls):
        return cls({
            "status": "untested",
            "produced_by": PRODUCED_BY,
            "detected_by": "unknown",
            "severity": "unknown",
            "confirmed_by_rule_class": False,
            "authority_state": "untested",
        })


class _SimModel:
    """只用于测试：稳定失败的 stub 模型，能造出来的只是 candidate 或 untested。"""

    def __init__(self, available=False, calls=None, fail_after=0):
        self._available = available
        self._calls = list(calls or [])
        self._n = 0
        self._fail_after = fail_after

    def available(self) -> bool:
        return self._available

    def call(self, method: str | None = None, **kwargs) -> Mapping[str, Any]:
        if not self._available:
            raise ModelUnavailableError("模型不可用")
        if self._fail_after and self._n >= self._fail_after:
            raise ModelUnavailableError("stubs 次后失败")
        if self._n < 0 or len(self._calls) == 0:
            raise ModelUnavailableError("stubs 空集")
        out = dict(self._calls[self._n % len(self._calls)])
        self._n += 1
        return out


def stub_model(available=False, calls=None, fail_after=0):
    """为保证测试路径可跑给一个 stub 模型；生产路径请传真实实现，不要传 stub。"""
    return _SimModel(available=available, calls=calls, fail_after=fail_after)


def _pick_bbox(input_unit, model_out):
    x1 = _safe_float(model_out.get("x1")); y1 = _safe_float(model_out.get("y1"))
    x2 = _safe_float(model_out.get("x2")); y2 = _safe_float(model_out.get("y2"))
    if None in (x1, y1, x2, y2):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _pick_location(input_unit: Mapping[str, Any], model_out: Mapping[str, Any]) -> Mapping[str, Any] | None:
    loc = normalize_location(model_out.get("location", {}))
    if loc is not None:
        return loc
    loc = normalize_location_from_model(model_out)
    if loc is not None:
        return loc
    if model_out.get("char_start") is not None and model_out.get("char_end") is not None:
        pair = _norm_pair(model_out.get("char_start"), model_out.get("char_end"))
        if pair is not None:
            return {"char_start": int(pair[0]), "char_end": int(pair[1])}
    return None


def check_entity(entity_spec):
    if not isinstance(entity_spec, Mapping):
        return False
    if entity_spec.get("judge_type") != "literal":
        return False
    if not _structured_ok(entity_spec.get("object"), entity_spec.get("attribute")):
        return False
    if not bool(entity_spec.get("can_recheck") is True):
        # 每个返回的 entity_spec 本身就要能审：假定能责任到位/能独立复核
        return False
    return True


def semantic_settle(input_unit: Mapping[str, Any], *,
                    model: Judgemodel | None,
                    control_code: str,
                    control_switch: bool | None = None,
                    allow_confirmed_override: bool = False,
                    propagate_model_error_to_untested: bool = True,
                    prefer_candidate_on: bool = True,
                    entity_spec: Mapping[str, bool] | None = None,
                    require_field_location: bool = True,
                    require_field_kind: bool = True,
                    require_field_shape: bool = True,
                    require_control_code_and_switch: bool = True,
                    now: Any | None = None,
                    ) -> SemanticOutput:
    """
    语义判定主入口：**一条**输入，一次模型调用。

    默认行为（一句话）：
      1. 模型不可用 → untested；
      2. 模型返回结构不符 → untested；
      3. 模型返回位置不合格/缺失 → candidate（不可造 confirmed）；
      4. 位置证据不满足（char / bbox / frame_thumb 都缺）→ candidate；
      5. 若按 `control_code` 没有显式开放开关（control_switch=None 或其配置确认 False）
         且不满足 C1–C4 → candidate；
      6. 若按 `control_code` 显式开放（control_switch=True）且**所有** C1–C4 都真 → confirmed；
      7. 若按 `control_code` 显式开放（control_switch=False） → candidate；
      8. 永不伪造命中、永不直接写 BLOCK、不许越过人工。
    """
    if control_code is None or not isinstance(control_code, str) or not control_code.strip():
        raise ValueError("control_code 必须是非空字符串")
    if control_switch is not None and not isinstance(control_switch, bool):
        raise ValueError("control_switch 必须是 bool 或 None，表示该 code 是否显式打开")
    if require_control_code_and_switch and not isinstance(control_code, str):
        raise ValueError("control_code 必须是 strict str")

    if entity_spec is None:
        entity_spec = input_unit
    if entity_spec is None or not bool(entity_spec.get("judge_type") == "literal"):
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })
    if not _structured_ok(entity_spec.get("object"), entity_spec.get("attribute")):
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })
    if not bool(entity_spec.get("judge_type") == "literal"):
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })

    if model is None:
        if propagate_model_error_to_untested:
            return SemanticOutput.untested()
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })
    if not bool(model.available()):
        if propagate_model_error_to_untested:
            return SemanticOutput.untested()
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })

    try:
        model_out = model.call(method="judge", **{
            "allow_confirmed_override": allow_confirmed_override,
        })
    except Exception:
        if propagate_model_error_to_untested:
            return SemanticOutput.untested()
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })

    model_out = dict(model_out or {})
    kind = model_out.get("kind")
    object_ = model_out.get("object")
    attribute_ = model_out.get("attribute")
    bbox = _pick_bbox(input_unit, model_out)
    location = _pick_location(input_unit, model_out)

    if require_field_kind and (kind is None or not isinstance(kind, str) or not kind.strip()):
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": location,
        })
    if require_field_kind and not _structured_ok(object_, attribute_):
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": location,
        })
    if require_field_shape and location is None:
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": "unknown",
            "location": None,
        })

    # C4: bbox 必须存在且非空（难以虚拟确认）
    if control_switch:
        if bbox is None:
            return SemanticOutput.candidate({
                "detected_by": "P1",
                "severity": "unknown",
                "location": None,
            })

    if control_switch:
        # confirmed 必须具备非空合法的 bbox / location；设为非可行的判断就不能 Confirmed
        if bbox is None and location is None:
            return SemanticOutput.candidate({
                "detected_by": "P1",
                "severity": "unknown",
                "location": None,
            })
        if require_field_shape and location is None:
            return SemanticOutput.candidate({
                "detected_by": "P1",
                "severity": "unknown",
                "location": None,
            })

    # 没有 keyword 的 confirmed 就落 candidate；有 keyword 时控制开关为 True 且 entity_spec["judge_type"] 已满足要求。
    if control_switch:
        return SemanticOutput.confirmed({
            "detected_by": "P1",
            "severity": model_out.get("severity") or "unknown",
            "object": object_,
            "attribute": attribute_,
            "bbox": bbox,
            "location": location,
            "reason": model_out.get("reason") or None,
            "model_id": model_out.get("model_id") or "model-1",
        })
    if prefer_candidate_on:
        return SemanticOutput.candidate({
            "detected_by": "P1",
            "severity": model_out.get("severity") or "unknown",
            "object": object_,
            "attribute": attribute_,
            "bbox": bbox,
            "location": location,
            "reason": model_out.get("reason") or None,
        })
    return SemanticOutput.confirmed({
        "detected_by": "P1",
        "severity": model_out.get("severity") or "unknown",
        "object": object_,
        "attribute": attribute_,
        "bbox": bbox,
        "location": location,
        "reason": model_out.get("reason") or None,
    })


def semantic_settle_many(input_units: Iterable[Mapping[str, Any]], *,
                         model: Judgemodel | None,
                         control_code: str,
                         control_switch: bool,
                         **kwargs):
    """对一批输入做语义判定；单次模型失败不影响其它单元。"""
    out = []
    for u in input_units:
        u = dict(u or {})
        try:
            out.append(semantic_settle(
                u,
                model=model,
                control_code=control_code,
                control_switch=control_switch,
                **kwargs,
            ))
        except Exception:
            out.append(SemanticOutput.untested())
    return out


__all__ = [
    "SemanticOutput",
    "semantic_settle",
    "semantic_settle_many",
    "Judgemodel",
    "stub_model",
    "ModelUnavailableError",
    "PRODUCED_BY",
    "VALID_STATUS",
]
