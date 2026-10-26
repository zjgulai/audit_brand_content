import { useMemo } from "react";
import Icon from "./icon";

/**
 * 分页控件（2026-10-26 新增）。
 *
 * ## 为什么现在才加
 *
 * 案件总览与报告索引此前都是 `rows.map(...)` 一次性渲染全部行 ——
 * 数据少时没问题，一旦累积到几百条：首屏变慢、滚动条长到没法定位、
 * 而且**没有任何「我现在看到的是第几页」的坐标**，找人只能靠肉眼扫。
 *
 * ## 设计上的三条硬约束
 *
 * 1. **不改变数据源**：分页只切数组，不重发请求、不引入服务端分页协议。
 *    换服务端分页要动 API 契约（属 ③ 案件建立那一环），那是另一个会话的事。
 *    这里只做**前端视图分页**，接口一个字节都没变。
 * 2. **筛选变化必须回到第一页**：否则「筛成 3 条却停在第 7 页」会显示空白，
 *    而读的人会以为「没有数据」。调用方用 `key` 或 `resetKey` 保证这件事。
 * 3. **没有分页时不许渲染空壳**：只有一页且用户没选择页大小时，整块不出现 ——
 *    多一行控件就多一处要读的东西。
 *
 * ## 无障碍
 *
 * · `<nav aria-label>` + 当前页 `aria-current="page"`；
 * · 页码按钮 ≥ 32px 高（窄屏 44px 由 .pager 的媒体查询接管）；
 * · 「上一页/下一页」在边界上 `disabled` 而不是隐藏 —— 位置固定才不会误点。
 */

export interface PagerProps {
  page: number;
  pageSize: number;
  total: number;
  onPage: (next: number) => void;
  onPageSize?: (next: number) => void;
  pageSizeOptions?: number[];
  /** 单位名词，用于「共 N 条」的读法：「条案件」/「份报告」 */
  noun?: string;
}

/** 页码序列：1 … 4 5 6 … 20（窗口 3 页 + 首尾 + 省略号）。 */
export function pageWindow(page: number, totalPages: number): (number | "…")[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }
  const out: (number | "…")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);
  if (start > 2) out.push("…");
  for (let p = start; p <= end; p += 1) out.push(p);
  if (end < totalPages - 1) out.push("…");
  out.push(totalPages);
  return out;
}

export function Pager({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
  pageSizeOptions = [20, 50, 100],
  noun = "条",
}: PagerProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const from = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const to = Math.min(safePage * pageSize, total);
  const items = useMemo(
    () => pageWindow(safePage, totalPages),
    [safePage, totalPages],
  );

  // 只有一页、且调用方不给页大小选择器时才完全不渲染 —— 没有可翻的东西
  if (totalPages <= 1 && !onPageSize) return null;

  return (
    <nav className="pager" aria-label="分页">
      <p className="pager__summary">
        共 {total} {noun} · 当前显示第 {from}–{to} {noun}
      </p>

      {totalPages > 1 && (
        <div className="pager__pages">
          <button
            type="button"
            className="pager__btn"
            onClick={() => onPage(safePage - 1)}
            disabled={safePage <= 1}
            aria-label="上一页"
          >
            <Icon name="chevron-left" size={13} />
          </button>
          {items.map((it, i) =>
            it === "…" ? (
              <span className="pager__gap" key={`gap-${i}`} aria-hidden="true">
                …
              </span>
            ) : (
              <button
                key={it}
                type="button"
                className={
                  "pager__btn" + (it === safePage ? " pager__btn--current" : "")
                }
                onClick={() => onPage(it)}
                aria-current={it === safePage ? "page" : undefined}
                aria-label={`第 ${it} 页`}
              >
                {it}
              </button>
            ),
          )}
          <button
            type="button"
            className="pager__btn"
            onClick={() => onPage(safePage + 1)}
            disabled={safePage >= totalPages}
            aria-label="下一页"
          >
            <Icon name="chevron-right" size={13} />
          </button>
        </div>
      )}

      {onPageSize && (
        <label className="pager__size">
          每页
          <select
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value))}
            aria-label="每页显示条数"
          >
            {pageSizeOptions.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          条
        </label>
      )}
    </nav>
  );
}

/**
 * 分页切片。**放这里而不是各页各写一遍** —— 切片口径只有一处，
 * 否则「第 2 页从哪开始」会在两个页面里有两种算法。
 */
export function slicePage<T>(rows: T[], page: number, pageSize: number): T[] {
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  return rows.slice(start, start + pageSize);
}

export default Pager;
