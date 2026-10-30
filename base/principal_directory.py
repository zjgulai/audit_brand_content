#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式主体目录：以 tenant_id + open_id 查本地受控角色/品线/capability。

## 两层名单（2026-10-30 加，委托方要求「放行所有人员飞书登录」）

| 层 | 文件 | 谁写 | 优先级 |
|---|---|---|---|
| **显式** | `principals.json`（只读挂载） | 人工，逐人登记 | **高** |
| **自动** | `principals-auto.json`（可写） | 首次扫码登录时本模块自己写 | 低 |

规则三条，缺一条这个功能就会变成一个洞：

1. **显式优先，且「显式 revoked」不许被自动复活。** 查表顺序是显式 → 自动 →
   自动登记。显式里有这个人（哪怕 `status=revoked`）就**不再看自动层** ——
   否则「撤掉某人」与「他来扫一次码」两件事会互相抵消，撤人等于没撤。
2. **自动层只能给角色矩阵推导出来的能力。** 配置里只接受 `roles` 与
   `product_lines`，`capabilities` 一律由 `rbac.role_capabilities()` 算出来；
   并且 `signer` / `it` / `machine` 三个角色**明确禁止**出现在自动配置里 ——
   它们分别对应签发/下线、平台管理、非人类主体，`dp3` 的自动扩散
   不该顺手把签发权也扩散出去。
3. **缺配置 = 关。** 没有 `auto_grant` 时行为与加这一层之前逐字相同
   （`verify_rbac` / `verify_production_app` 的既有断言不受影响）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

#: 自动登记**不许**给的角色。见模块文档第 2 条。
AUTO_FORBIDDEN_ROLES = frozenset({"signer", "it", "machine"})


class PrincipalDirectoryError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


class PrincipalDirectory:
    def __init__(self, path, *, require_authz_version=False,
                 auto_grant=None, auto_store_path=None, audit_path=None):
        self.path = Path(path).resolve()
        self.require_authz_version = bool(require_authz_version)
        self._lock = threading.RLock()
        self._digest = None
        self._last_error = None
        self._by_key = {}
        self._by_id = {}
        #: 自动登记配置（已归一化）。None = 关。
        self.auto_grant = self._normalize_auto_grant(auto_grant)
        self.auto_store_path = (
            Path(auto_store_path).resolve() if auto_store_path else None)
        self.audit_path = Path(audit_path).resolve() if audit_path else None
        if self.auto_grant is not None and self.auto_store_path is None:
            raise PrincipalDirectoryError(
                "principal_auto_store_missing",
                "开了自动登记就必须给 auto_store_path，否则「谁被放进来过」没有落点")
        if self.auto_grant is not None:
            self._assert_auto_store_writable()
        self._auto = {}
        self._auto_digest = None
        self._reload(force=True)

    def _assert_auto_store_writable(self):
        """★ 构造期就验可写 —— 不等到第一个陌生人扫码时才炸。

        为什么必须在构造期：`_persist_auto` 写不进去会 **抛**（那是刻意的，
        见它的注释）。而第一个触发它的时机是**真人扫码登录** —— 那一刻
        报 500，用户体验是「扫了十几次都进不去」，而真因是一个目录权限。
        构造期验的话，同样的故障表现为**服务起不来**，位置和原因都直给。

        判据是「父目录能建能写」，不是「文件不存在」：文件由第一次登记创建。
        """
        parent = self.auto_store_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            fd, probe = tempfile.mkstemp(dir=str(parent), prefix=".auto-probe-")
            os.close(fd)
            os.unlink(probe)
        except OSError as exc:
            raise PrincipalDirectoryError(
                "principal_auto_store_unwritable", type(exc).__name__) from exc

    @staticmethod
    def _normalize_auto_grant(cfg):
        """校验自动登记模板。非法即抛 —— 不做「忽略坏字段继续跑」。

        手写 JSON 里一个拼错的键（`role` vs `roles`）如果被静默忽略，
        表现是「所有人都登进来了，但没人能领案」，而那看起来像 RBAC 坏了。
        """
        if not cfg:
            return None
        if not isinstance(cfg, dict):
            raise PrincipalDirectoryError("principal_auto_grant_shape",
                                          "必须是对象")
        unknown = set(cfg) - {"roles", "product_lines", "capabilities"}
        if unknown:
            # capabilities 只用于「显式声明你想给的与推导结果一致」的写错提示，
            # 不在配置里被当真；见下面的校验。
            raise PrincipalDirectoryError(
                "principal_auto_grant_unknown_key", ",".join(sorted(unknown)))
        from base import rbac  # 延迟导入：本模块被 rbac 的消费者广泛 import

        roles = cfg.get("roles") or []
        if (not isinstance(roles, list) or not roles or
                not all(isinstance(x, str) and x.strip() for x in roles)):
            raise PrincipalDirectoryError("principal_auto_grant_roles",
                                          "roles 必须是非空字符串数组")
        roles = sorted({x.strip() for x in roles})
        bad = [r for r in roles if r not in rbac.ROLES]
        if bad:
            raise PrincipalDirectoryError("principal_auto_grant_role_unknown",
                                          ",".join(bad))
        forbidden = sorted(set(roles) & AUTO_FORBIDDEN_ROLES)
        if forbidden:
            raise PrincipalDirectoryError(
                "principal_auto_grant_role_forbidden", ",".join(forbidden))
        lines = cfg.get("product_lines") or []
        if (not isinstance(lines, list) or not lines or
                not all(isinstance(x, str) and x.strip() for x in lines)):
            raise PrincipalDirectoryError(
                "principal_auto_grant_product_lines",
                "product_lines 必须是非空字符串数组（空 = 通配，这里刻意不允许）")
        lines = sorted({x.strip() for x in lines})
        caps = sorted({c for r in roles for c in rbac.role_capabilities(r)})
        declared = cfg.get("capabilities")
        if declared is not None:
            if (not isinstance(declared, list) or
                    sorted({str(x).strip() for x in declared}) != caps):
                # 不静默接受：配的人以为自己在给某能力，实际不是 ——
                # 与 §2.4.1「读通了但口径读错」同一个形状。
                raise PrincipalDirectoryError(
                    "principal_auto_grant_capabilities_mismatch",
                    "capabilities 只能等于 roles 推导结果 %r" % (caps,))
        return {"roles": roles, "product_lines": lines, "capabilities": caps}

    def _reload_auto(self, *, force=False):
        if self.auto_grant is None:
            return
        try:
            raw_bytes = self.auto_store_path.read_bytes()
        except FileNotFoundError:
            digest = hashlib.sha256(b"").hexdigest()
            if not force and digest == self._auto_digest:
                return
            self._auto, self._auto_digest = {}, digest
            return
        except OSError as exc:
            raise PrincipalDirectoryError("principal_auto_store_unreadable",
                                          type(exc).__name__) from exc
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if not force and digest == self._auto_digest:
            return
        try:
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise PrincipalDirectoryError("principal_auto_store_unreadable",
                                          type(exc).__name__) from exc
        rows = raw.get("principals") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise PrincipalDirectoryError("principal_auto_store_shape",
                                          "principals 必须是数组")
        auto = {}
        for row in rows:
            item = self._validate(row)
            auto[(item["tenant_id"], item["open_id"])] = item
        self._auto = auto
        self._auto_digest = digest

    def _reload(self, *, force=False):
        try:
            raw_bytes = self.path.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            if not force and digest == self._digest:
                return
            raw = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise PrincipalDirectoryError("principal_directory_unreadable",
                                          type(exc).__name__) from exc
        rows = raw.get("principals") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise PrincipalDirectoryError("principal_directory_shape",
                                          "principals 必须是数组")
        by_key = {}
        by_id = {}
        for row in rows:
            item = self._validate(row)
            key = (item["tenant_id"], item["open_id"])
            if key in by_key or item["id"] in by_id:
                raise PrincipalDirectoryError("principal_duplicate", repr(key))
            by_key[key] = item
            by_id[item["id"]] = item
        # 先完整解析临时结构，再一次替换；坏更新不覆盖上一份可用目录。
        self._by_key = by_key
        self._by_id = by_id
        self._digest = digest
        self._last_error = None

    def _refresh(self):
        with self._lock:
            try:
                self._reload()
                self._reload_auto()
            except PrincipalDirectoryError as exc:
                self._last_error = exc.code
                raise

    # ── 自动登记 ───────────────────────────────────────────────────────────
    def _auto_row(self, tenant_id, open_id, display_name=None):
        """按模板造一条自动登记记录。`id` 从 open_id 推，稳定且可预期。

        ★ 不用姓名做 id：姓名会变、会重名，而 id 是 ACL 与审计里的那个键。

        ★★ `authz_version` 必须**这里就算出来**。
        2026-10-30 生产实测踩过：本地验的时候目录是
        `require_authz_version=False`（缺了会自动算一个哈希），于是
        `_auto_row` 不填也能跑；而 `ProductionRuntime.start()` 用的是
        `True`（`api/production_app.py`），那里缺这个字段直接
        `principal_field: authz_version` —— **第一个真人扫码就 500**。
        这正是「本地验的形状 ≠ 生产的形状」，所以现在不论 require 与否
        都算，并且断言里补了 `require_authz_version=True` 那一支。

        算法与 `_validate` 的兜底分支**同一个**：对记录本身取 sha256。
        于是「改了角色模板」→ 版本变 → 已登录的人被判「授权已变化」需重登，
        这是想要的行为（授权变了就该重新拿一次授权）。
        """
        key_hash = hashlib.sha256(
            ("%s\n%s" % (tenant_id, open_id)).encode("utf-8")).hexdigest()[:16]
        row = {
            "id": "auto-" + key_hash,
            "tenant_id": tenant_id,
            "open_id": open_id,
            "roles": sorted(set(self.auto_grant["roles"])),
            "product_lines": sorted(set(self.auto_grant["product_lines"])),
            "capabilities": sorted(set(self.auto_grant["capabilities"])),
            "product_line": sorted(set(self.auto_grant["product_lines"]))[0],
            "status": "active",
            "source": "auto",
        }
        if display_name:
            row["name"] = str(display_name)
        # ★ 与 `_validate` 的兜底分支逐字同一算法，且**不含 authz_version 自己**
        #   （否则它会是自己的输入，永远算不出一个稳定值）。
        row["authz_version"] = hashlib.sha256(json.dumps(
            row, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        return row

    def _persist_auto(self, row):
        """把新登记写进自动层。★ **写不进去就抛** —— 不放行。

        这一条改过一版，改的理由值得记：第一版是「写失败也让人进，只留痕」，
        读起来很宽容，实际是 §2.4.1 那个形状的复发 —— **一次登录成功了，
        而盘上什么都没记**。那个人能用到下次重启，重启之后又进不来，
        症状是「有时能进有时不能」，而日志里那行 `ok=false` 没人会去看。

        反过来说，写不进去＝这台部署坏了，那它就应该**当场说出来**：
        `principal_auto_store_unwritable` 是 500，运维一眼看得到；
        而「静默放行」要找很久。启动时的可写性检查在
        `PrincipalDirectory.__init__` 里，所以正常情况下根本走不到这里。
        """
        tmp = None
        try:
            # 重读一次再合并：两个请求同时首次登录时，谁都不该抹掉对方那条。
            self._reload_auto(force=True)
            merged = dict(self._auto)
            merged[(row["tenant_id"], row["open_id"])] = self._validate(row)
            payload = json.dumps(
                {"version": 1, "principals": sorted(
                    merged.values(), key=lambda r: (r["tenant_id"], r["open_id"]))},
                ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            self.auto_store_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=str(self.auto_store_path.parent), prefix=".principals-auto-")
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.auto_store_path)
            tmp = None
            self._auto = merged
            self._auto_digest = hashlib.sha256(payload).hexdigest()
            self._audit({"event": "principal_auto_registered",
                         "id": row["id"], "tenant": row["tenant_id"],
                         "open_id": row["open_id"], "name": row.get("name"),
                         "roles": row["roles"], "ok": True})
            return True
        except OSError as exc:
            self._audit({"event": "principal_auto_registered",
                         "id": row.get("id"), "tenant": row["tenant_id"],
                         "open_id": row["open_id"], "name": row.get("name"),
                         "ok": False, "error": type(exc).__name__,
                         "detail": str(exc)[:200]})
            raise PrincipalDirectoryError(
                "principal_auto_store_unwritable", type(exc).__name__) from exc
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _audit(self, record):
        if self.audit_path is None:
            return
        try:
            import time
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(dict(record, ts=time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                ensure_ascii=False, sort_keys=True)
            with open(self.audit_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass  # 审计写不进去不影响判定；它不是授权依据

    def _validate(self, row):
        if not isinstance(row, dict):
            raise PrincipalDirectoryError("principal_shape", "记录必须是对象")
        item = {}
        for name in ("id", "tenant_id", "open_id"):
            value = row.get(name)
            if not isinstance(value, str) or not value.strip():
                raise PrincipalDirectoryError("principal_field", name)
            item[name] = value.strip()
        for name in ("roles", "product_lines", "capabilities"):
            value = row.get(name, [])
            if not isinstance(value, list) or not all(
                    isinstance(x, str) and x.strip() for x in value):
                raise PrincipalDirectoryError("principal_field", name)
            item[name] = sorted(set(x.strip() for x in value))
        product_line = row.get("product_line")
        if product_line is not None and product_line not in item["product_lines"]:
            raise PrincipalDirectoryError("principal_field", "product_line")
        item["product_line"] = product_line
        item["status"] = row.get("status", "active")
        if item["status"] not in ("active", "revoked"):
            raise PrincipalDirectoryError("principal_field", "status")
        # 非判定字段：`name` 与 `source` 只为「这条是谁、从哪来的」留痕。
        # 不参与 ACL —— 姓名会变、会重名，判定只认 id / open_id。
        if isinstance(row.get("name"), str) and row["name"].strip():
            item["name"] = row["name"].strip()
        item["source"] = "explicit" if row.get("source") != "auto" else "auto"
        explicit_version = row.get("authz_version")
        if explicit_version is not None:
            if not isinstance(explicit_version, str) or not explicit_version:
                raise PrincipalDirectoryError("principal_field", "authz_version")
            item["authz_version"] = explicit_version
        elif self.require_authz_version:
            raise PrincipalDirectoryError("principal_field", "authz_version")
        else:
            item["authz_version"] = hashlib.sha256(json.dumps(
                item, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest()
        return item

    def _lookup_identity(self, tenant_id, open_id, display_name=None):
        """显式层 → 自动层 → 自动登记。见模块文档的三条规则。"""
        explicit = self._by_key.get((tenant_id, open_id))
        if explicit is not None:
            # ★ 显式 revoked 也在这里返回 None，且**不再往下走** ——
            #   否则「撤掉的人扫一次码就复活」。
            return explicit if explicit["status"] == "active" else None
        found = self._auto.get((tenant_id, open_id))
        if found is not None:
            return found if found["status"] == "active" else None
        if self.auto_grant is None:
            return None
        row = self._auto_row(tenant_id, open_id, display_name)
        # 先落盘再返回：跳不过去。写失败会抛 `principal_auto_store_unwritable`。
        self._persist_auto(row)
        return self._auto.get((tenant_id, open_id))

    def by_identity(self, tenant_id, open_id, display_name=None):
        """按 (tenant, open_id) 查主体。自动登记在这一跳里发生。

        `display_name` 只在**新建**自动登记时用到（写进记录供人认，
        **不参与任何判定**）；显式层与已登记的自动层都不看它。
        """
        self._refresh()
        row = self._lookup_identity(tenant_id, open_id, display_name)
        if row is None or row["status"] != "active":
            return None
        return copy.deepcopy(row)

    def by_id(self, principal_id, tenant_id):
        self._refresh()
        # 自动层也参与：session 里存的是 id，登录之后所有请求都从这里回来。
        row = self._by_id.get(principal_id) or next(
            (r for r in self._auto.values() if r["id"] == principal_id), None)
        if row is None or row["tenant_id"] != tenant_id or row["status"] != "active":
            return None
        # review_api/RBAC 同时使用 tenant 与 tenant_id、open_id。
        out = copy.deepcopy(row)
        out["tenant"] = out["tenant_id"]
        return out

    def eligible_assignee(self, principal_id, case):
        self._refresh()
        row = self._by_id.get(principal_id) or next(
            (r for r in self._auto.values() if r["id"] == principal_id), None)
        if row is None or row["status"] != "active":
            return False
        if row["tenant_id"] != case.get("tenant"):
            return False
        if case.get("product_line") not in row["product_lines"]:
            return False
        return bool({"dp3", "dp4"} & set(row["roles"]))


    def ready(self):
        try:
            self._refresh()
        except PrincipalDirectoryError:
            return False
        # 开了自动登记时，显式表为空**也是就绪的** —— 那正是「全员扫码即进」
        # 的常态（显式表只留给需要特批的人）。自动层未写盘由
        # `_persist_auto` 的留痕暴露，不靠 ready 这一格。
        if self.auto_grant is not None:
            return True
        return bool(self._by_key)
