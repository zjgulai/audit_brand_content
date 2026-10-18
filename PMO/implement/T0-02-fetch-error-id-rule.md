# T0-02 · `fetch_error` 的稳定 id 规则（S-3 设计关门）

> **要解决的问题**：`ContentUnit v1` 的 `unit_id` 由 `text_sha256` 派生。
> 但一条内容**抓取失败时没有正文**，算不出 `text_sha256` ——
> 于是「失败的那次尝试」在盘上没有稳定身份，回执、报告、重审都对不上号。
>
> **这不是命名问题**：S-3 已定「运行级 `ReviewIR` 为唯一真相」，
> 而 `ReviewIR` 要引用「这次审查的是哪条内容」。抓取失败的那条也得能被引用。

## 规则

```
unit_id = sha256( source.kind || 0x1F || normalized_locator )
```

| 组成 | 含义 | 规范化方式 |
|---|---|---|
| `source.kind` | 来源类型（`free_text` / `landing_page` / `image` / `video` / `文档` …） | 原值，小写 |
| `normalized_locator` | 规范化后的来源地址 | 见下表 |

两段用 `0x1F`（单元分隔符）拼接，避免任一字段含分隔符时产生碰撞。

> ★ **2026-10-18 更正：id 里不带时间。**
> 初版规则里有一个 `fetch_bucket`（抓取时刻按小时取整），**那是错的**：
> 同一来源反复失败会得到**多个 id**，于是回执归不了并、重审对不上号、还会制造重复工单。
> **失败的内容是同一件事，不管试了几次。**
> 若要区分「第几次尝试」—— 那是 `attempt_id` 的事，**不进 `unit_id`**（见未决第 1 条）。

## `normalized_locator` 的规范化

| `source.kind` | locator 是什么 | 规范化规则 |
|---|---|---|
| `free_text` | 提交内容的指纹 | `sha256(normalize(text))` —— 与 `unit_id` **不是同一件事**，它是 locator 的输入 |
| `landing_page` | URL | 小写 scheme + host；去掉默认端口、`#fragment`、`utm_*` 查询参数；路径保留 |
| `image` / `video` | 飞书 `file_token` 或消息资源 id | 原值（token 本身已稳定） |
| `文档` | 飞书 `document_id` + `block_id` | `doc:<id>#<block>` |

**规范化必须是纯函数**：同一输入任何时候都得同一输出，不受 locale、系统时区影响。

## 三条不变量（每条都要能变红）

| # | 不变量 | 怎么验 |
|---|---|---|
| **ID-1** | **同一来源、同一小时内两次抓取失败 → 同一个 `unit_id`** | 构造两次 `fetch_error`，断言 id 相等 |
| **ID-2** | **不同来源 → 不同 id** | 换 host / 换 token / 换 kind，各断言 id 不等 |
| **ID-3** | **同一来源跨小时 / 跨天 / 重试多次 → 同一个 `unit_id`** | 注入时钟差 1 小时、1 天各一次，断言 id **相等** |

## 正例 / 反例

| # | 输入 | 期望 |
|---|---|---|
| ✅ 正例 1 | `landing_page` + `https://Example.com/a?utm_source=x#frag`，10:00 抓取失败；10:20 再失败 | 两次 id **相同**（query 去掉 utm、fragment 去掉、host 小写） |
| ✅ 正例 2 | 同一 URL，11:00 再失败；次日 09:00 第三次失败 | **全部同一个 id** —— 三次失败是同一个案件的三次尝试 |
| ✅ 正例 3 | `image` + `file_token=abc123`，抓取失败 | 有稳定 id，且与任何 `landing_page` 的 id 不碰撞 |
| ❌ 反例 1 | `https://a.com/x` 与 `https://a.com/x/` | **必须相同**（尾斜杠规范化） |
| ❌ 反例 2 | `https://A.COM/x` 与 `https://a.com/x` | **必须相同**（host 小写） |
| ❌ 反例 3 | **把时间加进 id**（哪怕只精确到小时） | **ID-3 变红**：跨小时得到不同 id，回执归并不了 |
| ❌ 反例 6 | 同一内容抓成功后再失败，走不同的 id 生成路径 | **必须同 id** —— 成功与失败是同一条内容，只有 `parse_status` 不同 |
| ❌ 反例 4 | 用「错误文案」当 id 输入 | **禁止**：错误文案会变（超时措辞改一个字就变），id 就不稳了 |
| ❌ 反例 5 | 用「抓取时刻的秒」当 id 输入 | **禁止**：同一内容重试两次得两个 id，回执无法归并 |

## 明确不允许作为 id 输入的东西

- ❌ **错误文案**（会随版本改）
- ❌ **精确时间戳**（秒级/毫秒级 —— 重试会漂）
- ❌ **`text_sha256` 的空值或占位串**（`""` / `"unknown"` 会让所有失败共用一个 id）
- ❌ **进程内自增序号**（重启就变）

## 与 `ReviewIR` 的关系

`ReviewIR` 的 `source_ir_version` 指向 `ReviewIR` 自身版本（S-3 已定）。
`ReviewIR.content_unit_ref` 指向 `unit_id` —— **无论内容是抓成功还是抓失败**。
所以失败尝试的 `ReviewIR` 也存在，只是它的 `modality_facts` 为空、`parse_status = failed`。
**同一内容重试三次，仍只有一个 `unit_id`，但有三条 `attempt`** —— 两者回答不同的问题。

> **这解决了原 S-3 的第二个缺口**：不是「给失败找一个假正文」，而是
> **让失败本身有一个由稳定输入派生的身份**。

## 未决

| # | 什么 | 谁定 |
|---|---|---|
| 1 | **若要区分不同批次，另立 `attempt_id`，不进 `unit_id`** —— 批次身份是「第几次尝试」，`unit_id` 回答「审的是哪条内容」 | 产品 + 架构 |
| 2 | `free_text` 的 `normalize()` 是否需要版本号进 locator（改归一化规则会让旧 id 失效） | 产品 |
| 3 | 跨租户同 URL 是否该得同一 id（当前会） —— 若不该，`tenant` 要进 locator | 产品 + 法务 |
