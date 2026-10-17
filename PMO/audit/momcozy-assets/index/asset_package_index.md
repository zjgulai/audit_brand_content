# Momcozy AIGC 数据资产包 v1.0

> **项目**: Momcozy AIGC Prompt 深度优化
> **版本**: v1.2
> **生成日期**: 2026-05-23
> **覆盖范围**: 6图片场景 × 3模型 + 4视频类型 + 3文案调性 + 2喂养电器专项视频
> **核心目标**: 建立可复用、可扩展、品牌一致的AIGC生产系统

---

## 资产包结构

```
Momcozy/
├── CLAUDE.md                              ← AI协作指南 (现有)
├── momcozy_aigc_brand_semantic_library.md  ← Phase 1 品牌语义资产库
├── momcozy_aigc_prompt_templates.md        ← Phase 2 结构化Prompt模板
├── momcozy_brand_consistency_controls.md   ← Phase 3 一致性控制方案
├── momcozy_aigc_version_control.md         ← Phase 4 版本管理规范
├── momcozy_aigc_sop.md                     ← Phase 4 标准操作流程
├── momcozy_aigc_execution_roadmap.md       ← 项目执行路线图
└── momcozy_aigc_asset_package_index.md     ← 本文件 (资产总索引)

[配套支撑文件]
├── momcozy_design_tokens.json              ← 设计令牌 (现有)
├── momcozy_product_moat.json               ← 产品护城河 (现有)
├── momcozy_pdp_blueprint.md                ← PDP蓝图 (现有)
├── momcozy_ui_vars.css                     ← UI变量 (现有)
└── momcozy_quick_reference.md              ← 快速参考 (现有)
```

---

## 资产清单

### Phase 1: 品牌语义资产库

**文件**: `momcozy_aigc_brand_semantic_library.md`

| 资产项 | 内容 | 状态 |
|:---|:---|:---|
| 品牌色彩DNA | 主色/辅色/测量主导色/色温规范 | ✅ 已提取 |
| 风格锚点 | 光影/构图/材质/情绪指标 | ✅ 已定义 |
| 品牌词汇表 | Do's/Don'ts/禁用词/必用词 | ✅ 已建立 |
| 情感光谱 | 7级情感映射 + 微型叙事公式 | ✅ 已构建 |
| 负面Prompt库 | 3层级负面词表 (通用/品牌/场景) | ✅ 已整理 |
| 模型策略 | MJ/FLUX/SD 各模型适配指南 | ✅ 已制定 |

### Phase 2: 结构化Prompt模板

**文件**: `momcozy_aigc_prompt_templates.md`

| 类别 | 场景/类型 | 模板数 | 状态 |
|:---|:---|:---:|:---|
| **图片** | S1 Hero Lifestyle 首屏情感锚点 | 3 (MJ/FLUX/SD) | ✅ |
| **图片** | S2 白底产品图 | 3 (MJ/FLUX/SD) | ✅ |
| **图片** | S3 详情信息图/功能解剖 | 3 (MJ/FLUX/SD) | ✅ |
| **图片** | S4 营销Banner | 3 (MJ/FLUX/SD) | ✅ |
| **图片** | S5 包装/开箱图 | 3 (MJ/FLUX/SD) | ✅ |
| **图片** | S6 UGC真实感/社媒内容 | 3 (MJ/FLUX/SD) | ✅ |
| **视频** | V1 产品演示视频 | 2 (MJ+Runway/Sora) | ✅ |
| **视频** | V2 UGC/测评视频 | 1 (Sora/Runway) | ✅ |
| **视频** | V3 品牌广告视频 | 1 (Sora/Runway) | ✅ |
| **视频** | V4 社媒短视频(Reels/Shorts) | 1 (Sora/Runway/Pika) | ✅ |
| **文案** | C1 H1首屏标题 | 1 (GPT-4) | ✅ |
| **文案** | C2 产品描述文案 | 1 (GPT-4) | ✅ |
| **文案** | C3 社媒文案(UGC风格) | 1 (GPT-4) | ✅ |

**模板变量系统**: 14个核心变量，覆盖产品/场景/动作/情感/文案
**负面Prompt总库**: 按模型分类，含品牌专用禁用词
**参数速查表**: 3模型 × 6场景的完整参数配置

### Phase 3: 一致性控制方案

**文件**: `momcozy_brand_consistency_controls.md`

| 控制维度 | 技术手段 | 实施状态 |
|:---|:---|:---|
| 基础一致性 | 色彩DNA锚点 + 光影规范 + 构图规则 | ✅ 已定义 |
| 风格一致性 | MJ sref / FLUX Style LoRA / SD Identity+Style LoRA | ✅ 已规划 |
| 产品一致性 | IP-Adapter (SD/FLUX) / MJ --cref | ✅ 已规划 |
| 色彩一致性 | 色彩锚点系统 + 自动化验证脚本(概念) | ✅ 已设计 |
| 叙事一致性 | 情感词汇表强制执行 + 微型叙事结构 | ✅ 已制定 |
| 跨模型测试 | 标准化测试矩阵 + 对比工作流 | ✅ 已设计 |
| 一致性检查 | 生成前/后检查清单 + 自动化脚本(概念) | ✅ 已设计 |

**技术栈推荐**: 7个工具/平台，含兼容矩阵

### Step 6: sref 标杆图智能筛选 (新增)

**脚本**: `Brand_Data_Lake/scripts/momcozy_sref_selector.py`

| 指标 | 结果 |
|:---|:---|
| 扫描总量 | 185张品牌图片 |
| 有效分析 | 185张 (100%) |
| 入选标杆 | **58张** (6分类) |

**分类结果**:

| 场景类型 | 候选数 | 入选 | 均分 | sref用途 |
|:---|:---:|:---:|:---:|:---|
| SA-01 Lifestyle | 49 | 12 | 100.0 | 首屏情感锚点 |
| S2 白底产品 | 44 | 12 | 99.2 | 电商主图 |
| SA-02/03 信息图/Banner | 56 | 12 | 100.0 | 详情页/营销Banner |
| S5 包装开箱 | 6 | 6 | 99.2 | 开箱信任区 |
| S6 UGC真实感 | 4 | 4 | 81.8 | 社媒内容 |
| 其他 | 26 | 12 | 92.5 | 补充参考 |

**筛选标准** (基于品牌DNA):
- 色温: 4000K-6500K (最佳4500K-6000K)
- 饱和度: < 0.60 (低-中饱和)
- 亮度: 0.35-0.80
- 对比度: < 0.45 (低对比)
- 暖色比例: > 45%

**输出文件**:
- `Momcozy/sref_candidates/` — 58张候选图 (已复制+重命名)
- `Momcozy/momcozy_sref_candidate_report.json` — 完整元数据报告

### Step 7: LoRA 训练配置与数据集 (新增)

**配置文件**: `Momcozy/lora_training_configs/`

| 配置 | 模型 | Rank | 训练步数 | 用途 |
|:---|:---|:---:|:---:|:---|
| `sd35_identity_lora.toml` | SD 3.5 Medium | 16 | 3500 | 品牌身份锁定 |
| `flux_style_lora.toml` | FLUX.1-dev | 16 | 2000 | 品牌风格锁定 |

**数据集**:

| 模型 | 图片数 | 来源 | Caption | 状态 |
|:---|:---:|:---|:---:|:---|
| SD 3.5 | 42张 | sref_candidates top | 自动生成 | ✅ 就绪 |
| FLUX | 34张 | sref_candidates top | 自动生成(详细版) | ✅ 就绪 |

**自动化脚本**: `Brand_Data_Lake/scripts/momcozy_prepare_lora_dataset.py`
- 自动调整尺寸为1024×1024
- 自动生成分场景Caption
- 支持 `--model sd35` 或 `--model flux`
- 输出manifest.json

**训练准备状态**:
```
□ 训练图片已准备 (42张 SD / 34张 FLUX)
□ Caption已生成 (需人工审核微调)
□ .toml配置文件已创建
□ ⏳ 需修改配置中的路径并启动训练
```

### Step 8: 喂养电器品类 AIGC 视频专项方案 (新增, 2026-05-23)

**文件**: `Momcozy/momcozy_feeding_appliances_aigc_solution.md`

| 产品 | Image 2.0 故事板 | 关键帧 | Seedance 视频 | 剪辑方案 |
|:---|:---:|:---:|:---:|:---:|
| **暖奶器** (Bottle Warmer) | 12张 Prompt | 5张 Enhanced | 5段运动Prompt | ✅ 含Timeline |
| **消毒器** (Sterilizer Bags) | 12张 Prompt | 5张 Enhanced | 5段运动Prompt | ✅ 含Timeline |

**工作流**: Image 2.0 (12宫格故事板 → 5关键帧) → Seedance 2.0 (图生视频) → 剪映 (后期)

**额外交付**:
- Image 2.0 技术参数指南 (生成设置/中文Prompt技巧/负面库)
- Seedance 2.0 技术参数指南 (镜头运动词汇表/运动幅度/首尾帧)
- 品牌一致性规范 (跨产品统一视觉 + 差异化对照)
- 执行检查清单 (4层检查: 执行前/生成后/视频后/剪辑后)
- 产出清单 (标准文件夹命名规范)

**预计产出时间**: 4-7小时产出2条15-20秒成品视频

### Phase 4: 版本管理与SOP

**文件**: `momcozy_aigc_version_control.md` + `momcozy_aigc_sop.md`

| 系统 | 内容 | 状态 |
|:---|:---|:---|
| 版本号规则 | SemVer (Major.Minor.Patch) | ✅ |
| 资产ID规范 | 品牌_类型_场景_版本_日期 | ✅ |
| 4类资产管理 | Prompt / sref / LoRA / Output | ✅ |
| 三级环境 | DEV / STAGING / PROD | ✅ |
| Seed缓存 | Seed注册表 + 复现检查清单 | ✅ |
| 协作工作流 | Git分支模型 + 审批矩阵 | ✅ |
| SOP全流程 | 5步标准流程 (2.5-3h/次) | ✅ |
| 需求单模板 | YAML格式标准化需求 | ✅ |
| 质量审核 | 自动检查 + 人工双层审核 | ✅ |
| 紧急流程 | Hotfix简化流程 (60min) | ✅ |

---

## 验证清单

### 品牌一致性验证

```
□ 所有模板是否包含至少1个品牌情感词?
□ 所有模板是否避免禁用词列表?
□ 色彩描述是否符合品牌色板 (warm/cream/blush/sage)?
□ 光影描述是否符合规范 (soft diffused/low contrast)?
□ 负面Prompt是否包含品牌调性负面词?
□ 叙事结构是否隐含"痛点→方案→情感回报"?
□ 品牌术语是否正确使用 (DoubleFit™, Cozy Tech™)?
```

### 技术完整性验证

```
□ 6图片场景 × 3模型 = 18个Prompt模板是否完整?
□ 4视频类型是否都有对应Prompt?
□ 3文案调性是否都有对应模板?
□ 参数速查表是否覆盖所有场景?
□ 负面Prompt是否按模型分类?
□ 版本管理规范是否覆盖4类资产?
□ SOP是否包含5个完整步骤?
```

### 可操作性验证

```
□ 模板变量是否可实际替换?
□ 示例Prompt是否可直接复制使用?
□ sref使用规范是否清晰?
□ LoRA训练参数是否具体?
□ 审核清单是否可实际执行?
□ 归档命名规范是否无歧义?
```

---

## 快速启动指南

### 5分钟上手

```bash
# 1. 确认当前使用的Prompt模板版本
cat momcozy_aigc_prompt_templates.md | grep "v[0-9]"

# 2. 根据需求选择场景
# 需要首屏大图? → 查找 S1 Hero Lifestyle
# 需要Amazon主图? → 查找 S2 白底产品图
# 需要TikTok视频? → 查找 V4 社媒短视频

# 3. 选择模型并复制对应模板
# MJ最快 / FLUX最细节 / SD最可控

# 4. 替换变量 (参考模板变量说明)
# {PRODUCT_NAME} → "M5 Breast Pump"
# {COLOR} → "dusty rose pink"
# {SCENE} → "sunlit living room"

# 5. 加载sref (MJ) 或 LoRA (SD/FLUX)
# 复制对应的sref URL 或确认LoRA已加载

# 6. 生成 → 审核 → 发布
# 参考 SOP Step 3-5
```

### 典型工作流示例

**场景**: 为M5吸奶器生成官网首屏Hero图

```
Step 1: 打开 momcozy_aigc_prompt_templates.md
Step 2: 找到 S1 Hero Lifestyle → S1-MJ (MJ V7)
Step 3: 复制模板，替换变量:
  {PRODUCT_NAME} → "M5 wearable breast pump"
  {COLOR} → "dusty rose pink"
  {SCENE} → "sunlit living room"
  {MOM_ACTION} → "sipping coffee on an orange velvet armchair"
  {EMOTION} → "relief"
Step 4: 添加参数:
  --ar 4:5 --sref [SA-01_URL] --sw 150 --stylize 250 --style raw --c 0.3 --v 7
Step 5: 生成4张，选择最佳，记录Seed
Step 6: 运行品牌一致性检查
Step 7: 审核通过 → 命名归档 → 交付官网
```

---

## 后续优化建议

### 短期 (1-2周)

```
□ 生成首批10张测试图 (S1-S6各1-2张)，验证模板有效性
□ 从Momcozy品牌图库精选30张风格标杆图，建立sref资产
□ 训练首批LoRA (SD Identity + FLUX Style)
□ 完成跨模型对比测试，记录一致性数据
□ 根据测试结果优化Prompt模板 (v1.0.1)
```

### 中期 (1-2月)

```
□ 训练场景专用Style LoRA (生活方式/产品/信息图)
□ 建立自动化品牌一致性检查脚本
□ 完成品牌识别盲测 (目标≥70%)
□ 建立季度sref更新机制
□ 扩展到其他产品系列 (全SKU覆盖)
```

### 长期 (持续)

```
□ 跟踪AI模型更新，适配MJ V8 / FLUX 2 / SD 4
□ 建立AIGC资产性能追踪系统 (CTR/转化率)
□ 开发内部AIGC生成平台 (集成Prompt+审核+发布)
□ 探索多模态生成 (图文同步/视频+文案)
□ 建立AIGC内容库的全生命周期管理
```

---

## 联系与维护

| 角色 | 职责 | 交付物 |
|:---|:---|:---|
| AIGC设计师 | Prompt开发、生成执行、质量把控 | 生成资产 |
| 品牌经理 | 品牌合规审核、调性把控 | 审核意见 |
| Prompt工程师 | 模板优化、LoRA训练、技术实现 | 技术方案 |
| 市场总监 | 战略方向、最终审批 | 决策 |

**文档维护周期**: 每月审查，每季度重大更新
**下次评审日期**: 2026-06-23

---

## 项目统计

```
文档产出:
  - 核心文档: 6份 (约 80,000+ 字符)
  - Prompt模板: 21个 (图片18 + 视频4 + 文案3)
  - 风格锚点: 3类 (SA-01/02/03)
  - 变量系统: 14个核心变量
  - 负面Prompt: 3层级 × 多场景
  - 参数配置: 3模型 × 6场景 = 18组
  - 审核清单: 生成前7项 + 生成后7项
  - SOP步骤: 5步标准流程 + 2种特殊流程

覆盖范围:
  - 图片场景: 6个
  - 视频类型: 4个
  - 文案调性: 3个
  - AI模型: 3个 (MJ/FLUX/SD)
  - 视频平台: 3个 (Runway/Sora/Pika)
  - 执行阶段: 4个 (Phase A/B/C/D)
  - 里程碑: 7个 (M1-M7)
```

---

## 新增执行层文档

| # | 文档 | 用途 | 关联 |
|:---:|:---|:---|:---|
| 22 | `momcozy_aigc_execution_roadmap.md` | **项目执行路线图** | 4阶段详细计划、里程碑、资源、风险 |

> **路线图核心时间线**:
> - **Week 1**: sref URL获取 → LoRA训练 → 模型验证
> - **Week 2**: 全场景90张测试 → 品牌盲测 → 生产基线
> - **Week 3-4**: 自动化脚本 → 全SKU覆盖 → 视频内容
> - **Month 2+**: 数据追踪 → 模型迭代 → 平台扩展

---

*资产包版本: v1.1 | 2026-05-23 | Momcozy AIGC Deep Optimization Project*
*本资产包基于对Momcozy 185张图片 + 57个视频的媒体DNA分析构建*
*新增执行路线图 + 自动化工具产出 + sref/LoRA工程化资产*
