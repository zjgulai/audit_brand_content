import { useMemo, useState } from "react";
import type {
  ContentUnitData,
  Finding,
  MultimodalObservation,
} from "../api/client";
import StatusBadge from "./StatusBadge";
import Button from "../ui/Button";
import FieldState from "../ui/FieldState";
import Icon from "../ui/icon";

/**
 * 待审原件与覆盖边界查看器（Wave B · 落 G-02 决策，修复 D-04「盲审」缺陷）。
 *
 * 功能：
 *   1. 展示 ContentUnit 的三类视图：归一化正文（带 Finding.location 区间高亮与角标）、
 *      结构化字段（fields）、覆盖边界声明（covers / does_not_cover）与双指纹；
 *   2. 点击文中高亮区间 → 触发 onSelectFinding(findingId) 与右栏证据链联动；
 *   3. 当右栏选中 activeFindingId 时，对应原文高亮块呈现 600ms 琥珀色闪底/聚焦边框。
 */

/** 载体枚举 → 界面词。未知值原样显示（后端加了新载体不至于空白）。 */
const KIND_LABELS: Record<string, string> = {
  free_text: "自由文本",
  product_listing: "商品页",
  image: "图片",
  video: "视频",
};

const kindLabel = (k: string) => KIND_LABELS[k] ?? k;

interface Props {
  unit: ContentUnitData | null | undefined;
  unitRef?: {
    unit_id: string;
    kind: string;
    parse_status?: string;
    failure_kind?: string | null;
  } | null;
  findings: Finding[];
  activeFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
  /** T-439：L1 多模态观察。★ 与报告「画面语义（候选 · 待人工确认）」同源。 */
  observations?: MultimodalObservation[];
  /** 没有任何观察时「为什么没看」。有三态才说得清，见组件内注释。 */
  observationNote?: string | null;
  /** 案件 id —— 原件的读取按案件走（见下方「原件」那一块的注释）。 */
  caseId?: string | null;
}

interface TextSegment {
  text: string;
  finding?: Finding;
  index?: number;
}

/**
 * 送审原件（图片 / 视频）。
 *
 * ## 为什么它在这里，而之前没有
 *
 * 媒体进件那条链一直是完整的：上传落到 `<media_roots>/_uploads/`、提交时
 * 那个路径进 `source.uri`、OCR / 多模态拿它出观察、建案件。**读不回来** ——
 * 全仓没有任何一条路由把那个文件交给浏览器。于是审核员在详情页看到的只有
 * 「OCR 提出来的一段文字」，看不到那张图。
 *
 * 那不是「少个功能」，是**判的对象看不见**：判定链的输入是一个他无法核对的转写件。
 * 2026-11-03 补了 `GET /api/v1/cases/{case_id}/original`，这个组件是它的消费侧。
 *
 * ## 为什么按 caseId 取，不把路径交过来
 *
 * `source.uri` 是服务器绝对路径。放进接口响应等于把目录结构交给浏览器；
 * 让前端拿路径回来取文件，等于开一个「读机器上任意路径」的入口。
 * 所以前端只知道 case_id，路径只在服务端解析并校验仍在允许根内。
 *
 * ## 三态照实说
 *
 * 加载失败不许留白，也不许伪装成「没图」。读不出就说读不出，并给出下一步
 * （刷新 / 找后端确认原件是否还在盘上）。
 */
function OriginalMedia({
  caseId,
  kind,
}: {
  caseId?: string | null;
  kind: string;
}) {
  const [failed, setFailed] = useState<null | string>(null);

  if (!caseId) {
    return (
      <div className="unit-original" data-unit-original="unavailable">
        <div className="unit-original__state">
          这条案件没有关联 id，无法定位原件
        </div>
      </div>
    );
  }

  // ★ 路径与鉴权都在服务端：cookie 随请求走，`<img>` 天然带同源 cookie。
  const src = `/api/v1/cases/${encodeURIComponent(caseId)}/original`;

  return (
    <div className="unit-original" data-unit-original={kind}>
      <div className="unit-original__head">
        <span className="unit-original__label">
          送审原件{kind === "video" ? "（视频）" : ""}
        </span>
        <a
          className="unit-original__label"
          href={src}
          target="_blank"
          rel="noopener noreferrer"
        >
          看全尺寸
        </a>
      </div>
      <div className="unit-original__body">
        {failed ? (
          <div className="unit-original__state">
            原件读取失败（{failed}）。它可能已从磁盘移除，或在允许的素材根之外。
          </div>
        ) : kind === "video" ? (
          <video
            src={src}
            controls
            preload="metadata"
            onError={() => setFailed("无法解码或文件不存在")}
          />
        ) : (
          <img
            src={src}
            alt="送审原件"
            loading="lazy"
            onError={() => setFailed("无法解码或文件不存在")}
          />
        )}
      </div>
    </div>
  );
}

function segmentText(rawText: string, findings: Finding[]): TextSegment[] {
  const spans: Array<{ start: number; end: number; finding: Finding; index: number }> = [];
  findings.forEach((f, idx) => {
    const start = f.location?.start;
    const end = f.location?.end;
    if (
      typeof start === "number" &&
      typeof end === "number" &&
      start >= 0 &&
      end > start &&
      end <= rawText.length
    ) {
      spans.push({ start, end, finding: f, index: idx + 1 });
    } else if (typeof f.quote === "string" && f.quote.length > 0) {
      const pos = rawText.indexOf(f.quote);
      if (pos >= 0) {
        spans.push({
          start: pos,
          end: pos + f.quote.length,
          finding: f,
          index: idx + 1,
        });
      }
    }
  });

  spans.sort((a, b) => a.start - b.start || b.end - a.end);

  const out: TextSegment[] = [];
  let cursor = 0;
  for (const s of spans) {
    if (s.start < cursor) continue; // 重叠区间保持首条优先，不切碎字符
    if (s.start > cursor) {
      out.push({ text: rawText.slice(cursor, s.start) });
    }
    out.push({
      text: rawText.slice(s.start, s.end),
      finding: s.finding,
      index: s.index,
    });
    cursor = s.end;
  }
  if (cursor < rawText.length) {
    out.push({ text: rawText.slice(cursor) });
  }
  return out;
}

export default function ContentUnitViewer({
  unit,
  unitRef,
  findings,
  activeFindingId,
  onSelectFinding,
  observations,
  observationNote,
  caseId,
}: Props) {
  const [tab, setTab] = useState<"text" | "fields" | "boundary" | "semantics">(
    "text",
  );

  const kind = unit?.kind ?? unitRef?.kind ?? "未测";
  // ★ ADR-0021 · W-2：去掉 `?? "ok"`。
  //   改前：`parse_status ?? "ok"` —— 后端没给 parse_status 时显示「已提取正文」，
  //   于是**没解析的图看起来解析成功了**。这是六处「缺失装成有值」里最危险的一处：
  //   审核员会以为系统已经读过图里的文字。
  //   现在：拿不到就是 `undefined` → 由 FieldState 渲染成「未测」。
  const parseStatus = unit?.parse_status ?? unitRef?.parse_status;
  const failureKind = unit?.failure_kind ?? unitRef?.failure_kind ?? null;
  const fullText = unit?.text ?? null;
  const covers = unit?.textification?.covers ?? [];
  const doesNotCover = unit?.textification?.does_not_cover ?? [];
  const fields = unit?.fields ?? null;
  const rawSha = unit?.fingerprint?.raw_sha256 ?? null;
  const textSha = unit?.fingerprint?.text_sha256 ?? null;

  // ★ T-439：三态必须分开。空数组 + note 才是「没看，原因是 note」；
  //   空数组 + 空 note 是「这条数据源没有观察」（旧案件）。
  //   两种都不许渲染成「画面没问题」—— 与报告那一节同一口径。
  const obs = observations ?? [];
  const okObs = obs.filter((o) => o.status === "ok");
  const badObs = obs.filter((o) => o.status !== "ok");
  const noteText = (observationNote ?? "").trim();

  // ★ 2026-11-03：媒体载体才有原件可看。文本载体的「原件」就是正文本身，
  //   再放一个预览框只会挤占版面而没有任何新信息。
  const isMediaKind = kind === "image" || kind === "video";

  const segments = useMemo(() => {
    if (typeof fullText !== "string" || !fullText) return [];
    return segmentText(fullText, findings);
  }, [fullText, findings]);

  return (
    <aside className="unit-pane" aria-label="原文内容与覆盖范围">
      <div className="unit-pane__head">
        <div>
          <strong className="unit-pane__title">
            <Icon name="file-text" size={13} /> 原文内容
          </strong>
          <div className="unit-pane__meta">
            <span>载体：{kindLabel(kind)}</span>
            {/* ★ ADR-0021 · W-2：三态。
                有值 → 「已提取正文」/ 具体状态；
                没值 → 「未测」（**不许**回落成「已提取正文」）；
                failureKind 存在 → 走 unreadable 那一支，说清「读不出」。 */}
            <span>
              状态：
              {parseStatus === "ok" ? (
                "已提取正文"
              ) : (
                <FieldState
                  value={parseStatus}
                  unreadableReason={
                    parseStatus ? failureKind ?? undefined : undefined
                  }
                  missingReason={failureKind ? undefined : "后端未返回解析状态"}
                />
              )}
            </span>
            {failureKind && <span>异常：{failureKind}</span>}
          </div>
        </div>
        <div className="unit-pane__tabs" role="tablist" aria-label="原件视图切换">
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "text"}
            className={tab === "text" ? "unit-tab--active" : ""}
            onClick={() => setTab("text")}
          >
            正文内容
          </Button>
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "fields"}
            className={tab === "fields" ? "unit-tab--active" : ""}
            onClick={() => setTab("fields")}
          >
            送审信息
          </Button>
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "boundary"}
            className={tab === "boundary" ? "unit-tab--active" : ""}
            onClick={() => setTab("boundary")}
          >
            核查范围
          </Button>
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "semantics"}
            className={tab === "semantics" ? "unit-tab--active" : ""}
            onClick={() => setTab("semantics")}
          >
            画面语义
          </Button>
        </div>
      </div>

      {isMediaKind && (
        <OriginalMedia caseId={caseId} kind={kind} />
      )}

      {doesNotCover.length > 0 && (
        <div className="unit-pane__boundary-bar">
          <StatusBadge axis="coverage" value="partial" />{" "}
          <span>
            本单元未覆盖：<strong>{doesNotCover.join("、")}</strong>
          </span>
        </div>
      )}

      {tab === "text" && (
        <div className="unit-pane__body" data-unit-text="">
          {typeof fullText === "string" && fullText.length > 0 ? (
            <div className="unit-text">
              {segments.map((seg, i) => {
                if (!seg.finding) {
                  return <span key={i}>{seg.text}</span>;
                }
                const f = seg.finding;
                const isActive = activeFindingId === f.finding_id;
                return (
                  <mark
                    key={i}
                    id={`unit-mark-${f.finding_id}`}
                    className={
                      "unit-mark" + (isActive ? " unit-mark--active" : "")
                    }
                    data-finding-mark={f.finding_id}
                    tabIndex={0}
                    role="button"
                    aria-label={`定位到证据链第 ${seg.index} 条 ${f.control_code}`}
                    onClick={() => onSelectFinding(f.finding_id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelectFinding(f.finding_id);
                      }
                    }}
                  >
                    {seg.text}
                    <sup className="unit-mark__tag font-data">
                      [{seg.index}:{f.control_code}]
                    </sup>
                  </mark>
                );
              })}
            </div>
          ) : (
            <div className="state state--warn">
              <strong>这条案件没有附带原文内容</strong>
              <p className="hint">
                未提取到正文文本（{failureKind ?? "无文本内容"}），可在右侧查看命中的原文片段。
              </p>
            </div>
          )}
        </div>
      )}

      {tab === "fields" && (
        <div className="unit-pane__body">
          {fields && Object.keys(fields).length > 0 ? (
            <dl className="facts">
              {Object.entries(fields).map(([k, v]) => (
                <div key={k} className="facts__pair">
                  <dt className="font-data">{k}</dt>
                  <dd>{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="hint">无附加送审信息。</p>
          )}
        </div>
      )}

      {tab === "boundary" && (
        <div className="unit-pane__body">
          <dl className="facts">
            <dt>已核查范围</dt>
            <dd>{covers.length > 0 ? covers.join("、") : "未声明"}</dd>
            <dt>未核查范围</dt>
            <dd>{doesNotCover.length > 0 ? doesNotCover.join("、") : "无（全部覆盖）"}</dd>
            <dt>原件校验码</dt>
            <dd className="font-data">{rawSha ? `${rawSha.slice(0, 16)}…` : "未测"}</dd>
            <dt>正文校验码</dt>
            <dd className="font-data">{textSha ? `${textSha.slice(0, 16)}…` : "未测"}</dd>
          </dl>
        </div>
      )}

      {tab === "semantics" && (
        <div className="unit-pane__body" data-multimodal-observations="">
          {/* ★ 措辞与报告那一节逐字一致：「候选 · 待人工确认」。
              观察不是 finding —— 它没有 control_code 与 authority_ref，
              所以界面上不许渲染成已确认的违规，否则复核时无法对照规则。 */}
          <p className="hint">
            <strong>候选，待人工确认</strong>
            ：以下为机器对画面的观察，不是规则命中，须人工判断。
          </p>
          {okObs.length === 0 && badObs.length === 0 ? (
            <div className="state state--warn">
              <strong>本项未评</strong>
              <p className="hint">
                {noteText || "未提供原因（按未评处理）"}
              </p>
              <p className="hint">不得据此放行，须人工复核画面。</p>
            </div>
          ) : (
            <>
              {okObs.length > 0 ? (
                <ul className="facts">
                  {okObs.map((o, i) => (
                    <li key={`ok-${i}`}>
                      <span className="font-data">[{o.task}]</span>{" "}
                      {o.statement}
                      {typeof o.confidence === "number" ? (
                        <span className="hint font-data">
                          {" "}
                          置信 {o.confidence.toFixed(2)}
                        </span>
                      ) : null}
                      {o.bbox ? (
                        <span className="hint"> 位置：{o.bbox}</span>
                      ) : null}
                      {o.ts ? <span className="hint"> 时间：{o.ts}</span> : null}
                      {o.model ? (
                        <span className="hint font-data"> 模型：{o.model}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">无有效观察（下面逐条说明为什么）。</p>
              )}
              {badObs.length > 0 ? (
                <>
                  <p className="hint">
                    未评部分（{badObs.length} 条，原因如下）—— 未评不是没问题：
                  </p>
                  <ul className="facts">
                    {badObs.map((o, i) => (
                      <li key={`bad-${i}`}>
                        <span className="font-data">[{o.task}]</span> {o.status}：
                        {o.reason ?? "未说明"}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
              <p className="hint">
                覆盖状态：部分覆盖 —— 画面语义为候选观察，须人工确认。
              </p>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
