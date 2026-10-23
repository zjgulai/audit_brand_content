# 覆盖率审计 · `verify_release_gate.py`（13 行）与 `verify_normalizer.py`（7 行）

> **这张单回答一个问题**：`passed=121` 里，这两支脚本负责的那 20 行，有多少是**真的**被验了。
> **只审计，不改脚本、不改表格**（按 05 的约束 (a)）。修是下一张票。

> 方法：12 个 agent（20 行逐行审计 + 20 行对抗复核，0 错误，930,968 subagent tokens）。
> 复核的职责是**证伪**审计判定，不是附和。

---

## 〇、一句话结论

**20 行里没有一行是「行为覆盖」。**

| 终判 | release_gate（13 行） | normalizer（7 行） | 合计 |
|---|---:|---:|---:|
| `behavior_covered` | **0** | **0** | **0** |
| `partial`（验了一半 / 验的是相邻但不等价的东西） | 10 | 7 | **17** |
| `uncovered`（没有对应物） | 3 | 0 | **3** |

**对抗复核 0 条推翻** —— 20 条的判定全部经得起证伪。

> ★ 这个结果不是「脚本写得烂」。两支脚本各自的断言都是真的、都能变红。
> 问题是：**它们验的东西与验收表要求的东西，在 20 行里有 20 行不完全重合。**

---

## 一、必须回退到 `untested` 的行（14 条）

按 05 的约束 (b)：**不为读数好看说它覆盖了**。以下 14 行在审计者与复核者双方看来
都够不上「这一行验过了」，建议标回 `untested`。

| 行 | 终判 | 一句话缺口 |
|---:|---|---|
| 8 | `partial` | 只对上了「永不 PASS」这一句，而且只落在 judgment_gate 这个纯函数上：(1) judgment_gate 全仓零生产调用点——仅 base |
| 10 | `partial` | 缺三半：(1) 比较的量是 unit_id，不是验收行点名的 text_sha256（:654、:668-670） |
| 21 | `partial` | 几何契约大半覆盖，但行里点名要的行为缺五块：(1) 「按 bbox 在原图裁剪、确认裁出区域与 finding 描述一致」未验——验证器自己在 :537-5 |
| 89 | `partial` | 只覆盖了四个面里的一个、而且是相邻物：G1 调 ReleaseGate.apply_machine_patch 传 {"release_status":"已 |
| 90 | `partial` | 只验了四条边且缺少行里点名的两条：A1 待放行→已放行、A6 已放行→已撤回、A4 待放行→已拒绝、F4 失效重审后→待放行 |
| 91 | `partial` | 三组样本本身覆盖了：C1 signer==submitter → SoDViolation、C2 signer==final_reviewer → SoDV |
| 92 | `partial` | 跨租户与跨品线的拒绝样本有：C3 signer(tenant=t2) → SoDViolation、C4 signer(product_line=p2) → |
| 93 | `uncovered` | 脚本里没有任何名单治理内容：没有四类名单变更的构造，没有 proposal（法务）/execute（IT）/approve（第三方）三类记录的断言，没有「提 |
| 94 | `partial` | 五类触发源只覆盖 3.5 类：②规则(E2)/知识库(E3)、③冲突表(E5)、⑤已用 ref(E4，含 kb) 齐全；①只测了 raw_sha256（正文 |
| 98 | `uncovered` | 脚本只验重审 job 的状态迁移（queued 合并、running 建 successor、完成回 pending_release、重签 derived_ |
| 99 | `partial` | 「自动建任务并 queued」已验：E 段每条失效用例在同一 invalidate() 调用返回里断言 job 非空且 state==queued，结构上等 |
| 123 | `uncovered` | 脚本里没有「撤权」这个对象，三条样本与不变式全部无对应物 |
| 127 | `partial` | ①核心行为『任一类变化即失效』完全没有验：没有任何断言逐个改动 frame_manifest_hash / keyframe_set_hash / ocr_ |
| 130 | `partial` | ①跨语言复算完全没有验：脚本纯 Python、不调用 node，全仓也只有 base/release_gate.py:104-119 一份 media_ro |

---

## 二、逐行明细

### `tools/verify_release_gate.py`（13 行）

#### #89 —— **partial**（建议回退 `untested`）

**表格原文要点**：四个交互面职责边界：飞书群只收提交/通知、Web 工作台承载复核/法务/申诉/签发/队列/权限、静态报告只读、多维表禁写 release_status；逐面构造越界动作，每一种都必须被拒且留审计行；只验一个面即红

**脚本对应**：`G1 (tools/verify_release_gate.py:306-308) / G2 (tools/verify_release_gate.py:309-310)`

**缺什么**：只覆盖了四个面里的一个、而且是相邻物：G1 调 ReleaseGate.apply_machine_patch 传 {"release_status":"已放行"} 断言抛 MachineWriteDenied，这是 Python 侧机器写闸，不是行里点名的「多维表写回」面，也没测 patch 里的 "status" 键与「发布状态」字段。三个面完全没有任何构造：飞书群入口（不存在从群消息触发签发/复核的接口断言）、Web 工作台（复核/法务/申诉/签发/队列/权限的承载面一个字都没碰）、静态报告只读（没有任何「向静态报告写字段必须失败」的样本）。更关键的是「留审计行」一项零覆盖——脚本从不读 state()["events"]（全文件 0 处），而 base/release_gate.py 在 MachineWriteDenied 分支也不追加任何 event（实测越界后 state 的 events 为空/None），所以「每一种都被拒绝且留审计行」这半句既没被测、当前实现也做不到。行文本身写明「只验其中一个面即红」，故该行不能算已验。

---

#### #90 —— **partial**（建议回退 `untested`）

**表格原文要点**：放行状态机完整迁移序列（待放行→已放行→已撤回→待放行；待放行→已拒绝→修改后重新提交），每次迁移须人触发且记录必含内容版本/理由/操作者/时间四项、删任一项即红；反向对照：不存在从审查标签直跳「已放行」的路径

**脚本对应**：`A1 (tools/verify_release_gate.py:117-118) / A4 (:130-132) / A6 (:145-147) / F4 (:290-291) / B1 (:150) / B3 (:160)`

**缺什么**：只验了四条边且缺少行里点名的两条：A1 待放行→已放行、A6 已放行→已撤回、A4 待放行→已拒绝、F4 失效重审后→待放行。缺 已撤回→待放行：base/release_gate.py 根本没有该路径（实测对 revoked 案件再 sign 抛 InvalidTransition「只有 pending_release 可签发，当前 revoked」），脚本也不测；缺 已拒绝→修改后重新提交：同样不存在路径（实测 reject 后再 sign 抛 InvalidTransition），A4 只测了到达 rejected 就结束。四要素「删任一项即红」只覆盖 1/4：B3 的删除反向对照字段表是 case_version/ir_id/raw_sha256/rule_snapshot_hash/used_authority_refs/conflict_table_version/media_fingerprints_root_hash/signature_version，恰恰不含 理由 reason、操作者 signer_id、时间 signed_at（B1 只断言这几项存在于 dict，不验删了会红）；而且「落盘记录」无从谈起——ReleaseGate 的 _cases 是纯内存 dict，脚本没有任何持久化断言。反向对照「P0 命中 + 三条机结全满仍停在待放行」零覆盖：脚本没有 P0/机器结论的概念，G1（机器 patch 不可写 release_status）是相邻但不等价。另「每次迁移都由人触发」只有 sign 侧有 step-up 负向对照（D1–D5），revoke/reject 的无 token 负向对照未构造（A6 是正向成功样本）。

---

#### #91 —— **partial**（建议回退 `untested`）

**表格原文要点**：签发权分离：构造 (a) 签发人==提交人、(b) 签发人==最终复核人、(c) 三者互不相同 三组样本，(a)(b) 必须被拒且记违规审计行，(c) 必须成功；再断言撤回权不随签发权自动获得（只有签发权、无撤回权的账号发起撤回必须被拒）

**脚本对应**：`C1 (tools/verify_release_gate.py:189-191) / C2 (:192-194) / A1 (:117-118)`

**缺什么**：三组样本本身覆盖了：C1 signer==submitter → SoDViolation、C2 signer==final_reviewer → SoDViolation、(c) A1 用 u3/u1/u2 三者互异且签发成功。缺两件事，且第二件是真缺陷而非仅缺测试：(1)「记违规审计行」零覆盖——脚本从不读 state()["events"]，实测 SoD 拒绝后案件的 events 仍是 []，实现也不写审计，故「必须被拒绝且记违规审计行」只做到了「被拒绝」；(2)「撤回权不随签发权自动获得」完全没测——signer() 默认同时给 release.sign 与 release.revoke（:83），不存在只有签发权的账号样本；而 base/release_gate.py:304-307 对 revoke 的判据是「既无 release.revoke 又无 release.sign 才拒」，实测 capabilities=["release.sign"] 的账号调用 revoke 成功返回 {'status':'revoked','release_status':'已撤回'}，正是行里明令必须被拒的行为。该行原文「只验 (c) 会漏掉职责分离失效」，而脚本虽验了 (a)(b)，却漏掉了撤回权这一半。

---

#### #92 —— **partial**（建议回退 `untested`）

**表格原文要点**：授权名单粒度 = 租户 + 品线：授权 (租户A,品线1) 的签发人对 (租户B,品线1) 与 (租户A,品线2) 的案件签发均须被拒、对 (租户A,品线1) 须成功；并断言授权记录的键是二元组而非单一账号，缺任一维度即红

**脚本对应**：`C3 (tools/verify_release_gate.py:195-197) / C4 (:198-200) / A1 (:117-118)`

**缺什么**：跨租户与跨品线的拒绝样本有：C3 signer(tenant=t2) → SoDViolation、C4 signer(product_line=p2) → SoDViolation；正样本 (t1,p1) 走 A1 签发成功。缺行里最后一句的两个断言：(1)「缺任一维度即红」没有任何样本——脚本从不构造 tenant 缺失或 product_line 缺失的 principal（实测 base/release_gate.py:308-311 会因 None != 值抛跨租户/跨品线，但这是实现的巧合，验证器里没有对应断言，改坏它不会红）；(2)「授权记录的键是二元组而非单一账号」无对应物——该实现里根本没有「授权名单记录」这个结构，tenant/product_line 只是 principal dict 上的两个平铺字段，没有任何 (tenant, product_line) 二元组键、也没有对单一账号键的反向对照。核心的跨维度拒绝已验，但行文明确要求的「缺任一维度即红」与「键是二元组」两项都没有执行点，不能算整行已验。

---

#### #93 —— **uncovered**（建议回退 `untested`）

**表格原文要点**：名单治理 RL-5：构造四类名单变更（新增/扩大范围/授予撤回权/撤销授权），每次须同时有法务提案、IT 执行、另一名授权审批人确认三条留痕，提案人不得与确认人同一人（同人样本必须被拒），且留痕可查谁/何时/改了什么/依据。

**脚本对应**：`tools/verify_release_gate.py:189-203（C1–C5 仅为签发 SoD，与名单治理无关）；全文无对应断言`

**缺什么**：脚本里没有任何名单治理内容：没有四类名单变更的构造，没有 proposal（法务）/execute（IT）/approve（第三方）三类记录的断言，没有「提案人==确认人必须被拒」的同人样本，也没有 who/when/what/basis 四元留痕断言。C1–C5 测的是签发人不能是提交人/最终复核人，属于签发 SoD，与名单治理不是同一个行为。底层 base/rbac.py 的 validate_grant_actors（proposer/executor/approver 三主体）根本未被本脚本 import 或调用，其自证在 tools/verify_rbac.py，不在本行映射的脚本里。

---

#### #94 —— **partial**（建议回退 `untested`）

**表格原文要点**：变化即失效 RL-6：五类触发源（①内容正文/媒体指纹 ②规则或知识库依据 ③冲突裁定结果 ④送审双指纹 ⑤已用 authority_ref 版本含 kb_snapshot）逐条各改一次，每条断言旧签发→已失效、案件回待放行、并产生通知；反向对照：不改任何东西时不得失效（纯查询仍有效）；只验一条即红。

**脚本对应**：`tools/verify_release_gate.py:237-251（E1–E5 循环）；:259（E6 未使用 ref 不失效）`

**缺什么**：五类触发源只覆盖 3.5 类：②规则(E2)/知识库(E3)、③冲突表(E5)、⑤已用 ref(E4，含 kb) 齐全；①只测了 raw_sha256（正文），媒体指纹（media_fingerprints / media_root）从未作为失效触发源改变过（B5/B6/H2 测的是摘要本身与顺序无关，不是 invalidate）；④送审双指纹的 text_sha256 在全脚本中从未被改动，整套 E 段没有一条 text 变化用例。此外每条只断言返回的 invalidated=True 与 job.state==queued，没有读 state 断言 status=invalidated/release_status=已失效，也没有逐条断言案件回到待放行（只有 F4 在一次重审全部完成后断言 pending_release/待放行），更没有通知断言（base/release_gate.py 全文件无 notifications 调用）。反向对照「不改任何东西→不失效（纯查询）」未构造：E6 是未使用 ref 变化（SB-8），F6 是同一 change_set 重复投递（幂等），都不是纯查询。

---

#### #98 —— **uncovered**（建议回退 `untested`）

**表格原文要点**：全量重审 RL-10：触发失效重审后须①逐条重跑全部适用控制点、模态提取、依据同步与判定（对照控制点清单，不许抽样）②产出新 ReviewIR 与新报告且两者 id 均与旧版不同③旧 ReviewIR 与旧报告仍在盘上且内容逐字节未改；任一不满足即红。

**脚本对应**：`tools/verify_release_gate.py:268-291（F1–F4 仅验 job 状态机）；无重审产物/旧版本保全断言`

**缺什么**：脚本只验重审 job 的状态迁移（queued 合并、running 建 successor、完成回 pending_release、重签 derived_from、幂等），完全没有重审产物：没有 ReviewIR 的 ir_id/ir_version 与旧版不同，没有报告 report_id 与旧版不同，没有「对照控制点清单逐条重跑（非抽样）」、模态提取/依据同步/判定重跑的断言，也没有旧 IR/旧报告仍在盘上且逐字节未改的比对。base/report_store.py 与 base/orchestrator.py 的产物完全不在本脚本的 import/测试范围内。

---

#### #99 —— **partial**（建议回退 `untested`）

**表格原文要点**：失效即建重审任务并自动入队 RL-11：触发失效后，在不施加任何人工操作的前提下重审任务已创建且处于 queued，并已通知相关人；反向对照：不存在「等待人工确认才建任务」的中间态，失效后任务立刻存在。

**脚本对应**：`tools/verify_release_gate.py:250-251（E1–E5 每条断言 res.job 存在且 state==queued）`

**缺什么**：「自动建任务并 queued」已验：E 段每条失效用例在同一 invalidate() 调用返回里断言 job 非空且 state==queued，结构上等价于「不在等人工确认」（F1 :274-276 另验 queued 期间合并同一 job）。但行里的「且相关人已收到通知」没有任何断言：tools/verify_release_gate.py 与 base/release_gate.py 均无 notifications 调用（grep 通知/notify 均 0 命中），base/notifications.py 的 invalidation/auto_rereview 类型未接到失效路径上；也没有显式构造「等人工确认才建任务」的坏样本做反向对照，只是隐含依赖同步返回。

---

#### #102 —— **partial**

**表格原文要点**：连续变化合并与追加，不并行不丢历史（RL-14）：queued 期间连续两次变化 → 合并进同一 job 且 change_set 含两次变化的完整内容（缺一条即红）；running 期间再来一次变化 → 当前 job 完成后自动追加一次全量重审，且两次 job 不并行（时间区间不相交）；历史 job 与各自 change_set 全部保留

**脚本对应**：`F1 tools/verify_release_gate.py:274-276；F2 tools/verify_release_gate.py:280-282；F3/F4 :285-291（间接证明 successor 被提升）`

**缺什么**：① change_set 完整合并没有执行点：F1 只断言 job_created is False + 同一 job_id + len(change_set)>=1。两次变化都改同一个 raw_sha256，_merge 按 field 去重后必然只剩 1 条，len>=1 结构上抓不到「缺一条」。实测把 _merge 换成直接替换（完全不合并）F1 仍为 True，即该断言无法区分「合并」与「替换」。② 不并行没有执行点：全文件没有一行读 started_at/completed_at，F2 只断言 successor 新建、state=queued、job_id 不同；successor 的 change_set 内容与「全量重审」语义也未断言。③ 历史保留没有执行点：没有任何断言读 state()['events'] 或历史 job 列表；state() 只暴露 active_job/successor，complete_job 在有 successor 时把已完成 job 记录丢弃（base/release_gate.py:520-523），只剩 events 里的 job_id/change_set，脚本对此零断言。

---

#### #123 —— **uncovered**（建议回退 `untested`）

**表格原文要点**：撤权影响（TS-20）：(a) 撤权后撤回历史签发必须成功（一次性 SSO + 理由，三项留痕齐全）；(b) 撤权后新签必须被拒；(c) 撤权后原签发人对他人历史签发做撤回必须被拒；且历史签发有效性状态不因撤权而改变（撤权前后逐条比对）

**脚本对应**：`tools/verify_release_gate.py:145-147（A6，撤回成功——非撤权）；tools/verify_release_gate.py:201-203（C5，从未授权者不能签——非撤权后）`

**缺什么**：脚本里没有「撤权」这个对象，三条样本与不变式全部无对应物。① (a) A6 只验「已签发 → 撤回成功」，缺少撤权这个前置状态，也从不读 events，因此「一次性 SSO + 理由 + actor/step_up_ref/reason 三项留痕」无断言。② (b) C5 验的是 capabilities=[] 的 principal 不能签（从未授权），不是撤权后；base/ 下没有 signer_grants/撤权状态机。③ (c) 实现 revoke 的 _authorize（base/release_gate.py:370-388）根本不比对 signer_id，任何持 release.revoke 的同租户/同品线 principal 都能撤回他人签发，脚本没有这个负样本。④ 历史签发有效性不因撤权改变：signatures() 的三处使用（F5 :294-297、H1/H3 :313-319）都与撤权无关，没有撤权前后逐条比对。

---

#### #126 —— **partial**

**表格原文要点**：签发绑定九字段缺一不成立（TS-23）：九个字段逐个删一个，九个反例全部必须红；再喂一条九字段齐全的签发断言成立；反向对照把 used_authority_refs 改成空数组（字段在但没内容）同样必须被拒

**脚本对应**：`B3 tools/verify_release_gate.py:155-160（8 条删除反例）；B2 tools/verify_release_gate.py:151 + B1 :150（正向对照）`

**缺什么**：① 不是九个反例：B3 的 8 条删除里只有 7 条落在九字段上（case_version、ir_id、raw_sha256、rule_snapshot_hash、used_authority_refs、conflict_table_version、signature_version），另 1 条 media_fingerprints_root_hash 属媒体指纹组、不在九字段内；九字段中 text_sha256 与 kb_snapshot（version+hash）一条删除反例都没有，ir_version / rule_snapshot_version / kb_snapshot_version 也从未单独删过。② 反向对照完全缺失：脚本没有任何一处把 used_authority_refs 置成空数组。实测（临时目录导入 base/release_gate.py）sign() 接受空数组、validate_signature 返回 []，即该行要求的「字段在但没内容 → 同样被拒」在当前实现下本来就是红的，脚本没测出来。③ 正向对照（九字段齐全 → 成立）有 B1+B2+A1，这部分是真实覆盖。

---

#### #127 —— **partial**（建议回退 `untested`）

**表格原文要点**：签发记录须含四类媒体产物的独立指纹（抽帧清单/关键帧、OCR、ASR、模型与采样配置，共 6 个字段），任一类变化即自动失效并触发全量重审；反向对照：把四类压成一枚总指纹的样本须报红；失效后须能指出具体是哪一类变化

**脚本对应**：`verify_release_gate.py:150 B1（仅断言 set(SIGNATURE_FIELDS) <= set(sig)）；verify_release_gate.py:155-160 B3（删字段清单不含六枚媒体指纹）；verify_release_gate.py:163-164 B5（仅 media_fingerprints_root_hash 篡改）`

**缺什么**：①核心行为『任一类变化即失效』完全没有验：没有任何断言逐个改动 frame_manifest_hash / keyframe_set_hash / ocr_output_hash / asr_output_hash / model_config_hash / sampling_config_hash 后检查失效；我实测这六者任一变化都返回 invalidated=False / reason=no_change（_changes 只比 media_fingerprints_root_hash，从比这六枚），即实现本身就不满足该行，而脚本仍 54/54 绿。②B3 的逐字段删除反例只覆盖 case_version/ir_id/raw_sha256/rule_snapshot_hash/used_authority_refs/conflict_table_version/media_fingerprints_root_hash/signature_version 八个，六枚媒体逐项指纹一枚都没删过，没验证它们各自必填。③没有『四类压成一枚总指纹』的反向对照：B1 比的是同一模块导出的常量与 sign() 返回值，实现把常量一起改成聚合仍全绿，结构性恒真。④没有媒体类别的失效归因断言：change_set 里从不出现这六类 field（E1–E5 只覆盖 raw/rule/kb/used refs/conflict，属相邻但不等价）。

---

#### #130 —— **partial**（建议回退 `untested`）

**表格原文要点**：媒体集合指纹：Node 与 Python 各算一遍 root SHA-256 并断言逐字节相等；规范化须是 RFC 8785 JCS（含非 ASCII 键、浮点样本与标准向量比对），不是自定义；集合排序键为 kind+stable_id（打乱输入后重算 root 不变）；全仓文档与代码不得称该结构为 Merkle 或不可篡改（静态扫描命中即红）

**脚本对应**：`verify_release_gate.py:165-166 B6（media_root(MEDIA) == media_root(list(reversed(MEDIA)))）`

**缺什么**：①跨语言复算完全没有验：脚本纯 Python、不调用 node，全仓也只有 base/release_gate.py:104-119 一份 media_root 实现，不存在 Node/TS 侧实现或对拍，『两次 root 逐字节相等』无任何断言。②无 RFC 8785 JCS 断言：没有标准向量、没有非 ASCII 键、没有浮点样本；且实现用的 json.dumps(sort_keys=True, ensure_ascii=False, separators=(',',':')) 在浮点序列化与 UTF-16 键序上并非 JCS，脚本对此零检查。③B6 只用两条同 kind 记录做一次反转，无法证明排序键是 (kind, stable_id)——我实测按 sha256 排序时同一反转样本的 root 也完全相等，B6 照样绿，属结构性不足以区分。④没有『Merkle / 不可篡改』静态措辞扫描；仓里 base/release_gate.py:107 与多份规格文档都出现该词，真扫会命中，而脚本无此断言。B5/H2 只验 media root 被篡改就红，是相邻的绑定检查，不等于本行要求的规范化与跨语言可复算。

---

### `tools/verify_normalizer.py`（7 行）

#### #4 —— **partial**

**表格原文要点**：每种内容形态的 IR 双指纹：raw_sha256 与 text_sha256 都存在且为 64 位十六进制；用原件字节重算 raw_sha256、用解析出的正文重算 text_sha256，分别与字段相等；构造缺 raw_sha256 或 text_sha256 的 IR，断言 schema 拒绝。

**脚本对应**：`C7/R3 @ tools/verify_normalizer.py:642（text_sha256 重算）、:646（raw_sha256 仅查 len==64）、:636-638（样本清单只有 free_text/ad_record/image）`

**缺什么**：① 没有「用原件字节重算 raw_sha256」：:646 只判 isinstance(str) 且长度 64，samples 的原始输入（free_text 的 raw_bytes、ad_record 的规范化 JSON、image 的 raw）从未做 sha256 再与 fingerprint.raw_sha256 比对；② 没有「缺 raw_sha256 或 text_sha256 的 IR 被 schema 拒绝」：脚本只读 base/content-unit-v1.schema.json 的顶层 required（:157-161），从不执行 schema 校验，也没有缺指纹字段的负样本；③ 64 位十六进制只判长度，hex 只由生产侧 base/contract.py:606-610 的 H6 在 normalize 内部间接兜住，不是本脚本的独立断言；④「每种内容形态」只覆盖 free_text/ad_record/image，landing_page/structured_json/video 未进入 C7 的 samples（u_lp/u_sj/u_vid 在脚本别处构造，但不在指纹断言里）。

---

#### #5 —— **partial**

**表格原文要点**：各内容形态各取一份，连续两次调用归一化（其间重启进程并清字节码缓存），两次 unit_id 必须相同；再按声明的复算算法从 IR 的原始指纹与来路字段独立重算一次，三个值必须一致；打乱输入提交顺序不得改变结果。

**脚本对应**：`R4 @ tools/verify_normalizer.py:654（同进程两次 unit_id 相同）、:656-671（子进程 + 全新 PYTHONPYCACHEPREFIX 后仍相同）`

**缺什么**：① 只对 free_text 一个样本做稳定性（raw2，:651-671），不是「各内容形态样本各一份」；② 没有独立重算：脚本自身不实现也不调用 unit_id 算法（:232 反而断言 normalizer 内不得出现 `_unit_id`/`hashlib`），「从 IR 的 raw 指纹与来路字段重算」只由生产侧 base/contract.py:627-630 的 H7 在 normalize 内部自校验，属相邻但不等价，不是本脚本的独立重算，也没有「三个值一致」的第三条独立读数；③「打乱输入提交顺序不得改变结果」完全没有，全脚本无任何顺序置换样本。

---

#### #6 —— **partial**

**表格原文要点**：每种形态的 IR 都必须显式带 covers 与 does_not_cover（后者为数组）；构造只含 covers 的缺字段样本与由默认值自动补齐的样本，断言校验器拒绝；源码扫描确认这两个字段没有默认值分支，空数组是合法值、不等于默认值。

**脚本对应**：`C1 @ tools/verify_normalizer.py:177-180（仅 free_text 的 covers/does_not_cover 显式值）、C5/R1 @ :603-616（缺参数、空 covers、类型错 → 拒绝）`

**缺什么**：① 逐形态的键存在性只测了 free_text（:177-180）；ad_record 只查 covers（:195-197），landing_page/structured_json/image/video 均未断言 does_not_cover 键存在且为数组；② 没有「由默认值自动补齐的样本 → 校验器拒绝」：C5 只在 normalize 调用边界测缺参数/类型（抛 TypeError/ValueError），没有把 textification 缺 does_not_cover 的 ContentUnit 交给 validate_unit 断言拒绝——该规则在 base/normalizer.py:364-372 与 base/content-unit-v1.schema.json:110 都存在，但本脚本没有执行点；③ 没有源码扫描「这两个字段无默认值分支」：唯一的源码扫描 :232 查的是 `_unit_id`/`hashlib`，与本行无关；④「空数组是合法值」只被各处 dnc=[] 调用隐式带过，无显式断言（covers=[] 反而在 :606 被拒，与 normalizer 语义一致）。

---

#### #7 —— **partial**

**表格原文要点**：schema 校验 parse_status∈{ok,partial,failed}，failed 时 failure_kind 非 null 且∈{fetch_error,parse_error,empty,unsupported}；failed+null、failed+未知 kind、ok+非空 kind 三个负样本须按 I2/I2/I1 拒收；四种 failed 送入编排器后判定函数不执行、findings 为空、结论落未审查；failed 带 finding 须触发 I5 ERROR。

**脚本对应**：`C0 @ tools/verify_normalizer.py:165-169（取值域用独立字面量对拍）、C6 @ :619-633（三个负样本只断言抛异常）、C4 @ :551-578（四种 failed → judgment_gate.enter=False、can_pass=False、无 ir_id）`

**缺什么**：①「schema 校验」没有：脚本只读 base/content-unit-v1.schema.json 的顶层 required（:157-161），而该 schema 根本没有 parse_status/failure_kind；真正声明这两个域与 failed 条件必填的是 contracts/review-ir-v1.schema.json:46-54 与 :194-198，脚本从未加载或执行它；② 三个负样本只捕 `except Exception`（:627-633），不断言按 I1/I2 拒收，也无法区分「因正确理由拒」与「因别的原因拒」；I1/I2 在 base/decision_table.py:194-197，本脚本不 import 判定表；③「送入编排器」缺失：C4 只调 N.judgment_gate，未经过编排器或判定函数，「判定函数不执行」没有 spy，「findings 为空」「结论落未审查」均无断言（只断言 gate.enter/can_pass 为 False）；④「手工构造 failed 且带 finding → I5 ERROR」完全没有（脚本无 findings 输入路径；I5 在 base/decision_table.py:208-209）。

---

#### #8 —— **partial**（建议回退 `untested`）

**表格原文要点**：partial 只在已覆盖部分判定且永不 PASS（L1-6 / SEC-8-11）：构造 covers 只覆盖文本、不覆盖音轨的视频单元送判定；断言不产生任何音轨类 finding、结论带「覆盖不全」且不是 PASS；再构造落在 covers 声明之外的命中，断言被拒绝；把同一单元改成 full 后才允许 PASS。

**脚本对应**：`C3「partial 可进判定但永不 PASS」@ tools/verify_normalizer.py:542-549（关键比较在 :548：gate.enter is True and gate.can_pass is False）；被测实现是 base/normalizer.py:375-386（partial 分支 :381-383）。C1 @ tools/verify_normalizer.py:186-188 只对另一个 free_text ok 单元断言 can_pass is True。`

**缺什么**：只对上了「永不 PASS」这一句，而且只落在 judgment_gate 这个纯函数上：(1) judgment_gate 全仓零生产调用点——仅 base/normalizer.py:375 定义、本验证器三处调用；真实判定链 judge_entry.py 不使用它，coverage_composer.py:231 反而把 parse_status=partial 直接派生成 coverage_state=missing，所以「partial 可进判定」没有生产执行点证据。(2) 未构造「covers 只覆盖文本、不覆盖音轨」的视频单元送判定：C3 用的是 free_text 单元（:543-544），与行要求无关。(3) 没有 finding 产出路径，无法验「不产生任何音轨类 finding」：normalize 本身不产 finding，C9（:676-687）只断言 unit 里不出现 findings 字段，是另一件事。(4) 全仓 base/ 下没有「覆盖不全」结论串（只有 coverage_composer.py:22 的注释提到该词），脚本也没有任何结论文案断言。(5) 「落在 covers 声明之外的命中被拒绝」既无样本也无实现：covers 只被当成必填字符串列表保存，判定不消费它。(6) 「同一单元改成 full 后才允许 PASS」的对照没有：C1 用的是另一个 unit。

---

#### #10 —— **partial**（建议回退 `untested`）

**表格原文要点**：确定性解析双次正文指纹一致（L1-4a）：固定解析器版本，对同一份纯文本和同一份结构化记录各跑两次（两次之间重启进程并清干净本项目字节码缓存），断言 text_sha256 完全相等；再把解析器版本改一个字符重跑，作为「版本不同不要求相同」的对照。

**脚本对应**：`R4/C8「同输入两次 unit_id 相同」@ tools/verify_normalizer.py:650-655（比较在 :654）；R4「新进程 + 全新 pycache 后 unit_id 仍相同」@ tools/verify_normalizer.py:656-673（比较在 :668-670）。C7/R3 @ :635-648 只是单次运行内 text_sha256 == sha256(text)，不是跨两次运行。`

**缺什么**：缺三半：(1) 比较的量是 unit_id，不是验收行点名的 text_sha256（:654、:668-670）。unit_id 之所以间接受约束，是因为 base/contract.py:328-330 把 text_sha256 算进 unit_id；一旦 unit_id 公式改成不含正文指纹，这条断言会静默失去对正文指纹的约束（C7 只在单次运行内自洽）。(2) 只对 free_text 跑了两次（:651-653、:663-665）。验收行要求「同一份结构化记录」也各跑两次——landing structured_json 只在 :226-229 单跑一次、ad_record 只在 :192-197 单跑一次，均无第二次比对。(3) 「固定解析器版本」无断言，也没有「改解析器版本一个字符后重跑」的对照：脚本 0 处引用解析器版本 / normalization profile / PARSER_VERSION。(4) 这一半是做对的：第二次在子进程里跑，PYTHONPYCACHEPREFIX 指向空临时目录（:656-673），等效于重启进程 + 全新字节码缓存。

---

#### #21 —— **partial**（建议回退 `untested`）

**表格原文要点**：location 三形态可点回原片、帧号与抽帧参数可复算：文本断言 start/end/quote 存在、为整数/非空、origin[start:end]==quote 且缺字段或切片不等则拒绝；图片断言 image_id+bbox 存在、bbox 为长度 4 数组、0≤x1<x2≤1、0≤y1<y2≤1、绝对像素拒绝、按 bbox 在原图裁剪并与 finding 描述一致；视频断言五必填、只有全画面可缺 bbox 而区域断言缺 bbox 拒绝、time 为数字且 end≥start、精度 0.1、从回执读抽帧间隔与偏移独立复算 frame_no 且换参同步、frame_thumb 实读可解码并与重抽帧做感知哈希/人工比对；自然语言位置 schema 必须拒绝。

**脚本对应**：`C2c 段（脚本自称覆盖验收行 21）@ tools/verify_normalizer.py:414-540：C2c-6 独立复算 :474-484、C2c-8 换 interval :496-504、C2c-9/10/11 frame_thumb :516-528；C2b 段 :237-412：C2b-0d 文本 required :252-254、C2b-0e/0f/0g schema 三形态 :255-266、C2b-4 负样本循环 :300-344、C2b-9 直调 _location_problems :374-412；显式未测声明 NOTE :537-540。`

**缺什么**：几何契约大半覆盖，但行里点名要的行为缺五块：(1) 「按 bbox 在原图裁剪、确认裁出区域与 finding 描述一致」未验——验证器自己在 :537-540 的 NOTE 里排除，全仓也无裁图器/媒体管道。(2) 「frame_thumb 与 frame_no 重抽帧做感知哈希或人工比对」未验——同一 NOTE 排除。(3) 「只有全画面断言允许 bbox 缺省，区域断言缺 bbox 则拒绝」缺一半：schema 与 normalizer 都把 bbox 设为可选，没有任何 scope/区域标志；C2c-4（:459-463）只断言全画面可缺省，没有「区域断言缺 bbox」的负样本；base/README.md:111 写了这条规则但没有执行点。(4) 「从回执读取抽帧间隔与起始偏移」未验：验证器把 frame_sampling 直接塞进 raw（video_raw :415-422），生产只读 raw_input['frame_sampling']（base/normalizer.py:447），项目里不存在回执结构；「换抽帧参数后两处读数同步变化」也只在 interval=0.5 做过一次本地独立复算（C2c-6 :480-484），C2c-8 只断言生产输出 48，没有同步复算。(5) frame_thumb「实际发起读取、断言可访问、返回图片可解码」用的是验证器本地 thumb_problems（:61-89、:517-528），生产端只校验非空字符串（base/normalizer.py:178-179），所以这条断言拦不到生产回归；感知哈希/裁剪比对更是完全没有。另有两处口径偏差：(6) 文本「缺任一字段断言拒绝」与 C2c-1（:430-436）的「缺 quote 自动按切片补齐」冲突——只有在直接调用 _location_problems 的 C2b-9（:383）才拒绝，normalize 入口是修复而非拒绝；(7) bbox 的 y1<y2 与 0≤ 下界没有独立负样本（只有 x 方向倒置 C2c-3 :448-451 与零宽），schema 本身也只校验每项 0..1 与长度 4，不校验 x1<x2/y1<y2。

---

---

## 三、这 20 行**不是**同一个病的 20 个样本

同样是 `partial`，原因分三种，修法完全不同：

### ① 脚本验的是「相邻但不等价」的东西（最多的一类）

例：
- **#89** 要「四个交互面各自的越界面」，脚本只测了 **G1** 一个 —— 而且是 Python 侧的
  `apply_machine_patch`，**不是行里点名的「多维表写回」面**
- **#93** 要「名单治理三主体留痕」，脚本的 **C1–C5 是签发 SoD**，与名单治理无关
  （所以 #93 判 `uncovered`：换了个名字但验的不是同一件事）
- **#98** 要「新 IR / 新报告 / 旧版保留」，脚本的 **F1–F6 是重审 job 的状态机** ——
  状态迁移有，**产物一个都没有**

**修法**：补断言，不是改脚本。

### ② 断言存在，但**结构上不可能变红**

- **#92** 要「缺 tenant 或缺 product_line 即红」，脚本**从不构造缺省维度的样本**。
  当前实现会因为 `None != 值` 而拒 —— 但那是**实现的巧合**，
  把实现改成「跳过缺省维度」时，`C3`/`C4` 仍然全绿。

**修法**：补「缺一维度」的坏样本。

### ③ 实现本身违反行文要求（**这不是缺测试，是缺陷**）

这一类我只找到 **1 条**，但它比另外两类严重：

> **#91：「撤回权不随签发权自动获得」**
>
> `base/release_gate.py:306`：
> ```python
> if "release.revoke" not in caps and "release.sign" not in caps:
>     raise SoDViolation("缺少 release.revoke")
> ```
> 判据是「**既无** revoke **又无** sign 才拒」—— 于是**只有签发权的账号也能撤回**。
> 而验收表 #91 明写：「再断言撤回权不随签发权自动获得（只有签发权、无撤回权的账号
> 发起撤回必须被拒）」。

我实测确认：`base/release_gate.py:306` 就是这个判据，而
`tools/verify_release_gate.py:83` 的 `signer()` **默认同时给两个能力**，
所以脚本里**根本不存在**「只有签发权」的样本（`grep -c '"release\.sign"\]'` = **0**）。

**修法**：先把 `base/release_gate.py:306` 的 `and` 改成 `or`（或直接只认 `release.revoke`），
再补样本。**这条要单开票，且优先级高于其余 19 行的一半覆盖** ——
因为其余各行只是「没验到」，这一条是「验到了会红但没人验，而它本身是错的」。

---

## 四、另外两条「断了但不在我这 20 行里」的

审计过程中撞到两处，写在这里因为它们同源：

### ① `verify_decision_table.py` 覆盖 **14 行**（2026-10-23 实测），比派给我的两支都多

```
14 行 ← verify_decision_table.py
        [18, 25, 27, 28, 30, 31, 32, 33, 38, 39, 40, 45, 46, 47]
13 行 ← verify_release_gate.py    ← 本票
 7 行 ← verify_normalizer.py      ← 本票
```

> ★ 我第一次写这段时用的是**更早一次**的读数（当时是 16 行）。
> 写进文档前又跑了一遍，现在是 **14 行** —— 映射表在这半天里被其他会话改过。
> 按 §2.2 第 1 条：**文档里的数字要算出来**，这里补上复现命令与日期。

**它是全仓最大的一处「一行命令验十几行」。** 05 给我的是第二、第四大的两支，
**最大的那支没人审。**

### ② 行 86 的 `untested` 标签是错的（已在 `09f7aca` 里记录）

`untested` 说「缺 test_id / fixture / command」，而 #86 的判据**已建好、15/15 过**，
只是没映射（映射会让棘轮红）。**同一个形状：台账读数 ≠ 实际状态。**

---

## 五、方法上的一条（05 点名的坑，我没重复）

> **不许用 criteria 编号去 grep 脚本源码当判据。**

05 的第一版这么干，报了 94 行失配，全部是假阳性 ——
因为脚本用的是 `C0 四维取值域来自…` 这种**行为命名**，从不出现在编号。

这一轮 12 个 agent 的提示里都写死了这条禁令，并且要求：
**`assertion_ref` 必须给断言编号或 file:line，不给行号的判定不算证据。**

结果是 20 行**全部**给出了具体断言名与行号，没有一条是「编号没出现所以判未覆盖」。

---

## 六、我没做的

- **没改任何脚本、没改验收表**（约束 (a)）
- **没改 `verifier_map`** —— 那 14 行要不要回退 `untested`，是**编排的决定**，不是我的
- **没审 `verify_decision_table.py`**（16 行，最大的那支）—— 不在本票范围

---

## 七、自证

本票是**只读审计**，不产出可执行断言，所以没有「自证绿了」这回事。

我能给的是**可复核性**：

```bash
# 复现 fan-out 读数
python3 -c "
import json, collections
m = json.load(open('tests/acceptance/verifier_map.json'))['rows']
by = collections.defaultdict(list)
for k, v in m.items():
    by[str(v.get('command'))].append(int(k))
for cmd, rows in sorted(by.items(), key=lambda x: -len(x[1]))[:4]:
    print(len(rows), '行 ←', cmd.split('/')[-1])
"

# 复核我举的那条实现缺陷
grep -n 'release.revoke' base/release_gate.py
grep -c '"release\.sign"\]' tools/verify_release_gate.py    # → 0
```
