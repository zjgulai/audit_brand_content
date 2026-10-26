# audit_multi_content · 仓库物理边界与数据读写纪律

## 一、仓库边界

- 本仓**独立承载**内容合规审查 Agent 的全部代码与文档。禁止跨项目 import、禁止跨项目写入。
- 本仓是**公开仓**（`audit_brand_content`）。这条事实本身产生三条后果：
  1. **下载来的媒体/文档二进制不许进仓** —— 判据是 `git ls-files` 里没有任何媒体/文档二进制，
     执行点 `tools/verify_download_governance.py`（DG-1…DG-6）。
     ⚠️ `.gitignore` **不是执行点**（`git add -f` 照样能进）。
  2. **仓内文本里不许有凭据** —— 执行点 `tools/verify_secret_patterns.py`。
  3. 客户素材、个人信息一律不进版本库。

## 二、凭据红线

**凭据文件一律不许读。** 名单逐个点名，不做模糊匹配：

```
~/.dsh/credentials   ~/.dsh/.credentials.yaml   ~/.ssh   ~/.aws   ~/.config/gh
按文件名拦：.env  id_rsa  .netrc  .git-credentials
```

执行点：`tools/agent/tools.mjs` 的 `secretGuard()` + `tools/agent/secret_path.test.mjs`（27 项）。
已知的坑：模糊匹配 `secret|token|key` 会把仓里 `…/pycparser/ply/ctokens.py` 一起拦掉 ——
**误报比不报更糟**，因为一个会误报的检查器会让人开始不看报告。

## 三、写盘纪律

- **同一个量能算出两个数时，结论行必须两个都报**（`getsize` 逻辑视图 vs `stat` +4096），
  并写明判定用哪个、为什么（AGENTS.md §2.4.8）。
- 生成物写完必须做**字节级校验**：环境 +4096 填充会让 `read` 工具打不开文件，
  而 `tail` 会 seek 到填充区打出乱码。
- 超长内容**搬**进别的格子，一个字符不丢；**不截断**。

## 四、并行会话

本工作区**多个会话共用**，且 `.depad --fix` 是全量的。所以：

- 提交前**逐项归属**：只 `git add` 你确认是自己产出的具体路径，**绝不 `git add -A`**。
- 不许把别人在办的文件扫进自己的提交。
- 动共享文件（`AGENTS.md`、`verifier-coverage.json`）前先看 `git status`。

## 五、重启的边界

守衡（飞书机器人）**重启前必须先问、且必须留痕**。它是对外说话的东西 ——
重启窗口里群里发的消息不会被回答，而且不会有任何东西记下来。
- 只许走 `bash tools/restart_shouheng.sh` 闸门，**闸门默认拒绝**。
- **不要用 `kill -TERM`** —— 它的 `shutdown()` 是 `process.exit(0)`，launchd 按
  `KeepAlive{SuccessfulExit:false}` 认定「正常停机」，于是**永不拉起**，而日志看起来一切正常。
- 唯一正确的方式是 `launchctl kickstart -k`，由闸门执行。
