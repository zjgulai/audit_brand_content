# S3 · cbi（crossborder-image-agent-New-）平台规则注册表与证据合规

> 源码核对基于 `research/repos/` 下仓库快照（2026-09-15 抓取），
> 克隆目录名 `cbi/`，对应仓库 `xiaov971023/crossborder-image-agent-New-`，
> 逐文件实读，行数口径 `splitlines()`。
> 该目录内没有 `.git`，无法给出 commit hash，核对基准是快照文件内容本身。

本片回答一个问题：一个已经跑起来的「平台规则 + 视觉模型」双引擎图片合规工作台，把哪些部件拆成了可复用资产，哪些部件必须为美国母婴品类重写。

---

## 一、资产卡

### S3-01 平台 × 图片类型 × 维度的规则注册表结构

- **出处**：`cbi/backend/src/rules/platformRules.js:1-294`（已实读核实，`splitlines()` 计 294 行）
- **一句话**：三层乘法展开。平台 6 个，图片类型硬编码 8 个，每个「平台 × 图片类型」单元由 `imageRule()` 展开成固定维度的规则对象；平台层再把品类注册表的 key 全量灌进 `categories`。
- **原文**：

图片类型清单（8 个，硬编码，是全部规则矩阵的第二维）：

  ```7:16:cbi/backend/src/rules/platformRules.js
const imageTypeKeys = [
  'main_image',
  'feature_image',
  'size_image',
  'compatibility_image',
  'package_image',
  'lifestyle_image',
  'detail_image',
  'variant_image'
];
  ```

`imageRule()` 的参数默认值与返回结构。注意这里同时产出现代字段与一组 legacy 别名：

  ```31:84:cbi/backend/src/rules/platformRules.js
function imageRule({
  required = false,
  backgroundAllowed = ['clean_neutral'],
  backgroundRecommended = 'clean_neutral',
  backgroundStrict = false,
  textAllowed = true,
  productArea = 65,
  allowProps = true,
  allowLifestyleScene = false,
  forbiddenElements = globalForbidden,
  severity = {},
  notes = ''
} = {}) {
  return {
    required,
    background: {
      allowed: backgroundAllowed,
      recommended: backgroundRecommended,
      strict: backgroundStrict
    },
    text: {
      allowed: textAllowed,
      allowedExceptions: [],
      forbiddenLanguages: ['Chinese'],
      forbiddenPatterns: ['price', 'discount', 'promotion', 'best seller', 'no.1', 'review stars']
    },
    product: {
      mustShowProductClearly: true,
      mustNotCropProduct: true,
      recommendedProductAreaPercent: productArea,
      allowProps,
      allowLifestyleScene
    },
    forbiddenElements,
    file: {
      minWidth: 1000,
      minHeight: 1000,
      recommendedWidth: 2000,
      recommendedHeight: 2000,
      formats: ['jpg', 'jpeg', 'png']
    },
    severity: {
      text: textAllowed ? 'medium' : 'high',
      chineseText: 'high',
      nonWhiteBackground: backgroundStrict ? 'high' : 'medium',
      watermark: 'high',
      price: 'high',
      promotion: 'high',
      sellerLogo: 'high',
      unconfirmedCertification: 'high',
      unconfirmedCapacity: 'high',
      sourceMock: 'medium',
      ...severity
    },
  ```

两个预置模板。`strictMain` 给 Amazon / Noon 用（纯白底、禁文字、产品占画幅 85%），`simpleMain` 给其余平台用：

  ```105:115:cbi/backend/src/rules/platformRules.js
const strictMain = (notes) => imageRule({
  required: true,
  backgroundAllowed: ['pure_white'],
  backgroundRecommended: 'pure_white',
  backgroundStrict: true,
  textAllowed: false,
  productArea: 85,
  allowProps: false,
  allowLifestyleScene: false,
  notes
});
  ```

辅图模板与它的 override 通道：

  ```129:137:cbi/backend/src/rules/platformRules.js
const auxiliary = (notes, overrides = {}) => imageRule({
  textAllowed: true,
  allowProps: true,
  allowLifestyleScene: Boolean(overrides.allowLifestyleScene),
  backgroundAllowed: overrides.backgroundAllowed || ['clean_neutral', 'light_commercial', 'simple_scene'],
  backgroundRecommended: overrides.backgroundRecommended || 'clean_neutral',
  productArea: overrides.productArea || 65,
  notes
});
  ```

「平台 → 8 种图片类型」的装配函数，逐个图片类型写 `notes`（规则的自然语言版本）：

  ```139:161:cbi/backend/src/rules/platformRules.js
function imageTypesForPlatform(platformId) {
  const mainNotes = {
    amazon: 'Amazon main image: pure white background, no text, no icons, no selling points, no scene background.',
    temu: 'Temu main image: product clear and centered, simple background, no Chinese, price, watermark, or exaggerated promotion.',
    noon: 'Noon main image: white background preferred; no watermark, price, promotion, seller logo, or unsupported warranty text.',
    ozon: 'Ozon main image: product clear and complete; text and scene background are not recommended.',
    rakuten: 'Rakuten main image: product clear, simple background, avoid excessive text and promotional badges.',
    marketplace: 'Marketplace main image: product-first, no text, price, watermark, or promotional badges.'
  }[platformId];
  const main = platformId === 'amazon' || platformId === 'noon'
    ? strictMain(mainNotes)
    : simpleMain(mainNotes);
  return {
    main_image: main,
    feature_image: auxiliary('Auxiliary feature images may use target-language selling points if confirmed. No price, fake certification, watermark, or Chinese.'),
    size_image: auxiliary('Size/spec images may show confirmed dimensions, capacity, ports, and visible specs only.'),
    compatibility_image: auxiliary('Compatibility images may show confirmed devices/interfaces only; avoid broad unsupported compatibility claims.'),
    package_image: auxiliary('Package images may show confirmed package contents only.'),
    lifestyle_image: auxiliary('Lifestyle images may use a scene background while preserving product appearance. No price, watermark, or unconfirmed specs.', { allowLifestyleScene: true, backgroundRecommended: 'realistic_scene', productArea: 50 }),
    detail_image: auxiliary('Detail images may label confirmed material, ports, texture, and visible details.'),
    variant_image: auxiliary('Variant images may show confirmed color, capacity, size, or model variants only.')
  };
}
  ```

平台对象的工厂。`categories` 直接取品类注册表的全部 key，`certificationRules` 与 `globalForbidden` 在这一层注入：

  ```163:190:cbi/backend/src/rules/platformRules.js
function platform({ platformId, platformName, sites, defaultLanguage, supportedLanguages, notes }) {
  return {
    platformId,
    platformName,
    name: platformName,
    sites,
    defaultLanguage,
    supportedLanguages,
    languages: supportedLanguages,
    categories: supportedCategoryIds,
    imageTypes: imageTypesForPlatform(platformId),
    globalForbidden,
    languageRules: {
      forbiddenLanguages: ['Chinese'],
      targetLanguageOnly: true,
      supportedLanguages
    },
    certificationRules: {
      requireEvidence: true,
      forbiddenWithoutEvidence: ['FDA', 'CE', 'FCC', 'RoHS', 'warranty', 'waterproof', 'medical claims']
    },
    notes: [
      'Internal auxiliary rule set only. It does not represent official final marketplace approval.',
      ...notes
    ],
    ruleVersion: RULE_VERSION
  };
}
  ```

注册表本体（6 个 key，节选前 3 个）：

  ```192:208:cbi/backend/src/rules/platformRules.js
export const platformRuleRegistry = {
  marketplace: platform({
    platformId: 'marketplace',
    platformName: 'Marketplace',
    sites: ['US'],
    defaultLanguage: 'English',
    supportedLanguages: ['English'],
    notes: ['Generic fallback rules for unsupported platforms.']
  }),
  amazon: platform({
    platformId: 'amazon',
    platformName: 'Amazon',
    sites: ['US', 'JP', 'EU'],
    defaultLanguage: 'English',
    supportedLanguages: ['English', 'Japanese'],
    notes: ['Amazon rules are conservative: main image should be pure white and text-free.']
  }),
  ```

对外列表接口。这里有一个容易踩的细节：`marketplace` 被过滤掉，所以 HTTP 层看到的是 5 个平台，注册表内部是 6 个：

  ```257:274:cbi/backend/src/rules/platformRules.js
export function listPlatformRules() {
  return {
    platforms: Object.values(platformRuleRegistry)
      .filter((platformItem) => platformItem.platformId !== 'marketplace')
      .map((platformItem) => ({
        platformId: platformItem.platformId,
        name: platformItem.name,
        platformName: platformItem.platformName,
        sites: platformItem.sites,
        languages: platformItem.languages,
        supportedLanguages: platformItem.supportedLanguages,
        categories: platformItem.categories,
        ruleVersion: platformItem.ruleVersion
      })),
    imageTypes,
    rules: platformRuleRegistry
  };
}
  ```

- **为什么这样做 / 不这样做会出什么事**：把「平台 × 图片类型」当成二维矩阵、把「维度」当成每个单元的固定 schema，规则数量从写死的 N 条降到 6 × 8 = 48 个单元，每个单元再复用同一套维度定义。若改成逐条 if 判断，加一个平台就要动审核、提示词、导出三条链路；矩阵形态下只加一个 key。
- **代价与局限**：三种成本。第一，`imageRule()` 的返回对象有 19 处字面量、18 个不同键（`background` 在第 46 行与第 88 行各出现一次，两处值相同，后者覆盖前者，前一处是死代码），其中 10 个是 legacy 别名：`title`、`textAllowed`、`watermarkAllowed`、`logoAllowed`、`minSize`、`recommendedSize`、`productArea`、`fileFormats`、`bannedElements`、`languageRules`。legacy 兼容层没有被清理过。第二，`severity` 是每个 imageRule 各自持有的默认值，改一个平台的主图严重度要改模板，注册表没有平台级 override 通道。第三，8 个图片类型硬编码在 `imageTypeKeys` 里，加类型必须改源码，不能靠配置。
- **Momcozy 迁移形态**：直接搬矩阵形态，替换第二维取值。`imageTypeKeys` 改为 `['main_image','feature_image','size_image','compatibility_image','package_image','lifestyle_image','detail_image','variant_image','a_plus_module','video_cover','ugc_asset','benchmark_reference']`；平台维度改为 `amazon`（US，`sites: ['US']`，删掉仓库里的 `'JP','EU'`，欧盟另开一个 `amazon_eu` 行以免误放宽）、`tiktok_shop_us`、`walmart_us`、`shopify_dtc`、`target_plus`。维度保留 `background`、`text`、`product`、`forbiddenElements`、`file`、`severity` 六组加 `notes`，删掉 10 个 legacy 别名（`title`、`textAllowed`、`watermarkAllowed`、`logoAllowed`、`minSize`、`recommendedSize`、`productArea`、`fileFormats`、`bannedElements`、`languageRules`）与重复的 `background` 键一处。
- **证据强度**：已实读核实。`background` 重复键的判断来自逐行比对两个键的值完全相同。
- **横向对比**：`ad-review-agent/harness/constraints.yaml:1-198`（198 行）走的是另一条路，把阈值抽成 YAML 单一来源，按维度分组声明。它的代价是维度之间的组合关系（哪个平台的哪种图允许什么）无法在 YAML 里表达，只能靠代码里的维度名约定；cbi 的矩阵形态把组合关系编码进结构，代价是规则条目数量随平台数线性增长。

---

### S3-02 `globalForbidden` 全局禁列

- **出处**：`cbi/backend/src/rules/platformRules.js:18-29`、`cbi/backend/src/rules/platformRuleUtils.js:33-36`（已实读核实）
- **一句话**：10 项全局禁列声明在平台层，作为 `imageRule()` 的默认 `forbiddenElements` 灌进每一个图片类型；取值时与平台级禁列做并集去重。
- **原文**：

  ```18:29:cbi/backend/src/rules/platformRules.js
const globalForbidden = [
  'price',
  'discount',
  'promotion',
  'watermark',
  'seller_logo',
  'fake_certification',
  'best_seller_badge',
  'review_stars',
  'unsupported_logo',
  'chinese_text'
];
  ```

默认值把全局禁列塞进每个 imageRule，同时给 `text` 维度预置了语言与模式禁列：

  ```33:43:cbi/backend/src/rules/platformRules.js
  backgroundAllowed = ['clean_neutral'],
  backgroundRecommended = 'clean_neutral',
  backgroundStrict = false,
  textAllowed = true,
  productArea = 65,
  allowProps = true,
  allowLifestyleScene = false,
  forbiddenElements = globalForbidden,
  severity = {},
  notes = ''
} = {}) {
  ```

`text` 维度的完整定义：

  ```51:56:cbi/backend/src/rules/platformRules.js
    text: {
      allowed: textAllowed,
      allowedExceptions: [],
      forbiddenLanguages: ['Chinese'],
      forbiddenPatterns: ['price', 'discount', 'promotion', 'best seller', 'no.1', 'review stars']
    },
  ```

取值时做并集，平台级与图片类型级禁列合并后去重：

  ```33:36:cbi/backend/src/rules/platformRuleUtils.js
export function getForbiddenElements({ platformId, imageType } = {}) {
  const { platform, rule } = getPlatformRule({ platformId, imageType });
  return [...new Set([...(platform.globalForbidden || []), ...(rule.forbiddenElements || rule.bannedElements || [])])];
}
  ```

- **为什么这样做 / 不这样做会出什么事**：禁列放在平台层，图片类型层可以只声明增量。取值侧用 `Set` 并集，避免图片类型覆盖掉平台级禁列（若用 `rule.forbiddenElements || platform.globalForbidden`，一旦图片类型自定义了禁列，全局禁列就整批失效）。
- **代价与局限**：`globalForbidden` 是纯字符串枚举，与 `severity` 的键名不是一一对应。取值函数先做精确匹配，匹配不到再做 snake_case 到 camelCase 的转换匹配：

  ```51:54:cbi/backend/src/rules/platformRuleUtils.js
export function getRuleSeverity({ platformId, imageType, issueType } = {}) {
  const rule = getImageTypeRule({ platformId, imageType });
  return rule.severity?.[issueType] || rule.severity?.[String(issueType || '').replace(/_([a-z])/g, (_, char) => char.toUpperCase())] || 'medium';
}
  ```

按这两步算，10 个值里 `price`、`promotion`、`watermark` 精确命中，`chinese_text` 与 `seller_logo` 走 camelCase 命中 `chineseText` 与 `sellerLogo`，剩下 `discount`、`fake_certification`、`best_seller_badge`、`review_stars`、`unsupported_logo` 这 5 个在默认 `severity` 里没有对应键，会落到 `'medium'` 兜底。实际影响有限：`getRuleSeverity()` 在 `ruleBasedReview.js` 里的 8 个调用点传入的 issueType 是 `sourceMock`、`text`、`nonWhiteBackground`、`chineseText`、`price`、`promotion`、`unconfirmedCertification`、`unconfirmedCapacity`，没有一个来自 `globalForbidden` 的字面值，所以这 5 个缺口只影响那些直接拿禁列值当 issueType 的调用方。
- **Momcozy 迁移形态**：`globalForbidden` 扩充为 `['price','discount','promotion','watermark','seller_logo','fake_certification','best_seller_badge','review_stars','unsupported_logo','chinese_text','third_party_brand_logo','competitor_comparison_table','medical_facility_imagery','lactation_consultant_endorsement','before_after_pair','infant_sleep_claim']`。同时补一张 `severityByForbiddenElement` 映射表，把 `discount`、`fake_certification`、`best_seller_badge`、`review_stars`、`unsupported_logo` 这 5 个缺键的值补齐，避免它们统一落到 medium。`text.forbiddenLanguages` 从 `['Chinese']` 改为 `['Chinese','Japanese','Korean']`（Momcozy 供应链侧素材常带日韩标签），`text.forbiddenPatterns` 追加 `'FDA cleared'`、`'BPA free'`、`'#1'`、`'best seller'`、`'clinically proven'`、`'doctor recommended'`、`'hospital grade'`。
- **证据强度**：已实读核实。「5 个值没有对应 severity 键」是逐个键名比对 `globalForbidden` 与 `severity`，并计入 `getRuleSeverity()` 的 camelCase 回退后得到的。
- **横向对比**：`ad-review-agent/src/rules/forbidden_words.json:7-18` 的词库把每个词族写成对象，带 `severity`、`regulation_ref`（法条锚点）、`words[]`。词库形态天然带法规出处，适合中国大陆《广告法》这类有明确条文编号的语境；cbi 的禁列是平铺字符串数组，没有法条锚点，代价是每条违规无法回溯到具体法规，好处是同一套禁列能被多个平台共用而不必为每个平台写一遍法条。

---

### S3-03 `certificationRules.forbiddenWithoutEvidence`：认证类 claim 的无证据禁列

- **出处**：`cbi/backend/src/rules/platformRules.js:180-183`、`cbi/backend/src/providers/review/ruleBasedReview.js:8`、`cbi/backend/src/providers/review/ruleBasedReview.js:152-154`、`cbi/backend/src/rules/categoryRules.js:134-138`（已实读核实）
- **一句话**：平台层声明 7 项「无证据即禁」的认证与功效 claim，确定性正则层再做一次认证词命中检查并取 `unconfirmedCertification` 严重度；品类层有一份针对医疗器械的独立版本，逐条写具体措辞。
- **原文**：

平台层声明，注意这是所有 6 个平台共用的同一份清单：

  ```180:183:cbi/backend/src/rules/platformRules.js
    certificationRules: {
      requireEvidence: true,
      forbiddenWithoutEvidence: ['FDA', 'CE', 'FCC', 'RoHS', 'warranty', 'waterproof', 'medical claims']
    },
  ```

正则层的认证模式（`\b` 锚定，命中即报）：

  ```8:8:cbi/backend/src/providers/review/ruleBasedReview.js
const certificationPattern = /\b(fda|ce|fcc|rohs|certified|certification|warranty|guarantee|waterproof|medical|health)\b/i;
  ```

品类层里医疗器械品类把清单写成具体措辞，这一版比平台层细：

  ```134:138:cbi/backend/src/rules/categoryRules.js
  medical_device: {
    ...conservativeTemplate('medical_device', 'Medical Device', ['medical device', 'health device']),
    highRiskFields: ['medicalClaims', 'certifications', 'warranty', 'effectiveness'],
    forbiddenClaimsWithoutEvidence: ['FDA approved', 'medical grade', 'clinically proven', 'cure', 'treats']
  }
  ```

- **为什么这样做 / 不这样做会出什么事**：`forbiddenWithoutEvidence` 与「有证据就放行」的机制配套。平台层给的是宽口径的标记集合（`FDA`、`CE`、`medical claims`），正则层负责实际命中，品类层负责把宽口径展开成可判定的具体短语。三层各管一段，缺一层就会出现「规则写了但没人执行」。
- **代价与局限**：`forbiddenWithoutEvidence` 这个数组本身**没有被任何审核代码读取**。检索关键词 `forbiddenWithoutEvidence` 在 `backend/src/` 下只有一处命中，即写入点 `platformRules.js:182`（同一文件在扁平镜像目录 `cbi_src/` 里另有一处同内容的写入），没有任何读取点。真正生效的是 `platformRules.js:72-84` 的 `severity.unconfirmedCertification` 加上正则层的 `certificationPattern`。这是一处**声明与执行脱节**：改这个数组不会改变审核结论。
- **Momcozy 迁移形态**：保留三层的分工，把数组改成 Momcozy 母婴/吸乳器版并接上执行点。`certificationRules.forbiddenWithoutEvidence` 改为 `['FDA','FDA 510(k)','FDA cleared','FDA approved','class II device','BPA-free','BPA free','food-grade','food grade','medical-grade','medical grade','hospital-grade','pediatrician-recommended','pediatrician approved','doctor recommended','safe for newborns','newborn safe','clinically proven','clinically tested','lactation consultant approved','closed-system','anti-colic','hypoallergenic']`。在 `ruleBasedReview.js` 里新增一条按数组遍历的检查（参照第 169-173 行的 `forbiddenClaimsWithoutEvidence` 循环形态），在 `certificationPattern` 的粗粒度命中之外逐条判定。把 `severity.unconfirmedCertification` 保持 `'high'`，并为 `medicalClaims` 单列一个 `'high'` 键。
- **证据强度**：已实读核实。`forbiddenWithoutEvidence` 无读取点这一条来自全仓 `grep -rn` 检索。
- **横向对比**：`ad-compliance-agent/backend/review_agents/orchestrator.py:64-72` 把认证类主张归入「可验证主张」，要求先判定 `evidence_confirmed / evidence_missing / evidence_conflict / not_required` 四态，并明确禁止把「无法验证真实性」直接等同于虚假宣传。cbi 的做法更硬：只要命中认证词且没有 `visible_text` 证据就直接报 high，没有「证据冲突」这一态，代价是无法区分「用户填了但填错」与「用户完全没填」。

---

### S3-04 确定性正则层：价格 / 促销 / 认证 / 中文

- **出处**：`cbi/backend/src/providers/review/ruleBasedReview.js:1-8`、`120-123`（已实读核实，`splitlines()` 计 271 行）
- **更正**：前一份报告把这一层的实现文件写成 `backend/src/rules/ruleBasedReview.js`。该路径不存在。检索关键词 `promotionPattern`、`certificationPattern`、`chinesePattern`、`pricePattern`、`ruleBased` 后，真实位置是 `cbi/backend/src/providers/review/ruleBasedReview.js`（271 行），目录 `cbi/backend/src/rules/` 下只有 `platformRules.js`、`platformRuleUtils.js`、`categoryRules.js`、`categoryRuleUtils.js` 四个文件。扁平镜像目录 `cbi_src/` 提供了一条旁证：该目录把 26 个源文件按原路径用下划线拼成文件名，其中存在 `cbi_src/cbi_backend_src_providers_review_ruleBasedReview.js`（与 `cbi/backend/src/providers/review/ruleBasedReview.js` 逐字节相同），不存在任何 `_rules_ruleBasedReview.js` 形式的文件。
- **一句话**：四个正则常量定义在同一处，覆盖中文、价格、促销、认证四类；`runRuleBasedReviewChecks()` 把它们跑在「图片文字排版 + 计划文案块 + 标题 + 文件名」拼成的单一字符串上。
- **原文**：

真实实现文件的开头，同时给出它在 `providers/review/` 目录内、且被同目录三个文件 import：

  ```1:8:cbi/backend/src/providers/review/ruleBasedReview.js
import { maxRiskLevel, normalizeReviewResult } from './normalizeReviewResult.js';
import { getForbiddenElements, getRuleSeverity, isTextAllowed, platformRuleSnapshotForImage } from '../../rules/platformRuleUtils.js';
import { categoryRuleSnapshotForImage } from '../../rules/categoryRuleUtils.js';

const chinesePattern = /[\u3400-\u9fff]/;
const pricePattern = /([$€£¥]|USD|EUR|AED|SAR|JPY|RUB|\d+\.\d{2})/i;
const promotionPattern = /\b(discount|coupon|sale|best seller|no\.?\s*1|limited time|free shipping|% off)\b|\d+\s?%/i;
const certificationPattern = /\b(fda|ce|fcc|rohs|certified|certification|warranty|guarantee|waterproof|medical|health)\b/i;
  ```

四个正则的应用点，每一处都把命中的原文塞进 `evidence`：

  ```120:123:cbi/backend/src/providers/review/ruleBasedReview.js
  if (chinesePattern.test(text)) issues.push(issue('chinese_text', getRuleSeverity({ platformId, imageType, issueType: 'chineseText' }), 'Chinese text detected or planned in image text.', [text.match(chinesePattern)?.[0] || 'Chinese text'], meta('text', 'chineseText')));
  if (pricePattern.test(text)) issues.push(issue('price_text', getRuleSeverity({ platformId, imageType, issueType: 'price' }), 'Price text detected or planned in image.', [text], meta('text', 'price')));
  if (promotionPattern.test(text)) issues.push(issue('promotion_text', getRuleSeverity({ platformId, imageType, issueType: 'promotion' }), 'Promotion or marketplace-sensitive text detected.', [text], meta('text', 'promotion')));
  if (certificationPattern.test(text)) issues.push(issue('unconfirmed_certification_or_claim', getRuleSeverity({ platformId, imageType, issueType: 'unconfirmedCertification' }), 'Certification, warranty, waterproof, medical, or health claim needs explicit confirmation.', [text], meta('evidence', 'unconfirmedCertification')));
  ```

- **为什么这样做 / 不这样做会出什么事**：四类禁项各用一条正则在毫秒级跑完全部图片，不调模型。这一层的输出还会作为 `preliminaryRuleBasedIssues` 注入视觉模型的提示词（见 `cbi/backend/src/providers/review/reviewPrompt.js:45-50`），让模型在已命中的线索上做复核，省去它从零判断的步骤。
- **代价与局限**：正则跑在 `collectImageText()` 拼出的字符串上，该字符串包含 `image.fileName`（`ruleBasedReview.js:37`）。文件名里带 `$`、`%` 或 `fda` 会直接误报。促销正则 `/\b(discount|coupon|sale|best seller|no\.?\s*1|limited time|free shipping|% off)\b|\d+\s?%/i` 的尾部 `|\d+\s?%` 没有 `\b` 锚定也没有上下文约束，任何百分比数值（含 `100% cotton` 这类合规表述）都会命中。
- **另一个发现**：同一个仓库里存在**三套互不相同的确定性正则层**。除本卡的实现外，`cbi/backend/src/services/complianceService.js:1-5` 有一套更窄的版本（价格正则只有 `[$]`，还多了 `watermarkPattern` 与 `logoPattern`），`cbi/backend/src/services/ruleAuditService.js:3-4` 有第三套（价格正则要求币种符号后接数字，或数字后接币种代码）。

  ```1:5:cbi/backend/src/services/complianceService.js
const chinesePattern = /[\u3400-\u9fff]/;
const pricePattern = /([$]|USD|EUR|AED|SAR|JPY|RUB|\d+\.\d{2})/i;
const watermarkPattern = /(watermark|sample|preview)/i;
const logoPattern = /(nike|adidas|apple|disney|starbucks|coca-cola)/i;
const certificationPattern = /\b(fda|ce|ul certified|organic certified)\b/i;
  ```

  ```3:4:cbi/backend/src/services/ruleAuditService.js
const CHINESE_PATTERN = /[\u3400-\u9fff]/;
const PRICE_PATTERN = /(?:[$€£¥]\s?\d|\b\d+(?:\.\d{1,2})?\s?(?:usd|eur|gbp|rmb|cny)\b)/i;
  ```

三套正则的命中最弱的一套决定实际行为，判断哪一套在跑需要顺着调用链查。这是迁移时最需要避免继承的部分。
- **Momcozy 迁移形态**：只保留 `providers/review/ruleBasedReview.js` 一套，把另外两套标记为 deprecated 并从调用链摘除。四个正则按美国市场重写：`chinesePattern` 保留 `[\u3400-\u9fff]`；`pricePattern` 改为 `/[$]\s?\d|\b\d+(?:\.\d{2})?\s?(?:usd|dollars?)\b/i`（删掉 `€£¥` 与 AED/SAR/JPY/RUB，这些是欧亚站点币种）；`promotionPattern` 拆成两条，促销词一条 `/\b(discount|coupon|promo code|sale|best seller|#1|no\.?\s*1|limited time|free shipping|clearance|deal of the day)\b/i`，百分比一条 `/\b\d{1,3}\s?%\s?(off|more|savings?)\b/i`（加 `off/more/savings` 限定，避免 `100% cotton` 误报）；`certificationPattern` 改为 `/\b(fda|fda\s?510\(?k\)?|cleared|approved|bpa[- ]free|food[- ]grade|medical[- ]grade|hospital[- ]grade|pediatrician|clinically|hypoallergenic|certified|waterproof)\b/i`，并**从匹配文本中剔除 `image.fileName`**。
- **证据强度**：已实读核实。三套正则共存来自逐文件实读，不是推断。
- **横向对比**：`invoice/backend/app/agents/cross_validator.py:254` 的 `_execute` 也是确定性规则先行，但它把 4 条硬规则（金额一致性、主体匹配、重复、条目覆盖）写成**带上下文的检查函数**，每条返回结构化 issue，判定粒度高于单行正则。代价是每加一条规则要写一个函数；cbi 的形态加规则只需加一个词，代价是上下文丢失带来的误报。

---

### S3-05 Claim 必须带可见证据：`source === 'visible_text'` 的严格定义

- **出处**：`cbi/backend/src/providers/review/ruleBasedReview.js:40-59`、`131-135`、`169-173`；`cbi/backend/src/providers/vision/normalizeVisionResult.js:228-242`、`382-399`；`cbi/backend/src/prompts/imagePromptFactory.js:114-132`（已实读核实）
- **一句话**：证据对象有四种 source（`visible_text` / `visual` / `inferred` / `user_input`），只有 `visible_text` 能满足「高风险字段」的准入；另有一条更宽的 `hasAnyEvidence()` 只要求存在任意证据。
- **原文**：

严格版。只有 `source === 'visible_text'` 且文本包含待验证值才算证据，用户填写的字段本身不算：

  ```40:48:cbi/backend/src/providers/review/ruleBasedReview.js
function hasVisibleTextEvidence(task, field, value) {
  const evidence = task.fieldEvidence?.[field];
  if (!Array.isArray(evidence) || !evidence.length) return false;
  const expected = String(value || '').toLowerCase();
  return evidence.some((item) => {
    const text = String(item.text || item.value || '').toLowerCase();
    return item.source === 'visible_text' && (!expected || text.includes(expected));
  });
}
  ```

宽版。只要有任意 source 的证据即可，不做 source 过滤：

  ```50:59:cbi/backend/src/providers/review/ruleBasedReview.js
function hasAnyEvidence(task, field, value) {
  const evidence = task.fieldEvidence?.[field];
  if (!Array.isArray(evidence) || !evidence.length) return false;
  if (!value) return true;
  const expected = String(value || '').toLowerCase();
  return evidence.some((item) => {
    const text = String(item.text || item.value || '').toLowerCase();
    return !expected || text.includes(expected);
  });
}
  ```

严格版的实际调用点（容量声明）：

  ```131:135:cbi/backend/src/providers/review/ruleBasedReview.js
  for (const value of asArray(task.productInfoConfirmed?.capacity)) {
    if (text.toLowerCase().includes(String(value).toLowerCase()) && !hasVisibleTextEvidence(task, 'capacity', value)) {
      issues.push(issue('unconfirmed_capacity', getRuleSeverity({ platformId, imageType, issueType: 'unconfirmedCapacity' }), `Capacity "${value}" appears without visible text evidence.`, [value], meta('evidence', 'unconfirmedCapacity')));
    }
  }
  ```

品类层的通用循环，三种证据任一存在就放行：

  ```169:173:cbi/backend/src/providers/review/ruleBasedReview.js
  for (const claim of categoryRule.forbiddenClaimsWithoutEvidence || []) {
    if (claim && textContainsAny(text, [claim]) && !hasAnyEvidence(task, 'certifications') && !hasAnyEvidence(task, 'warranty') && !hasAnyEvidence(task, 'speed')) {
      issues.push(issue('category_forbidden_claim_without_evidence', 'high', `Category claim requires evidence before use: ${claim}`, [claim], categoryMeta('forbiddenClaim')));
    }
  }
  ```

四种 source 的白名单定义在视觉结果归一化层。白名单外的 source 一律降级为 `inferred`：

  ```228:242:cbi/backend/src/providers/vision/normalizeVisionResult.js
function normalizeEvidenceItem(item) {
  if (!item || typeof item !== 'object') return null;
  const source = ['visible_text', 'visual', 'inferred', 'user_input'].includes(item.source)
    ? item.source
    : 'inferred';
  return {
    source,
    imageIndex: Number.isInteger(item.imageIndex) ? item.imageIndex : null,
    imageName: typeof item.imageName === 'string' ? item.imageName : '',
    text: typeof item.text === 'string' ? item.text : '',
    reason: typeof item.reason === 'string' ? item.reason : '',
    value: stringifyArrayItem(item.value),
    confidence: clampConfidence(item.confidence)
  };
}
  ```

归一化层的强制剥离：`strictVisibleTextEvidenceFields` 里的字段若无 `visible_text` 证据，值被移到 `inferredCandidates` 并从确认信息里清空：

  ```382:399:cbi/backend/src/providers/vision/normalizeVisionResult.js
  for (const field of strictVisibleTextEvidenceFields) {
    const value = productInfoRaw[field];
    const reason = `${field} requires visible text evidence before it can be used as a confirmed product field.`;

    if (Array.isArray(value)) {
      const kept = [];
      for (const item of value) {
        if (hasVisibleTextEvidenceForValue(fieldEvidence, field, item)) kept.push(item);
        else pushInferredCandidate(inferredCandidates, field, item, reason);
      }
      if (kept.length !== value.length) notes.push(reason);
      productInfoRaw[field] = kept;
    } else if (value && !hasVisibleTextEvidenceForValue(fieldEvidence, field, value)) {
      pushInferredCandidate(inferredCandidates, field, value, reason);
      productInfoRaw[field] = null;
      notes.push(reason);
    }
  }
  ```

提示词工厂侧的同一条判定，产出 `blocked_without_visible_text` 状态，并给出中文提示语：

  ```114:132:cbi/backend/src/prompts/imagePromptFactory.js
function evidenceStatus(field, productInfo, fieldEvidence = {}) {
  const values = unique(valueForField(productInfo, field));
  const evidence = evidenceFor(fieldEvidence, field);
  const sources = evidenceSources(evidence);
  const hasVisibleText = sources.includes('visible_text');
  const onlyVisual = evidence.length > 0 && sources.every((source) => source === 'visual');
  const onlyInferred = evidence.length > 0 && sources.every((source) => source === 'inferred');
  let status = evidence.length ? 'has_evidence' : 'needs_confirmation';
  let riskLevel = evidence.length ? 'low' : 'medium';
  let message = evidence.length ? '有图片证据' : '需人工确认';

  if (!values.length) {
    return { field, values, evidence, sources, status: 'missing', riskLevel: 'medium', message: '缺少信息，建议补充' };
  }

  if (HIGH_RISK_TEXT_FIELDS.has(field) && !hasVisibleText) {
    status = 'blocked_without_visible_text';
    riskLevel = 'high';
    message = `${field} 缺少图片文字证据，不应进入图片文案`;
  ```

高风险与严格证据字段的名单：

  ```53:65:cbi/backend/src/prompts/imagePromptFactory.js
const HIGH_RISK_TEXT_FIELDS = new Set(['capacity', 'certifications', 'warranty']);
const STRICT_EVIDENCE_FIELDS = new Set([
  'capacity',
  'dimensions',
  'material',
  'interfaceType',
  'compatibleDevices',
  'packageIncluded',
  'certifications',
  'warranty',
  'model',
  'brand'
]);
  ```

- **为什么这样做 / 不这样做会出什么事**：用户手填的「容量 5TB」是**输入**，图中的「5TB」是**可核对的事实**。只有后者能证明这个数字真的出现在素材上。若把用户输入也算证据，审核就会退化成「相信自己填过的内容」，认证、容量、保修三类最容易造假的字段首当其冲。归一化层做了进一步的兜底：模型声称看到的值若没有对应 OCR 文本，就被降级成 `inferred` 并从确认字段里摘出去。
- **代价与局限**：`visible_text` 依赖 OCR 能读到文字。图片里是图形化排版、艺术字、异形角度的文字时，OCR 读不到，合规的素材也会被判 `blocked_without_visible_text`。仓库没有为这个漏检设计申诉通道，用户只能手工重新填。另外 `hasAnyEvidence()` 在品类循环里被当成放行条件，`certifications`、`warranty`、`speed` 三个字段任意一个有证据就放行全部 claim，这是一个**过宽的 or 条件**。
- **Momcozy 迁移形态**：`visible_text` 的定义保持不动，这是本仓库对美国市场合规最直接可用的一条。母婴幼儿品类扩一张字段表：`evidenceRequiredFields` 增加 `fdaClearance: 'visible_text'`、`bpaFree: 'visible_text'`、`foodGrade: 'visible_text'`、`medicalGrade: 'visible_text'`、`pediatricianEndorsement: 'visible_text'`、`ageRange: 'visible_text'`、`flowRate: 'visible_text'`、`noiseLevel: 'visible_text'`、`materialSafety: 'visible_text'`。把品类循环的 or 条件（第 170 行）改成按字段精确查表：`hasVisibleTextEvidence(task, claimEvidenceField, value)`，其中 `claimEvidenceField` 由 claim 到字段的映射表给出，`'FDA 510(k)'` 映射到 `fdaClearance`，`'BPA-free'` 映射到 `bpaFree`。`HIGH_RISK_TEXT_FIELDS` 从 `['capacity','certifications','warranty']` 扩为加上 `medicalClaims`、`fdaClearance`、`bpaFree`、`pediatricianEndorsement`。
- **证据强度**：已实读核实。
- **横向对比**：`ad-compliance-agent/backend/review_agents/orchestrator.py:64-72` 的四态（`evidence_confirmed / evidence_missing / evidence_conflict / not_required`）比 cbi 的两态（有 `visible_text` / 没有）表达力更强，能表达「用户填了但与图片矛盾」。它的代价是四态的判定要模型介入，无法只靠字符串比对得出；cbi 的严格定义牺牲表达力换来了完全确定性的判定，这也是它能被写成一个两行函数的原因。

---

### S3-06 issue 结构与 `ruleId` 命名

- **出处**：`cbi/backend/src/providers/review/ruleBasedReview.js:16-30`、`81-97`、`188-203`；`cbi/backend/src/providers/review/normalizeReviewResult.js:14-43`（已实读核实）
- **一句话**：issue 有 11 个字段，`ruleId` 按 `${platformId}.${imageType}.${type}` 拼装，品类层规则换成 `${categoryId}.${imageType}.${type}`；同一个 issue 在写入结果时会被 `normalizeIssue()` 补齐缺省值。
- **原文**：

issue 工厂，11 个字段，`evidence` 强制转字符串数组，`fixSuggestion` 有兜底：

  ```16:30:cbi/backend/src/providers/review/ruleBasedReview.js
function issue(type, level, message, evidence = [], meta = {}) {
  return {
    type,
    category: meta.category || 'general',
    level,
    message,
    evidence: asArray(evidence).map(String),
    imageArea: '',
    ruleId: meta.ruleId || type,
    platformId: meta.platformId || '',
    imageType: meta.imageType || '',
    categoryId: meta.categoryId || '',
    fixSuggestion: meta.fixSuggestion || `Fix: ${message}`
  };
}
  ```

两套 meta 生成器。平台/证据类用平台前缀，品类类用品类前缀：

  ```81:97:cbi/backend/src/providers/review/ruleBasedReview.js
  const meta = (category, type) => ({
    category,
    ruleId: `${platformRule.platformId}.${imageType}.${type}`,
    platformId: platformRule.platformId,
    imageType,
    categoryId: categoryRule.categoryId
  });
  const categoryMeta = (type, level = 'high') => ({
    category: 'category',
    ruleId: `${categoryRule.categoryId}.${imageType}.${type}`,
    platformId: platformRule.platformId,
    imageType,
    categoryId: categoryRule.categoryId,
    fixSuggestion: level === 'high'
      ? 'Remove the claim or add visible/user-confirmed evidence before using it in image copy.'
      : 'Use a narrower confirmed claim or ask the seller to confirm the detail.'
  });
  ```

写入审核结果时，快照与禁列一并挂在 `platformChecks` 上，使单条结果自带规则上下文：

  ```188:203:cbi/backend/src/providers/review/ruleBasedReview.js

  const riskLevel = issues.reduce((level, item) => maxRiskLevel(level, item.level), 'low');
  const pass = issues.length === 0;
  return normalizeReviewResult({
    pass,
    riskLevel,
    issues,
    fixSuggestions: issues.map((item) => `Fix: ${item.message}`),
    platformChecks: {
      mainImageTextAllowed: !(imageType === 'main_image' && asArray(plan.textBlocks).length),
      backgroundValid: true,
      watermarkDetected: false,
      platformRuleSnapshot: platformRule,
      categoryRuleSnapshot: categoryRule,
      forbiddenElements: forbidden
    },
  ```

视觉结果侧的归一化，把任意形状的 issue 收敛成同一组字段：

  ```14:43:cbi/backend/src/providers/review/normalizeReviewResult.js
function normalizeIssue(issue, index) {
  if (typeof issue === 'string') {
    return {
      type: 'general',
      category: 'visual',
      level: 'medium',
      message: issue,
      evidence: [],
      imageArea: '',
    ruleId: '',
    platformId: '',
    imageType: '',
    categoryId: '',
    fixSuggestion: ''
    };
  }
  return {
    type: String(issue?.type || `issue_${index + 1}`),
    category: String(issue?.category || 'visual'),
    level: normalizeRiskLevel(issue?.level, 'medium'),
    message: String(issue?.message || issue?.type || 'Review issue'),
    evidence: asArray(issue?.evidence).map((item) => String(item)),
    imageArea: String(issue?.imageArea || ''),
    ruleId: String(issue?.ruleId || ''),
    platformId: String(issue?.platformId || ''),
    imageType: String(issue?.imageType || ''),
    categoryId: String(issue?.categoryId || ''),
    fixSuggestion: String(issue?.fixSuggestion || '')
  };
}
  ```

- **为什么这样做 / 不这样做会出什么事**：`ruleId` 采用点分三段，可枚举、可统计、可回归。有了它，「近 30 天 Amazon 主图文字类违规下降了吗」这类问题可以只按前缀聚合。`evidence[]` 强制数组并转字符串，避免上游传字符串时下游 `.map` 崩掉。
- **代价与局限**：`ruleId` 里嵌的是 `imageType`，同一类规则在不同图片类型上是不同的 id，跨图片类型统计要先做前缀截断。另外 `ruleId` 不含版本号，规则版本号单独挂在结果的 `ruleVersion` 字段上，两者要在查询时手工拼。`ruleBasedReview.js:24` 的兜底是 `meta.ruleId || type`，一旦调用方忘了传 meta，产出的 `ruleId` 会退化成裸 `type`，与点分格式不一致。
- **Momcozy 迁移形态**：字段保留 11 个，追加三个：`assetId`（素材唯一 id，替代依赖 `imageArea` 的弱定位）、`locator`（改为结构化对象 `{assetId, frameIndex, bbox: [x, y, w, h], timecodeMs}`，兼容图片与视频）、`regulationRef`（法规锚点，取 `ad-review-agent` 的 `regulation_ref` 字段名，值形如 `FDA 21 CFR 801`、`FTC Health Products Compliance Guidance`）。`ruleId` 命名扩展为 `${platformId}.${imageType}.${ruleType}.${claimField}`，四段式，末段是 S3-05 的字段名，这样单条违规可以直接定位到需要补哪种证据。
- **证据强度**：已实读核实。
- **横向对比**：`ad-review-agent/src/rules/forbidden_words.json:9-10` 每条词族带 `severity` 与 `regulation_ref`（法条名加条款号），把法域信息编码进规则本身。cbi 的 issue 不带法条字段，代价是报告里给不出「违反了哪一条」；Momcozy 若要出美国市场审计报告，`regulationRef` 是必须补的字段，因为 FTC 与 FDA 的整改动作不同，报告要能区分。

---

### S3-07 规则快照冻结与版本号

- **出处**：`cbi/backend/src/rules/platformRules.js:3`、`184-189`、`276-294`；`cbi/backend/src/rules/categoryRules.js:1`；`cbi/backend/src/services/targetService.js:12-36`；`cbi/backend/src/prompts/imagePromptFactory.js:8`、`484-486`；`cbi/backend/src/providers/review/reviewPrompt.js:12`；`cbi/backend/src/services/exportService.js:30-49`（已实读核实）
- **一句话**：四个独立版本号（平台规则 `v3.2`、品类规则 `v3.3`、生图提示词 `v1.5`、审核提示词 `review-v3.1`），配套一个「快照对象」在 target 创建时算好，之后一路挂到 plan、审核结果、导出包，规则库再改也不影响已完成的审核。
- **原文**：

  ```3:3:cbi/backend/src/rules/platformRules.js
export const RULE_VERSION = 'v3.2';
  ```

平台对象把版本号写进自身，每条规则都带：

  ```184:189:cbi/backend/src/rules/platformRules.js
    notes: [
      'Internal auxiliary rule set only. It does not represent official final marketplace approval.',
      ...notes
    ],
    ruleVersion: RULE_VERSION
  };
  ```

快照函数，产出的是**值拷贝**而不是引用，这是冻结的关键：

  ```276:294:cbi/backend/src/rules/platformRules.js
export function getPlatformRuleSnapshot({ platformId, platform, site, language, category } = {}) {
  const normalizedPlatformId = normalizePlatformId(platformId || platform || 'amazon');
  const rule = platformRuleRegistry[normalizedPlatformId] || platformRuleRegistry.marketplace;

  return {
    platformId: rule.platformId,
    name: rule.name,
    platformName: rule.platformName,
    site: site || rule.sites[0],
    language: language || rule.defaultLanguage,
    category: category || rule.categories[0],
    imageTypes: rule.imageTypes,
    globalForbidden: rule.globalForbidden,
    languageRules: rule.languageRules,
    certificationRules: rule.certificationRules,
    notes: rule.notes,
    ruleVersion: rule.ruleVersion
  };
}
  ```

品类规则独立版本号：

  ```1:1:cbi/backend/src/rules/categoryRules.js
export const CATEGORY_RULE_VERSION = 'v3.3';
  ```

快照在 target 创建时算好并挂上，后续链路只读它：

  ```12:36:cbi/backend/src/services/targetService.js
  const rulesSnapshot = getPlatformRuleSnapshot({
    platformId,
    platform: input.platform,
    site: input.site,
    language: input.language || 'English',
    category: categoryId
  });
  const categoryRuleSnapshot = categoryRuleSnapshotForImage({
    categoryId,
    imageType: input.imageType,
    productInfoConfirmed: productInfo
  });
  return {
    id: input.id || input.targetId || `target-${rulesSnapshot.platformId}-${index + 1}-${nanoid(4)}`,
    targetId: input.targetId || input.id || undefined,
    platformId: rulesSnapshot.platformId,
    platformName: rulesSnapshot.platformName || rulesSnapshot.name,
    site: rulesSnapshot.site,
    language: rulesSnapshot.language,
    categoryId,
    category: categoryId,
    rulesSnapshot,
    platformRuleSnapshot: rulesSnapshot,
    categoryRuleSnapshot
  };
  ```

plan 上也挂一份：

  ```484:486:cbi/backend/src/prompts/imagePromptFactory.js
      rulesSnapshot: rule,
      platformRuleSnapshot: target.platformRuleSnapshot || null,
      categoryRuleSnapshot: target.categoryRuleSnapshot || null,
  ```

审核提示词版本与生图提示词版本各自独立：

  ```12:12:cbi/backend/src/providers/review/reviewPrompt.js
export const REVIEW_PROMPT_VERSION = 'review-v3.1';
  ```

  ```8:8:cbi/backend/src/prompts/imagePromptFactory.js
export const PROMPT_VERSION = 'v1.5';
  ```

导出侧从四个可能的位置回捞快照，并按「平台:站点:图片类型:语言」去重：

  ```30:49:cbi/backend/src/services/exportService.js
function platformRuleSnapshotFromImage(image = {}) {
  return image.platformRuleSnapshot ||
    image.generationRequestSummary?.platformRuleSnapshot ||
    image.generationRequest?.compliance?.platformRulesSnapshot ||
    null;
}

function platformRuleSnapshotsForTask(task, generatedImages = []) {
  const snapshots = [
    ...generatedImages.map(platformRuleSnapshotFromImage),
    ...(task.imagePlans || []).map((plan) => requestSummaryForPlan(task, plan)?.platformRuleSnapshot),
    ...(task.reviewResults || []).map((item) => item.platformRuleSnapshot || item.platformChecks?.platformRuleSnapshot)
  ].filter(Boolean);
  const byKey = new Map();
  for (const snapshot of snapshots) {
    const key = `${snapshot.platformId || snapshot.platformName || ''}:${snapshot.site || ''}:${snapshot.imageType || ''}:${snapshot.language || ''}`;
    byKey.set(key, snapshot);
  }
  return [...byKey.values()];
}
  ```

- **为什么这样做 / 不这样做会出什么事**：审核结论要能复现，就必须回答「当时用的是哪版规则」。`getPlatformRuleSnapshot()` 返回的是新对象，其嵌套值直接引用了注册表里的对象（JS 浅拷贝），所以规则库本身**没有冻结**，冻结的只是「平台 id、图片类型、禁列、严重度这些字段的当前取值」。三处写入（target、plan、审核结果）形成冗余，任一处丢失仍可从旁路恢复。
- **代价与局限**：浅拷贝是这里最需要注意的一点。`imageTypes: rule.imageTypes`（第 287 行）与 `globalForbidden: rule.globalForbidden`（第 288 行）传的是注册表内的对象引用，若运行时有代码修改注册表，历史快照会跟着变。仓库内没有这样的修改点，但这个不变量没有写下来保护。另一个代价是四个版本号彼此独立，没有「组合版本」，`v3.2 + v3.3 + review-v3.1` 这个三元组才能唯一确定一次审核行为，报告里必须三个都写。
- **Momcozy 迁移形态**：直接搬这个机制，并补两处。第一，`getPlatformRuleSnapshot()` 改为深拷贝（`structuredClone` 或 `JSON.parse(JSON.stringify())`），让快照真正不可变。第二，把四个版本号合并成一个 `auditProfileVersion`（形如 `momcozy-us-2026Q1`），内部记录 `{platformRuleVersion, categoryRuleVersion, imagePromptVersion, reviewPromptVersion, evidenceSchemaVersion}` 五项，单值入库。审核结果与导出包都带上这个单值，审计复现时只需比对它。
- **证据强度**：已实读核实。「浅拷贝」的判断来自第 287-288 行直接传引用。
- **横向对比**：`ad-review-agent/src/rules_loader.py` 走的是「数据库优先、JSON 保底、加缓存」的热更新路线，规则可在运行时替换。代价是历史结论必须自己存规则副本才能复现；cbi 选择了相反的取舍，快照随结果一起走，规则库不需要版本化存储，代价是每次结果都多存一份规则字段。

---

### S3-08 6 级严重度与 `isMockOnly` / `isRealComplianceRisk` 语义位

- **出处**：`cbi/backend/src/services/reviewFixSuggestionService.js:1-8`；`cbi/backend/src/services/reviewIssueService.js:103-127`、`165-167`；`cbi/backend/src/services/batchReviewReportService.js:4`、`56-64`；`cbi/backend/src/services/batchStabilityService.js:84-98`（已实读核实）
- **一句话**：6 级严重度 `fatal / high / medium / low / info / mockInfo`，`mockInfo` 单列一级；归一化时导出两个布尔位 `isMockOnly` 与 `isRealComplianceRisk`，报表统计、SKU 定级、批次稳定度三处都按这两个位分流。
- **原文**：

  ```1:8:cbi/backend/src/services/reviewFixSuggestionService.js
const SEVERITY_ORDER = {
  fatal: 0,
  high: 1,
  medium: 2,
  low: 3,
  info: 4,
  mockInfo: 5
};
  ```

issue 归一化。这两个布尔位在同一行导出，互为反相：

  ```103:127:cbi/backend/src/services/reviewIssueService.js
export function normalizeReviewIssue(issue = {}, context = {}) {
  const source = issue.source || context.source || 'reviewProvider';
  const code = normalizeCode(issue);
  const fieldKey = fieldKeyFor(issue);
  const category = categoryFor(issue, code);
  const severity = severityFor(issue, category);
  const isMockOnly = severity === 'mockInfo';
  return {
    code,
    severity,
    category,
    imageType: issue.imageType || issue.typeImage || context.imageType || '',
    fieldKey,
    fieldLabel: FIELD_LABELS[fieldKey] || issue.fieldLabel || '',
    message: String(issue.message || issueTextFromCode(code)),
    suggestion: suggestionFor(issue, code, category),
    source,
    isRealComplianceRisk: !isMockOnly,
    isMockOnly,
    canAutoFixLater: Boolean(!isMockOnly && ['text', 'field', 'platform'].includes(category)),
    requiresManualConfirm: Boolean(!isMockOnly && ['fatal', 'high'].includes(severity)),
    evidence: asArray(issue.evidence),
    rawLevel: issue.level || issue.severity || ''
  };
}
  ```

fix suggestion 侧再算一次，这里多了一个 `noActionNeeded` 的排除条件：

  ```132:150:cbi/backend/src/services/reviewFixSuggestionService.js
    const isMockOnly = actionType === 'skipMockOnly';
    const noAction = actionType === 'noActionNeeded';
    return {
      suggestionId: `fix-${String(index + 1).padStart(3, '0')}`,
      issueCode: issue.code || issue.type || 'UNKNOWN_ISSUE',
      severity,
      imageType: issue.imageType || '',
      fieldKey: issue.fieldKey || '',
      fieldLabel: issue.fieldLabel || '',
      actionType,
      actionLabel: ACTION_LABELS[actionType] || actionType,
      title: template.title,
      description: template.description,
      recommendedSteps: template.recommendedSteps,
      canAutoFixLater: canAutoFixLater(actionType, issue),
      requiresManualConfirm: requiresManualConfirm(actionType, issue),
      isMockOnly,
      isRealComplianceRisk: Boolean(!isMockOnly && !noAction && issue.isRealComplianceRisk !== false),
      priority: severityRank(severity) + (requiresManualConfirm(actionType, issue) ? 0.1 : 0.2),
  ```

级数清单与 SKU 定级。注意 `mockOnly` 是一个独立状态，不是 `passed`：

  ```4:4:cbi/backend/src/services/batchReviewReportService.js
const SEVERITIES = ['fatal', 'high', 'medium', 'low', 'info', 'mockInfo'];
  ```

  ```56:64:cbi/backend/src/services/batchReviewReportService.js
function classifySku(report) {
  if (!report || !report.meta?.reviewMode) return 'noReview';
  const summary = report.summary || {};
  if (summary.fatalCount > 0 || summary.highCount > 0) return 'failed';
  if ((summary.realComplianceIssueCount || 0) === 0 && (summary.mockOnlyIssueCount || 0) > 0) return 'mockOnly';
  if ((summary.mediumCount || 0) > 0 || (summary.manualConfirmRequiredCount || 0) > 0) return 'needsManualReview';
  if ((summary.realComplianceIssueCount || 0) === 0) return 'passed';
  return 'needsManualReview';
}
  ```

批次层从原始 issue 里重新数一遍，对 `mock` 的判定比上游更宽（多了 `issue.mockOnly === true` 这一条）：

  ```84:98:cbi/backend/src/services/batchStabilityService.js
function reviewCounts(task = {}) {
  const summary = task.normalizedReviewReport?.summary || {};
  let fatal = Number(summary.fatalCount || 0);
  let high = Number(summary.highCount || 0);
  let mockInfo = Number(summary.mockInfoCount || 0);
  for (const item of asArray(task.review?.items)) {
    for (const issue of asArray(item.issues)) {
      const level = issue.severity || issue.level || issue.riskLevel;
      if (level === 'fatal') fatal += 1;
      if (level === 'high') high += 1;
      if (level === 'mockInfo' || issue.category === 'mock' || issue.mockOnly === true) mockInfo += 1;
    }
  }
  return { fatal, high, mockInfo };
}
  ```

排序用的 rank 函数单独导出，报表与批次两处共用：

  ```165:167:cbi/backend/src/services/reviewIssueService.js
export function severityRank(severity) {
  return SEVERITY_ORDER[severity] ?? 99;
}
  ```

- **为什么这样做 / 不这样做会出什么事**：若 mock 预览产生的提示与真实违规共用同一严重度空间，测试环境的噪音会淹没真实合规问题，审核报告会长期处于「有高危」状态，团队逐渐不再看它。把 `mockInfo` 排在 `fatal` 之后的第 6 级，并用 `isRealComplianceRisk: !isMockOnly` 分开计数，报表里 `realComplianceIssueCount` 与 `mockOnlyIssueCount` 是两个独立指标。
- **代价与局限**：`mockInfo` 的判定依赖文本正则。`reviewIssueService.js:66` 的条件是「命中 `mock` 且未命中 `chinese|price|promotion|capacity|certification|warranty|main_image_text`」，一条 mock 图上的中文文案不会被判 `mockInfo`，这符合直觉，但规则写在正则里，加一类真实风险词就要同步改这行。另外 `isRealComplianceRisk` 在两处各算一遍（`reviewIssueService.js:120` 与 `reviewFixSuggestionService.js:149`），条件不同（后者多排除 `noActionNeeded`），同名语义位在不同链路上取值可能不一致。
- **Momcozy 迁移形态**：6 级保留，`mockInfo` 改名为 `benchmarkOnly`（Momcozy 的对应场景是 AIGC 视频 benchmark 素材，不是 mock 预览），语义位保留两个名字但收口到一处计算：在 `normalizeReviewIssue()` 里算完 `isBenchmarkOnly` 与 `isRealComplianceRisk`，下游只读不再重算。`classifySku()` 的状态枚举从 `['noReview','failed','mockOnly','needsManualReview','passed']` 扩为加 `'benchmarkOnly'`，并明确 `benchmarkOnly` 的 SKU 可以进入 AIGC 训练集但不能进入发布队列。
- **证据强度**：已实读核实。
- **横向对比**：`ad-review-agent/harness/constraints.yaml` 只有一档 severity 概念，没有「环境噪音」这一维，因为它的输入全部是真实广告素材，不存在预览态。cbi 需要这一级是因为它同时承担生图与审核两件事，生图侧必然产生预览产物。Momcozy 的审计系统若只审已有素材，这一级的必要性下降，但 AIGC 视频 benchmark 场景会把它重新带回来。

---

### S3-09 9 种 `actionType` 与自动/人工分流

- **出处**：`cbi/backend/src/services/reviewFixSuggestionService.js:10-20`、`42-55`、`114-125`、`127-156`；`cbi/backend/src/services/autoFixExecutionService.js:1-3`、`267-274`（已实读核实）
- **一句话**：每条 issue 映射成一个 `actionType`，9 种取值；`canAutoFixLater` 与 `requiresManualConfirm` 两个布尔位由 actionType 与 issue 属性共同决定；`priority = severityRank + (requiresManualConfirm ? 0.1 : 0.2)`，升序排序，人工确认项排在自愈项之前。
- **原文**：

9 种 actionType 的中文标签：

  ```10:20:cbi/backend/src/services/reviewFixSuggestionService.js
const ACTION_LABELS = {
  removeText: '删除违规文案',
  removeClaim: '删除未确认卖点',
  confirmFieldEvidence: '核对字段证据',
  editTextLayout: '调整文字排版',
  regenerateMock: '重新生成 mock 预览',
  regenerateRealSample: '重新生成真实小样本',
  manualCheck: '人工复查',
  skipMockOnly: 'mock 流程提示',
  noActionNeeded: '无需处理'
};
  ```

actionType 的判定链，顺序即优先级，逐条正则匹配：

  ```42:55:cbi/backend/src/services/reviewFixSuggestionService.js
function actionFor(issue = {}) {
  const text = lowerText(issue.code, issue.message, issue.category, issue.fieldKey, issue.fieldLabel);
  if (issue.isMockOnly || issue.severity === 'mockInfo' || /mock/.test(text)) return 'skipMockOnly';
  if ((issue.severity === 'info' || issue.category === 'info') && !issue.isRealComplianceRisk) return 'noActionNeeded';
  if (/main_image_text|main image.*text/.test(text)) return 'editTextLayout';
  if (/chinese|price|promotion|coupon|sale|discount|free shipping/.test(text)) return 'removeText';
  if (/background|non_white|not white/.test(text)) return 'regenerateMock';
  if (/unconfirmed|capacity|certification|warranty|speed|evidence/.test(text)) return 'confirmFieldEvidence';
  if (/conflict|interface|dimension/.test(text)) return 'manualCheck';
  if (/subject|preserve|distort|realgeneration/.test(text)) return 'manualCheck';
  if (/matting|edge/.test(text)) return 'manualCheck';
  if (issue.canAutoFixLater) return 'removeClaim';
  return issue.requiresManualConfirm ? 'manualCheck' : 'manualCheck';
}
  ```

两个布尔位的判定，actionType 的类别决定基准值，issue 上的同名字段只能往上加：

  ```114:125:cbi/backend/src/services/reviewFixSuggestionService.js
function canAutoFixLater(actionType, issue = {}) {
  if (['removeText', 'editTextLayout', 'regenerateMock', 'removeClaim'].includes(actionType)) return true;
  if (actionType === 'skipMockOnly' || actionType === 'noActionNeeded') return false;
  return Boolean(issue.canAutoFixLater);
}

function requiresManualConfirm(actionType, issue = {}) {
  if (['confirmFieldEvidence', 'manualCheck'].includes(actionType)) return true;
  if (['removeText', 'editTextLayout', 'regenerateMock', 'removeClaim'].includes(actionType)) return false;
  if (actionType === 'skipMockOnly' || actionType === 'noActionNeeded') return false;
  return Boolean(issue.requiresManualConfirm);
}
  ```

组装与排序。`priority` 用 `severityRank` 做整数部分，小数部分区分人工与自动：

  ```127:156:cbi/backend/src/services/reviewFixSuggestionService.js
export function buildFixSuggestions({ issues = [] } = {}) {
  const suggestions = asArray(issues).map((issue, index) => {
    const severity = normalizeSeverity(issue);
    const actionType = actionFor({ ...issue, severity });
    const template = templateFor(actionType, issue);
    const isMockOnly = actionType === 'skipMockOnly';
    const noAction = actionType === 'noActionNeeded';
    return {
      suggestionId: `fix-${String(index + 1).padStart(3, '0')}`,
      issueCode: issue.code || issue.type || 'UNKNOWN_ISSUE',
      severity,
      imageType: issue.imageType || '',
      fieldKey: issue.fieldKey || '',
      fieldLabel: issue.fieldLabel || '',
      actionType,
      actionLabel: ACTION_LABELS[actionType] || actionType,
      title: template.title,
      description: template.description,
      recommendedSteps: template.recommendedSteps,
      canAutoFixLater: canAutoFixLater(actionType, issue),
      requiresManualConfirm: requiresManualConfirm(actionType, issue),
      isMockOnly,
      isRealComplianceRisk: Boolean(!isMockOnly && !noAction && issue.isRealComplianceRisk !== false),
      priority: severityRank(severity) + (requiresManualConfirm(actionType, issue) ? 0.1 : 0.2),
      count: issue.count || 1,
      affectedImageTypes: issue.imageType ? [issue.imageType] : []
    };
  });
  return suggestions.sort((a, b) => a.priority - b.priority);
}
  ```

真正执行自动修复时，允许清单只有 3 种，比 `canAutoFixLater` 的 4 种更窄：

  ```1:3:cbi/backend/src/services/autoFixExecutionService.js
const ALLOWED_ACTION_TYPES = new Set(['removeText', 'removeClaim', 'editTextLayout']);
const PROMOTION_PATTERN = /[\u4e00-\u9fff]|\$|¥|€|£|\b(price|discount|coupon|sale|free shipping|promo|promotion|off)\b|[0-9]+%/i;
const CLAIM_PHRASE_PATTERN = /\b(best|no\.?\s*1|guaranteed|ultimate|perfect|top rated|world'?s best)\b/gi;
  ```

不允许执行的都有明确文案，费用类与人工类分开写：

  ```267:274:cbi/backend/src/services/autoFixExecutionService.js
function blockReason(action = {}) {
  if (action.actionType === 'regenerateRealSample') return '该操作会产生真实生图成本，当前版本禁止自动执行。';
  if (action.actionType === 'regenerateMock') return '当前版本禁止自动重生成图片。';
  if (action.actionType === 'editTextLayout') return '当前版本仅允许 Amazon main_image 清空文字，禁止复杂排版调整。';
  if (action.actionType === 'confirmFieldEvidence') return '该操作涉及人工确认证据，不能自动执行。';
  if (action.actionType === 'manualCheck') return '该操作需要人工复查，不能自动执行。';
  return '该 actionType 不在本阶段 allowlist 中，不能自动执行。';
}
  ```

- **为什么这样做 / 不这样做会出什么事**：`canAutoFixLater` 回答「这个动作将来能不能自动做」，`requiresManualConfirm` 回答「现在必须人来拍板吗」，两者独立。删文字既可以被自动执行，也不要求人工确认；补证据必须人工确认，且永远不能自动执行。`priority` 的小数位让同严重度下的人工项排在前面，因为人工项会阻塞流程。
- **代价与局限**：actionType 靠正则匹配 `code + message + category + fieldKey + fieldLabel` 拼接后的文本决定，message 是自然语言，换一个措辞就可能落到 `manualCheck` 兜底。`actionFor()` 的最后一行 `return issue.requiresManualConfirm ? 'manualCheck' : 'manualCheck'` 两个分支返回同一个值，这个三元表达式没有作用。另外 `canAutoFixLater` 的允许清单（4 种）与实际执行允许清单（3 种）不一致，`regenerateMock` 在计划层被标为可自动修，在执行层被 `blockReason()` 拒掉。
- **Momcozy 迁移形态**：保留 9 种与两个布尔位，改三处。第一，actionType 判定从正则匹配改为**由 `ruleId` 末段直接查表**（S3-06 的四段式命名让这件事成为可能），消除措辞敏感。第二，`regenerateRealSample` 在 Momcozy 场景改为 `regenerateVideoSample`，`blockReason()` 里的成本提示改为按单价与条数估算，并给出预计花费。第三，新增 `restoreFromBenchmark`，用于把 AIGC 视频从 benchmark 库回滚到候选态。允许清单收敛为一处常量，`canAutoFixLater` 与实际执行共用它。
- **证据强度**：已实读核实。「两个分支返回同一值」与「两份允许清单不一致」来自逐行比对。
- **横向对比**：`invoice/backend/app/agents/coordinator.py` 的处置是任务级三态，没有动作类型这一层，因为它的问题都是「数据对不上」，修法是回到上游系统改数据，没有可枚举的自愈动作。cbi 需要 9 种动作类型，是因为生图产物本身就带着可编辑的结构（文字块、排版元素、背景），修法可以在产物上原地执行。Momcozy 若只做审计不做出品，动作类型可以砍到 3 至 4 种（`removeText`、`removeClaim`、`confirmFieldEvidence`、`manualCheck`）。

---

### S3-10 品类规则第二层与平台规则的分工

- **出处**：`cbi/backend/src/rules/categoryRules.js:1-140`（`splitlines()` 计 140 行）；`cbi/backend/src/rules/categoryRuleUtils.js:59-74`、`76-87`；`cbi/backend/src/providers/review/reviewPrompt.js:91-98`（已实读核实）
- **一句话**：平台规则回答「这个平台的这种图允许出现什么」，品类规则回答「这类商品的哪些宣称没有证据就不能用」。两层各自有独立版本号、独立快照函数、独立注入提示词的摘要函数。
- **原文**：

品类注册表的兜底模板，9 个品类里有 6 个直接复用它：

  ```14:30:cbi/backend/src/rules/categoryRules.js
const conservativeTemplate = (categoryId, categoryName, aliases = []) => ({
  categoryId,
  categoryName,
  aliases,
  criticalFields: ['productName', 'category', 'packageIncluded', 'sellingPoints'],
  highRiskFields: ['certifications', 'warranty', 'medicalClaims'],
  evidenceRequiredFields: {
    certifications: 'visible_text',
    warranty: 'visible_text',
    medicalClaims: 'visible_text'
  },
  allowedClaims: [],
  riskyClaims: ['best performance', 'best seller', 'guaranteed result'],
  forbiddenClaimsWithoutEvidence: ['certified', 'warranty', 'guaranteed'],
  imageTypeGuidance: sharedImageTypeGuidance,
  notes: ['Conservative category fallback rule. Internal risk helper only.']
});
  ```

存储品类是全仓最完整的一份品类规则（别名、关键字段、高风险字段、证据要求）：

  ```48:71:cbi/backend/src/rules/categoryRules.js
  electronics_storage: {
    categoryId: 'electronics_storage',
    categoryName: 'Electronics / Storage Devices',
    aliases: [
      'external hard drive',
      'portable hard drive',
      'external SSD',
      'portable SSD',
      'storage device',
      'hard disk',
      'external storage',
      'portable external drive',
      'solid state drive'
    ],
    criticalFields: [
      'capacity',
      'interfaceType',
      'compatibleDevices',
      'dimensions',
      'packageIncluded',
      'material',
      'model',
      'brand'
    ],
  ```

它的三组 claim 名单。`forbiddenClaimsWithoutEvidence` 9 条，是把「没有证据就不能说」写成具体措辞：

  ```72:89:cbi/backend/src/rules/categoryRules.js
    highRiskFields: [
      'capacity',
      'certifications',
      'warranty',
      'speed',
      'waterproof',
      'shockproof',
      'compatibility'
    ],
    evidenceRequiredFields: {
      capacity: 'visible_text',
      certifications: 'visible_text',
      warranty: 'visible_text',
      speed: 'visible_text',
      waterproof: 'visible_text',
      shockproof: 'visible_text',
      compatibility: 'visible_text_or_user_confirmed'
    },
  ```

  ```106:116:cbi/backend/src/rules/categoryRules.js
    forbiddenClaimsWithoutEvidence: [
      'waterproof',
      'shockproof',
      'military grade',
      'up to 1000MB/s',
      '5-year warranty',
      'CE certified',
      'FCC certified',
      'RoHS certified',
      'guaranteed speed'
    ],
  ```

品类快照函数，与平台快照同构但字段不同：

  ```59:74:cbi/backend/src/rules/categoryRuleUtils.js
export function categoryRuleSnapshotForImage({ categoryId, imageType, productInfoConfirmed } = {}) {
  const rule = getCategoryRule({ categoryId, productInfoConfirmed });
  return {
    categoryId: rule.categoryId,
    categoryName: rule.categoryName,
    imageType,
    criticalFields: [...(rule.criticalFields || [])],
    highRiskFields: [...(rule.highRiskFields || [])],
    evidenceRequiredFields: { ...(rule.evidenceRequiredFields || {}) },
    riskyClaims: [...(rule.riskyClaims || [])],
    forbiddenClaimsWithoutEvidence: [...(rule.forbiddenClaimsWithoutEvidence || [])],
    imageTypeGuidance: rule.imageTypeGuidance?.[imageType] || null,
    ruleVersion: CATEGORY_RULE_VERSION,
    notes: [...(rule.notes || [])]
  };
}
  ```

两层的摘要函数都直接拼进审核提示词，模型同时看到两套规则：

  ```76:87:cbi/backend/src/rules/categoryRuleUtils.js
export function summarizeCategoryRulesForPrompt({ categoryId, productInfoConfirmed, imageType } = {}) {
  const snapshot = categoryRuleSnapshotForImage({ categoryId, productInfoConfirmed, imageType });
  return [
    `Category: ${snapshot.categoryName} (${snapshot.categoryId})`,
    `Critical fields: ${snapshot.criticalFields.join(', ') || 'none'}`,
    `High-risk fields: ${snapshot.highRiskFields.join(', ') || 'none'}`,
    `Evidence required fields: ${JSON.stringify(snapshot.evidenceRequiredFields)}`,
    `Risky claims: ${snapshot.riskyClaims.join(', ') || 'none'}`,
    `Forbidden claims without evidence: ${snapshot.forbiddenClaimsWithoutEvidence.join(', ') || 'none'}`,
    `Guidance: ${snapshot.imageTypeGuidance?.note || '-'}`
  ].join('\n');
}
  ```

- **为什么这样做 / 不这样做会出什么事**：认证、容量、防水、兼容性这四类 claim 的风险等级由品类决定而不由平台决定。同一条「waterproof」在 Amazon 主图和 Ozon 辅图上的处理可以一样，但在存储品类和服装品类上完全不同。拆成两层后，加一个品类只需写一份品类文件，不动平台矩阵。
- **代价与局限**：`categoryRuleRegistry` 的 9 个品类是 `general`、`electronics_general`、`electronics_storage`、`beauty`、`apparel`、`home`、`tools`、`pet`、`medical_device`，**没有母婴品类**，也没有吸乳器、婴儿监护、喂养用品。`medical_device` 品类存在但只覆盖 5 条 claim（`FDA approved`、`medical grade`、`clinically proven`、`cure`、`treats`），`criticalFields` 也没写。品类识别靠 `detectCategoryFromProductInfo()` 在商品名与类目文本里找别名，母婴商品若命名里没有匹配别名会落到 `general`，规则强度随之降到兜底模板。
- **Momcozy 迁移形态**：新增 `momcozy_nursing`（吸乳器 / 母乳喂养）、`momcozy_baby_monitor`（婴儿监护）、`momcozy_feeding`（奶瓶 / 喂养）、`momcozy_postpartum`（产后护理）四个品类，各写独立的 `criticalFields`、`highRiskFields`、`evidenceRequiredFields`、`forbiddenClaimsWithoutEvidence`。`momcozy_nursing` 的 `forbiddenClaimsWithoutEvidence` 至少包含 `['FDA cleared','FDA approved','510(k)','BPA-free','food-grade','medical-grade','hospital-grade','closed-system','clinically proven','increases milk supply','prevents mastitis','pediatrician recommended','safe for newborns','painless','silent']`，`evidenceRequiredFields` 里的键与 S3-05 的字段表对齐。`detectCategoryFromProductInfo()` 的别名表补 `['breast pump','wearable pump','milk collector','nursing bra','baby monitor','bottle warmer','sterilizer','postpartum']`。同时把 `medical_device` 的 5 条 claim 并进 `momcozy_*` 的名单，避免母婴品被识别成 `medical_device` 后规则反而变弱。
- **证据强度**：已实读核实。「没有母婴品类」来自对 `categoryRuleRegistry` 全部 key 的枚举。
- **横向对比**：`ad-review-agent/src/rules/category_rules.json` 与 `vivo_platform.json` 把「品类」与「平台」也拆成两个文件，与 cbi 同构。差别在于 ad-review 的品类文件是 JSON，可热加载；cbi 的品类规则是 JS 模块，改一条要走构建。cbi 的代价是规则更新需要发版，好处是品类规则里可以写函数（例如 `detectCategoryFromProductInfo()` 的正则分支），JSON 做不到。

---

### S3-11 AIGC 生成物的独立风险项

- **出处**：`cbi/backend/src/providers/review/ruleBasedReview.js:100-118`、`215-220`、`229-232`（已实读核实）
- **一句话**：审核函数开头先跑 4 条来源类检查，与内容类规则完全分开：mock 预览、降级 mock、文生图主体保真风险、主体保真质量位；主图另有一条「生成式场景背景」检查。
- **原文**：

  ```100:111:cbi/backend/src/providers/review/ruleBasedReview.js
  if (image.isMockPreview || image.provider === 'mock') {
    issues.push(issue('mock_preview', getRuleSeverity({ platformId, imageType, issueType: 'sourceMock' }), 'Mock preview image cannot be used as a final marketplace upload.', [image.fileName], meta('source', 'sourceMock')));
  }
  if (image.fallbackToMock) {
    issues.push(issue('fallback_mock', 'medium', 'Real generation failed and this image fell back to mock preview.', [image.realGenerationError?.message || 'fallback mock'], meta('source', 'fallbackMock')));
  }
  if (image.realGenerationMode === 'text_to_image' || image.productGeneratedByAI) {
    issues.push(issue('subject_preserve_risk', 'high', 'Text-to-image generation does not guarantee product appearance fidelity.', [], meta('source', 'subjectPreserve')));
  }
  if (image.preserveQuality?.subjectPreserveRisk === 'high') {
    issues.push(issue('subject_preserve_risk', 'high', 'Product subject preserve risk is high.', [], meta('source', 'subjectPreserve')));
  }
  ```

主图的额外一条，只在文生图模式下触发：

  ```116:118:cbi/backend/src/providers/review/ruleBasedReview.js
  if (imageType === 'main_image' && image.realGenerationMode === 'text_to_image') {
    issues.push(issue('main_image_scene_background', getRuleSeverity({ platformId, imageType, issueType: 'nonWhiteBackground' }), 'Main image appears to use generated scene background.', [], meta('platform', 'background')));
  }
  ```

来源状态原样写进结果，供下游判断这张图是什么来路：

  ```215:220:cbi/backend/src/providers/review/ruleBasedReview.js
    sourceChecks: {
      isMockPreview: Boolean(image.isMockPreview || image.provider === 'mock'),
      isRealGenerated: Boolean(image.isRealGenerated),
      fallbackToMock: Boolean(image.fallbackToMock),
      realGenerationMode: image.realGenerationMode || (image.isRealGenerated ? 'real' : 'mock')
    },
  ```

`notes` 里给两条人类可读的免责声明：

  ```229:232:cbi/backend/src/providers/review/ruleBasedReview.js
    notes: [
      image.isRealGenerated ? 'Real generated image still requires human review before marketplace upload.' : '',
      image.isMockPreview ? 'Mock preview cannot be used as final marketplace upload.' : ''
    ].filter(Boolean)
  ```

- **为什么这样做 / 不这样做会出什么事**：AIGC 产物的问题不在「文案写了什么」，而在「这张图本身是不是可信的素材」。mock 预览、降级产物、文生图产品主体，这三类都不能直接上架。若与内容规则混在一起，会出现「文案全对但图是 AI 凭空画的」通过审核的情况。`subject_preserve_risk` 直接打 `high`，理由是文生图不保证产品外观保真，这条对美国市场的商品图尤其重要，因为产品外观与实际不符属于误导性陈述。
- **代价与局限**：`realGenerationMode === 'text_to_image'` 时无条件报 high，这是一个**按生成方式给出的判定**，与画面实际保真度无关。若模型实际保真度很高，仍会报 high，用户会学会忽略这条。`preserveQuality.subjectPreserveRisk` 是唯一的结果侧信号（第 109-111 行），两处报同一个 type，无法区分「模式风险」与「实检风险」。
- **Momcozy 迁移形态**：来源类检查扩为 AIGC 视频版：新增 `asset_is_synthetic`（整段由模型生成）、`synthetic_performer`（合成人物形象，需按平台标记）、`voice_cloned`（合成配音）、`scene_generated`（背景由模型生成）、`product_composited`（产品主体抠图合成）、`temporal_flicker`（逐帧不一致）、`physics_violation`（物理不合理，如液体倒流、吸力管线不连贯）。`subject_preserve_risk` 保留并把两处拆成 `subject_preserve_risk_mode`（由 `realGenerationMode` 触发）与 `subject_preserve_risk_observed`（由质量位触发），两者分数不同，报告里分开列。`notes` 的免责声明改为中美市场通用的英文原文，并加一条「合成人物形象需在素材元数据中标记」。
- **证据强度**：已实读核实。
- **横向对比**：`sceneforge/docs/PRIVACY_AND_COMPLIANCE.md` 有合规边界声明，但视频质量门禁走的是指标路线（相似度、音频指纹、画面稳定性），没有「素材来源」这一维度。cbi 的来源类检查补的正是这一维度，代价是它只覆盖图片，视频的时序维度仍需另建。

---

### S3-12 双引擎合并的语义

- **出处**：`cbi/backend/src/providers/review/ruleBasedReview.js:236-245`；`cbi/backend/src/providers/review/normalizeReviewResult.js:89-91`；`cbi/backend/src/providers/review/RealVisionReviewProvider.js:62-68`；`cbi/backend/src/providers/review/reviewPrompt.js:45-50`、`100-101`（已实读核实）
- **一句话**：规则引擎与视觉模型各出一份结果，issue 直接拼接，风险取 `maxRiskLevel`；`pass` 是三个条件的合取，其中包含「没有任何 high 及以上 issue」这一条，所以即便两个引擎都自报通过，只要合并后出现 high，结论就是不通过。
- **原文**：

  ```236:245:cbi/backend/src/providers/review/ruleBasedReview.js
export function mergeReviewData(ruleData, visionData = null) {
  if (!visionData) return ruleData;
  const normalizedVision = normalizeReviewResult(visionData);
  const issues = [...asArray(ruleData.issues), ...asArray(normalizedVision.issues)];
  const riskLevel = issues.reduce((level, item) => maxRiskLevel(level, item.level), maxRiskLevel(ruleData.riskLevel, normalizedVision.riskLevel));
  return normalizeReviewResult({
    pass: Boolean(ruleData.pass && normalizedVision.pass && !issues.some((item) => item.level === 'high')),
    riskLevel,
    issues,
    fixSuggestions: [...asArray(ruleData.fixSuggestions), ...asArray(normalizedVision.fixSuggestions)],
  ```

`maxRiskLevel` 的实现，把 3 级排序后取最大：

  ```89:91:cbi/backend/src/providers/review/normalizeReviewResult.js
export function maxRiskLevel(...levels) {
  return levels.map((item) => normalizeRiskLevel(item)).sort((a, b) => riskOrder[b] - riskOrder[a])[0] || 'low';
}
  ```

真实审核路径里两个引擎的调用顺序（规则引擎先跑一遍完整结果，再与视觉结果合并）：

  ```62:68:cbi/backend/src/providers/review/RealVisionReviewProvider.js
    try {
      const prompt = buildReviewPrompt({ task, image, plan, generationRequest });
      const text = await this.callModel({ prompt, image });
      const parsed = parseJsonFromModelOutput(text);
      const visionData = normalizeReviewResult(parsed);
      const ruleData = runRuleBasedReviewChecks({ task, image, plan, generationRequest });
      const data = mergeReviewData(ruleData, visionData);
  ```

规则引擎的产出在调模型之前就注入提示词，让模型在已有线索上复核：

  ```45:50:cbi/backend/src/providers/review/reviewPrompt.js
  const preliminaryRuleReview = runRuleBasedReviewChecks({
    task,
    image,
    plan,
    generationRequest
  });
  ```

  ```100:101:cbi/backend/src/providers/review/reviewPrompt.js
Preliminary rule-based issues:
${JSON.stringify(context.preliminaryRuleBasedIssues, null, 2)}
  ```

- **为什么这样做 / 不这样做会出什么事**：两个引擎的失败模式互补。正则不会漏掉字面上的 `FDA`，但看不懂语境；视觉模型能判断主图背景是不是真的白底，但会漏字。合并时 issue 全量拼接（不去重），风险取最大，`pass` 取合取，这套语义的默认立场是「任一引擎发现问题就不通过」。
- **代价与局限**：`pass` 的第三个条件是 `!issues.some(item => item.level === 'high')`，只检查 `high`，不检查 `fatal`。若某个引擎产出 `level: 'fatal'` 的 issue，这一条不会命中。也就是说，在 `mergeReviewData` 这一层，`fatal` 与 `high` 的语义没有对齐（下游报表层用了 `['fatal','high']` 的正确写法，见 `cbi/backend/src/services/reviewReportService.js:117`）。另外 issue 不去重，同一处中文文案被两个引擎各报一次，`issues.length` 会翻倍。
- **Momcozy 迁移形态**：合并语义保留，修两处。第一，`pass` 条件改为 `!issues.some(item => ['fatal','high'].includes(item.level))`，与报表层对齐。第二，加一层 issue 去重：以 `${ruleId}:${evidence[0]}:${locator?.bbox}` 为键合并，保留较高严重度与两边的 evidence 并集。规则引擎的输出继续注入提示词，注入条数从 12 条（`reviewPrompt.js:59` 的 `.slice(0, 12)`）提到 30 条，因为美国母婴品类的证据类 issue 数量远多于存储品类。
- **证据强度**：已实读核实。「`pass` 只查 high 不查 fatal」来自逐字比对第 242 行与 `reviewReportService.js:117`。
- **横向对比**：`invoice/backend/app/agents/cross_validator.py:18-77` 的合并是「硬规则出 issue，LLM 只做补充与后置过滤」，最终状态由 `_determine_status()` 单点决定。cbi 是双向合并，两边平权。平权的代价是视觉模型可以单方面把结论拉到不通过，而它的输出没有 schema 之外的约束；invoice 的单点决定代价是硬规则的口径就是最终口径，模型的边界判断进不了结论。

---

### S3-13 Provider 抽象与统一返回信封

- **出处**：`cbi/backend/src/providers/index.js:1-29`；`cbi/backend/src/providers/review/index.js:1-18`；`cbi/backend/src/providers/vision/index.js:1-16`；`cbi/backend/src/providers/image/index.js:1-12`；`cbi/backend/src/providers/review/MockReviewProvider.js:14-20`；`cbi/backend/src/providers/review/RealVisionReviewProvider.js:50-61`、`70-76`（已实读核实）
- **一句话**：三类能力（vision / image / review）各自一个工厂函数，按环境变量选实现，全部返回同一个信封 `{provider, model, durationMs, status, error, data}`，失败时 `data: null` 且不抛异常。
- **原文**：

总入口。`mock` 模式一次性把三个 provider 全换成 mock 实现：

  ```8:27:cbi/backend/src/providers/index.js
export function getProviders(providerName) {
  const mode = typeof providerName === 'string'
    ? providerName
    : providerName?.mode;
  const normalizedMode = String(mode || 'mock').toLowerCase();

  if (providerName !== undefined && ['mock', 'mockonly', 'preview'].includes(normalizedMode)) {
    return {
      vision: new MockVisionProvider(),
      image: new MockImageProvider(),
      review: new MockReviewProvider()
    };
  }

  return {
    vision: getVisionProvider(),
    image: getImageProvider(),
    review: getReviewProvider('real')
  };
}
  ```

三个工厂各自读自己的环境变量，值不认识时抛错（构造期抛，不在调用期）：

  ```4:18:cbi/backend/src/providers/review/index.js
export function getSelectedReviewProvider() {
  return (process.env.REVIEW_PROVIDER || 'mock').toLowerCase();
}

export function getReviewProvider(mode = 'mock') {
  if (mode === 'mock') return new MockReviewProvider();
  const provider = getSelectedReviewProvider();
  if (provider === 'mock') return new MockReviewProvider();
  if (['vision', 'gemini', 'openai', 'qwen'].includes(provider)) {
    return new RealVisionReviewProvider(provider === 'vision' ? (process.env.VISION_PROVIDER || 'gemini').toLowerCase() : provider);
  }
  const error = new Error(`Unsupported REVIEW_PROVIDER: ${provider}`);
  error.statusCode = 500;
  throw error;
}
  ```

  ```6:16:cbi/backend/src/providers/vision/index.js
export function getVisionProvider() {
  const provider = (process.env.VISION_PROVIDER || process.env.AI_PROVIDER || 'mock').toLowerCase();

  if (provider === 'mock') return new MockVisionProvider();
  if (provider === 'qwen') return new QwenVisionProvider();
  if (provider === 'openai') return new OpenAIVisionProvider();
  if (provider === 'gemini') return new GeminiVisionProvider();

  const error = new Error(`Unsupported VISION_PROVIDER: ${provider}`);
  error.statusCode = 500;
  throw error;
  ```

  ```4:12:cbi/backend/src/providers/image/index.js
export function getImageProvider() {
  const imageProvider = String(process.env.IMAGE_PROVIDER || process.env.AI_PROVIDER || 'mock').toLowerCase();
  if (imageProvider === 'real') {
    return new RealBackgroundImageProvider({
      backgroundProviderName: process.env.BACKGROUND_PROVIDER || 'mock'
    });
  }
  return new MockImageProvider();
}
  ```

mock 实现的信封，带完整 `data`：

  ```14:20:cbi/backend/src/providers/review/MockReviewProvider.js
      return {
        provider: this.provider,
        model: this.model,
        durationMs,
        status: 'success',
        error: null,
        data: {
  ```

真实实现的失败分支。缺 API key 时不抛异常，返回失败信封：

  ```50:61:cbi/backend/src/providers/review/RealVisionReviewProvider.js
  async review({ task, image, plan, generationRequest }) {
    const startedAt = Date.now();
    if (!this.config.apiKey) {
      return {
        provider: this.provider,
        model: this.model,
        status: 'failed',
        durationMs: Date.now() - startedAt,
        error: missingKeyError(this.provider),
        data: null
      };
    }
  ```

真实实现的成功分支，`data` 里带上 provider、model、durationMs 与两份规则快照：

  ```70:76:cbi/backend/src/providers/review/RealVisionReviewProvider.js
      return {
        provider: this.provider,
        model: this.model,
        status: 'success',
        durationMs,
        error: null,
        data: {
  ```

- **为什么这样做 / 不这样做会出什么事**：审核链路的失败不能让整批任务崩掉。缺 key、超时、模型返回非 JSON，这三种情况都返回 `status: 'failed'` 加 `error` 对象，调用方按 status 决定是否降级到 mock。`durationMs` 与 `model` 落库后可以做成本与延迟归因。环境变量切换让同一套代码在无 key 的 CI 环境里也能跑通全链路。
- **代价与局限**：`getReviewProvider()` 在供应商值不认识时**抛异常**（第 15-17 行），与「失败不抛异常」的约定不一致，这个异常发生在构造期，调用方若没有捕获会让请求 500。`getProviders()` 的 mock 分支要求调用方显式传 `providerName`（第 14 行的 `providerName !== undefined`），不传时走真实分支，这个默认值对本地开发不友好。三个工厂的环境变量名各不相同（`VISION_PROVIDER` / `AI_PROVIDER`、`IMAGE_PROVIDER` / `AI_PROVIDER`、`REVIEW_PROVIDER`），`AI_PROVIDER` 被 vision 与 image 共用但不影响 review。
- **Momcozy 迁移形态**：信封结构原样搬，`{provider, model, durationMs, status, error, data}` 六字段已经是多模态审计的最小公约数。改造三点。第一，`error` 对象补 `retryable` 布尔位与 `httpStatus`，让上层能区分「key 错了，重试无用」与「限流了，退避重试」。第二，工厂选择从环境变量改为**按资产的 `modelRoute` 字段**决定，因为 Momcozy 的文本、图片、视频要走不同模型，环境变量无法表达这种维度。第三，审查 provider 的能力清单显式声明（`{supportsImage: true, supportsVideo: false, supportsAudio: false}`），让调度层能在选之前就知道某个 provider 能不能接视频，避免用异常表达能力缺失。
- **证据强度**：已实读核实。「构造期抛异常与失败信封约定不一致」来自逐行比对 `review/index.js:15-17` 与两个 provider 的返回结构。
- **横向对比**：`PolySafe/backend/app/services/doubao_service.py` 用一个统一服务封装多模态调用，没有 provider 工厂这一层，换模型要改服务内部。cbi 的工厂形态让 mock 与 real 在同一条链路上切换，这才使无 key 环境的全链路自测成为可能。代价是每加一个 provider 要改三处（工厂、index、环境变量文档）。

---

## 二、迁移判定表

| 资产 | 判定 | 理由 |
|---|---|---|
| 平台 × 图片类型矩阵与 `imageRule()` 维度 schema | 直接搬，替换取值 | 结构与法域无关，`background/text/product/file/severity` 五组维度在美国市场同样成立 |
| `globalForbidden` 全局禁列 | 搬结构，重写取值 | 现有 10 项里 `chinese_text` 与 `seller_logo` 需保留，其余要补母婴品类专有项 |
| `certificationRules.forbiddenWithoutEvidence` | 搬结构，必须接上执行点 | 声明与执行脱节，直接搬数组不生效 |
| 四条确定性正则 | 重写 | 促销正则的 `\d+\s?%` 分支与价格正则的欧亚币种不适用美国市场 |
| `source === 'visible_text'` 证据定义 | 直接搬 | 判定完全确定性，法域无关，是本仓库对美国市场最可用的一条 |
| issue 结构与 `ruleId` 命名 | 搬结构，加字段 | 需要补 `regulationRef` 与结构化 `locator` 才能出美国市场报告 |
| 规则快照冻结与版本号 | 直接搬，补深拷贝 | 浅拷贝引用注册表内对象，冻结不彻底 |
| 6 级严重度与两个语义位 | 直接搬，收口计算 | 同名语义位在两处各算一遍，需合并到归一化函数 |
| 9 种 actionType 与分流 | 搬结构，砍到 4 种 | Momcozy 若只审不出品，生图相关动作类型用不上 |
| 品类规则第二层 | 搬结构，新增母婴品类 | 现无母婴品类，识别不到会落到兜底模板 |
| AIGC 来源类风险项 | 搬结构，扩到视频 | 现有检查只覆盖图片，视频时序维度需另建 |
| 双引擎合并语义 | 搬结构，修 `pass` 条件 | `pass` 只查 `high` 不查 `fatal`，与报表层口径不一致 |
| Provider 信封 | 直接搬 | 六字段是多模态审计的最小公约数 |

---

## 三、前一份报告的核实结果

前一份报告在本仓库范围内有两处需要更正。

**第一处：确定性正则层的文件路径错误。**

被质疑的原话是前一份报告给出的实现位置 `backend/src/rules/ruleBasedReview.js`。实读结果：该路径在快照中不存在，目录 `cbi/backend/src/rules/` 下只有 `platformRules.js`、`platformRuleUtils.js`、`categoryRules.js`、`categoryRuleUtils.js` 四个文件。真实实现在 `cbi/backend/src/providers/review/` 下，且被同目录三个文件 import：

  ```1:3:cbi/backend/src/providers/review/ruleBasedReview.js
import { maxRiskLevel, normalizeReviewResult } from './normalizeReviewResult.js';
import { getForbiddenElements, getRuleSeverity, isTextAllowed, platformRuleSnapshotForImage } from '../../rules/platformRuleUtils.js';
import { categoryRuleSnapshotForImage } from '../../rules/categoryRuleUtils.js';
  ```

`cbi/backend/src/providers/review/ruleBasedReview.js` 共 271 行（`splitlines()` 口径）。

**第二处：正则原文转写不完整。**

前一份报告转写的促销正则为 `(discount|coupon|sale|best seller|no.1|limited time|free shipping|% off)`，认证正则为 `(fda|ce|fcc|rohs|certified|warranty|guarantee|waterproof|medical|health)`。实际第 7 行与第 8 行的原文见 S3-04 的引用块。差异有三：两处都缺 `\b` 词边界锚定；促销正则实际写作 `no\.?\s*1`（允许 `no1` 与 `no 1`）并在尾部多一个 `|\d+\s?%` 分支；认证正则实际多一个 `certification` 词。价格正则的转写与第 6 行一致，无差异。

前一份报告的另一条论断在这个仓库里成立：`rulesSnapshot` 确实存在，且确实挂在 target、plan、审核结果三处（见 S3-07）。这一条不属于错误。

---

## 四、README 与代码的对照

`cbi/README.md` 共 853 行。检索 `ruleBasedReview`、`platformRules.js`、`categoryRules.js` 三个关键词，README 内**零命中**。README 没有记载规则注册表的位置与结构，也没有记载四个版本号。规则体系的文档只存在于代码注释与 `notes` 字段里。这意味着规则库的任何变更不会在文档层留痕，接手者只能读源码。前一份报告提到的 README 第 796 行后的 mojibake 段落，本片未采信其任何技术陈述。
