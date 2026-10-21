# 内容审核工作台 · 部署准备方案 v1

> 日期：2026-10-20。状态：**PREPARE ONLY / 业务上线 NO-GO**。
> 本轮只整理本地文档与并行任务，不连接目标服务器，不上传、不改 DNS、不签发证书、不启动远端服务。
> 目标代号 **DEPLOY-01**；机房主机、SSH 用户/端口与域名已存本地部署环境记忆，**公开仓不记录内部主机及登录信息**。
> 本文件没有密码、私钥或令牌。用户提供过的认证信息不进入记忆、脚本、镜像、日志或 Git。

## 1. 结论与先后顺序

**可准备部署方案，不能把“本地页面验收过”视为“生产业务可用”。**

先收敛现有 Web 的写动作、安全与数据一致性，再准备独立的产品部署包。
不要把 `web/scripts/review_api_dev.py` 或 `dev-up.sh` 原样搬到服务器。

建议按四层开放，每一层单独验收、单独获部署授权：

| 层 | 允许 | 不允许 | 当前状态 |
|---|---|---|---|
| L0 本地准备（本轮） | 源码/文档核对、任务收口、方案与检查项 | 连接服务器、上传、网络配置、部署 | 本文件完成的范围 |
| L1 受限只读验收 | 隔离样例或经审批的脱敏冻结投影、静态 UI、鉴权后的读 API | 写业务台账、提交素材、签发、外发通知、自动任务 | **待准备**；现有开发入口不满足此边界 |
| L2 人工复核业务 | 真身份、认领/租约、持久草稿、显式提交、确认/驳回后可回读 | 自动放行、未经验证的多模态覆盖 | **NO-GO**，见 §4 |
| L3 多模态与完整发布 | 独立通过模型、媒体与签发门的能力 | 把未审查模态说成已覆盖、机器签发 | **NO-GO**；不与首批只读验收捆绑 |

L1 不是生产完成：必须持续标明“验收环境”，不收客户原始素材、不产生发布授权。
即使只开放 GET，API 仍可能续 session、写访问审计；**只读指业务状态不变，不是进程绝对零写盘**。

## 2. 部署目标与待核事实

DEPLOY-01 为用户提供的机房服务器，域名用于 HTTPS 工作台。
**尚未连接或验证可达性。** 以下都不能从开发机读数推断：

- OS/发行版、CPU 架构、CPU/RAM/磁盘、文件系统、GPU；
- SSH 主机指纹、登录认证方式、是否有受控 sudo、现有监听端口与服务；
- Docker/Compose 可用性、出网下载依赖/模型的限制、时间同步；
- 域名当前解析、公网入口、机房 NAT/反代、VPN/跳板、80/443 入站及 TLS 验证方式。

主机为私网地址：**公网 DNS 不能仅靠指向私网 IP 就让外部用户访问**。

推荐默认：运维 SSH 经公司内网/VPN或跳板，仅入口反代对已批准用户开放 HTTPS；
若要公网访问，先明确公网反代/NAT 到机房的路径，再确定证书与 DNS。
内网-only 可走内部解析与受信任证书；公网证书采用 HTTP 或 DNS 验证须由实际网络条件决定。
本轮不选定未经核实的网络拓扑、不探测远端。

服务器登录权限不等于应用用户权限。部署用户与容器运行身份分离，不以 root 运行应用。
登录凭据仅在未来用户授权的受控认证流程中使用；建议正式操作前更换已在会话中提供的凭据，并采用 SSH 密钥认证。

## 3. 推荐拓扑（提案，不是已落地配置）

产品合同规定 Compose 与 CPU-first；默认以 **Linux 主机 + Docker Compose** 设计。
如果目标 OS/架构不符合，先调整方案，不拿 macOS 二进制硬迁移。

    浏览器
      │ HTTPS（批准的访问范围）
      ▼
    入口反代（Nginx，建议）
      ├─ 静态前端：审定的 web/dist
      ├─ /review-api/* → 私网 API /api/v1/*
      ├─ 正式认证回调与 session 路径（实现后再开放）
      └─ /dev/*、内部探针与未获准 API：拒绝，不落入 SPA fallback
      │
      ▼
    正式 API 装配（Python 3.12，非 dev wrapper）
      ├─ 身份/session/RBAC/访问审计
      ├─ 人工动作 → 原始权威账本 → 派生投影 → GET 回读
      └─ worker / 投影协调器（生命周期与恢复经过验收后再启用）
      │
      ├─ 权威文件 + manifest（唯一真相）
      ├─ 投影/队列/审计持久卷
      └─ session/step-up 独立卷（不进业务备份）

部署纪律：

1. 浏览器优先同源 `/review-api`；Vite 的 `server.proxy` **只在开发生效**，静态构建不会替服务器做代理。
2. 入口反代显式区分 API、assets 与 SPA 路由。API 404/403/503 必须保持 JSON/状态码，不能被 SPA 的 200 页面覆盖。
3. TLS 在可信入口终止，转发头只信任该入口；不信任互联网客户端伪造的身份/转发头。
4. 前端静态包目前含分类规范、规则示例与争议描述：发布前确认其数据等级。仅给 API 上锁**不等于**静态包内容已受保护。
5. API/worker 不直接暴露宿主端口，进入 Compose 内网；数据库、账本、媒体卷不得置于静态站点根目录。
6. 当前锁与状态是进程级；首批不多 worker、不多副本。**单副本只是限制并发，不会自动修复重启丢状态**。
7. 守衡继续保持当前运行状态：不重启、不迁移、不另启同凭据副本。共存/迁移是独立决策，仍走 AGENTS.md §2.7 闸门。

## 4. 上线阻塞清单（从当前代码核实，不是服务端实测）

| ID | 缺口与证据 | 完成判据 | 归属 |
|---|---|---|---|
| D-ENV | DEPLOY-01 的 OS/网络/DNS/TLS/权限均未核 | 授权后只读采集环境清单，确认入口与 SSH 主机指纹；不能用本机读数顶替 | 用户/运维；未执行 |
| D-AUTH | **本地生产装配已补**：独立飞书 Web OAuth（登录 + 独立 reauth callback）、tenant+open_id、本地主体目录热撤销、opaque session、Origin+CSRF、浏览器绑定与 hashed/single-use step-up 均有 fake/离线正反对照；真实独立应用尚未创建 | 真实 IdP 的两个 redirect allowlist（`/auth/callback`、`/auth/reauth/callback`）、最小 scope、`prompt=consent`、HTTPS cookie 与 tenant/open_id 需单独联调；live evidence 缺失时门退 2 | 后端本地门通过；真实飞书未测 |
| D-DEV | **Web 侧已修**：生产 bundle 不含开发身份/写模块；dev wrapper 需显式 dev+opt-in 且只接 loopback；切身份隐藏旧内容并撤销旧 session | 网关仍须拒绝 `/dev/*`；真实 SSO 独立验收 | Web 生产边界 9/9（含坏样本反向对照）+ dev入口8/8 + 身份隔离通过；网关/后端待派 |
| D-WEB-WRITE | **开发链 + 首批生产复核链已补**：每个意图带 Idempotency-Key；生产 claim/unclaim/reassign/heartbeat、draft save/adopt/reference、submit 走仓外不可变 command batch + manifest，SQLite 只作投影；重启后全文可回读 | finding confirm/reject、appeal、takedown、release/sign/revoke 仍明确 501；不得因路由存在而开放 | 本地临时仓外目录通过，未部署 |
| D-LEDGER | review 权威已改为不可变文件+manifest；actor/tenant/key/request hash 幂等，OS `flock` 单写者，进程内 authority+projection 单飞；崩溃孤儿与并发均有反向对照 | 目标卷/容器 UID/GID、磁盘故障与真实负载仍须部署批验证；其余写域迁移前继续关闭 | 首批复核台账本地闭合 |
| D-FINDING | `FindingStore(path)` 有 JSONL 重放能力，但默认为空；`GET case` 读启动加载的投影，不读新写 store | 真实权威数据正常初始化→GET candidate→confirm/reject→权威追加→投影重建→GET 新版本；坏投影能重建，旧 IR 不改 | 后端未派 |
| D-PROJECTION | **本地生产投影已补**：SQLite WAL 逐批投影，`seq + manifest hash` 新鲜度、前缀链、202 lag、503 stale GET、绑定人/案的 read-your-write、在线 reconcile、删除后全量重建均有执行点 | 目标环境的磁盘/权限/负载与容器重建仍未测；SQLite 不进业务备份 | 本地 21 项投影自证通过 |
| D-TEST | Web 门 + 后端生产装配门已补：本地 claim→draft→submit→重启、两线程/两进程、投影滞后、身份/CSRF/reauth、备份恢复、health/readiness 故障注入；另有真实 uvicorn HTTP smoke | fake/离线协议只证明接线；真实飞书、目标机、容器、TLS、负载与长稳仍单列未测 | 本地后端门通过；部署门未闭 |
| D-STATE | 依据缺失时 `EvidenceItem` 仍默认 ok；覆盖非 partial 默认 pass 样式；当前规范版本展示不证明案件实际使用过该版本 | 未测/缺失不呈通过；每个 badge 取后端状态；区分“当前规范参考”与“案件使用的规则快照”，旧案不冒充按最新规范判定 | Web 下一批，未修 |
| D-HEALTH | **本地正式入口已补**：`/healthz` 仅固定存活；`/readyz` 真探配置、权威链、seq/hash 投影、session DB、OS writer lease、0700 与主体目录，响应低敏；uvicorn 进程级 HTTP smoke 已过 | 容器重启策略、磁盘满、目标 UID/GID 与双容器 writer 仍须目标环境实测 | 本地门通过；TS-15 仍未测 |
| D-MEDIA | 容器 OCR/ASR 基线未完成；macOS Vision/Speech 与 launchd 不可直接搬 Linux | 容器真实中英素材 benchmark，许可证/隐私/时码/bbox/latency/memory 齐；未覆盖模态继续未审查 | 多模态未派 |
| D-RELEASE | release gate/SoD/nonce/5分钟 single-use step-up 的领域与 API 自证已过；step-up 仅存 hash，签名只存不可逆 ref，独立 reauth 使用官方 `prompt=consent` | **首批生产 capability 仍关闭 sign/revoke**；真实飞书 consent 不能夸大为重新输入账号凭据，live evidence 与 Web 签发 UI 未完成前不开放 | 独立后续批次，当前 501 |

以上表中标“待实现”的仍是上线门；D-DEV、D-WEB-WRITE 与 D-TEST 的**本地 Web 执行器已新增并实跑**，其余不能写成已存在的保护。
端点/函数已有实现、本地单进程验收、生产装配与可靠性闭环是四件事，不能互相作证。

## 5. 并行任务收口

| 会话/方向 | 当前事实 | 部署关联 |
|---|---|---|
| 本会话（16） | 全权 Web 设计开发；已补开发验收写链与生产只读隔离 | D-WEB-WRITE/D-DEV/D-TEST 的本地门已闭；D-STATE 与生产后端门待下一批/另派 |
| 4b | 分类评测与规范维护；映射仍旧基线：42/638 可用码、35/638 可 join、欠定 0/7 | 其新分析认为 638 归类基准与生产检测规则不是同一库，**不强行映射**；产品定义确认前不新增 Finding.rule_id |
| 0e | 分类基准报告；反馈 finding JSONL 重放与 create_app 有实现；自己不接后端/媒体 | 模块自证通过不等于新部署认证与写后可见已通过 |
| 6d | 最新规则七轴归类：65条×5轮 stable_correct 42/65、stable_wrong 12/65、unstable 11/65；纯文本512条 axis_exact 22.07%、UNKNOWN 57.42% | 仅归类/改写建议评测，**不是生产内容检测质量**；语义准确率和多模态仍无生产读数 |
| 后端/运维/媒体 | finding 权威写入→投影刷新无接手人；生产部署包与媒体门未闭 | **未派**，不是“有人会处理” |

4b 对基准形态的最新分析：451 条改写建议、129 条命中规则、21 条词表、37 条其他。
其中“改写建议不是检测规则”的区分影响质量口径；这些是并行报告的当前分析，
**本轮未逐条复算其形态计数，不当成模型准确率或发布 readiness 证据**。
不能把规则归类欠定自动当作某条生产 finding 的依据冲突；也不能反过来说当前案件不受影响。

规则后续必须给出可执行检测规则、改写知识、规范元数据各自版本与来源；
只有产品明确关系、稳定键能真实产出时再谈字段，而非先加恒为空的字段。

## 6. 发布包与目录（设计建议）

建议目录以独立服务用户持有，示意：

- `releases/<release-id>/`：只读版本包、依赖锁与镜像 digest；
- `current`：当前审定版本指针；切版本不覆盖旧包；
- `data/authority/`：权威 records/IR/manifest；
- `data/projection/`：可重建投影；
- `data/session/`：session 与 step-up，独立于业务备份；
- `data/audit/`：长期审计（不和临时 session 混用）；
- `data/media/`：批准的仓外素材与模型缓存；
- `backups/`：加密、访问受控且位于不同故障域的备份。

数据目录权限按合同 **0700**，确定容器 UID/GID 与最小读写面；非秘密配置与静态文件按需要可读，
不要把所有路径一律 0700 导致反代无法读构建产物。凭据由受控文件/secret 注入，不能放 `VITE_*`。

**发布白名单**：

- 已审定的 `web/dist`（确认静态规则数据可向批准的读者提供）；
- 最小正式运行源码、必需的一方规则/契约与配置；需声明 runtime-import 清单，不能按顶层目录猜依赖；
- Python `pyproject.toml` + `uv.lock`，前端锁文件，审定镜像 digest；
- release manifest：commit、构建标识、规则/KB/规范指纹、文件 sha256、依赖版本、测试结果及未测项。

**明确排除**：密码/私钥、`.env`、`.git`、`.claude`/工作树/本地记忆、
`PMO` 全量研究与客户素材、gold、逐字稿、业务附件、日志、守衡状态、
浏览器 profile、`.venv`/`node_modules`/缓存/不必要 source maps。
不要整仓 tar/scp/rsync，不把当前工作区里其他会话未提交材料发布出去。

前端 TS-6/TS-7 合同写 pnpm/TanStack Router，当前实现是 npm/React Router。
需要确认书面例外或完成迁移后验收；**本方案不擅自迁移、不宣布偏差已获豁免**。
建议先可复现锁定现有实现（npm ci、Python locked sync）再在单独任务中处理合同偏差。

## 7. 未来上线流程（现在不执行）

1. **另获环境核实授权**：只读确认 DEPLOY-01 环境、SSH 主机指纹和入口；不修改服务。
2. **先补 §4 的门**：本会话完成 Web 正反验收，后端独立完成权威写入/投影/认证/持久台账；不以 demo 替身作生产 identity。
3. **审定发布 manifest**：冻结 commit 与规则/KB快照。规范版本与指纹可变，不能把本文件里的历史读数当固定版本。
4. **本地构建隔离产品包**：按锁文件构建、运行门禁；下载依赖/模型分别进入新目录，第三方脚本按审定入口执行。
5. **另获部署授权**后再上传白名单包、配置网络/TLS/目录与 Compose；不改机房其他服务，不动守衡。
6. **受限验收**：验证 HTTPS/深链/GET/403/API错误不被SPA兜底、`/dev/*` 禁用、样例标识与完整读者范围。
7. **业务写入开门**：认领/保存/提交/确认的正常、并发、重试、刷新、服务重启和备份恢复完整链全部实测；否则继续只读。
8. **正式切流**须另行批准；记录 actor、时间、版本、动作、结果。签发/多模态依各自门再开，不随切流自动启用。

不承诺固定时延、吞吐或完成日期：目标硬件、模型与基准均未核。

## 8. 回滚与备份

- 镜像/静态包按版本保留；代码回滚到上一审定版本，不覆盖本次权威记录。
- 数据格式变更先演练向后兼容与恢复，不能把“换回旧代码”当成数据已回滚。
- 权威文件+manifest 与长期审计需要一致备份；投影可重建但必须记录版本/滞后，不能无痕返回旧数据。
- session/step-up SQLite 及其 WAL/SHM **不进业务备份**。恢复后全员重新登录，并拒绝旧一次性 token。
- 先限定写入/处理队列再取一致快照，恢复演练在隔离数据目录；没有演练读数的备份不算可恢复。
- 故障时保持“待放行”，不能因为只读/API恢复而恢复发布权限。
- 不回滚其他会话的工作区、不清理他人文件、不使用破坏性 Git 重置。

## 9. 本轮证据与未测

| 项 | 本轮状态 |
|---|---|
| 目标服务器及公网入口 | **未测**；未连接、未解析域名、未探测端口 |
| 当前规范 JSON | `--check` rc=0、`--selftest` 9/9；当前页面读 `v1.1 / 4a96880b0cf8` |
| 本地完整 Web 联调 | **本轮实跑 rc=0**：11 阶段；生产 bundle 9/9（正常与 hostile-build 双跑）、dev fail-closed 8/8、写链 version 0→1→2→3、无障碍40项0违规、390×844无横向溢出且控件≥44px、切片15/15、身份隔离/旧session撤销通过 |
| API/前端/运行约束 | Web 本地写链与后端首批复核生产装配均已在临时仓外目录实跑；固定单 worker + OS writer lease，其他人工写域继续 501 |
| 后端持久化/认证/投影/恢复 | **本地通过**：权威 11/11、投影 21/21、reducer 15/15、session 39/39、OAuth 离线 8/8、生产装配 52/52、恢复 14/14；真实飞书 live gate 无 evidence 时退 2 |
| 容器媒体/负载/TLS/真实认证 | **未测**；TS-15、目标机、DNS/TLS、真实飞书两个 callback/scope/consent 不因本地绿而闭合 |
| 官方部署文档查询 | 本轮 Context7 超时、官方网页不可读；未据此声称远程配置已验证 |

未来验证入口（只登记，不自动执行）：

- Web：`bash web/scripts/dev-up.sh`；当前 D-WEB-WRITE/D-TEST 的本地单进程门已实跑，生产持久化/认证/投影门仍须后端补齐后重验。
- 规范：`python3 tools/gen_taxonomy_json.py --check` 与 `--selftest`。
- 后端：`.venv/bin/python tools/verify_business_event_store.py`、`verify_projection_store.py`、
  `verify_review_reducer.py`、`verify_auth_session.py`、`verify_web_auth.py`、
  `verify_production_app.py`、`verify_backend_recovery.py`；真实飞书：
  `verify_feishu_web_oauth_live.py`（无单独授权 evidence 时应退 2）。
- 离线运维：`.venv/bin/python tools/review_backend_admin.py {backup|restore|rebuild}`；
  session/projection/generation 不进业务备份，access/auth/step-up 长期审计可恢复。
- 总验收：`tools/verify_acceptance_run.py` 与 `tests/acceptance/verifier_map.json`；退 2 必须报未测，不能报通过。
- 发布治理：`tools/verify_download_governance.py` 与 `tools/verify_depad.py`。

这些脚本可能创建临时文件、启动本地进程或写审计，不以“名字像检查器”推断它们无副作用。
未给实际执行结果的条目均未闭，不把“命令存在”写成“门已实现”。

## 10. 证据入口

- `web/src/api/client.ts:119–145,184–225`：请求 header 与 cookie、人工动作。
- `web/src/pages/CaseDetailPage.tsx:387–418`：认领、草稿与提交实参。
- `web/src/components/IdentitySwitcher.tsx:51–105`、`web/scripts/review_api_dev.py:97–138`：开发身份功能。
- `web/scripts/check_review_slice.mjs:357–399`：A5/A7/A8 覆盖不足。
- `api/review_api.py:189–212,332–435,455–462,553,589`：启动加载投影、默认装配、鉴权与写路由。
- `base/finding_store.py:202–250,279–315`：文件回放、追加及迁移。
- `base/reviews_ledger.py:70–83`、`api/write_api.py:100–104,226–238`：内存台账、申诉与幂等。
- `Playbook/内容审查Agent-产品Playbook-v1.1.md:1252–1302`：运行时、锁依赖、Compose 与 CPU 媒体合同。
- `web/docs/handoff-4b.md`：确认读写断层与旧映射假设；本文件 §5 是并行任务的更新收口。

---

## 11. 批次 0 前端门禁（2026-10-21）

本地新增的门（**不改变部署形态，也不新增运行时依赖**）：

```bash
cd web
npm run verify:static     # 设计 token（DT-1…DT-8）；当前退 2：tokens.css/Button/icon.tsx 未建
npm run verify:build      # build + F11 体积预算 + 生产边界门；当前退 2：无 vite manifest
npm run verify:a11y:manual # TS-9 人工项；9 项全部 not_run → 退 2
npm run verify:visual     # 视觉基线；没有 visual 段 → 退 2
```

**部署前必须知道的三件事：**

1. **退 2 不是通过。** 体积预算要等 Stage 1 的 `build.manifest`、人工 a11y 要等 Stage 7 签收，
   在那之前它们只会退 2。不要把 CI 里的 2 配成「忽略」。
2. **已知红 A2d 未修**：缺 `authority_state` 的 finding 仍显示「可核」（Stage 5 / T-WEB-05）。
   它不影响部署形态，但**影响「未测不得呈通过」这条产品铁律** —— 上线前必须关闭。
3. 两条 a11y waiver（W-005 非文本对比、W-006 `/taxonomy` 1280×720 溢出 6px）
   到期日都是 2026-11-30；过期后 `a11y_check.mjs` 会退 1。

本节之前的后端装配读数由后端批次写入，与本节不是同一批改动。

