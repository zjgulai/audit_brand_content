// dt3-bare.mjs —— DT-3「样式层裸值」判据的**唯一实现**
//
// ★ 为什么要有这个文件（2026-10-23）
//
//   行 111 的裸值判据此前有**两份实现**：
//     · web/scripts/check_design_tokens.mjs 的 `bareValue()`（DT-3 棘轮用）
//     · web/scripts/check_frontend_gates.mjs 的 `isBarePropValue()`（#111 通道3 用）
//   两份各写一遍，改一处必漏另一处 —— 实测就漏了：DT-3 改完口径归零了，
//   而 #111 通道3 仍按旧口径算出 95 处，于是同一条 styles.css 在两处给出两个读数。
//
//   这正是 AGENTS.md §2.5「形态决策只能有一处」的同一个形状，
//   只不过这次分裂的是**判据**而不是形态。
//
// ## 判据本身（行 111 原文：「颜色/间距/字号全部来自 token」）
//
//   ★ 2026-10-23 口径校正：改前 DT-3 报「95 处裸值」，拆开是
//       67 处  hsl(var(--brand))             ← **不是裸值**，颜色来自 tokens.css
//       28 处  1px solid hsl(var(--border))  ← 线宽不在行 111 点名的三类里
//        0 处  真裸值
//
//     ① **假阳性**：旧写 `/\b(?:rgba?|hsla?)\(/` 只看见函数名 `hsl(` 就判裸值，
//        不看参数。`hsl(var(--brand))` 的通道值存在 tokens.css
//        （`--brand: 346.5 41.3% 29.4%`），**它是 token 引用**。
//     ② **越界**：行 111 只说「颜色/间距/字号」。`border: 1px solid …` 的 `1px`
//        是**边框线宽**，不在这三类里；但颜色写死（`1px solid #ff0000`）仍必须红 ——
//        所以不能整个属性跳过。
//
//   修法：**先把 token 引用整段抠掉，再在剩下的部分找裸值**。
//      `1px solid hsl(var(--border))` 抠掉后剩 `1px solid ` → 无裸值
//      `1px solid #ff0000`            抠掉后仍含 `#ff0000` → 裸值
//   **这不是放宽判据，是先认得出 token 引用。**

/** 行 111 点名的「间距」类（含几何偏移，后者是类推，见下）。 */
export const SPACING_PROPS = new Set([
  "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
  "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
  "gap", "row-gap", "column-gap",
  // 定位偏移：既不是颜色也不是字号，**也不是行 111 原文点名的三类的字面成员**。
  // 留在这里是因为它与「间距」同属几何尺寸。今天 styles.css 里这类裸值 0 处，
  // 所以这个类推不影响任何读数 —— 但要知道它是类推，不是原文。
  "top", "right", "bottom", "left",
]);

/** 行 111 点名的「字号」类。 */
export const FONT_PROPS = new Set(["font-size", "font-family"]);

/** 会走到本判据的全部属性（= 三类之并 + 颜色载体属性）。 */
export const BARE_PROPS = new Set([
  "color", "background", "background-color", "border", "border-color",
  "border-top", "border-bottom", "border-left", "border-right",
  "outline", "outline-color", "fill", "stroke", "box-shadow",
  ...FONT_PROPS,
  ...SPACING_PROPS,
]);

/**
 * 把 token 引用整段抠掉：`hsl(var(--x))` / `hsl(var(--x) / 0.4)` / `var(--x)`。
 *
 * ★ 2026-10-23 补 alpha 形态：第一版正则只认 `hsl(var(--x))`，
 *   **带 alpha 的 `hsl(var(--foreground) / 0.04)` 抠不掉**，于是：
 *     - 通道值来自 tokens.css（是真 token 引用），
 *     - 但 `rest` 里还剩 `hsl(`，被第 73 行判成裸值。
 *   这与 01cb34b 修掉的假阳性是**同一个形状**（认不出 token 引用 → 误报），
 *   只不过长在 alpha 语法上。实测由登录页 box-shadow 撞出来。
 *
 *   ★ 仍然不放过真裸值：`hsl(210 40% 50% / 0.4)` 里没有 `var(--x)`，抠不掉 → 仍判裸。
 */
export function stripTokenRefs(v) {
  return String(v)
    .replace(
      /\b(?:rgba?|hsla?)\(\s*var\(\s*--[a-z0-9-]+\s*\)\s*(?:\/\s*[\d.]+%?\s*)?\)/gi,
      " ",
    )
    .replace(/var\(\s*--[a-z0-9-]+\s*\)/gi, " ");
}

/** 一行声明是否含裸值 —— 按行 111 的三类判：颜色 / 间距 / 字号。 */
export function bareValue(prop, value) {
  const v = String(value || "").trim();
  if (!v) return false;

  // ① 先抠掉 token 引用，剩下的才是「写死的部分」
  const rest = stripTokenRefs(v);

  // ② 颜色：hex 或**不带 var 的**颜色函数
  if (/#[0-9a-fA-F]{3,8}\b/.test(rest)) return true;
  if (/\b(?:rgba?|hsla?)\(/.test(rest)) return true;

  // ③ 字号/字体族：font-family 必须来自 token
  if (prop === "font-family" && !/var\(--/.test(v)) return true;

  // ④ 长度：只有**间距 / 字号 / 定位**这几类属性上的 px 才算裸值。
  //    边框 / outline / box-shadow 上的 px 是线宽或偏移，行 111 没点它们。
  const pxOk = SPACING_PROPS.has(prop) || FONT_PROPS.has(prop);
  if (pxOk && /\b\d*\.?\d+px\b/.test(rest)) return true;

  return false;
}

/**
 * 极简 CSS 解析：返回 `[{selector, prop, value}]`，只保留**含裸值**的声明。
 *
 * 用花括号栈处理 @media 嵌套；选择器带上层 at-rule 前缀，保证基线键稳定。
 * ★ 与 `check_design_tokens.mjs` 里那份**必须是同一段代码** —— 所以它在这里。
 */
export function parseBareEntries(cssSrc) {
  const clean = String(cssSrc || "").replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  const stack = [];
  let buf = "";
  for (const ch of clean) {
    if (ch === "{") {
      stack.push(buf.trim().replace(/\s+/g, " "));
      buf = "";
    } else if (ch === "}") {
      const decls = buf;
      buf = "";
      const selector = stack.join(" > ").replace(/\s+/g, " ");
      stack.pop();
      if (!selector || selector.startsWith("@")) continue;    // @media 自身不是规则
      for (const d of decls.split(";")) {
        const i = d.indexOf(":");
        if (i < 0) continue;
        const prop = d.slice(0, i).trim().toLowerCase();
        const value = d.slice(i + 1).trim();
        if (BARE_PROPS.has(prop) && bareValue(prop, value)) {
          out.push({ selector, prop, value });
        }
      }
    } else {
      buf += ch;
    }
  }
  return out;
}

export function keyOf(file, e) {
  return `${file}\u0000${e.selector}\u0000${e.prop}\u0000${e.value}`;
}
