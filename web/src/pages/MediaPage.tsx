import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import LoadingRows from "../components/LoadingRows";
import { reviewApi, type CaseSummary } from "../api/client";
import { useIdentity } from "../components/IdentitySwitcher";
import Button from "../ui/Button";
import Pager, { slicePage } from "../ui/Pager";

/**
 * 素材库（P-13）。
 *
 * ## 它回答的问题
 *
 * 「我审过的那张图 / 那段视频，现在在哪儿？」
 *
 * 2026-11-03 之前这个问题答不了：媒体进件链是完整的（上传落盘 → 提交 →
 * OCR/多模态 → 建案件），但没有任何界面能把**已进件的素材**列出来。
 * 唯一的入口是从队列里挨个点开案件，而队列只显示待办的。
 *
 * ## 数据源：案件，不是目录
 *
 * 素材根目录（`REVIEW_MEDIA_ROOTS`）下确实躺着那些文件，但**不拿它当数据源**：
 *
 *   · 目录里有、却没建成案件的文件（上传后没提交）—— 那条素材没有任何判定，
 *     列出来等于给一个「看起来审过了」的假象；
 *   · 建了案件、文件却已不在盘上的 —— 目录扫不到，素材就从列表里消失，
 *     而案件还在，人却再也找不到它。
 *
 * 两条都会让「列表里有什么」和「系统里有什么」变成两个答案。
 * 所以这里只列**有案件的原件**：`content_kind ∈ {image, video}` 的案件。
 * 原件本身由 `GET /api/v1/cases/{id}/original` 提供（服务端校验路径与权限）。
 *
 * ## 为什么是网格不是表格
 *
 * 素材的识别靠「看一眼」。一行文字说「图片 · 2.1MB · 吸奶器」，
 * 人要读三遍才知道自己要找的是哪一张；缩略图扫一眼就定位了。
 * 布局承担识别工作，不靠标签文字。
 *
 * ## 三态
 *
 * 空 / 错误 / 加载各有各的样子，且空态**说清为什么空**
 * （「当前没有媒体案件」≠「媒体进件没开」—— 后者要在别处看）。
 */

const MEDIA_KINDS = new Set(["image", "video"]);

const KIND_LABEL: Record<string, string> = {
  image: "图片",
  video: "视频",
};

function MediaThumb({ caseId, kind }: { caseId: string; kind: string }) {
  const [broken, setBroken] = useState(false);
  const src = `/api/v1/cases/${encodeURIComponent(caseId)}/original`;

  if (broken) {
    return (
      <div className="media-card__fallback" data-media-fallback="">
        原件读取失败
      </div>
    );
  }
  if (kind === "video") {
    return (
      <video
        className="media-card__thumb"
        src={src}
        preload="metadata"
        muted
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <img
      className="media-card__thumb"
      src={src}
      alt=""
      loading="lazy"
      onError={() => setBroken(true)}
    />
  );
}

export default function MediaPage() {
  const { devEnabled, current, sessionEpoch } = useIdentity();
  const [rows, setRows] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [kindFilter, setKindFilter] = useState<string>("all");
  const [lineFilter, setLineFilter] = useState<string>("all");
  const [query, setQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(24);

  useEffect(() => {
    if (devEnabled && current === null) {
      setRows(null);
      setError(null);
      return;
    }
    let alive = true;
    setRows(null);
    setError(null);
    reviewApi
      .listCases()
      .then((data) => {
        if (alive) setRows(data);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        // ★ 失败时把列表从 null 里放出来 —— 与 AppealsPage / AdminGrantsPage
        //   同一条：`rows === null` 渲染骨架屏，若不清空，错误横幅会与
        //   永远转下去的骨架屏同时出现。
        setRows([]);
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
      });
    return () => {
      alive = false;
    };
  }, [current, devEnabled, sessionEpoch]);

  const mediaRows = useMemo(
    () => (rows ?? []).filter((c) => c.content_kind && MEDIA_KINDS.has(c.content_kind)),
    [rows],
  );

  const productLines = useMemo(() => {
    const s = new Set<string>();
    for (const c of mediaRows) if (c.product_line) s.add(c.product_line);
    return [...s].sort();
  }, [mediaRows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return mediaRows.filter((c) => {
      if (kindFilter !== "all" && c.content_kind !== kindFilter) return false;
      if (lineFilter !== "all" && c.product_line !== lineFilter) return false;
      if (q) {
        const hay = `${c.case_id} ${c.title_or_excerpt ?? ""} ${c.product_line ?? ""}`
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [mediaRows, kindFilter, lineFilter, query]);

  // 筛选变了就回第一页 —— 否则「筛成 3 条却停在第 7 页」会显示空白。
  useEffect(() => {
    setPage(1);
  }, [kindFilter, lineFilter, query, pageSize]);

  const visible = useMemo(
    () => slicePage(filtered, page, pageSize),
    [filtered, page, pageSize],
  );

  if (error) {
    return (
      <section className="page">
        <h1>素材库</h1>
        <div
          className={
            "state " +
            (error.status === 401 || error.status === 403
              ? "state--forbidden"
              : "state--error")
          }
          role="alert"
        >
          <h2>
            {error.status === 401
              ? "需要登录"
              : error.status === 403
                ? "无权读取素材"
                : "读取失败"}
          </h2>
          <p>{error.message}</p>
        </div>
      </section>
    );
  }

  if (rows === null) {
    return (
      <section className="page">
        <h1>素材库</h1>
        <LoadingRows rows={6} label="正在读取素材…" />
      </section>
    );
  }

  return (
    <section className="page" data-media-page="">
      <h1>素材库</h1>

      <div className="media-bar" role="group" aria-label="素材筛选">
        <label className="media-bar__field">
          载体
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value)}
          >
            <option value="all">全部</option>
            <option value="image">图片</option>
            <option value="video">视频</option>
          </select>
        </label>
        <label className="media-bar__field">
          品线
          <select
            value={lineFilter}
            onChange={(e) => setLineFilter(e.target.value)}
          >
            <option value="all">全部</option>
            {productLines.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label className="media-bar__field media-bar__field--grow">
          搜索
          <input
            type="search"
            value={query}
            placeholder="案件号 / 摘要 / 品线"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {(kindFilter !== "all" || lineFilter !== "all" || query) && (
          <Button
            variant="secondary"
            onClick={() => {
              setKindFilter("all");
              setLineFilter("all");
              setQuery("");
            }}
          >
            重置
          </Button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="state" data-media-empty="">
          <h2>
            {mediaRows.length === 0 ? "当前没有带原件的案件" : "没有匹配的素材"}
          </h2>
          {mediaRows.length === 0 ? (
            <p className="hint">
              素材库只列**已经建了案件**的图片与视频。上传后未提交的文件不在这里 ——
              它们还没有任何判定结论。媒体进件开关本身是否打开，看
              「安全审计」页的运行时读数，不要从这里的空列表推断。
            </p>
          ) : (
            <p className="hint">换个筛选条件，或清空搜索词。</p>
          )}
        </div>
      ) : (
        <>
          <ul className="media-grid" data-media-grid="">
            {visible.map((c) => (
              <li key={c.case_id} className="media-card">
                <Link
                  className="media-card__frame"
                  to={`/cases/${encodeURIComponent(c.case_id)}`}
                  aria-label={`打开案件 ${c.case_id}`}
                >
                  <MediaThumb
                    caseId={c.case_id}
                    kind={c.content_kind ?? ""}
                  />
                </Link>
                <div className="media-card__meta">
                  <span className="media-card__kind">
                    {KIND_LABEL[c.content_kind ?? ""] ?? c.content_kind ?? "未测"}
                  </span>
                  {c.product_line && (
                    <span className="media-card__line">{c.product_line}</span>
                  )}
                  {c.state && (
                    <span className="media-card__state">{c.state}</span>
                  )}
                </div>
                <div className="media-card__foot font-data">
                  <span title={c.case_id}>{c.case_id.slice(0, 12)}…</span>
                  {c.created_at && (
                    <span>{c.created_at.slice(0, 10)}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <Pager
            page={page}
            pageSize={pageSize}
            total={filtered.length}
            onPage={setPage}
            onPageSize={setPageSize}
            pageSizeOptions={[12, 24, 48]}
            noun="份素材"
          />
        </>
      )}
    </section>
  );
}
