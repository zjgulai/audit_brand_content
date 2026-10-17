# Momcozy AIGC Prompt 模板系统 v1.0

> **生成日期**: 2026-05-23
> **适用模型**: Midjourney V7 / FLUX 1.1 / Stable Diffusion 3.5
> **场景覆盖**: 图片(6) + 视频(4) + 文案(3)
> **配套文件**: `momcozy_aigc_brand_semantic_library.md` (品牌语义资产库)

---

## 目录

- [使用指南](#使用指南)
- [图片Prompt模板](#图片prompt模板)
  - [S1: Hero Lifestyle 首屏情感锚点](#s1-hero-lifestyle-首屏情感锚点)
  - [S2: 白底产品图](#s2-白底产品图)
  - [S3: 详情信息图 / 功能解剖](#s3-详情信息图--功能解剖)
  - [S4: 营销Banner](#s4-营销banner)
  - [S5: 包装 / 开箱图](#s5-包装--开箱图)
  - [S6: UGC真实感 / 社媒内容](#s6-ugc真实感--社媒内容)
- [视频Prompt模板](#视频prompt模板)
  - [V1: 产品演示视频](#v1-产品演示视频)
  - [V2: UGC/测评视频](#v2-ugc测评视频)
  - [V3: 品牌广告视频](#v3-品牌广告视频)
  - [V4: 社媒短视频(Reels/Shorts)](#v4-社媒短视频reelsshorts)
- [文案Prompt模板](#文案prompt模板)
- [负面Prompt总库](#负面prompt总库)
- [参数速查表](#参数速查表)

---

## 使用指南

### 模板变量说明

模板中使用 `{变量名}` 表示需要根据具体产品替换的部分：

| 变量 | 说明 | 示例 |
|:---|:---|:---|
| `{PRODUCT_NAME}` | 产品名称 | "M5 Hands-Free Breast Pump" |
| `{PRODUCT_TYPE}` | 产品品类 | "wearable breast pump", "belly moisturizer" |
| `{COLOR}` | 产品颜色 | "dusty rose pink", "sage green" |
| `{SCENE}` | 使用场景 | "cozy living room", "sunlit bedroom" |
| `{MOM_ACTION}` | 妈妈动作 | "sipping coffee while pumping", "applying cream with gentle circular motion" |
| `{BABY_ACTION}` | 宝宝动作 | "sleeping peacefully", "nursing contentedly" |
| `{KEY_FEATURE}` | 核心卖点 | "whisper-quiet", "invisible under clothing" |
| `{VALUE_PROP}` | 价值主张 | "freedom to multitask", "gentle healing support" |
| `{PAIN_POINT}` | 痛点 | "leaking milk", "sore nipples", "exhaustion" |
| `{EMOTION}` | 情绪关键词 | "relief", "confidence", "peace" |
| `{BADGE_TEXT}` | Badge文案 | "Best Seller", "Mom's Value Pick" |
| `{SLOGAN}` | Slogan | "Just You, Refreshed" |
| `{PRICE}` | 价格 | "$159.99" |

### 模板选择决策树

```
图片类型?
  ├─ 首屏大图/生活方式 → S1 Hero Lifestyle
  ├─ 产品单独展示 → S2 白底产品图
  ├─ 功能说明/卖点 → S3 详情信息图
  ├─ 促销/活动 → S4 营销Banner
  ├─ 包装/礼品 → S5 包装开箱图
  └─ 社媒/真实感 → S6 UGC真实感

视频类型?
  ├─ 产品使用教程 → V1 产品演示
  ├─ 第三方测评 → V2 UGC/测评
  ├─ 品牌形象片 → V3 品牌广告
  └─ TikTok/Reels → V4 社媒短视频
```

### 品牌叙事注入规则

每张生成的图片/视频必须在以下3个层面注入品牌叙事：

1. **情感层** (Emotional Layer): 1-2个品牌情感词 (cozy, breezy, empower)
2. **视觉层** (Visual Layer): 色彩+光影+材质符合品牌规范
3. **故事层** (Story Layer): 隐含"痛点→解决方案→情感回报"的微型叙事

---

## 图片Prompt模板

### S1: Hero Lifestyle 首屏情感锚点

> **用途**: 官网首屏、电商主图、社交媒体头图
> **比例**: 4:5 (竖版) 或 16:9 (横版)
> **核心目标**: 3秒内建立情感共鸣，不是卖产品而是卖"状态"

---

#### S1-MJ: Midjourney V7

```
{A real mother|MOM_TYPE} {MOM_ACTION} in a {SCENE}, 
{PRODUCT_NAME} {naturally integrated|subtly visible} in the scene, 
soft diffused natural window light, warm golden undertones, low contrast, 
{EMOTION} atmosphere, {cozy|breezy|effortless} mood, 
{COLOR} accents subtly woven into the composition,
authentic moment, imperfect beauty, natural skin texture, 
relaxed posture, genuine expression,
lifestyle editorial photography, shot on Canon EOS R5, 85mm f/1.4,
shallow depth of field, creamy bokeh, film grain subtle,
--ar 4:5 --sref {SA-01_URL} --sw 150 --stylize 250 --style raw --c 0.3 --v 7
```

**示例 (M5吸奶器):**
```
A real mother with curly hair sipping coffee on an orange velvet armchair 
in a sunlit living room, a dusty rose pink wearable breast pump 
naturally visible under her cream knit cardigan, 
soft diffused natural window light, warm golden undertones, low contrast, 
relief atmosphere, cozy effortless mood, 
crimson red accents subtly woven into the composition,
authentic moment, imperfect beauty, natural skin texture, 
relaxed posture, genuine warm smile,
lifestyle editorial photography, shot on Canon EOS R5, 85mm f/1.4,
shallow depth of field, creamy bokeh, film grain subtle,
--ar 4:5 --sref {SA-01_URL} --sw 150 --stylize 250 --style raw --c 0.3 --v 7
```

**负面Prompt:**
```
clinical setting, hospital environment, perfect model, heavy makeup, 
posed portrait, artificial smile, harsh lighting, high contrast, 
studio flash, cold fluorescent, dramatic shadows, 
sterile background, medical device aesthetic, anime, cartoon
```

---

#### S1-FLUX: FLUX 1.1

```
Photograph of a real mother {MOM_ACTION} in a {SCENE}. 
The {PRODUCT_NAME} in {COLOR} is naturally part of the scene, not the sole focus. 
Soft diffused natural window light creates warm golden undertones across the frame. 
Low contrast, gentle shadows, no harsh highlights. 
The atmosphere feels {EMOTION} and {cozy|breezy}. 
Authentic moment with natural skin texture, relaxed posture, genuine expression. 
Imperfect beauty. Lifestyle editorial style. 
Shot on Canon EOS R5 with 85mm f/1.4 lens, shallow depth of field, creamy bokeh.
```

**FLUX注意事项:**
- 不使用负面Prompt，用正面表达替代模糊/低质量
- 在正面加入: "sharp focus, crisp detail, high resolution, professional photography"
- 避免: "no blur" → 改用 "sharp focus"
- 避免: "no artificial look" → 改用 "authentic natural look"

---

#### S1-SD: Stable Diffusion 3.5

```
(real mother:1.3), (MOM_ACTION:1.2), (SCENE:1.1), 
(PRODUCT_NAME:1.0) in (COLOR:1.1), naturally integrated,
(soft diffused natural window light:1.3), (warm golden undertones:1.2), 
(low contrast:1.2), (gentle shadows:1.1),
(EMOTION:1.1) atmosphere, (cozy effortless mood:1.2),
(authentic moment:1.2), (natural skin texture:1.3), 
(relaxed posture:1.1), (genuine expression:1.2),
(imperfect beauty:1.1), (lifestyle editorial photography:1.2),
(shot on Canon EOS R5, 85mm f/1.4:1.1), 
(shallow depth of field:1.2), (creamy bokeh:1.1),
sharp focus, crisp detail, high resolution, professional photography
```

**负面Prompt:**
```
(clinical:1.4), (hospital:1.3), (perfect model:1.3), (heavy makeup:1.2), 
(posed portrait:1.3), (artificial smile:1.2), (harsh lighting:1.3), 
(high contrast:1.2), (studio flash:1.2), (dramatic shadows:1.2), 
(sterile background:1.3), (medical device:1.3), 
(anime:1.5), (cartoon:1.5), (illustration:1.4), (3D render:1.3),
low quality, worst quality, jpeg artifacts, blurry, noisy, pixelated,
ugly, deformed, extra fingers, bad anatomy, asymmetrical face
```

**推荐参数:**
```
Steps: 30, CFG: 7.5, Sampler: DPM++ 2M Karras
Size: 832×1216 (4:5竖版) 或 1216×832 (横版)
ControlNet: None (自由构图) 或 Depth (如需固定空间关系)
```

---

### S2: 白底产品图

> **用途**: Amazon主图、官网产品页、电商列表页
> **比例**: 1:1 或 3:4
> **核心目标**: 清晰展示产品外观，建立专业信任感

---

#### S2-MJ: Midjourney V7

```
{PRODUCT_NAME} in {COLOR}, professional product photography, 
pure white background, soft even studio lighting with warm undertones,
no harsh shadows, subtle soft shadow beneath product,
{MATERIAL} texture clearly visible, premium quality feel,
45-degree three-quarter angle view, sharp focus, crisp detail,
8k resolution, commercial catalog style,
--ar 1:1 --sref {SA-01_URL} --sw 80 --stylize 150 --style raw --v 7
```

**示例 (M5吸奶器):**
```
M5 wearable breast pump in dusty rose pink, professional product photography, 
pure white background, soft even studio lighting with warm undertones,
no harsh shadows, subtle soft shadow beneath product,
matte silicone texture clearly visible, premium quality feel,
45-degree three-quarter angle view, sharp focus, crisp detail,
8k resolution, commercial catalog style,
--ar 1:1 --sref {SA-01_URL} --sw 80 --stylize 150 --style raw --v 7
```

**负面Prompt:**
```
cluttered background, busy environment, people, hands, 
harsh shadows, cold blue lighting, clinical setting,
low quality, blurry, noisy, watermark, text overlay, logo
```

---

#### S2-FLUX: FLUX 1.1

```
Professional product photograph of {PRODUCT_NAME} in {COLOR}. 
Pure white background. Soft even studio lighting with subtle warm undertones. 
Gentle soft shadow beneath the product. No harsh edges. 
{MATERIAL} texture visible and appealing. 
45-degree three-quarter angle showing product form. 
Sharp focus throughout. Crisp detail. Premium commercial catalog quality. 
High resolution product photography.
```

---

#### S2-SD: Stable Diffusion 3.5

```
(PRODUCT_NAME:1.3) in (COLOR:1.2), 
(professional product photography:1.3), (pure white background:1.4),
(soft even studio lighting:1.3), (warm undertones:1.1), 
(subtle soft shadow:1.2), (no harsh shadows:1.2),
(MATERIAL texture:1.2), (premium quality:1.2),
(45-degree angle:1.1), (sharp focus:1.3), (crisp detail:1.3),
(commercial catalog style:1.2), 8k resolution
```

**负面Prompt:**
```
(cluttered background:1.3), (busy environment:1.3), (people:1.4), (hands:1.3),
(harsh shadows:1.3), (cold blue lighting:1.2), (clinical setting:1.3),
low quality, blurry, noisy, watermark, text overlay, logo, signature,
(jpeg artifacts:1.2), (pixelated:1.2), (oversaturated:1.2)
```

**推荐参数:**
```
Steps: 30, CFG: 7.0, Sampler: DPM++ 2M Karras
Size: 1024×1024 (1:1) 或 832×1216 (3:4)
ControlNet: Canny (如需保持产品轮廓一致性) 或 None
```

---

### S3: 详情信息图 / 功能解剖

> **用途**: PDP详情页、功能说明、技术卖点展示
> **比例**: 16:9 或 3:2
> **核心目标**: 温柔地解释技术，像闺蜜推荐而非说明书

---

#### S3-MJ: Midjourney V7

```
{PRODUCT_NAME} feature illustration, gentle technical diagram style,
product shown with 1px light gray annotation lines and 4px solid dot markers,
soft cream background (#FDFBF7), warm low-contrast lighting,
{KEY_FEATURE} highlighted with subtle sage green accent,
clean infographic layout, minimal text placeholders,
premium feel without clinical coldness,
3D product render with semi-transparent background overlay,
soft shadows, rounded corners everywhere,
--ar 16:9 --sref {SA-02_URL} --sw 120 --stylize 200 --style raw --v 7
```

**示例 (M5 DoubleFit技术):**
```
M5 breast pump feature illustration, gentle technical diagram style,
product shown with 1px light gray annotation lines and 4px solid dot markers,
soft cream background, warm low-contrast lighting,
DoubleFit flange seal highlighted with subtle sage green accent,
clean infographic layout, minimal text placeholders,
premium feel without clinical coldness,
3D product render with semi-transparent background overlay,
soft shadows, rounded corners everywhere,
--ar 16:9 --sref {SA-02_URL} --sw 120 --stylize 200 --style raw --v 7
```

---

#### S3-FLUX: FLUX 1.1

```
Clean feature illustration of {PRODUCT_NAME} on soft cream background. 
Gentle technical diagram style with thin light gray annotation lines 
and small circular markers pointing to product details. 
Warm low-contrast lighting throughout. 
{KEY_FEATURE} subtly highlighted. 
Premium product visualization without clinical coldness. 
Soft rounded corners. Minimal clean layout. 
Semi-transparent overlay showing internal structure. 
Professional infographic design.
```

---

#### S3-SD: Stable Diffusion 3.5

```
(feature illustration:1.3), (PRODUCT_NAME:1.2), 
(gentle technical diagram:1.2), (thin light gray annotation lines:1.3),
(small circular markers:1.2), (soft cream background:1.3),
(warm low-contrast lighting:1.2), (KEY_FEATURE highlighted:1.2),
(clean infographic layout:1.2), (minimal design:1.2),
(premium product visualization:1.2), (no clinical coldness:1.2),
(3D product render:1.1), (semi-transparent overlay:1.1),
(soft shadows:1.2), (rounded corners:1.2),
sharp focus, crisp detail, professional design
```

**负面Prompt:**
```
(clinical:1.4), (harsh technical:1.3), (cold blue:1.3), 
(complex background:1.2), (cluttered layout:1.3),
(sterile hospital:1.3), (medical device:1.3),
low quality, blurry, pixelated, watermark, text overlay,
(anime:1.5), (cartoon:1.5)
```

---

### S4: 营销Banner

> **用途**: 官网Hero Banner、社交媒体广告、邮件头图
> **比例**: 2:1 或 21:9
> **核心目标**: 高转化，清晰的文案空间 + 情感视觉焦点

---

#### S4-MJ: Midjourney V7

```
Wide marketing banner for {PRODUCT_NAME}, 
{SCENE} with soft warm gradient background,
{EMOTION} atmosphere, {cozy|breezy} mood,
product prominently positioned on right side,
left side with clean gradient space for text overlay,
subtle {COLOR} accents, soft bokeh elements,
pill-shaped badge area suggestion in warm red,
sparkle and gentle light effects,
premium e-commerce banner style,
no text, no logo, no watermark,
--ar 2:1 --sref {SA-03_URL} --sw 200 --stylize 300 --v 7
```

**示例 (Mama Registry Bundle):**
```
Wide marketing banner for Momcozy baby care bundle, 
cozy nursery corner with soft warm cream-to-blush gradient background,
warm welcoming atmosphere, cozy mood,
bundle products elegantly arranged on right side,
left side with clean gradient space for text overlay,
subtle dusty rose and sage green accents, soft bokeh light elements,
pill-shaped badge area suggestion in warm red,
gentle sparkle and soft light effects,
premium e-commerce banner style,
no text, no logo, no watermark,
--ar 2:1 --sref {SA-03_URL} --sw 200 --stylize 300 --v 7
```

---

#### S4-FLUX: FLUX 1.1

```
Wide panoramic marketing banner. {SCENE} with soft warm gradient 
from cream to subtle blush tones. {EMOTION} atmosphere. 
{PRODUCT_NAME} elegantly positioned on the right side of frame. 
Left side has clean smooth gradient space designed for text overlay. 
Subtle {COLOR} accent details. Soft bokeh light effects. 
Gentle sparkle highlights. Premium e-commerce banner aesthetic. 
No text. No logos. No watermarks. Clean commercial photography style.
```

---

#### S4-SD: Stable Diffusion 3.5

```
(wide marketing banner:1.3), (SCENE:1.1),
(soft warm gradient background:1.3), (cream to blush:1.2),
(EMOTION atmosphere:1.2), (PRODUCT_NAME:1.2) on right side,
(clean space for text:1.3) on left side,
(subtle COLOR accents:1.1), (soft bokeh:1.2),
(gentle sparkle:1.1), (premium e-commerce:1.2),
no text, no logo, no watermark,
sharp focus, crisp detail, professional commercial photography
```

**负面Prompt:**
```
(text:1.5), (logo:1.5), (watermark:1.5), (signature:1.4),
(cluttered:1.3), (busy composition:1.3), (harsh colors:1.2),
low quality, blurry, pixelated
```

---

### S5: 包装 / 开箱图

> **用途**: 产品页信任区、礼品场景、开箱视频封面
> **比例**: 1:1 或 4:5
> **核心目标**: 建立开箱期待感，传递礼品属性

---

#### S5-MJ: Midjourney V7

```
{PRODUCT_NAME} premium packaging, unboxing moment,
elegant box in {COLOR} with soft matte finish,
product partially revealed with tissue paper,
{SCENE} background (bedside table, nursery dresser),
soft natural light, warm undertones,
cozy gift-giving atmosphere,
premium unboxing photography, lifestyle feel,
--ar 1:1 --sref {SA-03_URL} --sw 100 --stylize 200 --style raw --v 7
```

---

#### S5-FLUX: FLUX 1.1

```
Premium packaging photograph of {PRODUCT_NAME}. Elegant box 
in {COLOR} with soft matte finish. Product partially revealed 
with delicate tissue paper. Placed on {SCENE}. 
Soft natural light with warm undertones. 
Cozy gift-giving atmosphere. Lifestyle unboxing photography. 
Premium quality feel without luxury pretension.
```

---

#### S5-SD: Stable Diffusion 3.5

```
(premium packaging:1.3), (PRODUCT_NAME:1.2), (unboxing moment:1.2),
(elegant box:1.2) in (COLOR:1.1), (soft matte finish:1.2),
(product partially revealed:1.2), (tissue paper:1.1),
(SCENE:1.1), (soft natural light:1.2), (warm undertones:1.1),
(cozy gift atmosphere:1.2), (lifestyle unboxing:1.2),
no text, no logo, sharp focus, crisp detail
```

---

### S6: UGC真实感 / 社媒内容

> **用途**: Instagram Feed, TikTok封面, 用户证言配图
> **比例**: 4:5 或 9:16
> **核心目标**: 真实感、不完美的美、生活化

---

#### S6-MJ: Midjourney V7

```
Authentic phone-camera photo of {PRODUCT_NAME} in real use,
{MOM_ACTION} at home, {SCENE},
natural indoor lighting, slightly grainy, candid moment,
{PAIN_POINT} subtly implied, {EMOTION} visible,
real home environment with natural clutter,
no filter look, iPhone photography aesthetic,
warm slightly yellow tint, authentic imperfection,
--ar 4:5 --style raw --stylize 50 --v 7
```

**示例 (真实 pumping 场景):**
```
Authentic phone-camera photo of wearable breast pump in real use,
mom working on laptop at kitchen table, morning coffee nearby,
natural indoor lighting from window, slightly grainy, candid moment,
exhaustion subtly visible but relief on face,
real home environment with natural clutter,
no filter look, iPhone photography aesthetic,
warm slightly yellow tint, authentic imperfection,
--ar 4:5 --style raw --stylize 50 --v 7
```

---

#### S6-FLUX: FLUX 1.1

```
Authentic candid photograph taken with phone camera. 
Real mother {MOM_ACTION} at home in {SCENE}. 
Natural indoor window light. Slightly grainy texture. 
Authentic imperfection. Real home environment with natural everyday clutter. 
No filter aesthetic. Warm slightly yellow tint. 
Candid unposed moment. iPhone photography style.
```

---

#### S6-SD: Stable Diffusion 3.5

```
(authentic phone photo:1.3), (candid moment:1.3), 
(real mother:1.2) (MOM_ACTION:1.2), (SCENE:1.1),
(natural indoor light:1.2), (slightly grainy:1.2),
(authentic imperfection:1.3), (real home:1.2), (natural clutter:1.1),
(no filter:1.3), (warm yellow tint:1.1), (iphone aesthetic:1.2),
(unposed:1.3), (genuine moment:1.2)
```

**负面Prompt:**
```
(professional photography:1.3), (studio lighting:1.3), (perfect:1.4),
(polished:1.3), (model:1.3), (posed:1.3), (filter:1.3),
(cold lighting:1.2), (sterile:1.3), (clinical:1.3)
```

---

## 视频Prompt模板

### V1: 产品演示视频

> **时长**: 15-60s
> **核心结构**: 产品展示 → 功能演示 → 使用场景

---

#### V1-MJ/Runway (图生视频):

```
Scene 1 [0-3s]: Smooth push-in shot of {PRODUCT_NAME} on clean surface,
soft studio lighting, product slowly rotating to show form,
warm cream background, gentle shadow

Scene 2 [3-15s]: Close-up of {KEY_FEATURE} in action,
smooth macro shot, shallow depth of field,
soft ambient light highlighting {MATERIAL} texture,
quiet elegance, no harsh movements

Scene 3 [15-30s]: Lifestyle context shot,
mom using product in {SCENE}, natural window light,
authentic moment, warm atmosphere,
slow smooth camera movement, handheld subtle feel

Scene 4 [30-60s]: Resolution shot,
mom {MOM_ACTION} with peaceful expression,
soft golden hour light, warm tones,
slow pull-out to reveal full scene,
cozy content mood

Runway Gen-3 params:
- Motion brush: subtle on product, moderate on camera
- Camera: slow push-in (Scene 1), static macro (Scene 2), 
          gentle tracking (Scene 3), slow pull-out (Scene 4)
- Style: cinematic, warm tones, soft lighting
```

---

#### V1-Sora (文生视频):

```
Cinematic product demonstration video. 
Opening: Slow elegant push-in on {PRODUCT_NAME} resting on cream linen surface, 
soft natural window light, warm undertones. 
Then: Smooth transition to close-up of {KEY_FEATURE} gently in action, 
macro lens feel, shallow depth of field. 
Then: Real mother {MOM_ACTION} in cozy {SCENE}, 
natural daylight, authentic relaxed moment. 
Ending: Slow pull-out showing mom peacefully {MOM_ACTION} 
with gentle smile, warm golden light, cozy atmosphere. 
Overall mood: calm, empowering, gentle. 
No fast cuts. No dramatic music cues. Soft ambient audio.
```

---

### V2: UGC/测评视频

> **时长**: 3-10min (长) / 60s (短)
> **核心结构**: 痛点共鸣 → 产品介绍 → 真实使用 → 诚实评价

---

#### V2-Sora/Runway (文生视频):

```
Authentic user-generated style review video. 
Opening hook [0-3s]: Real mom's tired face in mirror reflection, 
morning light, messy hair, authentic exhaustion. 
Cut to [3-10s]: Her holding {PRODUCT_NAME}, genuine curious expression, 
natural kitchen background. 
Then [10-30s]: Close-up unboxing, hands opening package, 
real reactions, natural lighting, slightly grainy phone quality. 
Then [30-60s]: Product in use in real life context, 
no staging, natural home environment, authentic moment. 
Ending [60-90s]: Mom's genuine reaction - relief smile, 
natural thumbs up, warm authentic feeling. 
Style: iPhone camera, natural indoor light, slightly warm tint, 
authentic imperfection, no filter.
```

---

### V3: 品牌广告视频

> **时长**: 15-30s
> **核心结构**: 情感钩子 → 产品融入 → 品牌Slogan

---

#### V3-Sora/Runway:

```
Cinematic brand advertisement for Momcozy. 
[0-3s] Hook: Extreme close-up of baby crying, then cut to mom's tired eyes, 
soft focus, warm but emotionally charged lighting. 
[3-8s] Transition: Soft focus pull to {PRODUCT_NAME} being gently picked up, 
smooth elegant motion, cream and warm red tones. 
[8-20s] Solution: Mom using product while peacefully reading a book, 
soft natural window light, warm golden hour feel, 
slow gentle camera movement, cozy atmosphere. 
[20-25s] Resolution: Mom's peaceful smile, baby content in background, 
warm sunset light through window. 
[25-30s] Logo reveal: Momcozy logo with slogan "Just You, Refreshed" 
in elegant serif typography, centered, warm fade.

Mood: empowering, peaceful, warm, authentic.
Lighting: warm golden tones throughout, soft diffused.
Camera: slow smooth movements, cinematic dolly shots.
Music suggestion: Lo-fi beats with gentle piano, building to peaceful resolution.
```

---

### V4: 社媒短视频 (Reels/Shorts)

> **时长**: 15-30s
> **核心结构**: 3秒钩子 → 快节奏展示 → CTA

---

#### V4-Sora/Runway/Pika:

```
Fast-paced social media short for Momcozy. 
[0-3s] HOOK: Split-second cut sequence: 
- Spilled milk (slow motion drop), 
- Mom's frustrated face (quick flash), 
- Text overlay space for "Tired of...?"
[3-8s] REVEAL: Quick zoom-in on {PRODUCT_NAME} in action, 
dynamic but smooth camera, warm red accent highlight on product.
[8-15s] BENEFIT: Rapid montage of mom doing multiple things 
while using product (typing, drinking coffee, reading), 
quick cuts but smooth transitions, warm tones.
[15-20s] PROOF: Real user reaction clip, authentic smile, 
natural lighting, text space for testimonial.
[20-25s] CTA: Product with price/badge, 
"Swipe Up" or "Link in Bio" text space, 
pill-shaped button suggestion in brand red.

Style: TikTok trending aesthetic, bold dynamic text spaces, 
warm color grade, Lo-fi beat synced to cuts.
```

---

## 文案Prompt模板

### C1: H1 首屏标题 (情感驱动)

```
Write a 10-word-or-less headline for Momcozy {PRODUCT_NAME}.
Tone: warm, empowering, slightly witty, never preachy.
Focus: emotional state, not product features.
Avoid: "best", "perfect", "should", command language.
Use brand lexicon: cozy, breezy, effortless, freeing.

Examples of good headlines:
- "Just You, Refreshed" (pump)
- "Wrapped in Comfort" (carrier)
- "Your Time, Reclaimed" (efficiency product)
- "Gentle on Skin, Fierce on Results" (skincare)

Output: 5 headline options with brief emotional rationale.
```

---

### C2: 产品描述文案 (利益驱动)

```
Write product description for Momcozy {PRODUCT_NAME}.
Structure:
1. Open with empathy (acknowledge the struggle)
2. Introduce solution gently (not "you need this")
3. Focus on benefit (time/freedom/dignity, not specs)
4. Close with warm CTA

Tone guidelines:
- Use "we" and "you" (平视视角)
- Never use "should", "must", "always"
- Never toxic positivity (no "enjoy every moment")
- Include 1 brand term naturally: Cozy Tech, DoubleFit, Momcozy Village
- Feel: like advice from a trusted friend, not a salesperson

Example opening: "We know 3am feedings don't leave much energy for...
" → Not: "Every mom needs this essential product..."

Output: 150-200 words, followed by 3 alternative opening hooks.
```

---

### C3: 社媒文案 (UGC风格)

```
Write Instagram caption for Momcozy {PRODUCT_NAME} in authentic UGC style.
Guidelines:
- Start with real moment, not product
- Use casual language, lowercase friendly
- Include 1-2 emojis max, natural placement
- Mention product benefit in personal story context
- Hashtag: #MomcozyVillage #CozyHer + 2 product-specific
- CTA: gentle, not pushy

Example style: "girl, i was SO skeptical about wearable pumps 
but this little thing let me actually finish my coffee 
while pumping this morning 🙌 no wires, no noise, 
just me and my cozy moment. #MomcozyVillage #CozyHer"

Output: 3 caption options (short/medium/long), 
each with suggested visual description.
```

---

## 负面Prompt总库

### 通用负面 (All Models)

```
low quality, worst quality, jpeg artifacts, blurry, noisy, 
pixelated, oversaturated, undersaturated, overexposed, underexposed,
watermark, signature, text overlay, logo, brand name,
ugly, deformed, extra fingers, bad anatomy, asymmetrical face,
floating limbs, disconnected limbs, extra limbs, mutated hands,
bad proportions, duplicate, morbid, mutilated, out of frame
```

### 品牌调性负面 (Momcozy Specific)

```
clinical, hospital, medical-grade, sterile, cold, rigid,
perfect model, professional model, heavy makeup, 
posed portrait, artificial smile, fake happiness,
toxic positivity, preachy, condescending,
machine, device, gadget, appliance (替代: companion, helper, support),
weight loss, slimming, diet, anti-aging,
harsh lighting, high contrast, dramatic shadows,
cold fluorescent, studio flash, blue tint,
complex background, cluttered, chaotic,
vector art, bold outlines, illustration style, 
3D render, CGI look, anime, cartoon, comic,
neon colors, fluorescent, psychedelic,
sterile digital look, overly polished, artificial perfection
```

### 场景特定负面

**Lifestyle场景额外负面:**
```
studio backdrop, fake home, set design, prop styling,
overly organized, Pinterest-perfect, showroom,
white walls only, no personality, generic apartment
```

**产品白底图额外负面:**
```
cluttered background, busy environment, people, hands,
dust, scratches, damage, fingerprints on product,
reflection distortion, color cast, uneven lighting
```

**Banner额外负面:**
```
text, logo, watermark, signature, 
cluttered composition, too many elements,
harsh gradients, neon colors, busy patterns
```

---

## 参数速查表

### Midjourney V7

| 场景 | --ar | --sref | --sw | --stylize | --c | --style |
|:---|:---|:---|:---|:---|:---|:---|
| S1 Hero Lifestyle | 4:5 | SA-01 | 150 | 250 | 0.3 | raw |
| S2 白底产品 | 1:1 | SA-01 | 80 | 150 | - | raw |
| S3 详情信息图 | 16:9 | SA-02 | 120 | 200 | - | raw |
| S4 Banner | 2:1 | SA-03 | 200 | 300 | - | - |
| S5 包装 | 1:1 | SA-03 | 100 | 200 | - | raw |
| S6 UGC | 4:5 | - | - | 50 | - | raw |

### FLUX 1.1

| 参数 | 建议值 |
|:---|:---|
| guidance_scale | 3.5 |
| steps | 28-30 |
| prompt_upsampling | false |
| 负面Prompt | 不使用 |
| 尺寸 | 按场景比例 |

### Stable Diffusion 3.5

| 参数 | 建议值 |
|:---|:---|
| Steps | 30 |
| CFG Scale | 7.0-7.5 |
| Sampler | DPM++ 2M Karras |
| ControlNet | 按需: Canny/Depth/Tile |
| LoRA | 风格LoRA权重 0.3-0.5 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| v1.0 | 2026-05-23 | 初始构建，覆盖6图片场景+4视频类型+3文案调性 |
