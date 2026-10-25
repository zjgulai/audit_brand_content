# 前后端接线联调 · browser harness 使用说明

> **这份文档写给谁**：要把某一票（尤其 T-401…T-413 这一批）**真的点一遍**的人。
>
> 它不解释业务判据（那些在票里），只说明「怎么把浏览器架起来 → 点一遍 →
> 得到三态结论」。读完应当能自己跑，而不需要读源码。

---

## 一 · 为什么要有这一套

本仓已有 8 个页面级脚本（`check_pages.mjs` / `check_review_slice.mjs` /
`a11y_check.mjs` / `check_visual.mjs` / `check_login_qr.mjs` /
`check_identity_switch.mjs` / `check_queue_page.mjs` / `check_review_actions.mjs`），
合计 3000+ 行，**每个都自己实现了一遍「起 Chrome → 连 CDP → 收消息 → 超时」**。

复制 8 份的直接后果不是丑，是三条：

1. 修一个 CDP 缺陷要改 8 个地方，漏一个就有一条通道继续带着旧行为；
2. 每个脚本的「未测」判定各自写，于是「Chrome 起不来」在不同脚本里表现为不同的东西；
3. 新写一个联调脚本，第一件事是**再复制一份** —— 因为它没有别的入口。

所以拆成两层：

| 层 | 文件 | 管什么 | 不管什么 |
|---|---|---|---|
| **驱动** | `web/scripts/lib/browser_harness.mjs` | 起浏览器、连 CDP、超时、诊断采集、幂等关闭 | 任何断言 |
| **场景** | `web/scripts/pairing_check.mjs` 等 | 打开哪些页、看什么算失败 | 怎么起浏览器 |

断言与场景绑定，驱动与场景无关 —— 混在一起的代价就是上面那 3000 行。

---

## 二 · 三态语义（这是本套东西最重要的一条）

| 退出码 | 含义 | 读的人该做什么 |
|---|---|---|
| `0` | 全部通过 | 可以继续 |
| `1` | **测了，但不符合预期** | 去查页面/接线 |
| `2` | **没测成** | 去查环境（Chrome 在不在、服务起没起） |

`2` **不是**「差不多通过」，也**不是**「红」。

写成这样是有具体代价的：如果「这台机器没装 Chrome」也报 `1`，
读的人会去改前端 —— 而问题根本不在前端。AGENTS §2.4.1 第 4 行说的就是这件事：
**否定结论的输入必须是「所有通道都采过且各自活着」**，不是「我采的那条没有」。

执行点：`tools/verify_browser_harness.py` 的 **H1**（无 Chrome → `HarnessUntested`
而不是普通 Error）与 **H4**（CLI 三态在**进程退出码**上成立）。
两者分开测，因为「各自都对、合起来错」是本仓踩过的形状（§2.4.5）。

---

## 三 · 跑一次完整联调

### 3.1 起服务并保留

```bash
bash web/scripts/dev-up.sh --keep
```

`--keep` 让它跑完**不杀**进程（默认会杀）。它会在最后几行打印：

```
API_PORT=xxxxx
WEB_PORT=xxxxx
API_PID=nnnnn
WEB_PID=nnnnn
RUN_DIR=/var/folders/.../review-web-integration.XXXXXX
```

★ 不写 `--keep` 的话，服务在脚本退出时就没了，后面的联调会「连不上」——
而那个报错看起来像前端坏了。这正是把 `2`（未测）与 `1`（红）分开的理由。

### 3.2 拿一个 session

```bash
SESSION=$(python3 web/scripts/make_session.py \
  --db "$RUN_DIR/sessions.db" --principal u_dp3 --tenant t1)
echo "$SESSION"
```

### 3.3 跑接线检查

```bash
node web/scripts/pairing_check.mjs \
  --base "http://127.0.0.1:$WEB_PORT" \
  --cookie "session=$SESSION" \
  --pages "/queue,/cases,/submit,/inbox,/appeals,/release,/takedown,/reports,/taxonomy,/admin/grants,/admin/sessions" \
  --screenshots /tmp/pairing-shots
```

它逐页报：

```
✅ /queue               requests=12 5xx/4xx=0 console=0 exc=0
```

四列分别回答四个不同的问题：

| 列 | 回答什么 |
|---|---|
| `requests` | 这一页真的打了多少个后端请求（**0 是可疑的**：说明页面没接线） |
| `5xx/4xx` | 有没有接线断了（4xx/5xx） |
| `console` | 浏览器控制台有没有 error |
| `exc` | 有没有未捕获异常 |

### 3.4 验一个具体写端点（可选，也是最有用的）

```bash
node web/scripts/pairing_check.mjs \
  --base "http://127.0.0.1:$WEB_PORT" \
  --cookie "session=$SESSION" \
  --pages "/appeals" \
  --expect-write "POST /api/v1/appeals"
```

`--expect-write` 会**点名 501**：

```
❌ POST /api/v1/appeals → 501 capability_not_enabled（白名单没放开）
```

这一条是 T-401/T-402 那类票的现场指纹 —— **开发装配能点、生产返 501**。
普通页面扫描发现不了它（前端会把 501 渲染成一个错误提示，而页面本身「正常」）。

### 3.5 收尾

```bash
kill "$API_PID" "$WEB_PID"
```

`--keep` 留着进程，**必须自己收**。不收的话，跑几次就堆一堆 Vite/uvicorn/Chrome。

---

## 四 · 用 CLI 驱动排查（最快的一条路）

`browser_harness.mjs` 自己就是一个 CLI：

```bash
node web/scripts/lib/browser_harness.mjs goto "http://127.0.0.1:5180/queue"
node web/scripts/lib/browser_harness.mjs text
node web/scripts/lib/browser_harness.mjs eval "document.title"
node web/scripts/lib/browser_harness.mjs click "[data-testid=claim]"
node web/scripts/lib/browser_harness.mjs fill "#td-ev-receipt" "AMZ-RM-001"
node web/scripts/lib/browser_harness.mjs wait ".cases-table" 5000
node web/scripts/lib/browser_harness.mjs shot /tmp/q.png
```

排查时它的价值在于：**不需要写脚本**就能确认「这条选择器找不找得到」。
`wait` 找不到会退 `1`（并说清等了多久），不是静默返回。

---

## 五 · 写一个新的场景脚本

```js
import { launch, HarnessUntested, HarnessFailed } from "./lib/browser_harness.mjs";

const s = await launch();          // Chrome 不在 → 抛 HarnessUntested
try {
  await s.enableDiagnostics();     // 从现在开始记 console/网络
  await s.goto("http://127.0.0.1:5180/queue");
  await s.waitFor(".cases-table");
  const { failures, consoleErrors, exceptions } = s.takeFailures();
  if (failures.length || exceptions.length) {
    throw new HarnessFailed(`接线有问题：${JSON.stringify(failures)}`);
  }
} finally {
  await s.close();                 // 幂等，且会删掉临时 profile
}
```

**必须注意的三件事**：

1. `enableDiagnostics()` 是**显式**的。不打开就采集不到任何诊断 ——
   第一版就是这样，导致「页面报错」在驱动里完全不可见。
2. `takeDiagnostics()` **取走即清空**（`reset` 默认 `true`）。
   不清空的话，上一页的失败会算到下一页头上。
3. 自己 catch 之后**必须**按上面三态退：`HarnessUntested` → `2`，
   `HarnessFailed` → `1`。写成「都退 1」会让没装 Chrome 的机器报红。

---

## 六 · 自证

```bash
python3 tools/verify_browser_harness.py            # 12 项
python3 tools/verify_browser_harness.py --controls # 2 项反向对照
```

它验的是**驱动本身**（H1…H7），不验任何页面。页面的事归各自的场景脚本。

| 断言 | 拦什么 |
|---|---|
| H1 | 无 Chrome 抛错类型不对 → 调用方会把「未测」报成「红」 |
| H2 | 超时不生效 → 页面卡死时整条链挂住（比失败更难查） |
| H3 | `close()` 不幂等 / 关掉后静默成功 → 漏杀 Chrome |
| H4 | CLI 三态退码错（★ 未测 ≠ 红，在进程退出码上的执行点） |
| H5 | `goto` 不等 load 完 / 页内 JS 抛错被吞 |
| H6 | 临时 profile 残留（★ 从 `_profileDir` 读真实路径，不猜目录） |
| H7 | `dev-up.sh --keep` 开关不在 / 未知参数不早退 |

---

## 七 · 一次真实的踩坑记录（别重踩）

**联调跑不起来，报的是 `403 Forbidden`，而根因不在浏览器，也不在接线。**

`bash web/scripts/dev-up.sh` 在阶段 `[8/11]`（真点击下线台 Start）必然失败：

```
POST /api/v1/takedown-tasks/td-smoke-1/start HTTP/1.1 403 Forbidden
```

根因：`base/rbac.py` 把**下线执行/豁免**与 `release.sign` 定为人级名单，
且「未注入名单源 → 回落空集 → 全拒」（fail closed）。生产装配会注入
`build_allowlist_source(projection)`，而 `web/scripts/review_api_dev.py`
这个**开发装配此前没有注入** —— 于是开发环境里没人能下线。

用 `git stash` 掉本轮改动后复跑同样 `rc=1`，确认是既有问题、不是新增回归。

修法是给开发装配套一份 **逐条点名** 的开发名单（`DEV_ALLOWLIST`），
只授 `u_dp3` 的 `takedown.execute` 与 `u_signer` 的 `release.sign`；
`takedown.waive` 刻意**不授** —— 它要求双人审批 + 独立钥匙，本地放开会让
那条链「看起来通过」，而生产里没人能豁免。

★ 这条值得单独记的原因：它长得**完全像**一个权限缺陷，而实际是
「开发夹具少接了一根线」。如果当时直接去改 `rbac`（比如把 fail-closed 放宽），
就会为了跑通联调而**削弱一条安全约束**。

---

## 八 · 第一次真跑联调抓到的东西（2026-10-25/26）

这一节记录的是**这套东西第一次实际用起来**的结果。它不是「harness 做好了」，
是「用 harness 找出了四个真实缺陷，其中三个从来没有任何断言盖到」。

### 8.1 `dev-up.sh` 从来没跑通过（11 个阶段，卡在第 8 个）

改前 `bash web/scripts/dev-up.sh` **恒 `rc=1`**。用 `git stash` 隔掉本轮改动后
复跑同样失败，确认是既有问题。

失败链有三环，逐环修掉（每一环修完都重跑，看下一环）：

| 环 | 症状 | 真因 |
|---|---|---|
| 1 | `POST /takedown-tasks/td-smoke-1/start → 403` | `_ROLE_CAPS` 里**只有 signer** 有 `takedown.execute`，而夹具用 `u_dp3` 去点；同时开发装配**没有注入人级名单**（fail-closed → 全拒） |
| 2 | 仍然 403 | 我把名单授给了 `u_dp3` —— 名单是**第二道**门，角色能力是**第一道**。两道都得过，而两道的失败是**同一个 403**，从症状反推不出是哪一道 |
| 3 | `下线任务回读不是 completed：null` | 断言写成 `Array.isArray(tdList) ? ... : null`，而接口返回 `{tasks, metrics}` —— **这条断言从来没真正跑过** |

修法分别是：开发装配套一份**逐条点名**的 `DEV_ALLOWLIST`（只授 `u_signer`
的 `takedown.execute` / `release.sign`，`takedown.waive` 刻意不授）；
联调夹具**切到 signer 身份**再点下线台、切回 dp3 继续；断言改成读 `{tasks}`。

★ 第 3 环最值得记：**一条写错了形状的断言，比没有断言更坏** ——
它一直在红，而红的样子像业务缺陷，于是读的人去查业务。

### 8.2 收件箱「标记已读」点了没反应（422）

`InboxPage.tsx` 发的是 `body: {}`，而后端 `NotificationItemBody` 要求
`notification_id` 必填 → 每次点都 **422**，前端把非 501 的失败吞进 catch，
于是「通知还是未读、也没有错误条」。

这是**联调本来就该抓的那类缺陷**：两端的单测各自都过（前端没测 body，
后端测了 body 但用的是自己构造的请求），只有真点一下才会撞上。

### 8.3 `--expect-write` 探针本身踩的两个坑（记下来防止再犯）

| 坑 | 症状 | 真因 |
|---|---|---|
| cookie 只当开关 | 探针永远 401 | `--cookie` 只用来判断「跑不跑」，**没注入浏览器**。要用 `Network.setCookie` |
| 打错前缀 | 探针永远 404 | 前端走 Vite 的 `/review-api`（rewrite 到 `/api/v1`）；直接打 `/api/v1/...` 落到 Vite 自己身上 |

两个坑的表现（401 / 404）都与「白名单没放开」的**反面**长得一样，
所以那两轮里我都以为探针在说「接线通」—— 实际它什么都没测到。
现在：cookie 注入失败直接退 `2`（未测），404 会额外打一次归因探针。

修好之后它立刻抓到了该抓的东西：

```
❌ POST /api/v1/reports/rp-x/resign → 501 capability_not_enabled（白名单没放开）
```

### 8.4 一个「数字整齐得可疑」的读数，查过之后是真的

第一版每页都报 `requests=36`，几乎一模一样。我第一反应是「一份输入被重复读了 N 次」，
并在注释里写下这个解释。**那个解释是错的**：连调两次 `takeFailures()`，第二次
`checked=0`，缓冲区清空正常；36 是真的，Vite dev 按**文件**发 ESM 模块。

页面之间的差异（`/release`=37、`/reports`=38/39）也对得上。

★ 「整齐得可疑」不等于「判据坏了」。**先去证它，不要先改它** ——
  改一个其实是对的判据，比不改更糟（§2.1.1：会误报的检查器会让人开始不看报告）。
