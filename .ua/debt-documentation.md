# 文档债审计 · audit_multi_content

> **性质**：只读审计。本次未修改、删除或「修复」仓库内任何文件；所有脚手架写在 `/tmp`。
> **审计对象**：`/Users/lute/Project/audit_multi_content`，工作区版本（`git rev-parse --short HEAD` = `243c6bf`，
> 但 `git status` 显示 6 个已跟踪文件被改动、`AGENTS.md` 在本轮审计期间被**连续改了三次**，见 §四）。
> **语料**：455 个被分析文件中的 **228 个 `docs` 类**（`.md` 225 + `.txt` 3），**81,581 行 / 6.80 MB**。
> 复现：`python3 -c "import json;[print(len([f for f in json.load(open('.ua/intermediate/scan-result.json'))['files'] if f['fileCategory']=='docs']))]"`
> **口径**：`git ls-files` 计数；忽略 `skills/`、`.venv-r4/`、`.pylibs/`、`.vendor/`、`node_modules/`、`.ua/`、`research/repos/`。

**headline：228 份文档里，从 `README.md` + `AGENTS.md` 出发有 142 份走不到（宽松口径），严格只沿文档互链则有 179 份走不到；而 `README.md` 本身只有 2 行、零链接。**

---

## 一 · 没有权威入口

### 【D1-01】`README.md` 是 35 字节、2 行、**零链接** —— 它独自只能到达它自己

**证据**：
```bash
wc -c README.md && wc -l README.md && od -c README.md
#   35 README.md
#    2 README.md
#    #   a u d i t _ m u l t i _ c o n t e n t \n 内 ** 容 ** 审 ** 计 ** \n
```
正文全文 = `# audit_multi_content` + `内容审计`。用与 §一 其余条目同一个链接抽取器（markdown 链接正则 `\[[^\]]*\]\(([^)\s]+?)\)` + 反引号路径 `^[\w./\-一-龥@+]+\.(md|py|mjs|…)$`）扫 `README.md`，得到**空集**。

**影响**：这是 228 份文档、6.80 MB 语料唯一被所有人和所有工具默认读的文件。它不指向任何东西 = 整个仓库没有门牌。工具（包括本轮用的 `.ua` 图谱）只能靠遍历目录，而不是靠作者声明的重要性排序。

**建议动作**：给 `README.md` 一页 15 行导航：宪法（`AGENTS.md`）、决策台账（`ADR/README.md`）、上游权威源（`PRD/feishu/README.md`）、事故记录（`PMO/`）、四个自证入口。

---

### 【D1-02】★ headline：**142 / 228 份文档从 `README.md` ∪ `AGENTS.md` 都走不到**

**证据（一条命令算完，两种口径都给）**：
```bash
python3 - <<'PY'
import json,os,re,collections,subprocess
os.chdir('/Users/lute/Project/audit_multi_content')
scan=json.load(open('.ua/intermediate/scan-result.json'))
DOCS=sorted(f['path'] for f in scan['files'] if f['fileCategory']=='docs'); DOCSET=set(DOCS)
tracked=set(t for t in subprocess.run(['git','-c','core.quotepath=false','ls-files'],
             capture_output=True,text=True).stdout.split('\n') if t)
allf=set()
for root,dirs,files in os.walk('.'):
    dirs[:]=[d for d in dirs if d not in ('.git','node_modules','.venv-r4','.pylibs','.vendor','.ua','skills','research/repos')]
    for f in files: allf.add(os.path.normpath(os.path.join(root,f)).lstrip('./'))
uni=tracked|allf
base=collections.defaultdict(set)
for p in uni: base[os.path.basename(p)].add(p)
MD=re.compile(r'\[[^\]]*\]\(([^)\s]+?)\)'); TICK=re.compile(r'`([^`\n]+)`')
PATHY=re.compile(r'^[\w./\-\u4e00-\u9fff@+]+\.(md|py|mjs|js|json|sh|yaml|yml|plist|txt|csv|tsv|html|xml|bin|bak)$')
def norm(p):
    p=p.strip().split('#')[0].split('?')[0]
    while p.startswith('./'): p=p[2:]
    return p
def refs(path):
    raw=open(path,encoding='utf-8',errors='replace').read(); out=set()
    for m in MD.finditer(raw):
        t=norm(m.group(1))
        if not t.startswith(('http','mailto:')): out.add(t)
    for m in TICK.finditer(raw):
        t=norm(m.group(1))
        if not t.startswith('http') and PATHY.match(t): out.add(t)
    return out
def resolve(src,t):
    c=[]
    c.append(t.lstrip('/') if t.startswith('/') else os.path.normpath(os.path.join(os.path.dirname(src),t)))
    c.append(os.path.normpath(t))
    b=base.get(os.path.basename(t))                       # 宽松：唯一同名文件也算命中
    if b and len(b)==1: c.extend(b)
    return [x for x in dict.fromkeys(c) if x in uni]
def bfs(seeds, docs_only):
    seen={s:None for s in seeds}; q=collections.deque(seeds)
    while q:
        cur=q.popleft()
        for t in refs(cur):
            for r in resolve(cur,t):
                if docs_only and r not in DOCSET and r not in ('README.md','AGENTS.md'): continue
                if r not in seen: seen[r]=cur; q.append(r)
    return seen
for lab,seeds in (('README.md 独自',['README.md']),('AGENTS.md 独自',['AGENTS.md']),('两者并起',['README.md','AGENTS.md'])):
    for mode,do in (('宽松(可经代码文件跳转)',False),('严格(只沿文档互链)',True)):
        s=bfs(seeds,do); n=len(DOCSET&set(s))
        print(f'{lab:>14} | {mode} | 可达 doc={n:>3} | 不可达={228-n:>3}')
PY
```
**读数**：

| 起点 | 宽松（可经 `.mjs`/`.py` 等被引文件再跳） | 严格（只沿文档互链） |
|---|---|---|
| `README.md` 独自 | 可达 **1** / 不可达 **227** | 可达 **1** / 不可达 **227** |
| `AGENTS.md` 独自 | 可达 **86** / 不可达 **142** | 可达 **49** / 不可达 **179** |
| 两者并起 | 可达 **86** / 不可达 **142** | 可达 **49** / 不可达 **179** |

两个数字都对，取决于「走得到」怎么定义：**142 是乐观上限**（允许顺着 `AGENTS.md` 里 `tools/verify_cards.mjs` 这种反引号路径跳进代码、再从代码的注释里跳到别的文档）；**179 是新人视角**（只点文档里的链接）。`README.md` 对两个数字都没有贡献。

**影响**：`AGENTS.md` 全文 622 行、43 KB，是本项目真正的门牌；但它只**直接点名 4 份文档**（见 D1-03）。62%–78% 的文档没有任何入口路径 —— 包括 `ADR/` 14 份决策里除索引外的全部、`PMO/` 9 份事故记录里的 5 份、`PRD/` 4 份里的 2 份。

**建议动作**：在 `AGENTS.md` 顶部加一个「本仓库的文档地图」小节，或在 `README.md` 里按目录列 8–12 条入口。不要求逐份可达，只要求「每个目录至少有一条路径 + 一份目录内的索引」。

---

### 【D1-03】`AGENTS.md` 只直接点名 **5** 份文档（+1 个占位符），且都不是索引类 —— 而这个数**在本轮审计期间从 4 变成了 5**

**证据（读的是当前版本 `md5 = 2c23b14e2d26a82ba6f8f3e2963fba8c`、622 行、42,364 B）**：
```bash
python3 -c "
import re
raw=open('AGENTS.md',encoding='utf-8').read()
print(sorted(set(re.findall(r'\`([^\`\n]+\.md)\`', raw))))"
# ['AGENTS.md', 'PMO/守衡-链路打通确认.md', 'PRD/feishu/README.md',
#  'PRD/feishu/内容审查Agent-PRD-v1.0.md', 'agent-skills/<名字>/SKILL.md',   ← 占位模板，不是真实路径
#  'skills/内容合规审查/SKILL.md', 'tools/reply-cards/contract.md']
grep -n "ADR/README\|PMO/守衡-\|PRD/feishu/README" AGENTS.md    # 只命中 PRD/feishu/README（:110 的散文）
grep -rn "](\./README\.md)\|](README\.md)" --include=*.md . | grep -v node_modules | grep -v '\.ua/'   # rc=1 —— 没有任何文档链接到仓库根 README
```
**去重后的真实文档 = 5 份**：`PMO/守衡-链路打通确认.md` · `PRD/feishu/README.md` · `PRD/feishu/内容审查Agent-PRD-v1.0.md` · `skills/内容合规审查/SKILL.md` · `tools/reply-cards/contract.md`（另加 `AGENTS.md` 自身）。

> ★ **同一个命令在本轮审计开始时给出 4 份**（没有 `PRD/feishu/README.md`）。`AGENTS.md` 在审计期间被连续改写（见 D4-01），这个数字随之漂移 —— **这就是「用可复现命令给出的读数」应有的样子：它会动，而且动的时候你知道。** 对比 D2-08 那个「29 项」（代码里根本没有这个数），差别在这里。

**另一个读数**：`PMO/守衡-架构说明.md` 之所以进入可达集，路径是 `AGENTS.md → tools/reply-cards/contract.md →（正文引用）→ PMO/守衡-架构说明.md`，即靠**下游文档**才被捞回来。

**影响**：`ADR/README.md`（决策台账 + 决策地图）这份全仓信息密度最高的索引，从两个入口都走不到；新人拿不到「这个项目决定过什么」。

**建议动作**：`AGENTS.md` §2.1 自证表里每一行的 `verify_*` 命令后面，挂上「它读的那份文档」的相对路径；并把 `ADR/README.md` 直接写进 §2.1 上方。

---

### 【D1-04】文档互引本身极稀疏：**77 份零入边 / 113 份零出边 / 44 份两头皆零**

**证据**：把 228 份 `docs` 当作节点、只看**文档 → 文档**的引用（markdown 链接 + 反引号 `.md` 路径），命令与上一条同源（见 `/tmp/docgraph.json`）：
```bash
# 同一脚本的度数部分：对 228 份文档两两建边后统计
#   零入边（没有任何文档引用它）        : 77
#   零出边（它不引用任何文档）          : 113
#   既无入边也无出边                    : 44
```
被引最多的 5 份：`AGENTS.md` 24 次 · `PRD/内容治理需求文档.md` 19 · `skills-inventory/refs/ecommerce-image/…/image-quality.md` 16 · `research/star-lists-audit-report.md` 9 · `README.md` 8。

> ⚠️ **口径更正，这一条必须自己先说清楚**：`README.md` 的 8 次入边**不是导航链接**。全仓 `grep -rn "](\./README\.md)\|](README\.md)" --include=*.md .`（排除 `node_modules` 与 `.ua/`）**零命中** —— 即**没有任何一份本项目文档用链接指向仓库根的 `README.md`**。那 8 次来自我的抽取器把裸 token `` `README.md` `` 按「仓库根相对」解析的结果，而它们实际指的是**别的项目的 README**（`research/method/`、`research/repos/` 里的对照项目）。**这一条本身就是本次审计要治的病的一个样本：一个没有指出的口径，会让读数比事实大。**

**影响**：这是一个「星形 + 大量孤岛」的引用图，不是网状。孤岛里包含 `research/readmes/` 全部 10 份、`research/distill/scratch/` 全部 19 份、`skills-inventory/refs/` 26 份。

**建议动作**：为每个目录补一份 `README.md` 索引；`research/readmes/` 与 `distill/scratch/` 这类明确的过程产物，把「这是过程产物、不是结论」写进目录名或目录内 README。

---

## 二 · 权威歧义：哪份文档说了算

### 【D2-01】`AGENTS.md` / `ADR` / `PRD` / `PMO` 四方**没有任何一处**写出优先级

**证据**：
```bash
grep -rn "唯一权威\|权威源\|以.*为准\|优先级\|冲突时" ADR/README.md PRD/*.md PRD/feishu/*.md | head
```
命中的全部是**局部**规则，没有一条是跨层的：
- `ADR/README.md:5-14` 只写 ADR **之间**的规则（新决策新建、`supersedes`、6 种状态）；
- `PRD/feishu/README.md:36-43` 只写「飞书是权威、本地是只读投影」；
- `PMO/` 13 份里没有一句声明它与 ADR / AGENTS 的关系；
- `agent-skills/守衡语域/SKILL.md:10` 只说「卡片格式在 `contract.md`」，不说冲突时谁赢；
- 唯一一次跨权威的裁定是**散文**：`PRD/PRD差异对照-20260921.md:16` 逐字引上游原话「PRD 以《内容审查 Agent PRD》为准」。

**影响**：本项目的所有规则（上限、语域、红线、状态）都靠「引哪一份」来定，而没有一份说「引错了怎么办」。本轮已抓到 4 处实际冲突（D2-05 / D2-06 / D2-07 / D2-08），全部只能靠人工交叉阅读发现。

**建议动作**：在 `AGENTS.md` 顶部（或 `README.md`）加一张 5 行的权威序列表：`上游 PRD > ADR > AGENTS.md > 目录内 README > 散文记录`，并声明「同一层冲突时以带日期的读数较新者为准」。

---

### 【D2-02】`cards.mjs` 顶部注释说「10 类」，同一文件里 `BUILDERS` 有 **11** 个键

**证据**：
```bash
sed -n '2p' tools/reply-cards/cards.mjs
#  * cards.mjs —— 守衡的群回复卡片模版（10 类）
grep -n "export const BUILDERS = {" tools/reply-cards/cards.mjs      # :400
node -e "import('./tools/reply-cards/cards.mjs').then(m=>{
  console.log('BUILDERS', Object.keys(m.BUILDERS).length);
  console.log('TONE    ', Object.keys(m.TONE).length);})"
# BUILDERS 11
# TONE     10
```
三份文档都说十一个：`tools/reply-cards/contract.md:93`「## 三 · 十一个类型」、`PMO/守衡-回复卡片模版与语域规程.md:64`「### 3.1 十一个卡片类型」、`agent-skills/守衡语域/SKILL.md:160`「十一个类型：…」。

**影响**：`cards.mjs` 是这张契约的**唯一实现**，也是新人第一眼读的文件。注释里的「10 类」会让人以为 `data-table` 不存在 —— 而 `data-table` 正是实测收益最大的一张卡（模块头注释自己写着「守衡 42% 的回复含数据表」）。`TONE` 只有 10 个键是因为 `dataTable()` 借用了 `TONE['query-answer']`（`cards.mjs:189`），这个「11 类 / 10 色」的双口径**没有任何一处文档说明**。

**建议动作**：改 `cards.mjs:2` 为「11 类」；在 `TONE` 上方加一行注释说明「`data-table` 与 `query-answer` 同色，故本表 10 项」。

---

### 【D2-03】★ `MAX_SECTIONS = 3` 是唯一「文档里没有、代码里有」的上限 —— 而 §2.4 点名的那个病**只补掉了 2/3**

**证据**：
```bash
grep -rn "MAX_SECTIONS" --include=*.mjs --include=*.js --include=*.py . | grep -v node_modules
# tools/reply-cards/cards.mjs:74:export const MAX_SECTIONS = 3;
# tools/reply-cards/envelope.mjs:28:  BUILDERS, VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS,
# tools/reply-cards/envelope.mjs:387:export const ENFORCED = { VERDICT_MAX, BOUNDARY_MAX, MAX_SECTIONS, … };
# tools/reply-cards/registry.mjs:16 / :499（转口）
# tools/verify_cards.mjs:297（断言）
grep -n "MAX_SECTIONS" tools/reply-cards/envelope.mjs | grep -v "^16:\|^28:\|^387:"   # → 空
grep -rn "最多 3 段\|≤3 段\|段落数上限" --include=*.md . | grep -v node_modules | grep -v '\.ua/'   # → 空
```
即：`MAX_SECTIONS` **定义在 `cards.mjs:74`，被 `envelope.mjs` import（:28）并转进 `ENFORCED`（:387），但整个仓库没有任何一行拿它做比较**。而 J1 的判据是：
```bash
sed -n '297,299p' tools/verify_cards.mjs
#   for (const k of ['VERDICT_MAX', 'BOUNDARY_MAX', 'MAX_SECTIONS']) {
#     if (!new RegExp(`\\b${k}\\b`).test(envSrc)) no(...);
#     else ok(`J1 ${k} 在 envelope.mjs 里被使用`);
```
**`import` 行本身就足以让 J1 变绿** —— J1 证明的是「这个名字在文件里出现过」，不是「这个上限在拦人」。
`AGENTS.md:295-299`（§2.4）正是拿这三个常量讲这个病，`tools/reply-cards/contract.md:293` 也写着「上限此前没有执行点 …… 现在有执行点了」。**第三个仍是一句注释。**

**影响**：这正是 `AGENTS.md` §2.4 那句「写进文档的每一个上限，必须能指出是哪一行代码在拦它」的反面 —— 一个**在代码里定义、却不在任何文档里出现的上限**。守衡可以合法地写超过 3 段正文，而 `contract.md` 与 `SKILL.md` 都不知情。同时 J1 是「会误报的检查器」的又一例（§2.1.1 的教训）：它绿着，遮盖了缺口。

**建议动作**：要么给 `MAX_SECTIONS` 补一行真实比较（`enforceLimits` 里按段数搬迁），要么删掉这个常量；并把 J1 的判据从「名字出现过」改成「名字出现在一次比较里」。

---

### 【D2-04】`≤60 字` / `≤90 字` 被**手抄在 5 处活体规范**里，无一致性断言

**证据**：
```bash
grep -rn "≤60 字\|不超过 60 个字符\|VERDICT_MAX = 60" --include=*.md --include=*.mjs tools/ PMO/ agent-skills/ AGENTS.md | grep -v node_modules
grep -rn "≤90 字\|不超过 90 个字符\|BOUNDARY_MAX = 90" --include=*.md --include=*.mjs tools/ PMO/ agent-skills/ AGENTS.md | grep -v node_modules
```
活体规范副本（不含叙述性回顾）：

| 数值 | 定义处 | 手抄副本 |
|---|---|---|
| 结论 ≤60 字 | `cards.mjs:70` | `registry.mjs:161` · `contract.md:29,105,239,286` · `PMO/守衡-回复卡片模版与语域规程.md:91` · `tools/agent/persona.mjs:108`（写进模型提示词的那一份） |
| 边界 ≤90 字 | `cards.mjs:72` | `registry.mjs:165` · `contract.md:30,239,287` · `PMO/…语域规程.md:92` · `tools/agent/persona.mjs:113` |

另加 `envelope.mjs:13,18` · `verify_cards.mjs:295,396,397` · `reply-cards/README.md:21` 的叙述性复述，合计 **9 个文件**。

**当前四处数值一致**（用 `node tools/verify_cards.mjs` 的 J1 + 手工比对 60/90 全部对上），所以这是**可漂移隐患，不是已发生的矛盾** —— 但 `persona.mjs` 那一份是**写进模型提示词的字符串字面量**（`persona.mjs:108` 写「不超过 60 个字符」，不是 `VERDICT_MAX` 插值），改常量不会改提示词。

**影响**：`AGENTS.md` §2.4 说的「上限必须有执行点」解决的是**有没有**执行点，没解决**多处副本**。今天改 `VERDICT_MAX = 80`，模型还会被告知 60。

**建议动作**：`persona.mjs` 的 `cardContract()` 改成从 `cards.mjs` 插值（`` `不超过 ${VERDICT_MAX} 个字符` ``）；`contract.md` 的数值处改用同一来源生成或加一条 `verify_cards` 断言。

---

### 【D2-05】★ `agent-skills/守衡语域/SKILL.md` 与 `PMO/…语域规程.md` **对同一件事给出相反结论**

**证据**：

| 说法 | 出处 | 原文 |
|---|---|---|
| 「三条硬约束**尚未写进** `persona.mjs` —— 守衡现在的提示词里没有它们」 | `agent-skills/守衡语域/SKILL.md:182` | 见文件 |
| 「卡片发送路径 **❌ 未接入**。守衡仍走 `replyMarkdown`（纯文本）」 | `agent-skills/守衡语域/SKILL.md:183` | 见文件 |
| 「三条硬约束写进 `persona.mjs` \| ✅ **已写**（`cardContract()`，清单由 registry 现算）」 | `PMO/守衡-回复卡片模版与语域规程.md:235` | 见文件 |
| 「接进 `ws_daemon.mjs` 的发送路径 \| ✅ **已接入**（`toCardOrText` + 单一降级点）」 | `PMO/守衡-回复卡片模版与语域规程.md:234` | 见文件 |

**代码裁决 —— PMO 说的是对的，`SKILL.md` 是错的**：
```bash
grep -n "toCardOrText" tools/ws_daemon.mjs
# 26:import { toCardOrText } from './reply-cards/envelope.mjs';
# 96:  // 决策本身在 reply-cards/envelope.mjs 里，这里只负责记录 ———
# 106:  const sent = await replyTo(chatId, msg.message_id, shaped.text, shaped.card ?? null);
grep -n "cardContract\|功能\|结论先行" tools/agent/persona.mjs | head
# 39:   用中文。简洁、具体、可核对。结论先行。
# 81:export function cardContract() {
# 138:  return `${SYSTEM_PROMPT}\n\n${cardContract()}\n\n# 当前时间\n…`;
```
`persona.mjs:81-135` 的 `cardContract()` 逐条写着「结论字段（`verdict`）…… **不超过 60 个字符**」（:108）、「边界字段（`boundary`）只写一行，**不超过 90 个字符**」（:113）、「内部记录…… **只能进折叠区的字段**」（:115）—— 就是 SKILL.md 说的「三条硬约束」。

**影响**：这两份是**同一份规程的两个正本**，而 `AGENTS.md:39`（§2.1 自证表）点名的、`verify_cards.mjs` E 段断言的、以及**被 `AGENTS.md` 直接引用的**是 `SKILL.md` 这一份。E 段只断言「类型名在 registry / contract.md / SKILL.md 三处一致」，不断言「§六 的边界声明表是否仍成立」—— 于是这张错表绿着。

**建议动作**：`SKILL.md` §六 的「卡片发送路径」「三条硬约束」两行改成带日期的重测读数，或直接删除该表（它的内容已由 `PMO/…语域规程.md` §六 承担）；并给 `verify_cards.mjs` 加一条断言：`SKILL.md` 里不许出现「未接入」这类状态词，或要求它带日期。

---

### 【D2-06】`ADR/README.md` 的决策台账把 2 份 ADR 的状态记反了（14 份里 2 份 = 14%）

**证据**：
```bash
python3 - <<'PY'
import re,glob,os
os.chdir('/Users/lute/Project/audit_multi_content')
idx={}
for i,l in enumerate(open('ADR/README.md',encoding='utf-8').read().split('\n'),1):
    m=re.search(r'\[(ADR-\d{4})\]\(\./([^)]+)\)',l)
    if m: idx[m.group(1)]=(re.findall(r'`(accepted|proposed|superseded|rejected)`',l) or ['?'])[0], i
for f in sorted(glob.glob('ADR/ADR-*.md')):
    k=os.path.basename(f)[:8]
    for i,l in enumerate(open(f,encoding='utf-8').read().split('\n'),1):
        if l.strip().startswith('- 状态'):
            st=(re.findall(r'`(accepted|proposed|superseded|rejected)`',l) or ['?'])[0]
            mark='❌' if idx[k][0]!=st else '✅'
            print(f'{mark} {k}: 索引={idx[k][0]}(README.md:{idx[k][1]})  正文={st}({f}:{i})')
            break
PY
```
**读数**：
```
❌ ADR-0001: 索引=accepted(README.md:21)  正文=proposed(ADR/ADR-0001-数据权威与双账本.md:3)
❌ ADR-0012: 索引=accepted(README.md:32)  正文=proposed(ADR/ADR-0012-判定引擎产品化与处置分层.md:3)
✅ 其余 12 份一致
```

**影响**：`ADR/README.md:5-14` 的规则 2 和规则 6 把「状态」定为这套台账的全部功能。ADR-0001 是「飞书为操作账本、本地为分析账本」，ADR-0012 是「判定引擎产品化 + 处置五层」—— 这两条是**引用次数最多**的两条（`AGENTS.md`、`PRD/feishu/README.md`、`base/` 都在引）。读者按索引会以为它们已决，按正文会以为待决。

**建议动作**：以 ADR 正文为准回填索引；或反过来，把两份正文的状态改成 `accepted` 并补一句裁定日期。无论哪个方向，加一条断言：索引状态 ≡ 正文状态。

---

### 【D2-07】`ADR/README.md` 自己在同一份文件里把 ADR-0012 说成「五层」又说成「四层」

**证据**：
```bash
grep -n "处置四层\|处置五层" ADR/README.md ADR/ADR-0012-判定引擎产品化与处置分层.md
# ADR/README.md:32:| [ADR-0012](…) | 判定引擎产品化：稳定契约…· 处置**五层**映射（DP0–DP4，原名 L1–L4）…
# ADR/README.md:56:    Q3 … -> A12["ADR-0012 引擎产品化<br/>稳定契约 + 处置四层 + 回执"]
# ADR/ADR-0012-…md:64:   ★ **2026-09-16 修正两处**（D5 / D8）：层级由 4 个变为 **5 个**（新增 `DP0 不可判`）
# ADR/ADR-0012-…md:205:**五层**（2026-09-16 · D8 把 ID 从 `L1–L4` 改为 `DP1–DP4` 并新增 `DP0`）
```
**影响**：`README.md:56` 是 mermaid 决策地图里的一个节点 —— 决策地图是「哪条决策触发/修正了哪条」的唯一可视化，正是给人快速建立心智模型用的。它比正文更早被读到，也更容易被记住。

**建议动作**：改 `README.md:56` 的节点文字为「处置五层 DP0–DP4」。顺带：这张 mermaid 图的节点文字是唯一没有量读校验的地方，可考虑抽成表由脚本渲染。

---

### 【D2-08】★ `AGENTS.md:40` 的「可达清单完整（**29 项**）」在代码里**不存在**

**证据**：
```bash
grep -rn "29" tools/verify_feishu_index.py tools/feishu_index.py
# tools/feishu_index.py:239:RATE_LIMIT_CODES = {99991400, 99991401, 429}     ← 唯一命中，与可达清单无关
grep -n "可达清单" tools/verify_feishu_index.py
# 200:    clist = os.path.join(REPO, "research", "feishu", "可达清单.md")
# 206:        ck("E", "E7 本租户 25 条**每一条**都进了可达清单", not miss,
head -1 research/feishu/可达清单.md
# # 守衡 · 飞书可达清单（**25 条**）
```
即：**代码断言 25，产物自称 25，宪法写 29。**

**影响**：`AGENTS.md:34-46` 那张表是「每个子系统的自证入口」—— 它这一格的第三列本来就是在告诉读者「这个命令会替你验什么、验多少条」。读者拿着 29 去对报告里的 34 项/25 条，对不上；更糟的是会去怀疑**产物**错了而不是**文档**错了（这个仓库明文记录过这种误判，§2.4.1 第 5 行）。

**建议动作**：改成「可达清单完整（本租户 25 条每条都在）」，或干脆去掉数字，只留 `verify_feishu_index.py` 的 **E7**。

---

### 【D2-09】`AGENTS.md` 对同一条命令给出两个不同的项数（23 vs 18）

**证据**：
```bash
grep -n "23 项\|18 项" AGENTS.md
# 41:| 责任人 → 投递地址 | `python3 tools/lark_people.py --controls` | 23 项离线反向对照：…
# 319:  … + `--controls` 的 18 项离线反向对照 |
python3 tools/lark_people.py --controls | tail -1
# ✅ 全部 23 项通过
```
¶41 对、¶319 错。同段里另外两个自证项数**都能复现**：`node tools/agent/prd_baseline.mjs --selftest` → `✅ 38 项全过`（¶43、¶392 都写 38 ✅）；`python3 tools/verify_pending.py --controls` → `✅ 32 项全过`（¶44、¶450 都写 32 ✅）。

**影响**：¶319 是 §2.4.1 的第 4 行 —— 讲「否定结论必须有全通道阳性对照」那一条。数字小 5 会让读者低估这条判据的覆盖面，而这正是本项目最贵的一课。

**建议动作**：改 ¶319 的 18 → 23。

---

### 【D2-10】语域/卡片规范「同一句话」被写在 4 份文档 + 2 份代码里，且已漂移

**证据**（逐字重复与近似重复）：

| 规范 | 副本 | 是否已漂移 |
|---|---|---|
| 「模型不写卡片 JSON，只写一个卡片块」 | `tools/reply-cards/contract.md:255` · `PMO/…语域规程.md:150` · `AGENTS.md:184` · `PMO/守衡-回话草稿-M12…:18` | 未漂移 |
| 「守住引用比守住卡片重要」 | `contract.md:318` ≡ `PMO/…语域规程.md:221`（逐字） | 未漂移 |
| 降级链图 | `contract.md:313-314` ≡ `PMO/…语域规程.md:216-217`（逐字） | 未漂移 |
| 十一个类型清单 | `SKILL.md:160` ≡ `PMO/…语域规程.md:75`（逐字）；`cards.mjs` 顶部；`persona.mjs:118` 现算 | **已漂移**（`cards.mjs:2` 写 10，D2-02） |
| 卡片发送路径状态 | `SKILL.md:183` vs `PMO/…语域规程.md:234` | **已漂移**（D2-05） |

行级相似度（归一化行集合交 / `difflib`，`autojunk=False`）：

| A | B | A 行 | B 行 | 共有行 | 占比 A | ratio | 最大连续块 |
|---|---|---:|---:|---:|---:|---:|---:|
| `SKILL.md` | `PMO/…语域规程.md` | 122 | 171 | 7 | 6% | 0.041 | 1 |
| `SKILL.md` | `contract.md` | 122 | 234 | 8 | 7% | 0.022 | 1 |
| `PMO/…语域规程.md` | `contract.md` | 171 | 234 | 9 | 5% | 0.064 | 5 |

**影响**：**文本相似度低（≤7%），规范重叠度高** —— 这正是最难用工具发现、又最容易静默漂移的形状。本轮已抓到 2 处实际漂移（D2-02、D2-05），全部只能靠人工跨文件对读。

**建议动作**：把「同一件事」收敛到**一个正本 + 若干指针**：卡片契约以 `tools/reply-cards/registry.mjs` 为唯一数据源（`persona.mjs` 已经这么做了，`contract.md` 与 `SKILL.md` 应改为「见 registry」）；状态类陈述（「已接入 / 未接入」）不进文档正文，改为打印自证输出。

---

### 【D2-11】★ 一份 ADR 已把「语境守卫 89 词」更正为 85，另**两份 ADR + 索引用 3 行仍写 89**

**证据（我自己复跑过）**：
```bash
python3 -c "
import json,collections
d=json.load(open('research/governance/skeleton/context-guards-v1.json'))
print('len(words):', len(d['words']))
print('stats.guards:', d['stats']['guards'], '| wired:', d['stats']['wired'], '| not_wired:', d['stats']['not_wired'])
print(collections.Counter(w.get('status') for w in d['words']))"
# len(words): 85
# stats.guards: 85 | wired: 46 | not_wired: 39
# Counter({'active': 46, 'pending': 39})

grep -rn "89 词\|85 词" --include=*.md ADR/ PMO/ research/governance/ AGENTS.md
```
**读数 —— 同一个数，两套说法共存**：

| 说法 | 位置 | 判定 |
|---|---|---|
| 「**共 89 词 = 46 + 39 + 4**」 | `ADR/ADR-0009-语境守卫独立成表.md:108` | ❌ 陈旧（4 已迁走） |
| 「语境守卫表（**89 词**，三态）」 | `ADR/ADR-0009-语境守卫独立成表.md:240` | ❌ 陈旧 |
| 「★ 语境守卫表规模 \| **89 词** = 46 已接线 + 39 待法务定性 + **4 走错通道**」 | `ADR/README.md:109` | ❌ 陈旧（决策台账！） |
| 「`context-guards-v1.json` \| 89 词（`misrouted` 4，G3 违反 4） \| **85 词（`misrouted` 0，G3 违反 0）**」 | `ADR/ADR-0012-判定引擎产品化与处置分层.md:361` | ✅ **就是那条更正**（「★ 2026-09-16 裁定：迁」） |
| 「白名单 26→30 词、守卫表 **89→85 词**」 | `research/governance/skeleton/迁移手册-机器词表.md:165` | ✅ 知道 |
| 「语境守卫 **85 词**里 39 条没接线」 | `PMO/守衡-知识库GAP分析与第一性原理决策-20260922.md:133` | ✅ 知道 |
| 「`context-guards-v1.json`（**85 词**）」 | `PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md:255,259` | ✅ 知道 |
| 「`语境守卫导入-飞书.csv` \| 89 词」 | `research/governance/skeleton/_data/deprecated/README.md:8` | ✅ 正确地标在 `deprecated/` 下 |

**影响**：这不是「没标日期」——`ADR/ADR-0012` 白纸黑字宣告了 89 已作废（迁走 4 个 misrouted 词，G3 违反 4→0），而 **`ADR-0009` 与 `ADR/README.md` 共 3 行没跟上**。`ADR/README.md:109` 尤其刺眼：那是**决策台账**，读者拿它当唯一索引。三处都在「binding decisions」这一层，而 `AGENTS.md:1-4` 说这一层「优先级高于任何单次会话里的默认行为」。

反过来看，这份仓库**有能力发现它**：`verify_feishu_index.py` 的 E1（分档之和 = 候选数）、`verify_pending.py` 的 C2/C3、`verify_cards.mjs` 的 I 段都是这个形状的断言 —— **只是没有一条覆盖 ADR 与代码之间的数字一致性**。

**建议动作**：新增一条断言（`tools/verify_adr_counts.py` 或并入 `verify_engine_contract.py`）：凡 ADR 里出现的 `<产物>.json` + 词数/条数，必须等于该 JSON 的实测规模；先只做 `whitelist-v1.json` / `context-guards-v1.json` / `rules-v1.json` 三张表（它们都有 `stats` 字段，判据现成）。同时把 `ADR-0009:108,240` 与 `ADR/README.md:109` 的 89 改成 85 并注明迁移日期。

---

## 三 · 陈旧断言：文档说的事，代码已经不做 / 从来不是那样

**抽样规模**：从 `ADR/`（15 份）、`PMO/`（13 份）、`PRD/`（7 份）、`AGENTS.md`（622 行）里抽取**可机检的断言 35 条**（「文件 X 存在 / 常量 Z 是 N / 脚本 W 在哪 / 状态是什么 / 数是多少」），逐条跑命令核对。

**结果（见下表逐个 ❌/⚠️/✅）**：

| 判定 | 条数 | 说明 |
|---|---:|---|
| ✅ 复现 / 成立 | **12** | #5 #6 #7 #12 #13 #14 #15 #16 #18 #20 #21 #25 |
| ❌ **假** | **20** | #1 #2 #3 #9 #10 #11 #17 #19 #22 #23 #26 #27 #28 #29 #30 #31 #32 #33 #34 #35 |
| ⚠️ 存疑（未标路径 / 仅作历史陈述） | **3** | #4 #8 #24 |

**假率**：去掉 3 条存疑后，**20 / 32 = 63%**。20 条 ❌ 归并为 **18 个独立缺陷**（`ADR-0008` 的文件名错写 2 行算 1 个；`ADR/README.md` 的两份状态错算 2 个；「227 项」在两份文档里算 1 个；`PMO/…语域规程.md` 的 PID 与「未重启」同源算 1 个；「89 词」在三处算 1 个）。

> 这个假率对本次抽样**偏高是设计使然** —— 抽的全是「能指得出对象」的结构性断言（路径、常量、状态、行号），这类断言本来就最容易腐烂；纯叙述性文字未计入。**不要把它读成「全部文档 63% 是错的」**，它衡量的是「一旦文档写下可核对的东西，它还站得住吗」。

**另一路独立取证（子代理，24 项点名到文件的数字复跑）**：16 项复现成功、**8 项复现失败**，且失败的全部是**过期数字或口径错位**，不是笔误：

| 文档声称 | 位置 | 实测 |
|---|---|---|
| 语境守卫 **89 词** | `ADR-0009:108,240` · `ADR/README.md:109` | **85**（见 D2-11） |
| `skeleton/rules-v1.json` **21 条** | 缺口表:26 | **26**（21 是**现网**口径，被安到骨架文件上） |
| 错题本 **143 行**（132+11） | 缺口表:24 · `research/governance/README.md:103` · `规范-审核规则库完整设计.md:1343,1430` | `errorbook.csv` **178 行** |
| R2 **3,189 行 / 311 KB** | `research/governance/README.md:58` | **3,647 行 / 365,322 B** |
| R5 **2,670 行** | 同上 :61 | **2,669**（差 1） |
| R7 shards **5,395 行**（W1 2,059） | 同上 :63 | **6,423**（W1 **3,087**） |
| R3 **213 KB** | 同上 :60 | **271,036 B** |
| 落地页URL 填充率 **0%** | `R2-adjudication-casebooks.md:1621` | **204/291 = 70.1%** |

（另有 16 项复现成功，含：规则 21 条 / 卖点边界 19 条 / 改写建议 52 条 / 白名单 active 26 / 424 个关键词 / Primary Text 232÷291=79.7% / `rules-v1.json` 26 条叶子规则 / 291 条广告 / 各证据文件行数字节数 5 项。）

**★ 这 8 项里最值钱的一条是口径错位，不是过期**：`缺口表:26` 把**现网口径**的「21 条」安到了 `research/governance/skeleton/rules-v1.json` 上 —— 而那个文件实测有 **26** 条规则。**这正是 `AGENTS.md` §2.4.1 第 2/3 行那个病的同一形状：数字是真的，被贴到了错误的载体上。**

### 三.A 逐条对照表

| # | 断言（file:line） | 核对命令 | 判定 |
|---|---|---|---|
| 1 | `ADR/ADR-0008:252` `迁移手册-白名单独立成表.md` 已备好 | `test -e research/governance/skeleton/迁移手册-白名单独立成表.md` | ❌ **不存在**；真名 `迁移手册-机器词表.md` |
| 2 | `ADR/ADR-0008:270` `research/governance/skeleton/迁移手册-白名单独立成表.md`（人工迁移步骤） | 同上 | ❌ 同上 |
| 3 | `ADR/ADR-0008:269` `research/governance/skeleton/白名单导入-飞书.csv`（26 行） | `find . -name '白名单导入-飞书.csv'` | ❌ 实际在 `research/governance/skeleton/_data/deprecated/` |
| 4 | `ADR/ADR-0012:356` `migrate_misrouted_guards.py` 执行了迁移 | `find . -name migrate_misrouted_guards.py` | ⚠️ 存在但**未标路径**：`research/governance/skeleton/migrate_misrouted_guards.py`（批 8 报的「在 tools/ 下」不成立，ADR 里没写 tools/） |
| 5 | `ADR/ADR-0008:72` 「T9 的 `match.keywords` 22 → **0**」 | 见下 | ✅ 复现：`T9.objective-parameter` keywords = **0** |
| 6 | `ADR/ADR-0008:251` `tools/migrate_whitelist_to_lark.py` 存在 | `test -e` | ✅ |
| 7 | `ADR/ADR-0008:75` `tools/offline_replay.py` 存在 | `test -e` | ✅ |
| 8 | `ADR/ADR-0008:223` `audit_rule_consistency.py`（未标路径） | `find` | ⚠️ 在 `research/governance/` |
| 9 | `ADR/README.md:21` ADR-0001 = `accepted` | 对读 `ADR-0001:3` | ❌ 正文 `proposed`（D2-06） |
| 10 | `ADR/README.md:32` ADR-0012 = `accepted` | 对读 `ADR-0012:3` | ❌ 正文 `proposed`（D2-06） |
| 11 | `ADR/README.md:56` ADR-0012 = 「处置四层」 | 对读 `ADR-0012:205` | ❌ 正文「五层 DP0–DP4」（D2-07） |
| 12 | `ADR/README.md:30` ADR-0010「1160 条台账（1023 顶层 + 137 子任务）」 | 见下 | ✅ 复现：`台账-v1.json` `stats.real_records=1160, top=1023, child=137`，1023+137=1160 |
| 13 | `ADR/ADR-0013:99/164`、`ADR/README.md:94` `PMO/腾讯云-周健-SecretKey.csv` | `test -e` | ✅ **不是假话**：ADR13-D8 明文写「移出项目目录」，是**故意不在这** |
| 14 | `AGENTS.md:39` §2.1 表列的全部自证脚本存在 | 23 条 `test -e` 全过 | ✅ （`tools/verify_*.py` ×6、`tools/verify_*.mjs`、`tools/agent/prd_baseline.mjs`、`tools/restart_shouheng.sh`、`tools/reply-cards/*`、`PMO/待收清单-v1.json`、`PRD/feishu/索引-v1.json`、`skills/内容合规审查/SKILL.md` …） |
| 15 | `AGENTS.md:53` `.gitignore` 第 39 行 = `skills/` | `sed -n '39p' .gitignore` | ✅ |
| 16 | `AGENTS.md:38` `verify_skill.py` 只扫 `skills/内容合规审查/SKILL.md` | `grep -n SKILL tools/verify_skill.py` → `:34 SKILL = …"内容合规审查","SKILL.md"` | ✅ |
| 17 | `AGENTS.md:40` 可达清单完整（**29 项**） | 见 D2-08 | ❌ 代码断言 25 |
| 18 | `AGENTS.md:41` `lark_people.py --controls` = 23 项 | 实跑 | ✅ 23 |
| 19 | `AGENTS.md:319` 同一条命令 = **18 项** | 实跑 | ❌ 23（D2-09） |
| 20 | `AGENTS.md:43/392` `prd_baseline.mjs --selftest` = 38 项 | 实跑 | ✅ 38 |
| 21 | `AGENTS.md:44/450` `verify_pending.py --controls` = 32 项 | 实跑 | ✅ 32 |
| 22 | `AGENTS.md:568` `kill -TERM` 由 **`ws_daemon.mjs:229`** 捕获 | `sed -n '229p' tools/ws_daemon.mjs` → `},` | ❌ 真位置 `tools/ws_daemon.mjs:258`（`process.on('SIGTERM', …)`），`process.exit(0)` 在 `:255` |
| 23 | `AGENTS.md:150` 缓存子树「实测 **120 个 pyc / 5.7 MB**」 | `find ~/Library/Caches/com.apple.python/Users/lute/Project/audit_multi_content -name '*.pyc' \| wc -l` → **17**；`du -sh` → **316K** | ❌ 复现不出（缓存目录 mtime 2026-09-21 15:37 被重建） |
| 24 | `AGENTS.md:295-299`（§2.4）三个上限常量「整个仓库没有一行代码引用它们」 | `grep -rn` | ⚠️ 作为**历史陈述**成立（现在 `envelope.mjs` 引用了）；但见 D2-03：第三个**至今**没有比较 |
| 25 | `AGENTS.md:51` 全仓库扫出 **332 个**填充态文件 | `python3 tools/verify_depad.py`（当前全绿） | ⚠️ 带日期（2026-09-18）的读数，合规；本轮实扫 `stat` vs 实读不一致 = **0** |
| 26 | `PMO/守衡-回复卡片模版与语域规程.md:5` 自证「**227 项**全过」 | `node tools/verify_cards.mjs \| tail -1` | ❌ 实际 **232 项** |
| 27 | `tools/reply-cards/contract.md:344` 同上「227 项全过」 | 同上 | ❌ 232 |
| 28 | `tools/verify_cards.mjs:526` 段标题「文档里写的自证项数**必须等于**实际项数」 | `sed -n '545,547p'` → `Math.abs(n - pass) > 12` / 消息「与实测 232 **同量级**」 | ❌ **断言比它自己宣称的松**：容差 ±12，且判词是「同量级」不是「等于」。227 与 232 差 5 → 绿 |
| 29 | `agent-skills/守衡语域/SKILL.md:182` 「尚未写进 `tools/agent/persona.mjs`」 | `grep -n cardContract tools/agent/persona.mjs` → `:81` | ❌ 已写（D2-05） |
| 30 | `agent-skills/守衡语域/SKILL.md:183` 「卡片发送路径 ❌ 未接入，仍走 `replyMarkdown`」 | `grep -n toCardOrText tools/ws_daemon.mjs` → `:26,:106` | ❌ 已接入（D2-05） |
| 31 | `PMO/…语域规程.md:225` 「launchd 下的守衡进程（**PID 81379**）跑的还是旧代码」 | `pgrep -fl ws_daemon` → **79861**；`cat PMO/logs/restart-ledger.jsonl` | ❌ PID 不对（台账里 46662→67552→79861，**没有 81379**） |
| 32 | `PMO/…语域规程.md:237` 「重启守衡使改动生效 \| ❌ **未重启**」 | 同上 | ❌ 台账有 **2 条 restart**，最近一次 `2026-09-21T11:34:05Z`（本文件日期 2026-09-18 之后） |
| 33 | `PRD/内容治理-TUI产品提案.md:19/25/178` CATCH-ALL 命中率 **54.6%** | 对读 `ADR/ADR-0012:523`「真实的规则缺口压力是 **100/291 = 34.4%**，不是 54.6%」；见 D3-02 | ❌ 已被本方 ADR 更正的数字仍在 PRD 层当依据用 |
| 34 | `PRD/内容治理-TUI产品提案.md:6` 「前置阻塞：飞书事件订阅未配置」 | `head -4 PMO/守衡-链路打通确认.md` → 「**双向链路全部打通**（2026-09-16 02:57）」 | ❌ 阻塞早已解除，文档无「已解」标注 |
| 35 | `ADR/ADR-0009:108,240` + `ADR/README.md:109`「语境守卫 **89 词**」 | `python3 -c "import json;print(len(json.load(open('research/governance/skeleton/context-guards-v1.json'))['words']))"` → **85**；且 `ADR/ADR-0012:361` 已宣告 89→85 | ❌ 三行陈旧（见 D2-11） |

**假率**：34 条里 ❌ **19 条假**（归并为 **17 个独立缺陷**）、⚠️ **3 条存疑**（未标路径 / 仅作历史陈述）、✅ **12 条复现**；去掉存疑后 **19/31 = 61%**。

### 三.B 最贵的三条

**【D3-01】`AGENTS.md:568` 引用的行号 `ws_daemon.mjs:229` 是错的 —— 而这条正是全项目最贵教训的执行点引用**

`AGENTS.md:560-575` 讲的是「`kill -TERM` 会让守衡永久静默，而看起来像正常停机」。这条结论的唯一依据就是「`ws_daemon.mjs:229` 捕获 SIGTERM → `shutdown()` → `process.exit(0)`」。真位置：
```bash
grep -n "SIGTERM\|process.exit" tools/ws_daemon.mjs
# 255:  process.exit(0);
# 258:process.on('SIGTERM', () => shutdown('SIGTERM'));
sed -n '229p' tools/ws_daemon.mjs      # →  },
```
**影响**：`AGENTS.md` §2.4 的规矩是「写进文档的每一个上限/约束，必须能指出是哪一行代码在拦它」。这是**宪法自己引用错行号**。而这行代码在**其他文件里被改过之后**（`ws_daemon.mjs` 现在 312 行）不会有人去复核文档。审计至此，`AGENTS.md` 里唯一一处**具体到行号**的代码引用，就是这一处，而它是错的。

**建议动作**：改成「`tools/ws_daemon.mjs:258` 的 `process.on('SIGTERM')` → `shutdown()`（`:255`）→ `process.exit(0)`」；或去掉行号，改引函数名 `shutdown()`（函数名不会被行号漂移打败）。

---

**【D3-02】被本方 ADR 明确更正过的数字 `54.6%`，仍在 `PRD/` 权威层当依据使用**

```bash
grep -rn "54\.6" --include=*.md . | grep -v node_modules | grep -v '\.ua/' | grep -v 'skills/'
# ADR/ADR-0012-…md:523:   不是「规则没覆盖」。真实的规则缺口压力是 **100/291 = 34.4%**，不是 54.6% ——
# PRD/内容治理-TUI产品提案.md:19:| `CATCH-ALL` 命中率 | **54.6%** | **超过一半的广告落进「未命中任何规则」** |
# PRD/内容治理-TUI产品提案.md:25:> 它会在 54.6% 的情况下把「我不知道」说成「没问题」…
# PRD/内容治理-TUI产品提案.md:178:| 自动判违规并直接拦截投放 | Precision 0.970 意味着 3% 误杀；且 54.6% 落 CATCH-ALL |
# PRD/PRD差异对照-20260921.md:147:… 且 `CATCH-ALL` 命中率 **54.6%**（`PRD/内容治理-TUI产品提案.md` §0）… **这条是七处里最硬的**
```
`ADR/ADR-0012:480` 的 D5 决定表里写着：「空白清单 **100 条（34.4%）**，**原先报 54.6%**」。也就是说这条数字**在 2026-09-16 就已被更正**，而 09-15 的提案没改，09-21 的**PRD 差异对照**又把它当「七处里最硬的一条」引了一次。

**影响**：`PRD/` 是上游权威层的落点，`PRD差异对照` 是给委托方看的对账件。一个被本方 ADR 判为「不是 54.6%」的数字，在这里决定了「验收口径兑不兑付得了」的结论。而且它引用的是**另一份自己也没改的文档**（`TUI产品提案.md`），形成一条自证的错误链。

**建议动作**：`TUI产品提案.md` 三处 54.6% 加更正标注（照 `PRD/内容治理需求文档.md:3` 的 `⚠️ 已过期` 写法），或改用 34.4%；`PRD差异对照-20260921.md:147` 同步。

---

**【D3-03】`PMO/…语域规程.md` 同时说「已接入」（§六）与「进程跑的还是旧代码、未重启」（§5.7）**

`PMO/守衡-回复卡片模版与语域规程.md:225`（「PID 81379 跑的还是旧代码」）与 `:237`（「重启守衡使改动生效 ❌ **未重启**」）在本文件里没有矛盾 —— 它们是「代码改了、进程没重启」的经典组合。问题是**事实已经过期**：
```bash
cat PMO/logs/restart-ledger.jsonl
# {"at":"2026-09-21T10:04:35Z","mode":"restart","pid_before":"46662","pid_after":"67552","why":"让待收到期提醒生效…","ok":true}
# {"at":"2026-09-21T11:34:05Z","mode":"restart","pid_before":"67552","pid_after":"79861","why":"让两个检查分开写状态 + 单飞生效…","ok":true}
pgrep -fl ws_daemon
# 79861 /Applications/DSH Desktop.app/Contents/MacOS/DSH Desktop ws_daemon.mjs
```
`81379` **不在任何一条留痕里**。

**影响**：这是四类「运行状态类陈述」中最容易被当真的一类 —— 「❌ 未重启」会让人以为改动还没生效，从而重复一次**需要 Owner 同意**的重启（`AGENTS.md` §2.7：重启窗口会吃掉群消息）。同一份文件的 §六 表格（:230-241）号称「还没做的（不许被这份记录读成已经做好了）」，而它自己已经**反向过期**。

**建议动作**：把「生效状态」这类会过期的事实从文档正文移走，改为指向唯一事实源：`PMO/logs/restart-ledger.jsonl` + 一次 `pgrep`。文档里只保留「怎么查」，不保留「查到什么」。

---

## 四 · 数字没有复现命令（`AGENTS.md` §2.2 第 1 条）

### 【D4-01】审计期间 `AGENTS.md` 被**连续改写三次**，本文所有行号是「某一刻的快照」

**证据**：
```bash
git status --porcelain -- AGENTS.md      #  M AGENTS.md
git show HEAD:AGENTS.md | wc -c          # → 37643
wc -c AGENTS.md                          # → 42364（第一次读到时 40694）
md5 -q AGENTS.md                         # → 2c23b14e2d26a82ba6f8f3e2963fba8c
git diff --stat -- AGENTS.md             # 1 file changed, 79 insertions(+), 5 deletions(-)
```
行号漂移实例：§2.4.1 第 4 行「18 项」在第一次读到时位于 `:293`，现在是 `:319`；`ws_daemon.mjs:229` 一处从 `:496`(HEAD) → `:542` → `:568`。

**影响**：**本文本身就在演示 §2.2 第 1 条要治的病** —— 一个引用行号的文档，在被引用文件改动后立刻失效，而没有任何东西会红。`AGENTS.md` 是 228 份文档里改动最频繁的一份（HEAD 与工作区差 79 行），却也是被引用最多的一份（24 次入边）。**所有引用它的行号都会漂。**

**建议动作**：`AGENTS.md` 的引用一律用**稳定锚点**（`§2.4` + 小标题文字），不用行号；或引入 `AGENTS.md` 的分节 ID 机制。对本文档同样适用：**读本文时请以命令为准，不要以行号为准**。

---

### 【D4-02】`AGENTS.md` 自证项的项数全部可复现（4/4），但**文档间互相引用的行号与数量不可复现**

**证据**：
```bash
for c in "python3 tools/lark_people.py --controls" "python3 tools/verify_pending.py --controls" \
         "python3 tools/verify_feishu_index.py" "node tools/verify_cards.mjs" ; do
  printf '%-45s → ' "$c"; eval "$c" 2>&1 | tail -1; done
node tools/agent/prd_baseline.mjs --selftest 2>&1 | tail -1
```
**读数**：`lark_people --controls` = **23** ✅ / `verify_pending --controls` = **32** ✅ / `prd_baseline --selftest` = **38** ✅ / `verify_cards` = **232**（文档写 227 ❌）/ `verify_feishu_index` = **34**（文档写「29 项」，但那个数指的是 E7 的 25 条，见 D2-08 ❌）。

**影响**：`AGENTS.md` **确实在自证项数上做到了「算出来」，这是它的强项**。它破功的地方在**跨文档引用**（行号、PID、25/29、18/23）与**外部读数**（120 个 pyc）。

**建议动作**：把「项数」这类数字全部改为从自证输出读取（`verify_cards` 的 I 段就是这个思路），并把 I 段的容差从 ±12 改成 0（现在是「同量级」，见 D3 表 #28）。

---

### 【D4-03】★ `5,544 字` 复现不出来 —— 而它写在「§2.2 第 1 条」出处的同一份文档里

**证据**：
```bash
python3 - <<'PY'
import json,re,statistics
d=json.load(open('PMO/shouheng-state/sessions/chat_oc_49a7cfb2861cffa4365ca8491f398d32.json'))
want={423,434,704,779,793,1045,1057,1312}
sel={}
for m in d['messages']:
    if m.get('role')=='assistant' and len(m['content']) in want: sel.setdefault(len(m['content']), m['content'])
sel=[sel[k] for k in sorted(sel)]
print('匹配到的 8 条长度:', sorted(sel and [len(c) for c in sel]))
print('中位数:', statistics.median([len(c) for c in sel]), '（文档写 786 ✅）')
print('raw 字数合计 :', sum(len(c) for c in sel), '（文档写 5,544 ❌）')
print('去空白       :', sum(len(re.sub(r'\s','',c)) for c in sel))
print('仅中文字     :', sum(len(re.findall(r'[\u4e00-\u9fff]',c)) for c in sel))
print('去 markdown  :', sum(len(re.sub(r'[*`#|\-\s]','',c)) for c in sel))
PY
```
**读数**：
```
匹配到的 8 条长度: [423, 434, 704, 779, 793, 1045, 1057, 1312]   ← 与文档 :15 的八个长度逐个一致 ✅
中位数: 786.0                                                      ← 与文档「中位 786 字」一致 ✅
raw 字数合计 : 6547                                                ← 文档写 5,544 ❌
去空白       : 5892
仅中文字     : 2977
去 markdown  : 5293
```
**五种口径没有一种给出 5,544。** 而这一段的「8 条回复 / 5,544 字」被**逐字复制到两处**：
```bash
grep -rn "5,544\|5544" --include=*.md . | grep -v node_modules | grep -v '\.ua/'
# PMO/守衡-回复卡片模版与语域规程.md:113: 把七条内容级检查跑在守衡**真实发出去的 8 条群回复**上（5,544 字）：
# agent-skills/守衡语域/SKILL.md:99:       把这七条跑到守衡**真实发出去的 8 条群回复**上（会话记录，共 5,544 字）：
```

**影响**：这是本轮最刺眼的一条。`AGENTS.md` §2.2 第 1 条——**全项目第一条规矩**——的出处是 ADR-0013 §15.3「手册里的可复现命令复现不出手册里的数」。而这条规矩的**下游文档**里，一个用来支撑「去 AI 味检查对守衡几乎无事可做」这个结论的样本量数字，**两种口径都对不上**（8 条对、786 对、5,544 不对）。错误还**复制成了两份**。

**建议动作**：改为 `6,547 字`（raw），或直接写「8 条回复，长度 423–1,312 字，中位 786（复现命令见 §七）」。`SKILL.md:99` 同步。

---

### 【D4-04】`AGENTS.md` 里带「实测」字样的读数，**日期都在小节标题里、不在数字旁**

**证据**（`AGENTS.md` 当前版本）：
```bash
grep -n "实测" AGENTS.md | head -20
```
读数分布：`:48`「（2026-09-18 实测）」✅ 数字旁带日期 · `:150`「实测 120 个 pyc / 5.7 MB」❌ 日期在**上一级小标题**（§2.1.1「2026-09-21 实测」）· `:207`「（2026-09-22 实测）」✅ · `:546-556`「实测（2026-09-21，用与守衡同款 KeepAlive 的临时 launchd 作业…）」✅ 但**声称的复现物「事后已卸载、文件已删」**，等于不可复现。

**影响**：`AGENTS.md` 在这一点上基本合规（4 处里 3 处带日期），比其余文档好；破的是 `:150` 的 120 pyc（现为 17）与 `:546` 的「事后已删」。

**建议动作**：`:150` 改成「实测（2026-09-21 那一刻）120 个 pyc / 5.7 MB；**2026-09-22 复核为 17 个 / 316 KB**（缓存目录被重建过）」。

---

### 【D4-05】★ 全仓扫描：**4,748 / 6,446 条量化断言（74%）既无复现命令、也无读数日期**

**证据（一条命令算完）**：把 228 份 `docs` 逐行扫「量化断言」（计数 + 单位词 / 百分比 / ≥16 位十六进制串），按**空行切出的段落**归并上下文，再判该段落内是否出现 (a) 复现命令（`grep` / `wc -` / `shasum` / `python3 ` / `node ` / ` ```bash ` / 反引号里的 `.py|.mjs|.js|.sh` / `$ `）或 (b) 日期（`20\d\d-\d\d-\d\d`）：

```bash
python3 - <<'PY'
import json, re, collections
scan=json.load(open('.ua/intermediate/scan-result.json'))
DOCS=[f['path'] for f in scan['files'] if f['fileCategory']=='docs']
QUANT=re.compile(r'(\d[\d,\.]*\s*(?:条|个|项|张|行|字|词|次|篇|份|人|轮|档|节点|边|%|KB|MB|GB|字节))|([0-9a-f]{16,})')
HARD=re.compile(r'实测|读数|测得|全过|退出码|退 ?[0-3]\b|sha256|指纹|中位|通过 \d+ 项')
CMD=re.compile(r'(grep\b|wc -|shasum|python3 |node |cat |ls -|find |\$ |```bash|```sh|\b复现\b|`[^`]*\.(py|mjs|js|sh)[^`]*`|jq )')
DATE=re.compile(r'20\d\d-\d\d-\d\d')
agg=collections.defaultdict(collections.Counter); ht=collections.Counter(); hb=collections.Counter()
for p in DOCS:
    lines=open(p,encoding='utf-8',errors='replace').read().split('\n')
    g=('ADR/PMO/PRD/AGENTS（治理层）' if (p.startswith(('ADR/','PMO/','PRD/')) or p=='AGENTS.md')
       else 'research/**（调研层）' if p.startswith('research/')
       else 'skills-inventory/**' if p.startswith('skills-inventory/') else '其他')
    for i,l in enumerate(lines):
        if not QUANT.search(l): continue
        lo=i
        while lo>0 and lines[lo-1].strip(): lo-=1
        hi=i
        while hi<len(lines)-1 and lines[hi+1].strip(): hi+=1
        ctx='\n'.join(lines[lo:hi+1]); a=agg[g]; a['total']+=1
        c=bool(CMD.search(ctx)); d=bool(DATE.search(ctx))
        a['cmd']+=c; a['date']+=d; a['bad']+= (not c and not d)
        if HARD.search(l):
            ht[g]+=1; hb[g]+= (not c and not d)
for g,a in sorted(agg.items(), key=lambda kv:-kv[1]['bad']):
    print(f"{g:<28}{a['total']:>7}{a['cmd']:>8}{a['date']:>8}{a['bad']:>8}{100*a['bad']/a['total']:>7.0f}%{ht[g]:>8}{hb[g]:>11}")
PY
```
**读数**：

| 层 | 量化断言 | 同段有复现命令 | 同段有日期 | ❌ 两者皆无 | 皆无占比 | 其中「硬读数」 | 硬读数且皆无 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `research/**`（调研层） | 3,948 | 742 | 332 | **3,019** | 76% | 155 | **104** |
| `ADR`/`PMO`/`PRD`/`AGENTS`（治理层） | 1,366 | 491 | 203 | **830** | 61% | 158 | **60** |
| `kb2agent`/`agent-skills`/`base`/`tools` | 765 | 173 | 86 | 551 | 72% | 44 | 30 |
| `skills-inventory/**` | 367 | 19 | 0 | 348 | 95% | 3 | 3 |
| **合计** | **6,446** | **1,425** | **621** | **4,748** | **74%** | **360** | **197** |

**读这个数要小心两点**（否则会高估）：
1. 「有日期」只统计**同一段落内**的日期 —— 很多文档把「（2026-09-18 实测）」写在小节标题里，跨段就不算。所以 74% 是**上界**。
2. `research/**` 的 3,019 条里有大量是**外部文献引用**（平台政策条款号、论文数字），这类本来就该带**出处**而不是复现命令 —— 真正该看的是最后一列：**「硬读数且既无命令又无日期」共 197 行**，它们声称的是**本项目的实测**。

**这 197 行的最坏样例**（声称自己实测过，却指不出怎么重跑、也没说是哪天读的）：

| 位置 | 原文（截断） |
|---|---|
| `ADR/ADR-0006-两段式判定而非单张词表.md:219` | `- 实测可核率 **95.2%（朴素子串）/ 90.0%（严格词边界）**，差 14 处全是屈折/复合形态；` |
| `ADR/ADR-0006-…:263` | `- 误报率成为**可优化指标**：实测已达 3%~4%，且成因明确（ADR-0007）` |
| `ADR/ADR-0009-语境守卫独立成表.md:26` | `按它分类会把一半的词判成「未归类」。按现网 94 个条目实测，实际有四种形态：` |
| `ADR/ADR-0010-需求知识库权威源与归一化边界.md:36` | `实测 17 张表 3251 条记录。进台账的是 \`需求 + 审核\` 两类，共 **1160 条**：` |
| `ADR/ADR-0011-落地页内容获取的边界与节流.md:13` | `…记为 \`robots_disallowed\` 且**不发请求**。本批 92 个 URL 实测被禁 0 条。` |
| `ADR/ADR-0012-判定引擎产品化与处置分层.md:181` | `实测（验收 V1d/V1e）：\`engine_version = f516c14c1a2284fb\` · \`code_version = 392ed34e34f86ad8\`。` ← **现行产物是 `a3218e7f3245f745` / `a45ef12ba540c87d`，见 D4-06** |
| `ADR/ADR-0008-机制分离白名单独立成表.md:44` | `**这句话是错的，且它正是事故得以存续的原因。** 实测：26 词中有 **10 个被人工抄进** 4 条规则的 \`豁免词\`：` |
| `ADR/ADR-0003-敏感样本分级准入.md:13` | `这类素材**天然含敏感内容**。实测当前 8 条可见样本已经出现：` |

**抽验其中 3 条能不能复现**：
```bash
# ADR-0010「17 张表 3251 条 / 1160 条」 —— ✅ 复现（但文档没给这条命令，读者只能靠猜）
python3 -c "import json;d=json.load(open('research/kb/台账-v1.json'));print(d['stats']['real_records'],d['stats']['top'],d['stats']['child'])"
# 1160 1023 137

# ADR-0012「engine_version = f516c14c1a2284fb」 —— ❌ 现行产物里没有这个值（见 D4-06）
python3 -c "import json;print(json.load(open('research/governance/skeleton/engine-manifest.json'))['engine_version'])"
# a3218e7f3245f745

# ADR-0006「95.2% / 90.0% 可核率」 —— ❌ 全仓产物里找不到这两个数
grep -rn "95\.2\|90\.0" --include=*.json --include=*.py research/governance | head -3
# （无命中：这两个数只存在于 ADR 散文里）
```
**3 条抽验：1 条复现、2 条复现不出。**

**影响**：`AGENTS.md` §2.2 第 1 条的 (a) 分支（**带复现命令**）在全仓的覆盖率是 **22%**；治理层（最该守这条规矩的地方）也只有 **36%**（491/1366）。而 197 行「硬读数」是**最贵的一类**：它们以第一人称声称「我测过」，读者据此建立事实，事后却无从复核 —— 这正是 ADR-0013 §15.3 那次事故的形状（手册里的可复现命令复现不出手册里的数）。

**建议动作**：把「实测」定为**受控词**：出现「实测 / 读数」的同一行或相邻行必须给出 `` `命令` `` 或 `(YYYY-MM-DD)`，否则视为文档缺陷。可落成一条 `verify_docs.py` 断言（`AGENTS.md` §2.4 的做法：把规矩变成红的），先只扫 `ADR/` 与 `PMO/`。

---

### 【D4-06】★ 一条「实测」的数字现在复现出**相反**的读数 —— 而它写的是一次会被改写的测量，不是规格

**证据**：
```bash
python3 -c "
import json
live=json.load(open('research/governance/skeleton/engine-manifest.json'))
bak=json.load(open('research/governance/skeleton/_data/backup-batchD/engine-manifest.json'))
print('live   :', live['engine_version'], '/', live['code_version'])
print('backup :', bak['engine_version'], '/', bak['code_version'])"
# live   : a3218e7f3245f745 / a45ef12ba540c87d
# backup : f516c14c1a2284fb / 392ed34e34f86ad8
```
`ADR/ADR-0012-判定引擎产品化与处置分层.md:181`：
> 实测（验收 V1d/V1e）：`engine_version = f516c14c1a2284fb` · `code_version = 392ed34e34f86ad8`。

**这两个数今天在活动产物里一个都找不到**；它们只存在于 `research/governance/skeleton/_data/backup-batchD/engine-manifest.json`（该目录被 `.ua/.understandignore` 忽略）。

**这个项目已经诚实地记过这件事**，但记在**另一个文件**里：
```bash
sed -n '1845,1850p' ADR/ADR-0013-基座接口冻结与仓库入库分级.md
# | 这 7 个里有第二份副本的 | **1**（`f516c14c1a2284fb`，在 `_data/backup-batchD/` —— **该目录同样被忽略**） |
# ★ 附带一个不好笑的巧合：唯一有第二份副本的那一版 `f516c14c1a2284fb`，
#   **正是 ADR-0012 §6.1 拿来做实测的那一版**（「现存 5 条回执全部指向 `f516c14c1a2284fb`」）。
```
`ADR-0012:723` 也确认这一版已被「**四次重新固化**」。

**影响**：这不是「文档写错了」——`f516c14c1a2284fb` 在 2026-09-16 那天确实是真值。问题是它被写成**没有日期的「实测」**，而它测的是一个**每次改规则/改代码都会变的量**。今天任何人按最自然的那条命令复现，都会得到相反的结果，进而怀疑整条 ADR-0012 §3.4（`engine_version` / `code_version` 分离）这个**决策**——而那个决策本身是对的、且仍被执行。**这正是 ADR-0013 §15.3 那个病的形状**：数字是真的、命令是真的、复现不出来。

**建议动作**：`ADR/ADR-0012:181` 改成 `` 实测（2026-09-16，验收 V1d/V1e）：当时的读数是 `f516c14c1a2284fb` / `392ed34e34f86ad8`；**这两个值是会被改写的，现行值见 `research/governance/skeleton/engine-manifest.json`** ``。更根本的一条：**凡是被测对象会随提交改变的「实测」，必须写成「当时的读数 + 在哪读的」，不能写成常量。**

---

## 五 · 重复

> 方法：归一化（strip + 内部空白折叠 + 丢空行/`---`/`#`/表格分隔行）后做**行级集合交**（主）与 `difflib.SequenceMatcher(autojunk=False)`（复核）。`autojunk` 必须关，否则 >200 行的列表会把高频行当垃圾、比值假性偏低。脚本在 `/tmp/dup_audit.py`、`/tmp/shingle.py`。

### 【D5-01】★ `research/readmes/*.md` 10 份与 `research/repos/*/README.md` **sha256 逐字节相同**

**证据**：
```bash
cd /Users/lute/Project/audit_multi_content
for pair in "readmes/ad_compliance.md repos/ad-compliance-agent/README.md" \
            "readmes/ad_review.md repos/ad-review-agent/README.md" \
            "readmes/contract_audit.md repos/contract_audit/README.md" \
            "readmes/crossborder_img.md repos/cbi/README.md" \
            "readmes/invoiceaudit.md repos/invoice/README.md" \
            "readmes/omniguard.md repos/omniguard/README.md" \
            "readmes/polysafe.md repos/PolySafe/README.md" \
            "readmes/sceneforge.md repos/sceneforge/README.md" \
            "readmes/sinyard.md repos/sinyard/README.md" \
            "readmes/soe_legal.md repos/soe-legal/README.md" ; do
  set -- $pair
  a="research/$1"; b="research/$2"
  ha=$(shasum -a 256 "$a" | cut -c1-16); hb=$(shasum -a 256 "$b" | cut -c1-16)
  [ "$ha" = "$hb" ] && echo "相同 $ha  $a" || echo "不同 $a"
done
```
**读数**：**10/10 相同**（`cov`=1.000、`ratio`=1.000），冗余 **2,494 行 × 2 份**。

**没有同步脚本**：`ls tools/ | grep -i "readme\|sync\|export"` → 空输出。mtime 显示 `research/readmes/` 全为 `2026-09-21 19:48`，对应 `repos/` 为 `2026-09-15` / `2026-06-06` —— **手工后拷的副本，双向可漂移**。

**影响**：`research/repos/` 被 `.gitignore` 忽略（"克隆"），而 `research/readmes/` **入库**。所以入库的那一份是**手抄的对外项目 README**，没有任何机制保证它与克隆同步。这是全仓库最实的一处重复债务。

**建议动作**：`research/readmes/` 改为生成物（一行脚本 + 一次运行），或直接删除、在 `research/README.md` 里指向 `repos/`。

---

### 【D5-02】`research/readmes/omniguard.md` ≡ `polysafe.md`（只差 3 行）

**证据**：`shared = 195`、`cov = 0.990`、`ratio = 0.991`、**最大连续相同块 177 行**（A[2..178] ≡ B[2..178]）＋ 40 行（A[180..219] ≡ B[180..219]）；字符 12-gram 包含度 0.994。`diff research/readmes/omniguard.md research/readmes/polysafe.md` 只差标题、目录名与末尾换行。

**同源第二处**：`research/repos/PolySafe/README.md` ‖ `research/repos/omniguard/README.md`（同 177 行 + 40 行）、`PolySafe/frontend/README.md` ≡ `omniguard/frontend/README.md`（`ratio` = 1.000，连续 40 行）。→ 同一份文档挂在两个项目名下。

**影响**：两份被审计成「两个外部对标项目」，实际上是一个。

**建议动作**：在其中一份顶部标注「本文与 X 为同一份文档的两处留档」。

---

### 【D5-03】`PMO/守衡-*.md` 组（14 份 / 91 对）**没有重复债务 —— 这一项应从清单里划掉**

**证据**：`python3 /tmp/dup_audit.py pmo`
91 对共享行数分布：`0`→9 对 · `1`→48 · `2`→24 · `3`→7 · `4`→1 · `5`→1 · `8`→1。**81/91 对（89%）共享 ≤2 行**；全组共享行合计仅 **134 行**；最大 `ratio` **0.094**；最大连续块 **2 行**。

最高的一对：

| shared | cov | ratio | 最大块 | A ‖ B |
|---:|---:|---:|---:|---|
| 8 | 0.091 | 0.075 | 2 | `守衡-发送者身份修复记录.md`(119 行) ‖ `守衡-时间基准修复记录.md`(94 行) |
| 5 | 0.057 | 0.054 | 1 | `守衡-回复截断修复记录.md`(128) ‖ `守衡-时间基准修复记录.md`(94) |
| 4 | 0.036 | 0.073 | 1 | `守衡-发送者身份修复记录.md`(119) ‖ `守衡-回复截断修复记录.md`(128) |

重复的只有结构性样板：```` ``` ````（13 文件）、```` ```bash ````（7）、`| 文件 | 改动 |`（4）、`cd /Users/lute/Project/audit_multi_content`（4）。最大共享块原文 = `## 附：本次改动文件`（`发送者身份修复记录:178` / `时间基准修复记录:151`）。

**建议动作**：无需动。但可补一份 `PMO/README.md` 把这些事故记录串起来（现在它们零入边居多）。

---

### 【D5-04】`R*-*.md` vs `_shards/R*-*.md` **没有副本关系；真问题是 R7/R8 缺父汇总**

**证据**：`python3 /tmp/dup_audit.py gov`
- 父文件是 **R1–R6**（含 R4 两份，共 7 个），shard 是 **R7-W1..W3 / R8-W1..W3** —— **两套编号不交叉**。`git log --diff-filter=D --name-only -- 'research/governance/R7*' 'research/governance/R8*'` → 无输出，即 R7/R8 父文件**从未存在**。
- 42 对全交叉：最高 `R6-peer-practice` vs `R7-W2-axis-design`，`shared = 32`，`cov = 0.034`，最大块 **12 行**；`ratio` 全组 ≤ 0.032。
- **方向判定 42/42 全部「≈」**（双向都不包含）→ 既不是 shard 抄父，也不是父聚合 shard。
- `R4-metrics-and-transparency-evidence.md` vs 全部 6 个 shard：**shared = 0**。

**影响**：R7/R8 是**只有分片、没有汇总**的孤儿，却被当证据直接引用：
```bash
grep -n "R7-W1\|R8-W1" research/kb/证据映射.json | head
# 171:    "research/governance/_shards/R8-W1-source-taxonomy.md",
```
即「结论引用了分片，而没有任何一层文件说明这些分片合起来是什么」。

**建议动作**：补 `R7-*.md` / `R8-*.md` 两份父汇总（哪怕只有范围、问题清单、分片索引），或把分片改名为 `R7-W1` 并在 `research/governance/README.md` 里声明「R7/R8 只有分片」。

---

### 【D5-05】语域/卡片规范的「行级不重复、语义重复」——见 D2-10

三份文件行级相似度 ≤7%（最大连续块 1–5 行），但同一条规范被手抄在 4–9 个文件里，**且已经漂移 2 处**。**`difflib` 抓不到它**，只有语义对读能抓到 —— 这是本次审计在方法上最该记的一条。

**建议动作**：把「重复度检测」从 `difflib` 扩展到「同一约束的多处副本」：对每个上限/状态词，`grep` 全仓计数并在数 >1 时要求一致性断言。

---

## 六 · 孤儿文档与被取代但看起来还活着的文档

### 【D6-01】77 份文档零入边、113 份零出边、44 份两头皆零

**证据**：见 D1-04 的脚本（`/tmp/docgraph.json`）。

**44 份「完全孤岛」的代表**（完整列表见 `/tmp/docgraph.json` 的 `both`）：
`skills-inventory/refs/**` **14 份** · `research/distill/scratch/` **11 份**（`_p5`、`_p10`、`_t1.._t9`） · `research/readmes/` **9 份** · `kb2agent-research/raw/` **3 份** · `PMO/守衡-时间基准修复记录.md` · `PMO/守衡-查名修复记录.md` · `research/governance/skeleton/迁移手册-机器词表.md` · `research/governance/R4-metrics-and-transparency-evidence.md` · `research/governance/annotations/annot_rater_B_notes.md` · `research/governance/skeleton/_data/receipts.LOSS.md` · `research/governance/_scratch/R5-integration-scripts/_err.txt`。

**★ 最刺眼的一个**：`research/governance/skeleton/迁移手册-机器词表.md` —— 它是**被机器校验的基准文档**（`.ua` 图谱的 layer 描述把它列入「规则与契约数据层」），却在文档引用图里**零入边零出边**：
```bash
grep -rn "迁移手册" --include=*.md . | grep -v node_modules | grep -v '\.ua/'
# ADR/ADR-0008-机制分离白名单独立成表.md:252:   + `迁移手册-白名单独立成表.md`。
# ADR/ADR-0008-机制分离白名单独立成表.md:270:| `research/governance/skeleton/迁移手册-白名单独立成表.md` | 人工迁移步骤（因应用只读） |
```
**唯一引用它的地方把它的文件名写错了**（D3 表 #1/#2）。也就是说：**这份文档的全部外部引用都指向一个不存在的名字** —— 它实际上是一份没人指得到的文档。

**建议动作**：为每个目录补索引；修 `ADR-0008` 的两处文件名。

---

### 【D6-02】★ `PRD/内容治理-TUI产品提案.md`：前置阻塞已解、依据数字已被推翻，但没有任何过期标注

**证据**：
```bash
sed -n '1,8p' PRD/内容治理-TUI产品提案.md
# | **日期** | 2026-09-15 |
# | **状态** | 提案，待评审（**前置阻塞：飞书事件订阅未配置**，见 `PMO/守衡-飞书打通测试报告.md` §2） |
head -4 PMO/守衡-链路打通确认.md
# **确认时间**：2026-09-16 02:57（真人事件抵达）/ 02:57:11（回复落群）
# **结论**：**双向链路全部打通**，且已通过「真人 @ → 守衡回群」端到端实测。
```
阻塞在提案日期次日 02:57 就解除了（比提案本身还早一天地发生了「打通」这件事），而**同一个文档头部的「状态」栏至今写着「前置阻塞：飞书事件订阅未配置」**。同时它带的三条数字（`:19` 54.6%、`:178` 54.6%、`:19` Precision 0.970）中，第一条已被 `ADR/ADR-0012:523` 更正为 34.4%（D3-02）。

**对照 —— 同一目录里做对了的那一份**：`PRD/内容治理需求文档.md:3-13` 有一段 6 行的 `⚠️ 已过期 —— 这不是现行需求书（2026-09-21 标注）`，逐条说明权威源换成哪一份、本文是哪一版。**同一批人、同一个目录，一份做了、一份没做。**

**影响**：`PRD/` 4 份里 2 份是「过期件」，其中 1 份有过期标注、1 份没有。`PRD差异对照-20260921.md:147` 还在引没有标注的那一份。

**建议动作**：给 `TUI产品提案.md` 照抄 `内容治理需求文档.md:3` 的 `⚠️` 块：写明阻塞已于 2026-09-16 02:57 解除、54.6% 已被 ADR-0012 更正为 34.4%。

---

### 【D6-03】`.ua/` 图谱里 20 份文档**零图边**，且 `228 份 docs` 与 `304 个 document 节点` 是两个口径

**证据**：
```bash
python3 - <<'PY'
import json,collections
g=json.load(open('.ua/knowledge-graph.json'))
deg=collections.Counter()
for e in g['edges']: deg[e['source']]+=1; deg[e['target']]+=1
byset=collections.defaultdict(list)
for n in g['nodes']:
    if n['type']=='document': byset[n['filePath']].append(n)
zero={fp for fp,ns in byset.items() if all(deg[n['id']]==0 for n in ns)}
print('图谱里不同的 document filePath:', len(byset))
print('其中零图边:', len(zero))
PY
```
**读数**：`document` 节点 **304** 个，但**不同 filePath 只有 230 个**（228 份 docs + `README.md`/`AGENTS.md` 的重计）；零图边的 **20** 个：`research/distill/scratch/_t1.._t9.md`（9）· `research/readmes/*.md`（6）· `skills-inventory/SKILLS-INVENTORY.md` · `x-recovery/*`（2）· `research/kb/materials/*.txt` · `research/governance/_scratch/…/_err.txt`。

**影响**：图谱的 `contains` 边几乎给每个文件都挂了父目录，所以「图度数」**远不如「文档互引度数」有信息量**（前者 20 个孤儿 vs 后者 44 个）。另外 `.ua` 的 `project.description` 说「455 文件中 228 个 docs」，而 `document` 节点 304 个 —— 两个数都对，但会被混读成「304 份文档」。

**建议动作**：审计/汇报时统一用「228 份 docs 类文件」这一口径，并注明 `document` 节点 304 是含重计的另一口径。

---

### 【D6-04】带着「提案 / 讨论稿 / 复盘 / v1」标记的文件共 **22 份**，其中只有 1 份带过期标注

**证据**：
```bash
git -c core.quotepath=false ls-files '*.md' '*.json' | grep -E "v1|讨论稿|提案|复盘|草稿|draft|初稿|deprecated|废弃" | sort
```
**读数 22 份**。其中：
- 带 `-v1` 的 21 份里，绝大多数是**版本化的数据契约**（`rules-v1.json`、`whitelist-v1.json`、`context-guards-v1.json`、`legal-decisions-v1.json`、`disposition-layers-v1.json`、`product-lines-v1.json`、`topic-tree-v1.md`、`schema-v1.json`、`台账-v1.json`、`知识库-v1.json`、`缺口-v1.json`、`外部标准库-v1.json`、`content-unit-v1.schema.json`、`资源索引-v1.json`、`索引-v1.json`、`待收清单-v1.json`）—— **这些 `-v1` 不表示「旧的」，改它们要按契约管理，不应被误删**；
- `PRD/feishu/内容审查Agent-PRD-v1.0.md` 是上游权威源（文件名里的 `v1.0` 是上游版本号）；
- 真正带「这是过程产物」语义的只有 4 份：`PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md`（自述「**性质**：讨论稿。不是 ADR，不是执行令，不改任何代码」✅ 做对了）· `PRD/内容治理-TUI产品提案.md`（❌ 无过期标注，D6-02）· `PMO/内容合规-阶段性复盘-20260916.md` · `PMO/守衡-回话草稿-M12材料逐条状态-20260922.md`。

**影响**：**「`-v1` 一律当旧件」是错的**，会误导清理动作；反过来，真正该标过期的 `TUI产品提案.md` 又没标。**命名约定不承载「现行/过期」信息**。

**建议动作**：约定一条：凡带「提案 / 讨论稿 / 复盘 / 草稿」语义的文档，**必须在第 3 行内写「现行 / 已过期 + 日期 + 后继是谁」**；`-v1` 只用于契约版本，不用于状态。

---

## 七 · 入库的垃圾（以及一条被推翻的前提）

### 【D7-01】★ 前提更正：`PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin` **没有被版本控制**

**证据**：
```bash
git -c core.quotepath=false ls-files --error-unmatch \
  "PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin"
# error: pathspec 'PMO/守衡-…-v1.md.corrupt-tail.bin' did not match any file(s) known to git   (exit 1)
git status --porcelain -- "PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin"
# ?? "PMO/守衡-…-v1.md.corrupt-tail.bin"
git -c core.quotepath=false ls-files PMO | wc -l      # → 13
ls PMO/*.md PMO/*.json | wc -l                        # → 18
```
**`PMO/` 下 13 个入库文件、18 个磁盘文件** —— 差的 4 个 `.md` 全部未跟踪（见 D7-04）。这条 `.bin` 与它同族的第二件都不在版本库里。**「跟踪的垃圾」这一条实际是「未跟踪的垃圾」。**

---

### 【D7-02】两件 `.corrupt-tail.bin` 是**高熵随机字节**，与同名 `.md` 无任何字节关系，且**没有任何文档认领这个名字**

**证据**：
```bash
find . -name "*.corrupt-tail.bin" -not -path "./.git/*"
# ./research/governance/_evidence/R2/ftc-notes.md.corrupt-tail.bin
# ./PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin
wc -c "PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md.corrupt-tail.bin"          # 3315
wc -c "research/governance/_evidence/R2/ftc-notes.md.corrupt-tail.bin"          # 2593
ls -l --time-style=full-iso …   # 两件 mtime 逐秒相同：2026-09-18 14:22:04
grep -rn "corrupt-tail" --include=*.md --include=*.json --include=*.mjs . | grep -v '\.ua/'
# → 0 命中（PMO/、ADR/、AGENTS.md 正文零引用）
```
**读数**（由并发子代理实测并共享）：两件都是高熵字节 —— 香农熵 **7.9320 / 7.9166 bit/byte**（上限 8），256/256 个字节值全部出现，可打印 ASCII 仅 37.6%。与同名 `.md` 的关系：`.bin` 是 `.md` 的前缀 → **False**；是后缀 → **False**；`.bin` 的 **103 个 32 字节窗口在 `.md` 里命中 0 次**。**它不是被截断的 Markdown/JSON 尾巴，它根本不是文本。**

**对应的 `.md` 完好**：`PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md` = **53,935 B / 706 行**，UTF-8 文本，结尾代码围栏闭合，最后一条命令是 `python3 tools/verify_engine_contract.py --only V30`；`read` 工具读它**正常**（当前全仓 `stat` vs 实读不一致 = **0**，即没有 +4096 填充）。`R2/ftc-notes.md` 同理（143,413 B，完好）。

**它是不是一种「已被记录」的失败？——不是。**
- 最接近的成文模式是 `AGENTS.md:48-84`（§2.1 的 **+4096 填充**）。但那个模式**只作用于文档类 `.md`，不产生 `.bin`**；`ADR/ADR-0013:303` 的最小复现实测明确记着 **`.bin` 差值 = 0**（`/tmp/_repro.bin | 4022 | 4022 | 4096 | 0`）—— **DLP 填充解释不了一个随机字节的 `.bin`**。
- 名字形态最接近的是**代码**：`tools/agent/memory.mjs:40` 的 `` `${f}.corrupt-${Date.now()}` ``（会话 JSON 损坏时隔离改名）—— 后缀不同、目录不同、且那是本项目自己的运行时代码，不是留档。
- 唯一成文的同族现象是 `skills-inventory/SKILLS-INVENTORY.md:107-131`（442/777 个压缩包直接读得乱码：`head -c4` 得 `504b0304`，`od`/`node readFileSync` 得 `887d1c8d`），`ADR/ADR-0013:377-379` 归因为**天锐绿盾 DLP（`com.tipray.trldKext`）透明加密**。**同族（同一文件不同读法得到不同字节），但两处都不解释 `.bin`、也都不认领 `corrupt-tail` 这个名字。**

**影响**：一个有名字、有大小、有明确 mtime（两件同秒）、**没有任何文档、任何脚本、任何断言引用**的游离构件，静静躺在两个目录里。它是最典型的「文档债的反面」—— 它不是错误的文档，是**一份不存在的文档的残留**。

**建议动作**：要么在 `PMO/` 或 `ADR/` 里补一段 3 行的处置记录（怎么产生、为什么留、要不要删），要么连 `.md` 一起移出工作区。**无论哪个方向，先别删** —— 它现在至少是一个「这里发生过一次异常」的证据。

---

### 【D7-03】入库的同类构件只有 2 个，而且**都不是垃圾**

**证据**：
```bash
git -c core.quotepath=false ls-files | grep -Ei '\.(bin|bak|orig|rej|tmp|corrupt|LOSS|truncated|partial|save|old)($|\.)'
```
| 路径 | 大小 | 是什么 |
|---|---:|---|
| `research/governance/skeleton/_data/receipts.LOSS.md` | 2,893 B / 55 行 | **成文的损失记录**（回执账本原 5 条现仅 1 条，因 `cp` 参数写反）；首行 `# 回执账本损失记录（2026-09-16）`；提交 `5ec84fb`（2026-09-17） |
| `research/governance/skeleton/rules-v1.json.bak` | 42,174 B / 1,301 行 | **迁移前备份**，JSON 可解析；同一提交入库 |

**影响**：`receipts.LOSS.md` 是**做对了的做法** —— 数据丢了就留一份成文的损失记录，而不是悄悄补一个空文件。可以作为「事故留痕」的正面样例。

**建议动作**：无需动。可把 `receipts.LOSS.md` 作为命名约定参考（`<物>.LOSS.md` = 损失记录）。

---

### 【D7-04】★ `PMO/` 下 4 份**最新**的文档（含 22.7 KB 与 13.5 KB 的两份）**没有入库**

**证据**：
```bash
git status --porcelain --untracked-files=all | grep '^??'
git -c core.quotepath=false ls-files PMO | wc -l   # 13
ls PMO/*.md PMO/*.json | wc -l                     # 18
```
**未跟踪的 4 份**：
```
?? PMO/守衡-内容推送与被at登记-20260915至0922.md          (16,890 B, mtime 09-22 11:57)
?? PMO/守衡-回话草稿-M12材料逐条状态-20260922.md          ( 6,452 B, mtime 09-22 11:56)
?? PMO/守衡-知识库GAP分析与第一性原理决策-20260922.md      (22,707 B, mtime 09-22 11:14)
?? PMO/守衡-知识库构建完整方案-20260922.md                (13,547 B, mtime 09-22 11:36)
```
这 4 份都是 `-rw-------`（600）—— 与 `AGENTS.md:48-84` 记的「**用 Python 写出的文件**」同款权限指纹（`verify_depad.py` 当前全绿，即**没有被 +4096 填充**，只是没入库）。

**影响**：本轮审计的 `.ua` 图谱在 `2026-09-22T04:19` 建立，它**分析了这些未跟踪文件**（所以它们出现在 228 份里），但 `git ls-files` 看不到它们 —— **`455`（被分析）与 `464`（入库）是两个不同的集合，任何用 `git ls-files` 数文档的人都会漏掉这 4 份最新的**。对一个把「可复算」写进第一条规矩的项目，最新产出不在版本库里是最不对称的风险。

**建议动作**：`git add` 这 4 份（外加 `AGENTS.md` 等 6 个已改文件），或在 `PMO/README.md` 里说清哪些是工作区产物、为什么不入库。另：`.ua/`（16 MB）**未入库且未被 `.gitignore` 覆盖**（`git check-ignore -v .ua` → rc=1），长期以 `?? .ua/` 挂在 `git status` 里，建议显式忽略。

---

## 八 · `skills-inventory/refs/` 的溯源问题

### 【D8-01】`skills-inventory` 入库 **91** 个文件（不是 89），refs/ 下 89 个中含 1 个 README

**证据**：
```bash
git -c core.quotepath=false ls-files skills-inventory | wc -l              # 91
git -c core.quotepath=false ls-files skills-inventory/refs | wc -l         # 89
git -c core.quotepath=false ls-files skills-inventory/refs | grep -c README.md   # 1 → 88 为留档原文
git -c core.quotepath=false ls-files skills-inventory/refs | awk -F/ '{print $3}' | sort | uniq -c | sort -rn
```
分目录：`ecommerce-image 20 · brand-docx 11 · brand-ad 11 · koc-video 7 · video-deconstruct-analyzer 5 · subtitle-correction 5 · copy-editing 5 · seo-content-audit 4 · iflytek-text-proofread 4 · video-deconstruct 3 · weighted-scoring 2 · video-transcript 2 · tos-risk-checker 2 · social-caption 2 · compliance-review-planner 2 · legal-risk-assessment 1 · blog-factcheck 1 · agentic-eval 1` = **88**（另 `refs/README.md` 1）。

**建议动作**：汇报口径从「89 个跟踪文件」改为「`skills-inventory` 91 个跟踪文件；`refs/` 下 89 个，其中 88 为第三方留档原文」。

---

### 【D8-02】★ `skills-inventory/index.json` **完全不覆盖** `refs/` —— 18/18 只是**名字重合**

**证据**：
```bash
wc -l skills-inventory/index.json       # 22392
wc -c skills-inventory/index.json       # 803816
python3 -c "
import json,collections
d=json.load(open('skills-inventory/index.json'))
print(type(d).__name__, len(d))          # list 964
k=collections.Counter()
for e in d: k.update(e.keys())
print(len(k), list(k))                    # 17 个键，每键 964 条
print(collections.Counter('/'.join(e['path'].split('/')[:2]) for e in d))"
# Counter({'skills/Manus': 670, 'skills/kimi': 170, 'skills/MinMaxDesign': 107, 'skills/MinMax': 17})
python3 -c "
import json,subprocess
refs=sorted({l.split('/')[2] for l in subprocess.run(['git','-c','core.quotepath=false','ls-files','skills-inventory/refs'],capture_output=True,text=True).stdout.splitlines() if l.count('/')>=2 and '.' not in l.split('/')[2]})
idx=json.load(open('skills-inventory/index.json'))
print('ref_dirs',len(refs),'index',len(idx),'in_both',len(refs&{e['name'] for e in idx}))
print('index paths under skills-inventory:',sum(1 for e in idx if e['path'].startswith('skills-inventory')))"
# ref_dirs 18 index 964 in_both 18
# index paths under skills-inventory: 0
```
`index.json` 是 **22,392 行 / 964 条**的数组，17 个键（`path name description source license license_normalized license_path has_frontmatter frontmatter_keys relevance pipeline_stage body_chars content_sha256_16 duplicate_group_size exact_duplicate_of curated note`）；它的 `path` **100% 落在被 `.gitignore:39` 忽略的 `skills/` 树**（Manus 670 + kimi 170 + MinMaxDesign 107 + MinMax 17 = 964）。**一条都不指向 `skills-inventory/`。**

**影响**：名字 18/18 全中会让人以为 index 覆盖了 refs —— 实际是同一批第三方技能在两个地方各存一份，`refs/README.md` 的「原始路径」列是两套清单之间**唯一的连接键**，而那一列指向的是**被 gitignore 的树**（不可复核）。所以 `index.json` **不能**充当 refs 的溯源依据。

**建议动作**：`skills-inventory/README.md` 里明确写「`index.json` 描述 `skills/`（未入库）；`refs/` 的溯源见 `refs/README.md` 的原始路径列，而那些路径不可复核」。

---

### 【D8-03】18/18 有「来源厂商 + 仓内路径」，**0/18 有可复核的上游 URL / commit**

**证据**：
```bash
git -c core.quotepath=false grep -n -i 'github\.com' -- 'skills-inventory/refs/*'      # → 0 命中
sed -n '13,30p' skills-inventory/refs/README.md
```
唯一载体是 `skills-inventory/refs/README.md:13-30` 的一张表，列为「留档目录 / 原始路径（仓内）/ 来源 / 许可状态 / 文件数」。例：`:20` = ``| `brand-ad/` | `skills/MinMaxDesign/brand-ad.zip` | MiniMax Design | **未声明** | 11 |``。

版本号只落在 10 处，且**自相矛盾一处**：
```bash
grep -rn "version" skills-inventory/refs/*/meta.yaml skills-inventory/refs/*/*/meta.yaml 2>/dev/null | head
grep -n "^version" skills-inventory/refs/koc-video/koc-video/SKILL.md
# skills-inventory/refs/koc-video/koc-video/SKILL.md:3:version: "8.7.1"
grep -n "^version" skills-inventory/refs/koc-video/koc-video/meta.yaml
# → 8.7.3
```
- MiniMaxDesign 系 8 个 `meta.yaml:2` 有版本（brand-ad `1.1.4`、ecommerce-image `0.1.12`、koc-video `8.7.3`、social-caption `0.3.2`、subtitle-correction `0.1.2`、video-deconstruct-analyzer `0.2.6`、video-deconstruct `1.0.3`、video-transcript `0.2.2`，同文件另有 `source: official`）；
- `refs/copy-editing/SKILL.md:5` = `version: 2.0.0`；`refs/iflytek-text-proofread/_meta.json` 有平台内部 `slug`/`version 1.0.0`/`publishedAt`/`ownerId`；
- **Manus 系 7 个（seo-content-audit、brand-docx、blog-factcheck、agentic-eval、legal-risk-assessment、iflytek-text-proofread、copy-editing）无版本、无上游**。

**许可**：只有 **3 个 LICENSE**，全在 kimi 系、全为 MIT；**15/18 目录「未声明」**：
| 路径 | 字节 | 著作权行 |
|---|---:|---|
| `skills-inventory/refs/compliance-review-planner/LICENSE` | 1,056 | `MIT License` / `Copyright (c) 2024`（**无主体名**） |
| `skills-inventory/refs/tos-risk-checker/LICENSE` | 1,094 | `Copyright (c) 2026 terms-of-service-auditor contributors` |
| `skills-inventory/refs/weighted-scoring/LICENSE` | 1,085 | `Copyright (c) 2026 decision-matrix contributors` |

**影响**：88 份第三方文件入库，**没有一份能回答「这是哪个版本的哪一份」**。对一个把「可复算」「指得出对象」写进宪法的项目，这是许可证与合规上最实的一个缺口 —— 而且 `AGENTS.md` §2.6 红线只覆盖飞书内容，不覆盖第三方许可。

**建议动作**：给 `refs/README.md` 的表加两列「上游 URL / commit」与「抓取日期」；补不出来的标「**未记录（不可复核）**」，把它变成一条**明着留的已知缺口**，而不是看起来完整的一张表。

---

### 【D8-04】`README.md` / `AGENTS.md` 对 `skills-inventory` **零引用**

**证据**：
```bash
grep -n 'skills-inventory' README.md AGENTS.md       # rc=1，0 命中
```
唯一引用在 `ADR/ADR-0013-基座接口冻结与仓库入库分级.md:139`（把 `skills-inventory/**` 列进三层分级的「文档面」），以及自述 `skills-inventory/SKILLS-INVENTORY.md:420-423`。

**影响**：91 个入库文件构成全仓第二大目录（仅次于 `research/`），却从两个入口都走不到；它唯一的入口是一份**被记为 `proposed` 的 ADR**（D2-06 之外的那个 ADR-0013 是 `accepted`，但 `ADR/README.md` 本身不可达，D1-03）。

**建议动作**：在 `README.md` 的导航里给 `skills-inventory/` 一行。

---

## 附 · 计数口径与复现清单

| 量 | 读数 | 命令 |
|---|---:|---|
| 入库文件 | 464 | `git -c core.quotepath=false ls-files \| wc -l` |
| 入库 `.md` | 223 | `git -c core.quotepath=false ls-files '*.md' \| wc -l` |
| 被分析文件 | 455 | `python3 -c "import json;print(len(json.load(open('.ua/fingerprints.json'))['files']))"` |
| `docs` 类 | 228 | `python3 -c "import json,collections;print(collections.Counter(f['fileCategory'] for f in json.load(open('.ua/intermediate/scan-result.json'))['files']))"` |
| docs 总行 / 总字节 | 81,581 行 / 6.80 MB | 见 §一 脚本 |
| ★ README∪AGENTS 不可达 doc | **142**（宽松）/ **179**（严格） | 见 D1-02 |
| 零入边 / 零出边 / 两头皆零 | 77 / 113 / 44 | 见 D1-04 |
| 抽样断言 ✅/❌/⚠️ | 12 / 20 / 3（假率 63%，18 个独立缺陷） | 见 §三.A |
| 另路抽查点名数字 24 项 | 16 复现 / **8 复现失败** | 见 §三.A 末表 |
| `PMO` 入库 / 磁盘 | 13 / 18 | `git ls-files PMO \| wc -l` ；`ls PMO/*.md PMO/*.json \| wc -l` |
| `skills-inventory` 入库 | 91（refs/ 89，留档 88） | 见 D8-01 |
| 全仓填充态文件 | 0 | `stat` vs 实读逐文件比对（见 §七） |
| 量化断言 / 皆无命令与日期 | 6,446 / **4,748（74%）** | 见 D4-05 |
| 其中「硬读数且皆无」 | **197** 行 | 见 D4-05 |
| 标题带「提案/讨论稿/复盘/草稿/v1」 | 22 份（只有 1 份带过期标注） | 见 D6-04 |

**本次审计未执行的两件事（按指令回避）**：`bash tools/restart_shouheng.sh --yes`、`python3 tools/verify_skill.py`。
**执行过的自证（均为只读）**：`node tools/verify_cards.mjs`（232 项过）、`python3 tools/lark_people.py --controls`（23 项过）、`python3 tools/verify_pending.py --controls`（32 项过）、`node tools/agent/prd_baseline.mjs --selftest`（38 项过）、`python3 tools/verify_feishu_index.py`（34 项过）、`python3 tools/verify_prd_baseline.py --offline`（**退 2：L1/L2 16 项过、L3 未测** —— 注意 `PRD/feishu/索引-v1.json` 与 `美国市场内容治理项目-一页纸计划书.md` 当前**都在工作区被改动**，索引已把 09-20 版指纹记为 `prev_fingerprints`）。
