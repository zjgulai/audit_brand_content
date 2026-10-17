# Momcozy 品牌一致性控制方案 v1.0

> **目标**: 确保AI生成的所有视觉资产在风格、色彩、情感、叙事上保持品牌一致性
> **适用**: Midjourney V7 / FLUX 1.1 / Stable Diffusion 3.5
> **关联文档**: `momcozy_aigc_brand_semantic_library.md`, `momcozy_aigc_prompt_templates.md`

---

## 目录

- [一致性控制技术栈总览](#一致性控制技术栈总览)
- [Midjourney V7: Style Reference (sref) 策略](#midjourney-v7-style-reference-sref-策略)
- [FLUX 1.1: 风格锁定方案](#flux-11-风格锁定方案)
- [Stable Diffusion 3.5: LoRA + ControlNet 方案](#stable-diffusion-35-lora--controlnet-方案)
- [产品一致性: IP-Adapter 应用](#产品一致性-ip-adapter-应用)
- [色彩一致性: 色彩锚点系统](#色彩一致性-色彩锚点系统)
- [跨模型一致性对比测试](#跨模型一致性对比测试)
- [品牌一致性检查清单](#品牌一致性检查清单)
- [实施路线图](#实施路线图)

---

## 一致性控制技术栈总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    Momcozy 品牌一致性控制金字塔                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  第4层: 叙事一致性 (Narrative Consistency)                       │
│  ├─ 情感词汇表强制执行 (cozy, breezy, effortless)                │
│  ├─ 微型叙事结构 (痛点→方案→情感回报)                             │
│  └─ 禁用词拦截 (clinical, machine, should)                       │
│                                                                 │
│  第3层: 产品一致性 (Product Consistency)                         │
│  ├─ IP-Adapter (产品形象锁定)                                   │
│  ├─ 产品色准控制 (dusty rose / sage green / cream)              │
│  └─ 品牌术语嵌入 (DoubleFit™, Cozy Tech™)                        │
│                                                                 │
│  第2层: 风格一致性 (Style Consistency)                           │
│  ├─ MJ: sref (Style Reference URLs)                             │
│  ├─ FLUX: Style LoRA + Prompt Injection                         │
│  └─ SD: Identity LoRA (Rank 16-32) + Style LoRA (Rank 8)        │
│                                                                 │
│  第1层: 基础一致性 (Base Consistency)                            │
│  ├─ 色彩DNA锚点 (#E30022, #A8B8A0, #FDFBF7)                    │
│  ├─ 光影规范 (soft diffused, warm golden, low contrast)         │
│  └─ 构图规则 (80-120px spacing, 1px annotation lines)           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 各模型技术路线对比

| 控制维度 | Midjourney V7 | FLUX 1.1 | SD 3.5 |
|:---|:---|:---|:---|
| 风格锁定 | `--sref` + `--sw` | Style LoRA | Identity LoRA + Style LoRA |
| 产品锁定 | `--cref` / Prompt | IP-Adapter | IP-Adapter |
| 构图控制 | Prompt + `--c` | Prompt | ControlNet (Canny/Depth/Tile) |
| 色彩控制 | Prompt + sref | Prompt + LoRA | Prompt + LoRA + VAE |
| 负面控制 | `--no` (有限) | 不使用 | Negative Prompt (有效) |
| 一致性强度 | ★★★☆☆ | ★★★★☆ | ★★★★★ |
| 易用性 | ★★★★★ | ★★★★☆ | ★★★☆☆ |

---

## Midjourney V7: Style Reference (sref) 策略

### sref 资产规划

sref 通过引用现有图片的视觉风格来控制输出。需要准备3类风格锚点：

#### SA-01: 生活方式情感锚点 (Lifestyle Emotional Anchor)

> **用途**: S1 Hero Lifestyle, S6 UGC, V1 产品演示
> **风格特征**: 暖色调、柔光、真实感、不完美之美
> **来源**: 从Momcozy现有品牌图库中选5-10张最佳Lifestyle图片
> **--sw 建议**: 150-250

**生成 sref 图片的选择标准:**
```
✅ 选择标准:
  - 暖色温 (色温 4500K-5500K)
  - 柔和高光 (无过曝)
  - 自然肤色 (无过度修图)
  - 真实环境 (非影棚)
  - 情感真实 (非摆拍)
  - 品牌色自然融入 (非强制高饱和)

❌ 排除标准:
  - 冷色调主导
  - 高对比度/戏剧性光影
  - 明显修图/磨皮过度
  - 纯白背景产品图
  - 医学/临床风格
```

#### SA-02: 信息图风格锚点 (Infographic Style Anchor)

> **用途**: S3 详情信息图, S4 Banner
> **风格特征**: 干净、柔和、奶油色背景、低对比度标注
> **来源**: 现有详情页截图/设计稿
> **--sw 建议**: 120-200

#### SA-03: 品牌视觉锚点 (Brand Visual Anchor)

> **用途**: S4 Banner, S5 包装, 品牌广告
> **风格特征**: 品牌红+绿+奶油色组合, 温暖氛围, 圆润柔和
> **来源**: 品牌VI手册关键页面、官网Hero Banner
> **--sw 建议**: 200-300

### sref 使用规范

```
# 单一风格参考 (最常用)
--sref [SA-01_URL] --sw 150

# 多重风格混合 (高级)
--sref [SA-01_URL] [SA-03_URL] --sw 200
# 注意: MJ会自动blend，可能导致风格稀释

# 权重调整
--sw 80   # 轻微影响，保留Prompt主导权
--sw 150  # 平衡，推荐默认值
--sw 250  # 强风格锁定，可能限制创意
--sw 400  # 极强锁定，几乎复刻参考风格

# 结合字符参考 (产品一致性)
--sref [SA-01_URL] --sw 150 --cref [PRODUCT_IMG_URL] --cw 50
```

### sref 工作流建议

```
Step 1: 从Momcozy品牌图库中精选10-15张风格标杆图
Step 2: 上传至Discord/MJ服务器获取URL
Step 3: 分类标注: SA-01(生活方式), SA-02(信息图), SA-03(品牌视觉)
Step 4: 每类测试5-10张生成图，评估一致性
Step 5: 记录最佳sref组合，建立sref资产库
Step 6: 定期更新(每季度)，加入新优秀生成图作为参考
```

---

## FLUX 1.1: 风格锁定方案

### 核心原则

FLUX是guidance-distilled模型，**不使用负面Prompt**。所有约束通过正面表达实现。

### 风格锁定技术栈

#### 方案A: Prompt Injection (最轻量)

在每个Prompt末尾注入统一的风格指令块：

```
[具体场景描述]... 

Style: warm lifestyle editorial photography. Soft diffused natural light. 
Warm golden undertones. Low contrast. Gentle shadows. 
Cozy effortless mood. Authentic moment. Natural skin texture. 
Cream and blush color palette with subtle sage green accents. 
Shot on Canon EOS R5 with 85mm f/1.4 lens. 
Shallow depth of field. Creamy bokeh. Subtle film grain.
```

#### 方案B: Style LoRA (推荐)

训练Momcozy专用Style LoRA：

```
训练数据集: 50-100张Momcozy品牌标杆图
  ├─ 30张 生活方式图 (SA-01类型)
  ├─ 20张 产品白底图 (SA-02类型)
  ├─ 20张 信息图/Banner (SA-03类型)
  └─ 10张 包装/开箱图

训练参数:
  - 基础模型: FLUX.1-dev
  - LoRA Rank: 16 (风格) / 32 (强锁定)
  - 学习率: 1e-4
  - 训练步数: 2000-4000 steps
  - 重复次数: 10x per image
  - 触发词: "Momcozy style", "cozy editorial"

使用方式:
  <lora:momcozy_style_v1:0.6>  # 轻度风格影响
  <lora:momcozy_style_v1:0.8>  # 中度风格影响 (推荐)
  <lora:momcozy_style_v1:1.0>  # 强风格锁定
```

#### 方案C: FLUX + IP-Adapter (产品一致性)

```
# 同时使用Style LoRA + IP-Adapter
Prompt: [场景描述] <lora:momcozy_style_v1:0.8>

IP-Adapter:
  - 参考图: Momcozy产品多角度白底图 (5-8张)
  - 权重: 0.6-0.8
  - 模式: "style+content" (同时锁定风格和内容)

效果:
  - 产品外观保持一致
  - 风格自动匹配品牌调性
  - 场景和构图由Prompt控制
```

### FLUX 色彩一致性技巧

由于FLUX不使用负面Prompt，需要用正面表达排除不需要的颜色：

```
# ❌ 不推荐 (FLUX无效)
no blue tones, avoid cold colors

# ✅ 推荐 (正面引导)
warm golden undertones throughout, 
cream and blush color palette, 
subtle sage green accents only, 
no cold blue or purple tones

# 更高级的写法 (语义引导)
late afternoon golden hour warmth, 
cozy living room lamp light,
not fluorescent or daylight-balanced
```

---

## Stable Diffusion 3.5: LoRA + ControlNet 方案

### LoRA 分层策略

```
┌─────────────────────────────────────────────────────┐
│              SD 3.5 LoRA 堆栈方案                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Layer 1: Base Model                                │
│  └─ SD 3.5 Medium / Large                           │
│                                                     │
│  Layer 2: Identity LoRA (品牌身份)                   │
│  └─ Rank: 16-32                                     │
│  └─ 权重: 0.5-0.7                                   │
│  └─ 训练数据: 品牌全套视觉资产                        │
│  └─ 触发词: "Momcozy brand identity"                │
│                                                     │
│  Layer 3: Style LoRA (场景风格)                      │
│  └─ Rank: 8                                         │
│  └─ 权重: 0.3-0.5                                   │
│  └─ 训练数据: 按场景分类 (生活方式/产品/信息图)        │
│  └─ 触发词: "cozy lifestyle", "clean product"       │
│                                                     │
│  Layer 4: Product LoRA (产品形象)                    │
│  └─ Rank: 8-16                                      │
│  └─ 权重: 0.4-0.8                                   │
│  └─ 训练数据: 具体产品的多角度图                      │
│  └─ 触发词: "M5 pump", "belly moisturizer"          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### ControlNet 使用矩阵

| 场景 | ControlNet类型 | 预处理 | 强度 | 用途 |
|:---|:---|:---|:---|:---|
| S2 白底产品 | Canny + Depth | 自动 | 1.0 + 0.6 | 保持产品轮廓和透视一致 |
| S3 信息图 | Lineart + Depth | 自动 | 0.8 + 0.5 | 保持标注线和空间结构 |
| S4 Banner | Depth + Tile | 自动 | 0.6 + 0.4 | 保持前景/背景层次 |
| S1 Lifestyle | SoftEdge | 自动 | 0.3 | 轻微构图引导，保留创意 |
| V1 产品演示 | TemporalNet | 视频帧 | 0.7 | 视频帧间一致性 |

### SD 3.5 推荐配置

```yaml
# 通用配置
checkpoint: sd3.5_medium.safetensors
vae: sd3.5_vae.safetensors
sampler: DPM++ 2M Karras
steps: 30
cfg_scale: 7.5
size: 1024x1024 (或按场景比例)

# LoRA 堆栈示例 (S1 Hero Lifestyle)
lora_stack:
  - momcozy_identity_v1: 0.6
  - momcozy_lifestyle_style_v1: 0.4
  - momcozy_m5_product_v1: 0.5

# ControlNet (可选)
controlnet:
  - type: SoftEdge
    model: control_v11p_sd15_softedge
    strength: 0.3
    start: 0.0
    end: 0.6
```

---

## 产品一致性: IP-Adapter 应用

### 什么是 IP-Adapter

IP-Adapter 允许将参考图片的"内容特征"注入生成过程，保持产品外观一致，同时允许场景/风格变化。

### 适用场景

| 场景 | 推荐度 | 说明 |
|:---|:---|:---|
| 多场景同一产品展示 | ★★★★★ | 确保产品在不同场景中外观一致 |
| 产品变体生成 | ★★★★★ | 同一产品不同颜色/角度 |
| 品牌吉祥物/IP | ★★★★☆ | 保持角色一致性 |
| 纯风格迁移 | ★★☆☆☆ | 更适合用Style LoRA |

### 实施步骤

```
Step 1: 准备产品参考图库
  ├─ 每个产品: 5-10张多角度白底图
  ├─ 分辨率: 512×512 或 768×768
  ├─ 格式: PNG (透明背景最佳)
  └─ 命名: {product_id}_angle_{01-10}.png

Step 2: 生成IP-Adapter嵌入
  ├─ 使用CLIP Image Encoder提取特征
  ├─ 或使用预训练IP-Adapter模型
  └─ 保存为 .bin 或 .safetensors

Step 3: 生成时调用
  Prompt: "product photo of M5 breast pump in cozy scene"
  IP-Adapter:
    - image: m5_reference_set.png
    - scale: 0.6-0.8
    - mode: "full" (保留完整产品特征)

Step 4: 一致性验证
  ├─ 对比生成图与参考图的产品特征
  ├─ 检查: 形状、比例、颜色、材质
  └─ 调整scale值 (0.4=弱, 0.8=强)
```

### 跨模型 IP-Adapter 兼容性

| 模型 | IP-Adapter支持 | 备注 |
|:---|:---|:---|
| SD 1.5 | ✅ 原生支持 | 最成熟生态 |
| SD XL | ✅ 原生支持 | 推荐 |
| SD 3.5 | ✅ 社区适配 | 需要最新版本 |
| FLUX | ✅ 社区适配 | flux-ip-adapter |
| Midjourney | ❌ 不支持 | 用--cref替代 |

---

## 色彩一致性: 色彩锚点系统

### 品牌色彩DNA (已测量)

```
┌──────────────────────────────────────────────────────────┐
│              Momcozy 色彩锚点系统                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Primary Red     #E30022  RGB(227,0,34)   品牌主张色     │
│  Sage Green      #A8B8A0  RGB(168,184,160) 自然/信任     │
│  Cream           #FDFBF7  RGB(253,251,247) 背景/温暖     │
│                                                          │
│  实际测量主导色:                                          │
│  Warm Rose       #B47C80  RGB(180,124,128) 56%图片出现   │
│  Soft Cream      #E8E0D4  RGB(232,224,212) 背景色        │
│  Sage Tint       #C5D4BE  RGB(197,212,190) 点缀色        │
│                                                          │
│  情感色温: 暖色调为主, 色温 4500K-5500K                   │
│  饱和度: 低-中 (避免高饱和刺眼)                            │
│  对比度: 低 (柔和过渡, 无硬边)                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Prompt色彩控制技巧

**Midjourney:**
```
# 通过sref间接控制色彩
--sref [SA-03_URL] --sw 200

# 直接Prompt控制
warm cream and blush color palette, 
subtle sage green accents, 
soft golden undertones,
no cold blue or neon colors
```

**FLUX:**
```
Color palette: warm cream (#FDFBF7) base, 
dusty rose (#B47C80) accents, 
sage green (#A8B8A0) subtle details. 
Overall warm golden tone. 
Late afternoon light quality.
```

**SD 3.5:**
```
Prompt: ... (warm color palette:1.2), (cream base:1.1), 
         (soft rose accents:1.1), (sage green details:1.0)

Negative: (cold blue:1.3), (neon:1.3), (high saturation:1.2), 
          (fluorescent:1.3), (purple:1.2)

# 或使用ColorPalette LoRA
<lora:momcozy_color_palette:0.5>
```

### 自动化色彩验证

```python
# 伪代码: 生成后自动色彩验证
def verify_color_consistency(image_path):
    img = Image.open(image_path)
    
    # 提取主色调 (K-means)
    dominant_colors = extract_dominant_colors(img, k=5)
    
    # 检查品牌色出现频率
    brand_colors = ['#E30022', '#A8B8A0', '#FDFBF7', '#B47C80']
    color_match_score = 0
    for color in dominant_colors:
        for brand_color in brand_colors:
            if color_distance(color, brand_color) < 30:
                color_match_score += 1
    
    # 检查色温
    avg_temp = estimate_color_temperature(img)
    is_warm = 4000 <= avg_temp <= 6000
    
    # 检查饱和度
    avg_saturation = calculate_avg_saturation(img)
    is_soft = avg_saturation < 0.6
    
    return {
        'color_match': color_match_score / len(dominant_colors),
        'warm_tone': is_warm,
        'soft_saturation': is_soft,
        'pass': color_match_score >= 2 and is_warm and is_soft
    }
```

---

## 跨模型一致性对比测试

### 测试矩阵

为验证不同模型间的风格一致性，建议执行以下标准化测试：

| 测试项 | MJ V7 | FLUX 1.1 | SD 3.5 | 一致性阈值 |
|:---|:---|:---|:---|:---|
| 同Prompt生成3张 | 风格差异<20% | 风格差异<15% | 风格差异<10% | <25% |
| 色彩偏差 (ΔE) | ΔE<15 | ΔE<12 | ΔE<10 | <20 |
| 色温一致性 | ±500K | ±300K | ±200K | ±800K |
| 情感词一致性 | 人工评分≥7/10 | 人工评分≥7/10 | 人工评分≥7/10 | ≥6/10 |
| 品牌术语出现率 | ≥80% | ≥85% | ≥90% | ≥70% |

### 标准测试Prompt (S1场景)

```
"A real mother with curly hair sipping coffee on an orange 
velvet armchair in a sunlit living room, a wearable breast 
pump naturally visible under her cream knit cardigan, soft 
diffused natural window light, warm golden undertones, low 
contrast, relief atmosphere, cozy effortless mood, crimson 
red accents subtly woven into the composition, authentic 
moment, imperfect beauty, natural skin texture, relaxed 
posture, genuine warm smile, lifestyle editorial photography"
```

### 对比测试工作流

```
Round 1: 单模型一致性
  ├─ 同一Prompt生成10张
  ├─ 评估: 风格一致性、色彩一致性、情感一致性
  └─ 目标: 同模型内差异 < 20%

Round 2: 跨模型一致性
  ├─ 同一Prompt在3个模型各生成5张
  ├─ 评估: 跨模型风格对齐度
  └─ 目标: 人工评分 ≥ 6/10 "看起来属于同一品牌"

Round 3: 品牌识别测试
  ├─ 将生成图混入竞品图中
  ├─ 盲测: "哪些图看起来像Momcozy?"
  └─ 目标: 识别率 ≥ 70%
```

---

## 品牌一致性检查清单

### 生成前检查 (Pre-Generation)

```
□ Prompt中是否包含至少1个品牌情感词? (cozy/breezy/effortless)
□ Prompt中是否避免禁用词? (clinical/machine/should)
□ 色彩描述是否符合品牌色板? (warm/cream/blush/sage)
□ 光影描述是否符合品牌规范? (soft diffused/low contrast)
□ sref/LoRA是否正确加载?
□ 负面Prompt是否包含品牌调性负面词?
□ 构图参数是否符合场景规范? (spacing/annotation lines)
```

### 生成后检查 (Post-Generation)

```
□ 色彩检查: 主色调是否为暖色? (红/橙/黄/奶油)
□ 光影检查: 是否柔和低对比? (无硬阴影/无过曝)
□ 情感检查: 画面传达的情感是否为正面温和? (非焦虑/非夸张)
□ 产品检查: 产品外观是否准确? (颜色/形状/材质)
□ 叙事检查: 是否隐含"痛点→方案"结构? (适用场景)
□ 禁用词检查: 画面中是否出现禁用元素? (临床感/机器感)
□ 品牌识别: 这张图是否"看起来"像Momcozy?
```

### 自动化检查脚本

```python
# brand_consistency_checker.py (概念代码)

BRAND_CONFIG = {
    "forbidden_keywords": [
        "clinical", "hospital", "sterile", "medical-grade",
        "machine", "device", "gadget", "appliance",
        "should", "must", "always", "perfect mother"
    ],
    "required_emotions": ["cozy", "breezy", "effortless", "warm", "gentle"],
    "brand_colors": {
        "primary_red": "#E30022",
        "sage_green": "#A8B8A0",
        "cream": "#FDFBF7",
        "warm_rose": "#B47C80"
    },
    "color_temp_range": (4000, 6000),  # Kelvin
    "saturation_max": 0.6,
}

def check_prompt(prompt_text):
    """检查Prompt是否符合品牌规范"""
    issues = []
    
    # 检查禁用词
    for word in BRAND_CONFIG["forbidden_keywords"]:
        if word.lower() in prompt_text.lower():
            issues.append(f"❌ 禁用词: '{word}'")
    
    # 检查情感词
    has_emotion = any(e in prompt_text.lower() 
                     for e in BRAND_CONFIG["required_emotions"])
    if not has_emotion:
        issues.append("⚠️ 缺少品牌情感词 (cozy/breezy/effortless/warm/gentle)")
    
    return len(issues) == 0, issues

def check_image(image_path):
    """检查生成图是否符合品牌规范"""
    # 调用OpenCV/PIL进行色彩/光影分析
    # 返回一致性评分
    pass
```

---

## 实施路线图

### Phase 1: 立即实施 (Week 1)

```
□ 整理Momcozy品牌图库，选出30张风格标杆图
□ 上传至Midjourney，获取sref URL，标注SA-01/02/03
□ 建立Prompt模板复用库 (基于本文档)
□ 配置基础负面Prompt模板
□ 完成首批10张测试生成 (S1-S6各1-2张)
```

### Phase 2: 短期优化 (Week 2-3)

```
□ 训练SD 3.5 Identity LoRA (Rank 16)
□ 训练FLUX Style LoRA (Rank 16)
□ 建立产品参考图库 (每个产品5-10张)
□ 实施IP-Adapter产品一致性控制
□ 完成跨模型对比测试，记录一致性数据
□ 优化Prompt模板 (基于测试结果)
```

### Phase 3: 中期完善 (Month 2)

```
□ 训练场景专用Style LoRA (生活方式/产品/信息图)
□ 建立自动化一致性检查脚本
□ 集成到内容生成工作流
□ 建立sref资产季度更新机制
□ 完成品牌识别盲测 (目标≥70%)
```

### Phase 4: 长期维护 (Ongoing)

```
□ 每月审查生成资产一致性
□ 季度更新风格参考图库
□ 跟踪AI模型更新 (MJ V8, FLUX 2, SD 4)
□ 持续优化LoRA权重和训练数据
□ 建立品牌资产版本控制
```

---

## 附录: 工具推荐

| 工具 | 用途 | 推荐度 |
|:---|:---|:---|
| **Midjourney** | 生活方式/概念图 | ★★★★★ |
| **FLUX.1-dev** | 细节精度/文字渲染 | ★★★★★ |
| **SD 3.5 + ComfyUI** | 精细控制/LoRA堆栈 | ★★★★☆ |
| **Kohya_ss** | LoRA训练 | ★★★★★ |
| **IP-Adapter** | 产品一致性 | ★★★★★ |
| **Runway Gen-3** | 视频生成 | ★★★★☆ |
| **Sora** | 长视频/复杂场景 | ★★★★☆ |
| **ColorThief** | 色彩提取 | ★★★★☆ |
| **Adobe Color** | 色板管理 | ★★★★★ |

---

*文档版本: v1.0 | 2026-05-23 | Momcozy AIGC Optimization Project*
