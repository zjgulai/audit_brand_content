# `skill/` · 内容审核 skill 成员（37 个）

> 这一页是**来历说明**，不是简介。它回答两件事：**这些 skill 是什么**、**它们从哪来**。
>
> ★ **这一份有五个来源，别当成一个**：27 个来自 Momcozy 知识库（§二）·
> 2 个来自 SI-Agent 视频证据层（§六）· 5 个来自 kimi（§七）· 3 个来自 MinMax（§七）。
> **标准化裁定与体检读数在 [`标准化台账-20261017.md`](标准化台账-20261017.md)。**

## 一、这一份是什么

**27 个知识库成员 + 2 个 SI-Agent 证据层 + 5 个 kimi + 3 个 MinMax 文档 skill**，
含各自的 `SKILL.md`、`references/`、`scripts/`、`agents/`、`templates/` 与 `.skill-meta/`。

| 读数 | 值 |
|---|---|
| 成员数 | **37**（13 知识库工具 + 13 中文审查 + 1 brand-* + 2 证据层 + 5 kimi + 3 MinMax） |
| 文件数 | **220** |
| 体积 | 约 2.0 MB 落盘 |

复现上面几个数（**必须带 `-z`**：不带时 git 与 `find` 都会把中文路径转义，
按扩展名或名字过滤会静默漏掉它们 —— 本仓为同一个坑付过学费）：

```bash
cd /Users/lute/Project/audit_multi_content
ls -d skill/*/ | wc -l                     # 37
find skill -type f | wc -l                 # 220
ls -d skill/kb-*/ | wc -l                  # 13
```

## 二、从哪来（出处可核）

| 项 | 值 |
|---|---|
| 源仓库 | `github.com/zjgulai/audit_multi_content`（**公开**） |
| 源路径 | `内容治理知识库/skills-打包/安装位-27个成员/` |
| 提取时的远端 `main` | `d94ac69f7dce09f508a41de6db13da2bdb62cc83` |
| 提取日期 | 2026-10-17 |

★ **本地仓库里没有 `内容治理知识库/` 这棵树** —— 它在远端才有，本地工作区从未存在过。
所以这一份**不是在本地仓库里找到的，是从远端取的**。取法（可复现）：

```bash
rm -rf /tmp/skillpull && mkdir -p /tmp/skillpull
git clone --depth=1 --filter=blob:none --sparse \
    https://github.com/zjgulai/audit_multi_content.git /tmp/skillpull/repo
cd /tmp/skillpull/repo
git sparse-checkout set "内容治理知识库/skills-打包"
```

### 为什么取「安装位」而不是另外两个来源

那份打包件的 README（`内容治理知识库/skills-打包/README.md`）写明了三处来源同名不同物，**别搞混**：

| 来源目录 | 是什么 | 权威性 |
|---|---|---|
| **安装位-27个成员/**（← **本份取的是这个**） | `~/.dsh/skills/` 下的**实际安装副本** | **运行时真正被加载的就是这份** |
| 库内源-l7skills/ | 库内 `kb/l7/skills/`（含 `-fix` 修复副本） | 其中 9 个是安装位软链的真身 |
| 登记源-中文专项-登记表所指/ | `~/Desktop/skill/内容治理中文skill/`（登记表里的 `source`） | 13 个中文专项的登记源 |

安装位那份是**解引用后的真内容**（`cp -RL` 过的），所以它**自足**：27 个成员都有 `SKILL.md`、
无软链残留、无内嵌 `.git`。这三点是实测的，不是照抄 —— 复现：

```bash
find skill -type l | wc -l            # 0   软链残留
find skill -name .git | wc -l         # 0   内嵌 git 仓库
ls skill/*/SKILL.md | wc -l           # 27  每个成员都有
```

## 三、搬过来时的验收（逐字节，不是抽检）

**154 个文件逐个等于 git 对象里的字节**，不是「复制成功」四个字：

```bash
python3 - <<'PY'
import os, subprocess
REPO='/tmp/skillpull/repo'; BASE='内容治理知识库/skills-打包/安装位-27个成员'
raw = subprocess.run(['git','-C',REPO,'ls-tree','-r','-z','--name-only',f'HEAD:{BASE}'],
                     capture_output=True).stdout
bad = miss = 0
for nb in [n for n in raw.split(b'\0') if n]:
    n = nb.decode()
    blob = subprocess.run(['git','-C',REPO,'cat-file','-p',f'HEAD:{BASE}/{n}'],
                          capture_output=True).stdout
    p = os.path.join('skill', n)
    if not os.path.exists(p): miss += 1
    elif open(p,'rb').read() != blob: bad += 1
print('缺失', miss, '不符', bad)   # 缺失 0 · 不符 0
PY
```

### 一处会骗人的读数，记在这里（本仓的 +4096 填充态）

`skill/视频安全审查/使用前必读.txt` 在**源侧**的 `stat` 报 **5638** 字节，而实际内容只有
**1542** 字节 —— 差的**正好 4096**。这**不是**内容损坏，是本仓
`AGENTS.md` §2.1 记过的那种「**视图不一致**」：`stat` 在撒谎，读出来的字节是对的。
`cp` 按内容复制，所以**副本是对的**（1542 字节、sha256 与 git blob 相同）。

> 教训（下次别踩）：**校验这一份别用 `du` / `stat` / `wc -c` 对总数** —— 源侧的填充会让
> 「源 829927 字节 vs 目标 825831 字节」看起来像是丢了 4 KB，而实际上一个字节没丢。
> 判据要**比内容**（sha256 / 逐字节），不要比 `stat` 报的大小。

## 四、这一份**不含**什么（照实写）

- **不含** `root-skills-*`（skill 评测家族）与 `lark-*`（宿主工具）—— 它们不是知识库成员。
- **不含**另外两处来源（`库内源-l7skills`、`登记源-中文专项`）。本份只取安装位那一处；
  三处的差异见上面第二节。
- **含** 4 个带备份后缀/提案后缀的文件，**原样带过来、未清理**（它们是打包件的一部分）：
  `kb-media-extractor/SKILL.md.bak-pre-asr-20261009` ·
  `kb-media-extractor/references/capability-matrix.md.bak-pre-asr-20261009` ·
  `.../capability-matrix.md.bak-pre-videokf-20261008` ·
  `kb-l0-feishu/references/gotchas.proposals.md`

### 两处已知的、不属于本份的问题

1. **成员数是 27 还是 26，本仓两处对不上。** 打包件 README 自己写着：仓内 `AGENTS.md` 说
   「26 个 skill（14 个 `kb-*`/`brand-*` ＋ **12** 个中文专项）」，而登记表
   `kb/l7/registry/routes.yaml` 的 `dir_name_map` 实测是 **13** 条映射。本份按**登记表实测的
   27 个**取，这个出入**没有被我改掉** —— 改 `AGENTS.md` 需要 Owner 定哪个数才对。
2. **一个凭据形态的默认值**（照实记，不藏）：`kb-l0-feishu/scripts/preflight.sh:18` 里
   `KB_BASE_TOKEN="${KB_BASE_TOKEN:-GnRZbIuXraCzf0sGr2UcmZ62nfc}"` —— 一个飞书 Base token 的
   硬编码默认值。它**本来就在公开远端仓库里**（不是本次提取新暴露的），
   但既然搬进了一份会被读的文件夹，这里点名一次：**真要用它，先确认这个 token 的有效范围与
   是否该轮换**。本仓 `AGENTS.md` §2.6 第 3 条（凭据文件一律不许读）管的是读凭据文件，
   这一条是**值被写进了源码**，是另一件事，留给 Owner 判。

## 五、这份 skill 家族怎么用

27 个成员**分两层**（登记表 `kb/l7/registry/skills.yaml` 的口径）：

| 层 | 成员 | 是什么 |
|---|---|---|
| 工具层（14 个） | `kb-*`（13）+ `brand-product-fact-curator` | 知识库 L0–L7 各层的入口：抽取、切分、蒸馏、召回、体检、修复、编排 |
| 审查层（13 个） | 中文专项：`内容审查总控` · `送审登记` · `文案合规审查` · `图片安全审查` · `视频安全审查` · `美国本地化审查` · `产品宣称核验` · `证据源维护` · `审查裁决` · `审查报告与记忆` · `审查流程评测` · `飞书审查流转` · `AI溯源与权利审查` | 面向业务的发布前审查 |

**入口是 `内容审查总控`** —— 它串起送审、各专项检查、裁决与报告。
`kb-review` 是评审链入口（三态 PASS / REVIEW / BLOCK）。

⚠️ **安装位是 `~/.dsh/skills/`，不是本目录。** 本目录是**提取件**，供阅读与归档；
运行时加载的仍是 `~/.dsh/skills/` 下那份。中文 skill 名要靠
`dsh-chinese-skill-patch` 才能用 `/` 调用（`视频安全审查/vendor/` 下带着这个补丁）。

---

## 六、另外 2 个：从 SI-Agent 取来的**视频证据层**（2026-10-17 加入）

上面 27 个来自 Momcozy 知识库；这 2 个来自**另一个仓**，来源与形态都不同，单独一节写。
**上面 §一 到 §五 的 27 个读数不含这 2 个** —— 本节自成一段。

| | |
|---|---|
| 源仓库 | `github.com/zjgulai/SI-Agent`（**私有**，匿名 API 看不到，要走 SSH） |
| 源路径 | `skills/video-deep-parse/` · `skills/video-evidence-audit/` |
| 取时的远端 `main` | `fd4b2c5d` |
| 加入日期 | 2026-10-17 |

取法（可复现）：

```bash
rm -rf /tmp/siagent && mkdir -p /tmp/siagent
git clone --depth=1 --filter=blob:none --sparse \
    git@github.com:zjgulai/SI-Agent.git /tmp/siagent/repo
cd /tmp/siagent/repo && git sparse-checkout set skills
```

### 为什么取这两个（SI-Agent 的 8 个 skill 里只取 2 个）

SI-Agent 的 `skills/` 下有 8 个，其中 **6 个是爆款 / 增长分析**（`viral-*`、`matched-control-*`、
`controlled-vocab-*`、`video-comment-*`、`video-trend-*`、`video-viral-*`）——
它们的阈值绑死在 SI 自己的 PRD V3.0 上，**与内容审核无关**，取过来只会变成噪音。

取的是**证据层那 2 个**，理由具体：

| skill | 补的是本仓哪个缺口 |
|---|---|
| `video-deep-parse` | 本仓 `视频安全审查` / `图片安全审查` **以转写/OCR/关键帧为证据，但没有结构化证据层** —— 它产出 claim 对象，每条 claim 的证据指向可解析的 ref（`frame:`/`ocr:`/`asr:`/`audio:`） |
| `video-evidence-audit` | 本仓**没有对抗式证据审计** —— 它的姿态是「**只否定与追问，不产出新结论**」，与本仓 `AGENTS.md` §2.4.1「否定结论的输入必须是所有通道都采过且自证活着」同源，而本仓此前没把它落到媒体证据上 |

### ⚠️ 适配是必做步骤，不是可选项

这两个 SKILL.md 正文里引用 SI-Agent 自己的文件（`tools/social/analysis_v2|v3/*.py`、
`contract.py:46-49` 等），**本仓没有这些文件**。它们有两类，必须分开看：

- **测量留痕**（「这条规矩是从哪段代码量出来的」）—— 保留，但要标明「本仓没有」；
- **生产线**（「ref 由哪个脚本产出」）—— **必须重新接到本仓引擎上**，否则技能会要求
  一个我们产不出来的东西（正是 `AGENTS.md` §2.4.1 那个坑）。

**接线表：[`video-deep-parse/references/wiring-本仓引擎.md`](video-deep-parse/references/wiring-本仓引擎.md)**
—— 逐通道对照本仓引擎，并如实标出接不上的那几路。其中最要紧的一条：

> **本仓 ASR 产出「整段文本、无逐句时间码」，所以今天产不出 `asr:` 的毫秒区间 ref。**
> 涉及口播的 claim **不许写区间 ref**；需要「精确到哪一秒说了什么」的结论**今天答不了**。
> 反过来，**画面那半（`frame:` / `ocr:`）是完整的**，SI 这套语法对画面证据**立刻可用**。
> 残缺的只是声音那半 —— 「半条能用」与「整条不能用」是两件事。

### 与 27 个知识库成员的关系

这 2 个是**证据层**，不是审查入口 —— 它们**不替代** `内容审查总控` / `视频安全审查` /
`图片安全审查`，只产出「可被第三方逐行核验的 claim」及其审计结论。
判定与裁决仍在审查层那 13 个成员里。

### 安全扫描（加入前做的）

无密钥 / JWT / `sk-` / `ghp_` / AKIA 形态，无 `open_id` / `chat_id`；
唯一的绝对路径是 `/Users/lute`（家目录）。
