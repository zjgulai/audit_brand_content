import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ApiError,
  request,
  reviewApi,
  type CaseDetail,
  type ReportSummary,
} from "../api/client";
import InlineMetricSummary from "../components/InlineMetricSummary";
import StatusBadge, { resolveAuthorityState } from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 报告查看页（P-09 · Wave C 落 G-06 决策，修复 D-10）。
 *
 * 1. 保留原有元信息区（report_id / case_id / ir_id / 发布时刻 / 静态报告，100% 兼容 check_pages.mjs）；
 * 2. 当关联案件可读时，内嵌渲染不可变静态报告的**六区块正文**：
 *    ① 结论摘要 · ② 命中的问题 · ③ 覆盖证明 · ④ 依据清单 · ⑤ 未审说明 · ⑥ 执行回执与双指纹；
 * 3. 提供「申请重签过期链接（POST /api/v1/reports/{id}/resign）」入口（不修改报告正文）。
 */
export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  const [resignMsg, setResignMsg] = useState<{ ok: boolean; text: string } | null>(
    null,
  );
  const [resigning, setResigning] = useState(false);

  useEffect(() => {
    if (!reportId) return;
    let alive = true;
    setReport(null);
    setCaseDetail(null);
    setError(null);
    reviewApi
      .getReport(reportId)
      .then(async (r) => {
        if (!alive) return;
        setReport(r);
        if (r.case_id) {
          try {
            const c = await reviewApi.getCase(r.case_id);
            if (alive) setCaseDetail(c);
          } catch {
            /* 关联案件不可读时仍展示报告元信息 */
          }
        }
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        setError({ status: err.status ?? 0, message: err.message ?? String(e) });
      });
    return () => {
      alive = false;
    };
  }, [reportId]);

  const handleResign = async () => {
    if (!reportId || resigning) return;
    setResigning(true);
    setResignMsg(null);
    try {
      await request(`/reports/${encodeURIComponent(reportId)}/resign`, {
        method: "POST",
        body: {},
        idempotencyKey: crypto.randomUUID(),
      });
      setResignMsg({
        ok: true,
        text: "已生成新的签名访问链接（旧报告正文保持不可变）。",
      });
    } catch (e: unknown) {
      if (e instanceof ApiError) {
        setResignMsg({
          ok: false,
          text:
            e.status === 501
              ? "重签端点当前为 501 占位（尚未在后端启用动态重签服务），原存档保持不变。"
              : `重签请求未完成（${e.status}）：${e.message}`,
        });
      } else {
        setResignMsg({ ok: false, text: String(e) });
      }
    } finally {
      setResigning(false);
    }
  };

  if (error) {
    const forbidden = error.status === 403 || error.status === 404;
    return (
      <section className="case">
        <h1>报告查看</h1>
        <div
          className={"state " + (forbidden ? "state--forbidden" : "state--error")}
          role="alert"
        >
          <h2>
            {error.status === 404
              ? "报告不存在"
              : error.status === 403
                ? "无权读取该报告"
                : "读取失败"}
          </h2>
          <p>{error.status === 404 ? "该报告编号没有对应的存档。" : error.message}</p>
        </div>
        <p>
          <Link to="/queue">
            <Icon name="arrow-left" size={12} /> 返回复核队列
          </Link>
        </p>
      </section>
    );
  }

  if (!report) {
    return (
      <section className="case">
        <h1>报告查看</h1>
        <p className="hint">加载中…</p>
      </section>
    );
  }

  const ir = caseDetail?.ir;
  const unit = caseDetail?.content_unit;
  const findings = ir?.findings ?? [];
  const notEvaluated = ir?.coverage?.not_evaluated_reason ?? [];

  return (
    <section className="case case--dual">
      <div className="case__head">
        <h1>报告查看</h1>
        <span className="font-data">{report.report_id}</span>
        {ir && <StatusBadge axis="decision" value={ir.decision.state} />}
        <Button
          variant="secondary"
          disabled={resigning}
          onClick={() => void handleResign()}
        >
          {resigning ? "申请重签中…" : "申请重签过期链接"}
        </Button>
      </div>

      {resignMsg && (
        <div
          className={"state " + (resignMsg.ok ? "" : "state--warn")}
          role="status"
        >
          {resignMsg.text}
        </div>
      )}

      <InlineMetricSummary
        scope="report"
        countsLabel={`查出问题 ${findings.length} 处，未查 ${notEvaluated.length} 项`}
        trendLabel={null}
        untestedLabel={ir?.coverage?.coverage_state ?? "未测"}
      />

      <dl className="facts">
        <dt>report_id</dt>
        <dd className="font-data">{report.report_id}</dd>
        <dt>case_id</dt>
        <dd className="font-data">
          {report.case_id ? (
            <Link to={`/cases/${encodeURIComponent(report.case_id)}`}>
              {report.case_id}
            </Link>
          ) : (
            "未登记"
          )}
        </dd>
        <dt>ir_id</dt>
        <dd className="font-data">{report.ir_id ?? "未登记"}</dd>
        <dt>发布时刻</dt>
        <dd className="font-data">{report.published_at ?? "未发布"}</dd>
        <dt>静态报告</dt>
        <dd>
          {report.url ? (
            <a href={report.url} target="_blank" rel="noreferrer">
              {report.url}
            </a>
          ) : (
            "未生成"
          )}
        </dd>
      </dl>

      <p className="hint">
        报告是不可变静态存档；本页只展示后端返回的元信息与关联 IR 快照，不编辑、不重算。
        IR 变更会产生新报告文件，旧文件不改不删。
      </p>

      {/* 内嵌六区块只读报告视图（G-06 / UX-03） */}
      {ir ? (
        <div className="report-sections" data-report-six-blocks="">
          <h2>结论摘要</h2>
          <dl className="facts">
            <dt>对外标签</dt>
            <dd>
              <StatusBadge axis="decision" value={ir.decision.state} />（处置层{" "}
              <span className="font-data">{ir.decision.layer}</span>）
            </dd>
            <dt>放行状态</dt>
            <dd>
              {ir.decision.release_status}（五标签均不等于自动放行）
            </dd>
            <dt>并行义务</dt>
            <dd>{(ir.decision.obligations ?? []).join("、") || "无"}</dd>
          </dl>

          <h2>命中的问题（共 {findings.length} 项）</h2>
          {findings.length === 0 ? (
            <p className="hint">本次运行未记录命中 finding。</p>
          ) : (
            <ol className="evidence">
              {findings.map((f, idx) => {
                const auth = resolveAuthorityState(f.authority_state);
                return (
                  <li key={f.finding_id} className="evidence__item">
                    <div className="evidence__head">
                      <span className="font-data">
                        <strong>
                          {idx + 1}. {f.control_code}
                        </strong>
                      </span>
                      <span className="font-data hint">{f.finding_id}</span>
                      <StatusBadge axis="severity" value={f.severity} />
                      <span className="hint">{f.status}</span>
                    </div>
                    <div className="evidence__quote">
                      {f.quote ?? "无原文引用"}
                    </div>
                    <div className="evidence__why">
                      依据：
                      {(f.authority_ref ?? []).map((r) => r.ref_id).join("、") ||
                        "未登记"}{" "}
                      <span className={auth.cls}>{auth.text}</span>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}

          <h2>覆盖证明</h2>
          <dl className="facts">
            <dt>覆盖状态</dt>
            <dd>
              <StatusBadge axis="coverage" value={ir.coverage.coverage_state} />
              {ir.coverage.coverage_state === "partial" && (
                <strong> 仅已覆盖部分可判</strong>
              )}
            </dd>
            <dt>已评估模态</dt>
            <dd>{(ir.coverage.modalities_evaluated ?? []).join("、") || "未测"}</dd>
            <dt>已跑控制点</dt>
            <dd className="font-data">
              {(ir.coverage.control_points_applied ?? []).join("、") || "无"}
            </dd>
          </dl>

          <h2>依据清单与快照</h2>
          <dl className="facts">
            <dt>规则快照</dt>
            <dd className="font-data">{ir.rule_snapshot ?? "未测"}</dd>
            <dt>知识库快照</dt>
            <dd className="font-data">{ir.kb_snapshot ?? "未测"}</dd>
            <dt>控制点版本</dt>
            <dd className="font-data">{ir.control_points_version ?? "未测"}</dd>
          </dl>

          <h2>未查的部分</h2>
          {notEvaluated.length === 0 ? (
            <p className="hint">无未评估项（所有适用控制点均已评估）。</p>
          ) : (
            <ul className="notrun">
              {notEvaluated.map((it, i) => (
                <li key={i}>
                  <span>{it.what ?? "未命名控制点"}</span>
                  <span className="notrun__why">
                    {it.label ?? it.why ?? "未说明"}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h2>执行回执与指纹锚点</h2>
          <dl className="facts">
            <dt>回执编号</dt>
            <dd className="font-data">{ir.receipt_ref ?? "未测"}</dd>
            <dt>IR 版本</dt>
            <dd className="font-data">
              {ir.ir_id}（{ir.ir_version}）
            </dd>
            <dt>原件指纹 raw_sha256</dt>
            <dd className="font-data">
              {unit?.fingerprint?.raw_sha256 ?? "未内嵌原件指纹"}
            </dd>
            <dt>正文指纹 text_sha256</dt>
            <dd className="font-data">
              {unit?.fingerprint?.text_sha256 ?? "未内嵌正文指纹"}
            </dd>
          </dl>
        </div>
      ) : null}

      <p>
        <Link to="/reports">
          <Icon name="arrow-left" size={12} /> 报告索引
        </Link>
        {"　"}
        <Link to="/queue">
          <Icon name="arrow-left" size={12} /> 返回复核队列
        </Link>
      </p>
    </section>
  );
}
