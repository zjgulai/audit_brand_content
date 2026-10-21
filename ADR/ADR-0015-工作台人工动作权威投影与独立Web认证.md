# ADR-0015：工作台人工动作以文件 + manifest 为唯一真相，独立飞书 Web 应用认证

- 状态：`accepted`（Owner 于 2026-10-20 在本会话逐题选择：①文件+manifest唯一真相 ②独立飞书 Web 应用 ③首批仅复核台账）
- 日期：2026-10-20；实现验收读数更新：2026-10-21
- 决策者：Owner（以上三项均在本轮逐题确认；命中 ADR/README 规则 3 的“改变权威存储 / 开放外部身份输入”，故在文件内留直接依据）
- 实现 owner：`audit-multi-content-16`（后端生产装配单一写者）
- 依赖：ADR-0001（旧双账本背景）· ADR-0002（记录级溯源）· ADR-0005（工具不替人过门）· ADR-0013（仓库分级与文件指纹）
- supersedes：**仅在「内容审核工作台人工动作」范围替代 ADR-0001 的“人的动作以飞书为权威”**；ADR-0001 原文保留，业务既有 Base 的权威范围不被本 ADR 静默改写。

## 一、触发

Web 已完成本地单进程 claim → draft → submit 验收，但 `ReviewsLedger`、申诉、幂等和签发状态仍在内存；`FileProjectionRepository` 只在启动时加载 JSON，坏文件会静默退为空。验证器绿不等于服务重启、并发与恢复可用。

同时，旧 ADR-0001 与新 UI/UX 合同存在权威冲突：前者把人的动作交给飞书，后者要求“文件 + manifest 唯一真相、SQLite 只是可重建投影”。若不先裁定，持久化会造出两个真值源。

## 二、决策

### D1 · 工作台人工动作的唯一真相

内容审核工作台的复核、草稿、正式提交，以及后续迁入的 finding、申诉、下线与签发事件，以**仓外不可变事件文件 + manifest** 为唯一真相。

- 一个命令形成一个 `command-batch/v1`；manifest rename 是唯一可见提交点。
- SQLite 只作查询投影，必须能从 manifest 全量重建；不进业务备份。
- 飞书只作身份、通知、批量入口或只读状态投影，不作这批人工动作的权威写库。
- 旧 IR、报告、签名与历史事件不改不删；人工动作只能追加。

### D2 · 投影落后语义

权威提交成功而投影失败时：

- 不回滚权威；
- 返回 HTTP 202，以及低敏 `authority_snapshot`、`projection_lag=true`、`reconcile_token`；
- read-your-write 可凭 token 读取该命令受限结果；
- 其他当前态 GET 在投影落后时返回 503，不把旧投影冒充新状态。

坏 manifest、断序、哈希不符、权限错与坏 SQLite 必须分别成为 `corrupt` / `unavailable` / `lagging`，不得退化为空集合。

### D3 · 单写者

第一阶段固定单 API worker，并在数据卷使用跨进程 writer lease。第二写者获取不到 lease时不得 ready、不得执行写；`--workers 1` 不是互斥锁的替代。

### D4 · 正式认证

正式 Web 使用**独立飞书企业自建应用**直连 OAuth/SSO，不复用守衡应用。

- principal = `tenant_id + open_id`；角色、品线和 capability 从本地受控授权投影解析，不接受浏览器自报。
- Session 独立 SQLite；cookie 仅 opaque id，`Secure; HttpOnly; SameSite=Lax; Path=/; 无 Domain`。
- 所有状态变更请求校验固定 Origin/Referer + session-bound CSRF。
- sign/revoke 另走 SSO re-auth，step-up 5 分钟、single-use、绑定 principal + case + action + nonce。
- session DB 与 step-up 不进业务备份；恢复后全员重新登录。
- 守衡应用凭据、生命周期和权限不被 Web OAuth 复用或改变。

### D5 · 首批生产写面

首批只开放：claim / unclaim / reassign / heartbeat、draft save/adopt/reference、formal submit。

以下继续 fail-closed：finding confirm/reject、新 IR/run/report、appeal、takedown、release/sign/revoke 与通知 mutation。路由或领域类“已经存在”不等于生产 capability 已开放。

## 三、代价

- 需要权威事件层、SQLite 投影与恢复工具，不能直接把现有内存对象序列化一次了事。
- 原有飞书操作习惯不能直接作为工作台权威写入；需要明确通知/投影同步。
- 独立飞书应用需要额外创建、最小 scope、redirect allowlist 与密钥轮换。
- 首批生产能力刻意小于 UIUX 完整页面清单；换来可证明的重启、并发、恢复和幂等。

## 四、验收

1. 同 Idempotency-Key + 同请求在重启后返回同一结果，不产生第二批事件；异请求 409。
2. 两进程并发 claim 恰一成功；第二 writer 不 ready。
3. 投影删除可重建；坏/落后投影不返回旧值；权威成功投影失败返回 202。
4. 空目录按 manifest 链逐哈希恢复，session 不恢复。
5. fake OAuth 只能证明协议与安全门；真实独立飞书应用未配置时真实 OAuth 必须退 2 未测。
6. confirm/reject、appeal、takedown、release 在生产入口明确拒绝。

## 五、当前状态（2026-10-21 读数）

已完成并有机器执行点：

- 不可变 business command batch、manifest SHA 链、重启幂等、OS `flock` 单写者；
- 复核 reducer 九种命令、SQLite WAL 投影、seq + manifest hash 新鲜度、202/503/read-your-write；
- `claim → draft → submit → 重启 → 回读`，以及仓外备份、空目录校链恢复和从零重建；
- 独立 Web OAuth 的当前授权/v2 token/v1 user_info 接线，opaque session、Origin+CSRF、浏览器绑定；
- 独立 reauth callback，5 分钟 single-use step-up，token 只存 hash，签名只存不可逆 ref；
- `/healthz` 固定低敏，`/readyz` 真探 authority/projection/session/lease/权限/主体目录。

本地 fake/离线协议与临时仓外目录的验证器可通过；**真实独立飞书应用仍未创建/配置，真实 code exchange、redirect allowlist、scope 和 HTTPS cookie 联调保持退 2 未测**。容器化、目标机、DNS/TLS 也仍未测。本 ADR 的实现完成不代表可部署；部署另需明确授权与环境验收。
