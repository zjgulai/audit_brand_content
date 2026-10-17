# Momcozy AIGC 标准操作流程 (SOP) v1.0

> **目标**: 标准化AIGC内容生成流程，确保品牌一致性、效率、可追溯性
> **适用角色**: AIGC设计师、品牌经理、内容运营、审核人员
> **配套文档**: 
>   - `momcozy_aigc_brand_semantic_library.md` (品牌语义资产库)
>   - `momcozy_aigc_prompt_templates.md` (Prompt模板系统)
>   - `momcozy_brand_consistency_controls.md` (一致性控制方案)
>   - `momcozy_aigc_version_control.md` (版本管理规范)

---

## 流程总览

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 需求分析  │ → │ 素材准备  │ → │ 生成执行  │ → │ 质量审核  │ → │ 发布归档  │
│  (30min) │    │  (20min) │    │  (60min) │    │  (40min) │    │  (10min) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**单次生成全流程预估时间**: 2.5-3小时 (含审核)
**批量生成(10张)预估时间**: 4-6小时

---

## Step 1: 需求分析 (30分钟)

### 1.1 填写《AIGC内容需求单》

```yaml
需求单模板:

基本需求:
  内容类型: [图片 / 视频 / 文案]
  场景分类: [S1/S2/S3/S4/S5/S6 / V1/V2/V3/V4 / C1/C2/C3]
  产品名称: [具体产品SKU]
  使用渠道: [官网/Amazon/Instagram/TikTok/邮件/广告]
  尺寸比例: [1:1 / 4:5 / 16:9 / 2:1 / 9:16]
  目标受众: [新妈/孕晚期/回购客户/送礼购买者]
  投放时间: [YYYY-MM-DD]

内容策略:
  核心信息: [一句话卖点]
  情感目标: [cozy/breezy/empower/relief/other]
  痛点关联: [具体痛点，如"夜间噪音"]
  行动号召: [Shop Now/Learn More/Join Village]
  竞品参考: [如有，附链接]

品牌约束:
  必须出现: [品牌术语/产品色/包装元素]
  必须避免: [特定场景/人物类型/颜色]
  特殊要求: [如"需留出文案空间"]

审核人:
  设计师: [姓名]
  品牌经理: [姓名]
  市场总监: [姓名] (仅高优先级)
```

### 1.2 选择生成策略

```
决策树:

图片? 
  ├─ 高情感/生活方式 → MJ V7 + sref
  ├─ 高细节/文字渲染 → FLUX 1.1
  ├─ 精细控制/产品一致性 → SD 3.5 + LoRA + IP-Adapter
  └─ 快速概念验证 → MJ V7 (最快)

视频?
  ├─ 品牌广告/高品质 → Sora
  ├─ 产品演示/可控 → Runway Gen-3 (图生视频)
  └─ 社媒短视频/快速 → Pika / Runway

文案?
  ├─ H1标题 → GPT-4 + 品牌词汇表注入
  ├─ 产品描述 → GPT-4 + 利益驱动结构
  └─ 社媒文案 → GPT-4 + UGC风格模板
```

---

## Step 2: 素材准备 (20分钟)

### 2.1 加载品牌资产

```bash
# 检查清单
□ 确认使用最新版Prompt模板 (检查版本号)
□ 加载对应场景的sref URL
□ 确认LoRA模型版本 (如使用SD/FLUX)
□ 准备产品参考图 (如使用IP-Adapter)
□ 确认负面Prompt模板 (如适用)
```

### 2.2 变量填充

使用模板系统中的变量替换：

```
原始模板 (S1-MJ):
"A real mother {MOM_ACTION} in a {SCENE}, 
{PRODUCT_NAME} naturally visible..."

填充后:
"A real mother sipping coffee on an orange velvet armchair 
in a sunlit living room, M5 wearable breast pump 
naturally visible under her cream knit cardigan..."

变量来源:
  - {PRODUCT_NAME} → 产品知识库
  - {COLOR} → 产品设计规格
  - {SCENE} → 品牌场景库
  - {MOM_ACTION} → 用户画像研究
  - {EMOTION} → 品牌情感词表
```

### 2.3 预处理检查

```
□ Prompt长度检查:
    MJ: 建议 < 200 words
    FLUX: 建议 40-50 words (精简)
    SD: 建议 < 300 tokens

□ 品牌合规预检:
    - 是否包含品牌情感词? (cozy/breezy/effortless)
    - 是否避免禁用词? (clinical/machine/should)
    - 色彩描述是否合规? (warm/cream/sage)

□ 技术合规预检:
    - 参数格式是否正确? (--ar, --sref等)
    - LoRA语法是否正确? (<lora:name:weight>)
    - Seed是否设置 (如需要复现)
```

---

## Step 3: 生成执行 (60分钟)

### 3.1 首轮生成 (Seed探索)

```
目标: 找到最佳Seed，探索风格空间

操作:
  1. 使用Prompt + 参数，不指定Seed，生成4-8张
  2. 观察整体风格倾向
  3. 选出最佳1-2张，记录Seed
  4. 如风格偏离，调整sref权重或Prompt

时间: 15-20分钟
```

### 3.2 迭代优化

```
问题 → 解决方案对照表:

┌────────────────────────┬────────────────────────────────────┐
│ 问题                   │ 解决方案                            │
├────────────────────────┼────────────────────────────────────┤
│ 色彩偏冷               │ Prompt增加 "warm golden undertones" │
│                        │ 或提高sref权重 (--sw +50)           │
├────────────────────────┼────────────────────────────────────┤
│ 产品外观不准           │ 增加IP-Adapter权重 (+0.2)           │
│                        │ 或增加产品Prompt权重 (SD: :1.3)     │
├────────────────────────┼────────────────────────────────────┤
│ 过于完美/不自然        │ 增加 "authentic", "imperfect"       │
│                        │ MJ: 降低 --stylize                  │
├────────────────────────┼────────────────────────────────────┤
│ 临床感/机器感          │ 添加负面Prompt: clinical, machine   │
│                        │ Prompt增加: cozy, warm, home        │
├────────────────────────┼────────────────────────────────────┤
│ 文字/水印出现          │ 负面Prompt: text, watermark, logo   │
│                        │ FLUX: 正面强调 "no text"            │
├────────────────────────┼────────────────────────────────────┤
│ 构图不符合要求         │ 增加构图描述词                      │
│                        │ SD: 添加ControlNet (Depth/Canny)    │
└────────────────────────┴────────────────────────────────────┘
```

### 3.3 批量生成

```
确定最佳参数组合后:
  1. 使用固定Seed，生成变体 (±3张)
  2. 或使用Seed范围 (seed+1, seed+2...) 探索微变
  3. 生成目标数量的资产 (通常需求量的150%)

示例 (MJ):
  Prompt... --seed 42 --v 7
  Prompt... --seed 43 --v 7
  Prompt... --seed 44 --v 7
  
  保留最佳3-5张进入审核
```

---

## Step 4: 质量审核 (40分钟)

### 4.1 自动检查 (5分钟)

```bash
# 运行品牌一致性检查脚本 (概念)
python3 brand_consistency_check.py \
  --input ./outputs/batch_20260523/ \
  --config ./brand_config.json \
  --report ./reports/consistency_20260523.json

检查项:
  □ 色彩合规 (暖色调? 饱和度<0.6?)
  □ 禁用元素检测 (clinical? machine?)
  □ 品牌色出现率
  □ 分辨率/尺寸正确
  □ 无水印/文字/Logo
```

### 4.2 人工审核 (25分钟)

**设计师自审清单:**
```
视觉层:
  □ 色彩是否符合品牌? (暖色/低饱和/奶油基调)
  □ 光影是否柔和? (无硬阴影/无过曝)
  □ 产品外观是否准确? (颜色/材质/形状)
  □ 构图是否符合场景规范?

情感层:
  □ 画面传达的情绪是否正面温和?
  □ 是否有"说教感"或"完美主义"?
  □ 人物表情是否自然真实?
  □ 是否有"闺蜜推荐"的亲切感?

叙事层:
  □ 是否隐含"痛点→方案"结构?
  □ 场景是否真实可信?
  □ 是否传递了品牌价值观?

技术层:
  □ 分辨率是否满足渠道要求?
  □ 文件格式是否正确? (PNG/JPG/WebP/MP4)
  □ 是否有压缩伪影?
```

**品牌经理审核清单:**
```
品牌合规:
  □ 是否包含品牌情感词? (cozy/breezy)
  □ 是否避免禁用词/禁用概念?
  □ 品牌术语使用是否正确? (DoubleFit™, Cozy Tech™)
  □ 是否符合品牌叙事风格? (平视视角/不评判)
  □ 竞品差异是否明显? (非通用母婴图)

法律合规:
  □ 人物肖像是否可商用? (AI生成=无肖像权问题)
  □ 是否有误导性声明?
  □ 医疗/健康声明是否合规?
```

### 4.3 反馈与修正

```
审核结果处理:

通过 → 标记 "approved" → 进入发布流程
有条件通过 → 标记 "approved_with_notes" → 记录备注
驳回 → 标记 "rejected" → 记录原因 → 返回Step 3.2

常见驳回原因:
  1. 色彩偏离品牌 (35%)
  2. 产品外观不准确 (25%)
  3. 情感调性不符 (20%)
  4. 构图/尺寸错误 (15%)
  5. 其他 (5%)
```

---

## Step 5: 发布归档 (10分钟)

### 5.1 输出命名与归档

```
命名规范:
  {品牌}_{场景}_{产品}_{用途}_{版本}_{seed}.{格式}

示例:
  momcozy_S1_Hero_M5_WebsiteHero_1.3.2_seed42.png
  momcozy_S4_Banner_Bundle_EmailHeader_1.3.2_seed88.jpg
  momcozy_V1_Demo_M5_TikTok_1.3.2_seed15.mp4

归档路径:
  /Momcozy/aigc_assets/outputs/{YYYY-MM}/{YYYY-MM-DD}/
```

### 5.2 元数据记录

```json
{
  "output_id": "momcozy_S1_Hero_M5_WebsiteHero_1.3.2_seed42",
  "prompt_version": "1.3.2",
  "generation_date": "2026-05-23",
  "model": "Midjourney V7",
  "full_prompt": "...",
  "parameters": {"ar": "4:5", "sref": "SA-01", "sw": 150},
  "seed": 42,
  "review_status": "approved",
  "reviewer": "Jane Doe",
  "usage": {
    "channel": "Website",
    "page": "M5 Product Page",
    "position": "Hero Banner",
    "live_date": "2026-05-25"
  },
  "performance": {
    "impressions": null,
    "ctr": null,
    "conversion": null
  }
}
```

### 5.3 渠道交付

```
交付清单:

Website:
  □ WebP格式 (优先) 或压缩JPG
  □ 响应式尺寸: 1920x, 1280x, 768x, 480x
  □ Alt text按SEO规范

Amazon:
  □ 白底图: 纯白色RGB(255,255,255)
  □ 主图: 1000x1000+ 像素
  □ 副图: 按Amazon规范

Instagram:
  □ Feed: 1080x1350 (4:5)
  □ Story: 1080x1920 (9:16)
  □ Reels: 1080x1920, < 90s

TikTok:
  □ 1080x1920 (9:16)
  □ < 60s (最佳15-30s)
  □ 包含字幕空间
```

---

## 特殊情况处理

### 紧急需求流程 (Hotfix)

```
触发条件: 24小时内需要上线的紧急需求

简化流程:
  Step 1: 口头确认需求 (10min) ← 跳过书面需求单
  Step 2: 使用现有模板直接填充 (10min) ← 跳过素材准备
  Step 3: 生成2-3张快速选择 (20min) ← 减少迭代
  Step 4: 设计师+品牌经理快速审核 (15min) ← 单人审核
  Step 5: 直接交付 (5min) ← 事后补录元数据

总时间: 约60分钟
风险: 品牌一致性可能降低，需事后复盘
```

### 失败重试流程

```
生成失败类型:

类型A: 输出质量不达标 (画面崩坏/产品变形)
  → 增加负面Prompt权重
  → 降低CFG scale (SD)
  → 更换Seed
  → 如多次失败，检查模型/LoRA兼容性

类型B: 品牌一致性不达标 (色彩/情感偏离)
  → 调整sref权重
  → 强化Prompt中的品牌色彩词
  → 增加Style LoRA权重
  → 如仍不达标，检查sref是否过期

类型C: 技术失败 (API错误/超时)
  → 重试3次
  → 切换备用模型
  → 记录错误日志
```

---

## 常见问题 FAQ

**Q: 同一产品需要多少张不同场景的图?**
A: 建议每个产品至少6张: S1(首屏)+S2(白底)+S3(信息图)×2(不同卖点)+S5(包装)+S6(UGC)

**Q: sref多久更新一次?**
A: 建议每季度审查一次，当品牌视觉方向调整时立即更新。

**Q: 如何确保多人协作时的一致性?**
A: 强制使用统一Prompt模板版本，所有生成必须通过品牌一致性检查脚本。

**Q: AI生成图是否可以完全替代拍摄?**
A: 当前阶段: Hero图建议保留30%实拍 (信任感)，产品白底图可100%AI，UGC建议混合。

**Q: 如何处理季节性/节日内容?**
A: 基于基础模板创建节日变体，保留品牌核心元素(色彩/情感)，添加季节限定变量。

---

## 附录B: 自动化工具使用指南

### B1: sref标杆图智能筛选器

**脚本**: `Brand_Data_Lake/scripts/momcozy_sref_selector.py`

**用途**: 当品牌图库新增图片时，自动筛选符合品牌DNA的标杆图

**执行**:
```bash
cd Brand_Data_Lake
python3 scripts/momcozy_sref_selector.py
```

**输出**:
- `Momcozy/sref_candidates/` — 候选图 (按场景分类)
- `Momcozy/momcozy_sref_candidate_report.json` — 完整分析报告

**何时使用**:
- 季度sref资产更新
- 新增SKU后补充品牌图库
- 品牌视觉方向调整后重新筛选

### B2: LoRA训练数据集自动准备

**脚本**: `Brand_Data_Lake/scripts/momcozy_prepare_lora_dataset.py`

**用途**: 从sref_candidates自动准备标准格式的LoRA训练数据

**执行**:
```bash
cd Brand_Data_Lake

# SD 3.5数据集
python3 scripts/momcozy_prepare_lora_dataset.py \
  --source ../Momcozy/sref_candidates \
  --output ../Momcozy/lora_training_data \
  --model sd35 \
  --max-per-scene 8

# FLUX数据集
python3 scripts/momcozy_prepare_lora_dataset.py \
  --source ../Momcozy/sref_candidates \
  --output ../Momcozy/lora_training_data \
  --model flux \
  --max-per-scene 6
```

**输出**:
- `Momcozy/lora_training_data/sd35/` — 42张PNG (1024×1024) + Caption
- `Momcozy/lora_training_data/flux/` — 34张PNG (1024×1024) + 详细Caption
- `_manifest.json` — 完整清单

**后续步骤**:
1. 人工审核Caption质量
2. 修改 `.toml` 配置文件中的 `image_dir` 路径
3. 启动Kohya_ss / ai-toolkit 训练

---

## 流程优化建议

| 优化项 | 当前时间 | 优化后 | 方法 |
|:---|:---|:---|:---|
| 需求分析 | 30min | 15min | 标准化需求单模板 |
| 素材准备 | 20min | 10min | 预填充变量库 + 自动化脚本 |
| 生成执行 | 60min | 40min | Seed库复用 + LoRA风格锁定 |
| 质量审核 | 40min | 20min | 自动化预检脚本 |
| **总计** | **150min** | **85min** | **效率提升43%** |

---

## 相关文档索引

| 文档 | 用途 | 查看时机 |
|:---|:---|:---|
| `momcozy_aigc_execution_roadmap.md` | 项目执行路线图 | **每日工作开始前** |
| `momcozy_aigc_asset_package_index.md` | 资产总索引 | 需要查找具体模板时 |
| `momcozy_aigc_prompt_templates.md` | Prompt模板 | 每次生成前 |
| `momcozy_brand_consistency_controls.md` | 一致性控制 | 遇到品牌偏差问题时 |
| `momcozy_aigc_version_control.md` | 版本管理 | 提交资产/发布前 |
| `momcozy_aigc_test_prompts_m5.md` | 测试Prompt | 首次测试/培训新人 |

---

*SOP版本: v1.1 | 2026-05-23 | 更新: 新增自动化工具指南*
*配套执行路线图: momcozy_aigc_execution_roadmap.md*
