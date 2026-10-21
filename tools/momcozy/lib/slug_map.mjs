// tools/momcozy/lib/slug_map.mjs
//
// 双站系列键 → 主站 collection slug 映射(配置常量,可 import)
//
// 已知关系(2026-10-17 实测):
//   - /collections/breast-pump  → 301 → /collections/hospital-grade-breast-pump
//   - 同一 series 在主站可能没有 1:1 collection(详见方案 §三)
//
// 谁 import: tools/momcozy/scrape_breast_pump.mjs

export const SLUG_MAP = Object.freeze({
  schema_version: 'momcozy-slug-map/1.0',
  updated_at: '2026-10-17T17:30:00Z',
  entries: [
    {
      support_key: 'breast-pump',
      main_collection_slugs: ['hospital-grade-breast-pump'],
      verified: true,
      verified_at: '2026-10-17T16:50:00Z',
      source: '实测 /collections/breast-pump 301 → /collections/hospital-grade-breast-pump',
      note: '此 series 在主站是"子集"(只装 Hospital Grade),其他子集合(M/S/Air/Wellness)在 v1.2 调研',
    },
    ...Object.freeze([
      'bottle-washer-sterilizer',
      'milk-warmer',
      'white-noise',
      'baby-monitor',
      'nasal-aspirator',
      'baby-care',
      'baby-strollers',
      'belly-band',
      'baby-carrier',
      'pillows',
      'maternity-essential',
      'others',
    ]).map((k) => Object.freeze({
      support_key: k,
      main_collection_slugs: Object.freeze([]),
      verified: false,
      source: '未验证',
    })),
  ],
});

export function getEntry(supportKey) {
  return SLUG_MAP.entries.find((e) => e.support_key === supportKey) ?? null;
}
