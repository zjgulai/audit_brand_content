# Momcozy AIGC Prompt 版本管理规范 v1.0

> **目标**: 确保所有AIGC生成资产可追溯、可复现、可协作
> **适用范围**: Prompt模板、sref资产、LoRA模型、生成参数、输出资产

---

## 版本号规则

### 语义化版本 (SemVer)

```
格式: {major}.{minor}.{patch}

示例: 1.3.2

Major (主版本): 
  - 品牌视觉战略重大调整
  - 新模型适配 (如 MJ V7 → V8)
  - 品牌色/字体/调性变更
  - 触发条件: 业务层决策
  
Minor (次版本):
  - 新增场景模板
  - 新增模型支持
  - sref/LoRA资产更新
  - 触发条件: 月度迭代
  
Patch (修订版本):
  - Prompt微调优化
  - 参数调整
  - Bug修复
  - 触发条件: 日常优化
```

### 资产ID命名规范

```
{品牌}_{资产类型}_{场景}_{版本}_{日期}

资产类型:
  PROMPT    = Prompt模板
  SREF      = Style Reference图片
  LORA      = LoRA模型文件
  OUTPUT    = 生成输出图/视频
  PARAM     = 参数配置文件

示例:
  momcozy_PROMPT_S1_Hero_1.3.2_20260523
  momcozy_SREF_SA01_Lifestyle_1.2.0_20260515
  momcozy_LORA_Identity_R16_1.1.0_20260520
  momcozy_OUTPUT_S1_M5_Hero_1.3.2_seed_42_20260523
```

---

## 资产分类与版本管理

### 1. Prompt模板版本管理

```
存储路径: /Momcozy/aigc_assets/prompts/

文件命名:
  momcozy_prompt_S1_Hero_MJ_v1.3.2.md
  momcozy_prompt_S1_Hero_FLUX_v1.3.2.md
  momcozy_prompt_S1_Hero_SD_v1.3.2.md

变更日志 (Changelog):
  ## [1.3.2] - 2026-05-23
  ### Changed
  - S1-MJ: 调整 --sw 从150→180 (增强风格锁定)
  - S1-FLUX: 补充色彩描述 (加入sage green)
  ### Fixed
  - S3-SD: 修复负面Prompt语法错误
  
  ## [1.3.1] - 2026-05-20
  ### Added
  - S6场景UGC模板 (新场景)
  ### Changed
  - 通用负面Prompt增加"fluorescent"
```

### 2. sref资产版本管理

```
存储路径: /Momcozy/aigc_assets/sref/

结构:
  sref/
  ├── SA01_Lifestyle/
  │   ├── v1.0.0_20260501/
  │   │   ├── reference_01.jpg
  │   │   ├── reference_02.jpg
  │   │   └── metadata.json
  │   └── v1.1.0_20260523/
  │       ├── reference_01.jpg (更新)
  │       ├── reference_03.jpg (新增)
  │       └── metadata.json
  ├── SA02_Infographic/
  └── SA03_BrandVisual/

metadata.json 格式:
{
  "version": "1.1.0",
  "date": "2026-05-23",
  "author": "AIGC Team",
  "type": "SA01_Lifestyle",
  "description": "生活方式情感锚点风格参考",
  "images": [
    {
      "filename": "reference_01.jpg",
      "source": "Brand photo library #BB-2024-0892",
      "mj_url": "https://...",
      "color_temp": "5200K",
      "dominant_colors": ["#B47C80", "#E8E0D4"],
      "tags": ["lifestyle", "warm", "natural_light"]
    }
  ]
}
```

### 3. LoRA模型版本管理

```
存储路径: /Momcozy/aigc_assets/lora/

结构:
  lora/
  ├── identity/
  │   ├── momcozy_identity_v1.0.0_R16.safetensors
  │   ├── momcozy_identity_v1.1.0_R16.safetensors
  │   └── identity_training_config_v1.1.0.json
  ├── style_lifestyle/
  ├── style_product/
  ├── style_infographic/
  └── product_m5/

模型元数据 (同目录 .json):
{
  "model_name": "momcozy_identity",
  "version": "1.1.0",
  "base_model": "SDXL 1.0",
  "rank": 16,
  "training_images": 87,
  "training_steps": 3500,
  "trigger_words": ["Momcozy style", "cozy editorial"],
  "recommended_weight": 0.6,
  "test_results": {
    "style_consistency": 0.85,
    "color_accuracy": 0.78,
    "brand_recognition": 0.72
  }
}
```

### 4. 生成输出资产版本管理

```
存储路径: /Momcozy/aigc_assets/outputs/

结构:
  outputs/
  ├── 2026-05/
  │   ├── 2026-05-23/
  │   │   ├── S1_Hero_M5_01_v1.3.2_seed42.png
  │   │   ├── S1_Hero_M5_01_v1.3.2_seed42_meta.json
  │   │   └── ...
  │   └── 2026-05-24/
  └── 2026-06/

输出元数据格式:
{
  "output_id": "momcozy_OUTPUT_S1_M5_Hero_1.3.2_seed42_20260523",
  "prompt_version": "1.3.2",
  "scene": "S1_Hero_Lifestyle",
  "model": "Midjourney V7",
  "product": "M5 Breast Pump",
  "prompt_hash": "sha256:abc123...",
  "full_prompt": "A real mother...",
  "parameters": {
    "ar": "4:5",
    "sref": "SA-01",
    "sw": 150,
    "stylize": 250,
    "style": "raw",
    "c": 0.3,
    "seed": 42
  },
  "sref_urls": ["https://..."],
  "negative_prompt": "clinical, hospital...",
  "generation_time": "2026-05-23T14:30:00Z",
  "review_status": "approved",
  "reviewer": "Jane Doe",
  "use_case": "Website hero banner - M5 product page"
}
```

---

## 环境管理

### 三级环境

```
┌─────────────────────────────────────────────────────────────┐
│                    三级环境架构                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  DEV (开发环境)                                              │
│  ├─ 用途: Prompt实验、新模板测试、参数调优                     │
│  ├─ 权限: AIGC设计师、Prompt工程师                            │
│  ├─ 版本: 最新开发版本 (可能不稳定)                           │
│  ├─ 审核: 自审 (设计师本人)                                   │
│  └─ 输出: 不用于生产，仅内部参考                               │
│                                                             │
│  STAGING (预发布环境)                                        │
│  ├─ 用途: 批量生成前的质量验证、品牌一致性检查                  │
│  ├─ 权限: 设计主管、品牌经理                                   │
│  ├─ 版本: 已冻结的候选版本 (如 v1.3.2-rc1)                    │
│  ├─ 审核: 双人审核 (设计师+品牌经理)                          │
│  └─ 输出: 可用于内部评审，不可对外发布                         │
│                                                             │
│  PROD (生产环境)                                             │
│  ├─ 用途: 正式内容生成、对外发布                               │
│  ├─ 权限: 仅生产账号                                          │
│  ├─ 版本: 仅正式release版本 (如 v1.3.2)                       │
│  ├─ 审核: 三级审核 (设计师+品牌经理+市场总监)                  │
│  └─ 输出: 可直接用于官网/电商/社媒                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 环境切换流程

```
DEV → STAGING:
  1. 设计师提交版本冻结申请 (Freeze Request)
  2. 自动运行一致性测试套件
  3. 品牌经理审核Prompt和sref
  4. 审核通过 → 标记为 rc 版本
  5. 生成20张测试图进行质量验证

STAGING → PROD:
  1. 质量验证通过率 ≥ 90%
  2. 品牌一致性评分 ≥ 7/10 (人工)
  3. 市场总监最终审批
  4. 打 tag: v{major}.{minor}.{patch}
  5. 发布 Release Notes
  6. 生产环境锁定使用该版本
```

---

## 种子缓存与复现

### Seed管理策略

```python
# seed_registry.json
{
  "version": "1.3.2",
  "seeds": {
    "S1_Hero_M5": {
      "mj_v7": {
        "seed_42": {
          "status": "approved",
          "use_count": 15,
          "last_used": "2026-05-23",
          "notes": "最佳M5首屏生成种子"
        },
        "seed_88": {
          "status": "rejected",
          "reason": "产品颜色偏差"
        }
      }
    }
  }
}
```

### 复现检查清单

```
□ Prompt版本是否一致? (使用相同版本号)
□ 模型版本是否一致? (MJ V7, FLUX 1.1等)
□ sref URL是否一致?
□ 参数是否一致? (--sw, --stylize, CFG等)
□ Seed是否一致? (如需完全复现)
□ LoRA权重是否一致? (SD/FLUX)
□ ControlNet配置是否一致? (SD)
□ 负面Prompt是否一致?
```

---

## 协作工作流

### Git分支模型 (适用于代码化Prompt管理)

```
main (生产分支)
  ↑
release/v1.3.2 (发布分支)
  ↑
develop (开发分支)
  ↑    ↑    ↑
feature/S6-UGC  feature/flux-lora  hotfix/color-bug
```

### 变更审批矩阵

| 变更类型 | 设计师 | 品牌经理 | 市场总监 | 自动测试 |
|:---|:---|:---|:---|:---|
| Prompt文字微调 | 审 | - | - | 必须 |
| 新增场景模板 | 审 | 审 | - | 必须 |
| sref资产更新 | 审 | 审 | - | 必须 |
| LoRA模型更新 | 审 | 审 | - | 必须 |
| 参数默认值调整 | 审 | 审 | - | 必须 |
| 品牌色变更 | 审 | 审 | 审 | 必须 |
| 模型版本升级 | 审 | 审 | 审 | 必须 |

---

## 文档版本历史

| 版本 | 日期 | 作者 | 变更说明 |
|:---|:---|:---|:---|
| v1.0.0 | 2026-05-23 | AIGC Team | 初始版本管理规范建立 |

---

*本文档定义了Momcozy AIGC资产的全生命周期版本管理规范*
