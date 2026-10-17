# Momcozy AIGC 品牌语义资产库

> **生成日期**: 2026-05-23
> **版本**: v1.0
> **用途**: 为 Midjourney / FLUX / Stable Diffusion 生成提供结构化品牌语义输入
> **覆盖**: 图片(6场景) + 视频(4类型) + 文案(3调性)

---

## 1. 品牌灵魂层 (Brand Soul Layer)

### 1.1 核心定位
```
定位: "Total Comfort Ecosystem" — 全场景舒适生态
使命: "Always Put Moms First" — 永远把妈妈放在第一位
角色: 智慧赋能者 (The AI-Empowerer) + 真实陪伴者 (The Authentic Companion)
愿景: 通过AI驱动的自适应技术与共情设计的融合，为现代妈妈创造"无摩擦"的生活
```

### 1.2 情感词汇库 (Emotional Lexicon)

**高频正向词** (必须在Prompt中出现1-2个):
| 英文 | 中文 | 使用场景 |
|:---|:---|:---|
| cozy | 舒适 | 全场景 |
| breezy | 轻松 | 产品使用场景 |
| empower | 赋能 | 技术卖点 |
| gentle | 温柔 | 产品触感 |
| effortless |  effortless | 便捷功能 |
| freeing | 解放 | 穿戴类产品 |
| nurturing | 滋养 | 护肤品类 |
| seamless | 无缝 | 技术体验 |

**情感锚点短语**:
- "Just You, Refreshed" — 首屏Hero
- "Wrapped in comfort" — Lifestyle场景
- "Your time, reclaimed" — 效率类产品
- "Gentle on skin, fierce on results" — 护肤品
- "Invisible support, visible confidence" — 穿戴类

### 1.3 禁忌词汇库 (Forbidden Lexicon)

**绝对禁止出现在任何Prompt中的词**:
```
clinical, machine, medical-grade, hospital, sterile, cold, rigid,
perfect, flawless, ideal mother, supermom, effortless parenting,
weight loss, slimming, diet, anti-aging,
should, must, always, never (命令式),
anime, cartoon, illustration, vector art, 3D render (写实场景),
neon, fluorescent, high contrast, dramatic shadow (与品牌调性冲突)
```

**必须避免的视觉元素**:
- 过于完美的模特（无瑕疵皮肤、过度修图）
- 临床/医院环境
- 冷色调主导画面
- 尖锐的几何线条
- 过度的科技感UI界面

---

## 2. 视觉语义层 (Visual Semantic Layer)

### 2.1 色彩体系 (Color System)

```json
{
  "primary": {
    "hex": "#E30022",
    "name": "Momcozy Red",
    "usage": "CTA按钮, Logo, Badge高亮, 核心卖点强调",
    "hsv": {"h": 352, "s": 100, "v": 89},
    "prompt_phrase": "subtle dark red accent, crimson highlight, warm red detail"
  },
  "secondary": {
    "hex": "#A8B8A0",
    "name": "Sage Green",
    "usage": "产品点缀, 环保/自然属性, 次要按钮",
    "hsv": {"h": 100, "s": 13, "v": 72},
    "prompt_phrase": "muted sage green, soft olive tone, gentle green accent"
  },
  "surface": {
    "hex": "#FDFBF7",
    "name": "Cream White",
    "usage": "背景, 卡片底色, 留白区域",
    "hsv": {"h": 40, "s": 3, "v": 99},
    "prompt_phrase": "warm cream background, off-white surface, ivory tone"
  },
  "warm_palette": {
    "measured_dominant": ["#b47c80", "#fbf7f5", "#e1c6c2"],
    "description": "粉棕暖调, 奶油色, 玫瑰米色",
    "prompt_phrase": "warm beige, dusty rose, soft terracotta, cream ivory"
  },
  "lighting_temperature": "warm golden undertones, soft amber highlights"
}
```

### 2.2 光影体系 (Lighting System)

```
核心特征:
- 低对比度 (Low contrast)
- 柔和漫反射自然光 (Soft diffused natural light)
- 暖色基调 (Warm undertones)
- 避免硬边阴影 (No hard shadows)

Prompt表达:
  "soft diffused natural window light, low contrast, warm golden undertones,
   gentle shadows, no harsh highlights, ambient daylight feel"

负面表达 (SD/MJ):
  "harsh lighting, high contrast, dramatic shadows, cold fluorescent,
   studio flash, hard edge shadows, blown out highlights"
```

### 2.3 构图体系 (Composition System)

```
Lifestyle场景:
  - 4:5 比例 (竖版优先)
  - 妈妈第一人称视角 或 极近情绪特写
  - 产品自然融入生活场景
  - 留白充足 (80-120px模块间距感)

产品白底图:
  - 1:1 或 3:4
  - 45度角或正面微侧
  - 柔和studio lighting (非冷白)
  - 影子柔和、带暖色偏移

详情信息图:
  - 16:9 或 3:2
  - 1px浅灰色标注线
  - 4px实心圆点端点
  - 文字All-Caps或Italic

Banner:
  - 2:1 或 21:9
  - 左侧文案空间 / 右侧视觉焦点
  - 渐变背景 (暖色调)
  - Pill Shape Badge (全圆角)
```

### 2.4 材质与触感 (Material & Texture)

```
核心触感词汇:
- ultra-soft fabrics, knits, cotton, plush blankets
- brushed silicone, matte finish, velvety texture
- organic cotton, bamboo fiber, natural linen

Prompt表达:
  "ultra-soft knit texture, matte silicone surface, natural cotton feel,
   gentle touch, premium material quality"
```

### 2.5 人物规范 (Human Subject Guidelines)

```
模特类型:
  - 真实妈妈 (Real mothers, not models)
  - 多元化: 不同种族、体型、年龄
  - 自然状态: 微笑但不完美，可以有疲惫但幸福的表情

姿态:
  - 放松的 (Relaxed posture)
  - 与宝宝自然互动
  - 第一人称视角: 低头看宝宝、轻抚宝宝

表情:
  - 温暖、满足、略带疲惫但幸福
  - 避免: 过度灿烂的笑容、完美的妆容、商业化的摆拍

Prompt表达:
  "real mother, natural warm expression, relaxed posture,
   authentic moment, genuine smile, imperfect beauty,
   diverse ethnicity, natural skin texture"

负面表达:
  "perfect model, professional model, flawless skin,
   heavy makeup, posed portrait, artificial smile,
   stereotypical beauty"
```

---

## 3. 叙事语义层 (Narrative Semantic Layer)

### 3.1 图片叙事流 (Image Narrative Flow)

```
[首屏] 情感锚点 (Emotional Anchor)
  钩子: 状态而非功能
  例: "Just You, Refreshed" — 妈妈在阳光下喝咖啡的平静画面

[二屏] 功能解剖 (Feature Anatomy)
  钩子: 温柔的技术解释
  例: 1px标注线展示产品细节，不冰冷，像闺蜜推荐

[三屏] 感官网格 (Sensory Grid)
  钩子: 多维度舒适体验
  例: 2x2图文块 — 柔软、静音、便携、智能

[四屏] 真实共鸣 (Authentic Proof)
  钩子: 真实用户故事
  例: 无滤镜的手机拍摄感，生活杂乱的背景
```

### 3.2 视频叙事流 (Video Narrative Flow)

```
前3秒 (The Hook):
  痛点特写: 溢出的奶、凌乱的厨房、疲惫揉腰
  情绪: 共鸣、"这说的就是我"

中段 (The Solution):
  Lo-fi音乐起
  一键启动的流畅动作
  产品融入日常的无缝感

结尾 (The Resolution):
  妈妈喝咖啡、看书、平静微笑
  Slogan居中跳出
  品牌红 #E30022 高亮关键词
```

### 3.3 文案调性层级 (Copy Tone Hierarchy)

```
H1 (首屏标题): 情感驱动, 10字以内
  例: "Just You, Refreshed" / "Cozy Her"

H2 (功能标题): 利益驱动, 温和表达
  例: "Gentle support for your healing journey"

Body (正文): 平视视角, 先共情后方案
  例: "We know mornings can be tough. That's why..."

CTA (按钮): 行动导向, 温暖有力
  例: "Find Your Cozy" / "Join the Village"

Badge/标签: 权威但不冰冷
  例: "Mom's Value Pick" / "Best Seller"
```

---

## 4. 技术规范层 (Technical Specification Layer)

### 4.1 模型特异性规范

**Midjourney V7:**
```
Prompt风格: 短句高信号短语
风格控制: --sref [锚定图URL] --sw 150 --stylize 250 --style raw
负面Prompt: 有效，控制在10-15词
参考图: 垫图(--iw 1.5) + /describe 辅助
```

**FLUX 1.1/2:**
```
Prompt风格: 40-50词精炼结构化描述
负面Prompt: 不支持，用正面表达替代
结构: Subject → Action → Environment → Lighting → Style
```

**Stable Diffusion 3.5:**
```
Prompt风格: 结构化加权关键词
权重语法: (keyword:1.4)
负面Prompt: 有效，支持加权
ControlNet: OpenPose/Depth/Canny + Style LoRA
```

### 4.2 推荐参数配方

**Momcozy通用参数 (Midjourney):**
```
--ar 4:5 --sref [风格锚定图] --sw 150 --stylize 250 
--style raw --c 0.3 --v 7
```

**Momcozy通用参数 (FLUX):**
```
 guidance_scale: 3.5
 steps: 28
 prompt_upsampling: false
```

**Momcozy通用参数 (SD 3.5):**
```
 steps: 30
 cfg: 7.5
 sampler: DPM++ 2M Karras
 negative_prompt: [品牌负面词表]
```

---

## 5. 风格锚定图建议 (Style Anchor Images)

基于资产分析，以下图片最适合作为风格锚定图：

| 编号 | 推荐锚定图 | 用途 | 理由 |
|:---|:---|:---|:---|
| SA-01 | SKU01_Pump_Clean/Bundle assets img_03.jpg | Lifestyle主锚定 | 完美体现品牌DNA: 暖色调、自然光、真实妈妈、产品自然融入、放松氛围 |
| SA-02 | SKU03_Pro_Collagen assets img_01.jpg | 详情/真实感锚定 | 真实皮肤纹理、暖色调拼图、奶油色背景、Expert-Led信任感 |
| SA-03 | SKU01_Pump_Clean/Bundle assets img_01.png | Banner/营销锚定 | Pill Shape、粉色调、sparkle装饰、价值主张表达 |
| SA-04 | SKU01_M5_Smart assets img_04.png | 首屏Hero锚定 | 母婴共处、自然光、奶油色调、App界面融入 |
| SA-05 | design_tokens.json 色板 | 色彩锚定 | #E30022 + #A8B8A0 + #FDFBF7 官方定义 |

---

## 6. 竞争差异化语义 (Competitive Differentiation)

```
Vs. Medela/Spectra (传统大牌):
  强调: "untethered freedom", "lighter, quieter", "no wires"
  避免: clinical, hospital-grade, medical device aesthetic

Vs. Elvie/Willow (高端穿戴):
  强调: "affordable premium", "double-sealed comfort", "no leaks"
  避免: luxury positioning, exclusive, unattainable

Momcozy独特定位:
  "The smartest high-performance choice that truly understands a mom's budget"
  → 在Prompt中体现: 精致但不奢侈，高科技但亲切，专业但温暖
```

---

## 7. 版本历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-05-23 | 初始构建，基于185张图片+22个视频+品牌知识库+行业最佳实践 |
