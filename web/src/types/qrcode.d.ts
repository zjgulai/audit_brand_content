/**
 * `qrcode` 的最小类型声明（2026-10-23）。
 *
 * 为什么不装 `@types/qrcode`：本仓只用到它一个 API（`toString`），
 * 为一行调用再引入一个**第三方 @types 包**（它本身也是外部代码，进 devDependencies
 * 同样要过依赖审查）不划算。这里把用到的那个签名写死，其余一概不声明 ——
 * 于是「用了别的 API」会在编译期报错，而不是靠人记得不要用。
 *
 * ★ 只声明 `type: "svg"` 这一支：我们只生成 SVG（不用 canvas、不用 data URL），
 *   且 `check_login_qr.mjs` 断言过产物里没有 `<canvas>`。
 */
declare module "qrcode" {
  export interface QrToStringOptions {
    type: "svg";
    errorCorrectionLevel?: "L" | "M" | "Q" | "H";
    margin?: number;
    width?: number;
    color?: { dark?: string; light?: string };
  }

  export function toString(
    text: string,
    options: QrToStringOptions,
  ): Promise<string>;

  const _default: { toString: typeof toString };
  export default _default;
}
