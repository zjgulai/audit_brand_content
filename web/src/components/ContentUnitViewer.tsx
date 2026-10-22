import { useMemo, useState } from "react";
import type { ContentUnitData, Finding } from "../api/client";
import StatusBadge from "./StatusBadge";
import Button from "../ui/Button";
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
}

interface TextSegment {
  text: string;
  finding?: Finding;
  index?: number;
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
}: Props) {
  const [tab, setTab] = useState<"text" | "fields" | "boundary">("text");

  const unitId = unit?.unit_id ?? unitRef?.unit_id ?? "未登记";
  const kind = unit?.kind ?? unitRef?.kind ?? "未测";
  const parseStatus = unit?.parse_status ?? unitRef?.parse_status ?? "ok";
  const failureKind = unit?.failure_kind ?? unitRef?.failure_kind ?? null;
  const fullText = unit?.text ?? null;
  const covers = unit?.textification?.covers ?? [];
  const doesNotCover = unit?.textification?.does_not_cover ?? [];
  const fields = unit?.fields ?? null;
  const rawSha = unit?.fingerprint?.raw_sha256 ?? null;
  const textSha = unit?.fingerprint?.text_sha256 ?? null;

  const segments = useMemo(() => {
    if (typeof fullText !== "string" || !fullText) return [];
    return segmentText(fullText, findings);
  }, [fullText, findings]);

  return (
    <aside className="unit-pane" aria-label="待审原件与覆盖边界">
      <div className="unit-pane__head">
        <div>
          <strong className="unit-pane__title">
            <Icon name="file-text" size={13} /> 待审原件（ContentUnit）
          </strong>
          <div className="unit-pane__meta font-data">
            <span>{unitId}</span>
            <span> · 形态 {kind}</span>
            <span> · 解析 {parseStatus}</span>
            {failureKind && <span> · 失败原因 {failureKind}</span>}
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
            归一化正文
          </Button>
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "fields"}
            className={tab === "fields" ? "unit-tab--active" : ""}
            onClick={() => setTab("fields")}
          >
            结构化字段
          </Button>
          <Button
            variant="secondary"
            role="tab"
            aria-selected={tab === "boundary"}
            className={tab === "boundary" ? "unit-tab--active" : ""}
            onClick={() => setTab("boundary")}
          >
            覆盖与双指纹
          </Button>
        </div>
      </div>

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
              <strong>当前案件未附带原件全文（ContentUnit.text 为空）</strong>
              <p className="hint">
                可能是无文案格式（DP0）、解析失败（{failureKind ?? "未知"}）或旧版冻结投影未内嵌原件。
                右侧证据链仍展示每条 finding 自带的原文切片 <code>quote</code>。
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
            <p className="hint">无额外结构化字段（fields 为空）。</p>
          )}
        </div>
      )}

      {tab === "boundary" && (
        <div className="unit-pane__body">
          <dl className="facts">
            <dt>已覆盖模态/范围</dt>
            <dd>{covers.length > 0 ? covers.join("、") : "未声明"}</dd>
            <dt>未覆盖范围</dt>
            <dd>{doesNotCover.length > 0 ? doesNotCover.join("、") : "无（全覆盖）"}</dd>
            <dt>原件指纹 raw_sha256</dt>
            <dd className="font-data">{rawSha ?? "未测"}</dd>
            <dt>正文指纹 text_sha256</dt>
            <dd className="font-data">{textSha ?? "未测"}</dd>
          </dl>
        </div>
      )}
    </aside>
  );
}
