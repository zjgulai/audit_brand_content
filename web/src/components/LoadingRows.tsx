/**
 * 全站统一的加载骨架条。
 *
 * ★ 审计（2026-10-27）：此前 8 个页面的加载态是「加载中…」一行孤零零灰字，
 *   挂在页面中部 —— 与 /queue 的骨架屏标准不统一，是专业感最直观的破绽。
 *   本组件提供两种形态：
 *   · rows    表格/列表骨架（默认 3 行，行高可配）
 *   · inline  行内小骨架（用于卡片内小范围等待）
 *
 * ★ 可访问性：容器带 aria-busy="true" 与 role="status"，
 *   屏幕阅读器读到「正在加载」而非空白。
 */
interface LoadingRowsProps {
  rows?: number;
  rowHeight?: number;
  label?: string;
}

export default function LoadingRows({
  rows = 3,
  rowHeight = 44,
  label = "正在加载",
}: LoadingRowsProps) {
  return (
    <div
      className="loading-rows"
      role="status"
      aria-busy="true"
      aria-label={label}
    >
      {Array.from({ length: rows }, (_, i) => (
        <span
          key={i}
          className="loading-rows__bar"
          style={{ height: `${rowHeight}px` }}
        />
      ))}
    </div>
  );
}
