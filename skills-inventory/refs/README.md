# refs/ — 关键技能原文留档

本目录存放 18 个与本项目（Momcozy 品牌内容审计 Agent）直接相关的第三方技能**原文**，供后续只读参考。

- **只读引用的第三方材料，不是本项目的产物**。请勿在本目录内改编后直接当自研资产使用。
- 所有文件均从原始压缩包/目录**逐字节复制**，未做任何改写、合并或格式转换。
- 每个技能一个子目录，目录内保持原压缩包中的**相对路径结构**（MinMaxDesign 系技能带一层同名父目录）。

## 一、来源与许可状态

| 留档目录 | 原始路径（仓内） | 来源 | 许可状态 | 文件数 |
|---|---|---|---|---|
| `seo-content-audit/` | `skills/Manus/skill01/seo-content-audit.skill` | Manus | **未声明**（frontmatter 无 `license`，包内无 LICENSE 文件） | 4 |
| `copy-editing/` | `skills/Manus/skill01/copy-editing.skill` | Manus | **未声明** | 5 |
| `brand-docx/` | `skills/Manus/skill01/brand-docx.skill` | Manus | **未声明** | 11 |
| `blog-factcheck/` | `skills/Manus/skill01/blog-factcheck.skill` | Manus | MIT（frontmatter `license: MIT`） | 1 |
| `agentic-eval/` | `skills/Manus/skill01/agentic-eval.skill` | Manus | **未声明** | 1 |
| `legal-risk-assessment/` | `skills/Manus/skill01/legal-risk-assessment.skill` | Manus | **未声明** | 1 |
| `iflytek-text-proofread/` | `skills/Manus/skill01/iflytek-text-proofread.skill` | Manus | **未声明**（含讯飞开放平台 API 依赖，见 `SKILL.md` 与 `_meta.json`） | 4 |
| `brand-ad/` | `skills/MinMaxDesign/brand-ad.zip` | MiniMax Design | **未声明** | 11 |
| `video-deconstruct/` | `skills/MinMaxDesign/video-deconstruct.zip` | MiniMax Design | **未声明** | 3 |
| `video-deconstruct-analyzer/` | `skills/MinMaxDesign/video-deconstruct-analyzer.zip` | MiniMax Design | **未声明** | 5 |
| `video-transcript/` | `skills/MinMaxDesign/video-transcript.zip` | MiniMax Design | **未声明** | 2 |
| `subtitle-correction/` | `skills/MinMaxDesign/subtitle-correction.zip` | MiniMax Design | **未声明** | 5 |
| `social-caption/` | `skills/MinMaxDesign/social-caption.zip` | MiniMax Design | **未声明** | 2 |
| `ecommerce-image/` | `skills/MinMaxDesign/ecommerce-image.zip` | MiniMax Design | **未声明** | 20 |
| `koc-video/` | `skills/MinMaxDesign/koc-video.zip` | MiniMax Design | **未声明** | 7 |
| `compliance-review-planner/` | `skills/kimi/skills/compliance-review-planner/` | Kimi | MIT（`LICENSE` 文件 + frontmatter） | 2 |
| `tos-risk-checker/` | `skills/kimi/skills/tos-risk-checker/` | Kimi | MIT（`LICENSE` 文件 + frontmatter） | 2 |
| `weighted-scoring/` | `skills/kimi/skills/weighted-scoring/` | Kimi | MIT（`LICENSE` 文件 + frontmatter） | 2 |

合计 **18 个技能 / 88 个文件**。其中 **15 个许可未声明**，3 个为 MIT。

> 「未声明」= 该压缩包/目录内既无 `license` frontmatter 字段，也无 `LICENSE`/`LICENSE.txt` 文件。这不等于「无版权」；在对外交付或商用前需另行确权。

## 二、复现方式

这些原文来自 `/tmp` 下的工作副本（因原始文件存在读取异常，见下），复制命令等价于：

```bash
# Manus .skill / .zip
unzip -o /tmp/m1/<name>.skill -d refs/<name>/
unzip -o /tmp/m2/<name>.zip   -d refs/<name>/
# MinMaxDesign .zip
unzip -o /tmp/mm2/<name>.zip  -d refs/<name>/
# Kimi / MinMax 为普通目录，直接复制
cp -R skills/kimi/skills/<name>/. refs/<name>/
```

**注意**：`skills/Manus/skill02/` 与 `skills/MinMaxDesign/` 下的全部 442 个压缩包存在读取异常（详见主报告 §2「格式真相」第 3 条）——直接 `readFileSync` / `od` / `md5` 读出的是乱码头部（如 `887d1c8d`），`unzip` 也无法定位中央目录。**必须先 `cp` 到 `/tmp` 或工作区临时目录，对副本操作才可靠。** 本目录中的文件均已按此方式取得。

## 三、留档内容的看点（择要）

- `seo-content-audit/templates/verdict.md` — 现成的三档裁决模板（PUBLISH / PUBLISH WITH FIXES / NO PUBLISH）
- `seo-content-audit/references/core-eeat.md` — 60 项评分细则
- `brand-docx/reference/profile-schema.md` + `reference/idoc.schema.json` — 品牌档案的字段级 schema
- `copy-editing/evals/evals.json` — 带正负样例的评测集（全库罕见）
- `brand-ad/references/adsqa-target-answers.md` — 广告问答式合规靶向层
- `video-deconstruct-analyzer/references/report-template.md` — 视频拆解报告模板
- `ecommerce-image/references/categories/05-baby.md` — 母婴品类专章（全库仅此一处把母婴当独立品类处理；`ecommerce-design.zip` 内有同名同源文件，未留档）
- `ecommerce-image/references/platform-specs.md` — Amazon/Shopify/TikTok Shop/IG Shop 等平台图片规范
- `koc-video/references/creator-direction.md` + `hook-decision.md` — KOC/达人内容的归属与钩子判定
- `subtitle-correction/scripts/subtitle_tool.py` — 时间轴保持校验 + diff 报告工具
