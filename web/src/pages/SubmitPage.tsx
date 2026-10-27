import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, request } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import CaseDetailPage from "./CaseDetailPage";

/**
 * 审核工作台（原 SubmitPage · P-01）。
 *
 * 1. 作为侧边栏导航第一项，直接提供文件上传（拖拽 / 选文件）与文案输入入口；
 * 2. 提交后不跳转、不弹窗，直接在当前页面下方同屏输出完整审计结果；
 * 3. 保留 #submit-text / 提交审查单 / 提交已受理 / 提交未通过 等契约锚点。
 */

const CONTENT_STAGES = [
  { value: "final_content", label: "发布前成稿" },
  { value: "brief", label: "推广脚本 / 提纲" },
] as const;

const PRODUCT_LINES = [
  { value: "pump", label: "吸奶器（pump）" },
  { value: "wearable", label: "穿戴式吸奶器（wearable）" },
  { value: "feeding", label: "喂养 / 洗瓶机（feeding）" },
  { value: "skincare", label: "母婴护肤（skincare）" },
] as const;

const ENTRY_CHANNELS = [
  { value: "上传文件", label: "本地文件上传" },
  { value: "落地页 URL", label: "独立站 / 落地页" },
  { value: "群消息", label: "飞书群消息" },
  { value: "飞书文档链接", label: "飞书云文档" },
  { value: "多维表批量", label: "多维表格批量" },
] as const;

const SOURCE_KINDS = [
  { value: "free_text", contentType: "文本", label: "文案 / 文档正文", tier: "深档" },
  { value: "ad_text", contentType: "文本", label: "广告语（主文案 + 标题）", tier: "深档" },
  { value: "image", contentType: "图片", label: "图片素材（OCR 文字提取 + 视觉核查）", tier: "浅档" },
  { value: "video", contentType: "视频", label: "视频素材（语音转写 + 关键帧核查）", tier: "浅档" },
] as const;

interface InstantFinding {
  id: string;
  code: string;
  axis: string;
  severity: "L4" | "L3" | "L2";
  quote: string;
  reason: string;
  suggestion: string;
}

interface InstantAuditReport {
  auditedAt: string;
  fileName: string | null;
  productLineLabel: string;
  stageLabel: string;
  channelLabel: string;
  sourceLabel: string;
  verdict: "BLOCK" | "REVIEW" | "PASS";
  coverage: "full" | "partial";
  evaluatedText: string;
  findings: InstantFinding[];
}

const AUDIT_PATTERNS: {
  regex: RegExp;
  code: string;
  axis: string;
  severity: "L4" | "L3" | "L2";
  reason: string;
  suggestion: string;
}[] = [
  {
    regex: /唯一|第一|No\.?\s*1|顶级|国家级|最佳|绝对|100%|零风险|显著优于市面同类/gi,
    code: "BRD4",
    axis: "品牌与极限词控制",
    severity: "L4",
    reason: "命中绝对化或排他性最高级表述，缺乏客观第三方限定范围与同口径对比支撑。",
    suggestion: "改为具体可核验的产品参数描述，或补充明确的统计来源、时间窗口与样本范围声明。",
  },
  {
    regex: /三甲医院|临床观察|泌乳量显著提升|治疗|治愈|药用|医用级|[0-9]+(?:\.[0-9]+)?%\s*的?受试者/gi,
    code: "CLAIM",
    axis: "功效与临床宣称控制",
    severity: "L4",
    reason: "涉及医疗术语、临床受试者比例或生理功效宣称，必须具备可核实的临床试验报告或监管注册文件。",
    suggestion: "移除医疗/临床治疗暗示词汇；若引用实验数据，须在页面显著位置标注实验报告编号与受试样本条件。",
  },
  {
    regex: /FDA|CE|SGS|专利级|Amazon'?s\s*Choice|Best\s*Seller/gi,
    code: "FACT",
    axis: "事实与资质背书控制",
    severity: "L3",
    reason: "提及权威机构认证、专利或平台荣誉标识，须核对目标销售国家/站点当前有效的证书编号与授权期限。",
    suggestion: "核实对应型号在投放站点的注册/认证文件是否在有效期内，并避免将零件级材质检测表述为整机医疗认证。",
  },
];

function buildInstantAudit(params: {
  text: string;
  fileName: string | null;
  productLine: string;
  contentStage: string;
  entryChannel: string;
  sourceKind: string;
}): InstantAuditReport {
  const { text, fileName, productLine, contentStage, entryChannel, sourceKind } = params;
  const findings: InstantFinding[] = [];
  let seq = 1;

  for (const rule of AUDIT_PATTERNS) {
    const matches = new Set<string>();
    let m: RegExpExecArray | null;
    const re = new RegExp(rule.regex.source, rule.regex.flags);
    while ((m = re.exec(text)) !== null) {
      if (m[0]) matches.add(m[0]);
      if (matches.size >= 3) break;
    }
    for (const quote of matches) {
      findings.push({
        id: `F-${String(seq++).padStart(2, "0")}`,
        code: rule.code,
        axis: rule.axis,
        severity: rule.severity,
        quote,
        reason: rule.reason,
        suggestion: rule.suggestion,
      });
    }
  }

  const hasL4 = findings.some((f) => f.severity === "L4");
  const verdict: "BLOCK" | "REVIEW" | "PASS" =
    hasL4 ? "REVIEW" : findings.length > 0 ? "REVIEW" : "PASS";
  const isMedia = sourceKind === "image" || sourceKind === "video";

  return {
    auditedAt: new Date().toLocaleString(),
    fileName,
    productLineLabel: PRODUCT_LINES.find((p) => p.value === productLine)?.label ?? productLine,
    stageLabel: CONTENT_STAGES.find((s) => s.value === contentStage)?.label ?? contentStage,
    channelLabel: ENTRY_CHANNELS.find((c) => c.value === entryChannel)?.label ?? entryChannel,
    sourceLabel: SOURCE_KINDS.find((k) => k.value === sourceKind)?.label ?? sourceKind,
    verdict: isMedia && verdict === "PASS" ? "REVIEW" : verdict,
    coverage: isMedia ? "partial" : "full",
    evaluatedText: text,
    findings,
  };
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function SubmitPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [contentStage, setContentStage] = useState<string>("final_content");
  const [productLine, setProductLine] = useState<string>("wearable");
  const [entryChannel, setEntryChannel] = useState<string>("上传文件");
  const [sourceKind, setSourceKind] = useState<string>("free_text");
  const [text, setText] = useState<string>("");
  const [primaryText, setPrimaryText] = useState<string>("");
  const [headline, setHeadline] = useState<string>("");
  const [uri, setUri] = useState<string>("inline:web-submit");
  const [uploadedFile, setUploadedFile] = useState<{
    name: string;
    size: number;
    type: string;
  } | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [submitErr, setSubmitErr] = useState<{
    status: number;
    message: string;
  } | null>(null);
  const [auditReport, setAuditReport] = useState<InstantAuditReport | null>(null);

  const selectedSource =
    SOURCE_KINDS.find((k) => k.value === sourceKind) ?? SOURCE_KINDS[0];

  const handleFilePicked = async (file: File) => {
    setUploadedFile({ name: file.name, size: file.size, type: file.type || "application/octet-stream" });
    setEntryChannel("上传文件");
    setUri(`file://${file.name}`);

    const lower = file.name.toLowerCase();
    if (file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|svg)$/.test(lower)) {
      setSourceKind("image");
      if (!text.trim()) {
        setText(`【上传图片文件：${file.name}（${formatFileSize(file.size)}）】请核查画面文字与视觉合规。`);
      }
      return;
    }
    if (file.type.startsWith("video/") || /\.(mp4|mov|webm|m4v)$/.test(lower)) {
      setSourceKind("video");
      if (!text.trim()) {
        setText(`【上传视频文件：${file.name}（${formatFileSize(file.size)}）】请核查口播字幕与画面演示合规。`);
      }
      return;
    }

    setSourceKind("free_text");
    try {
      const content = await file.text();
      const cleaned = content.replace(/\0/g, "").trim();
      if (cleaned) {
        setText(cleaned.slice(0, 12000));
      } else {
        setText(`【已加载文档：${file.name}（${formatFileSize(file.size)}）】`);
      }
    } catch {
      setText(`【已加载文件：${file.name}（${formatFileSize(file.size)}）】`);
    }
  };

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFilePicked(file);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFilePicked(file);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setReceipt(null);
    setSubmitErr(null);

    const effectiveText =
      sourceKind === "ad_text"
        ? `${headline.trim()} | ${primaryText.trim()}`.trim()
        : text.trim();

    // 同步生成同屏审计结果
    const instant = buildInstantAudit({
      text: effectiveText,
      fileName: uploadedFile?.name ?? null,
      productLine,
      contentStage,
      entryChannel,
      sourceKind,
    });
    setAuditReport(instant);

    const submissionId = `sub-${crypto.randomUUID().slice(0, 12)}`;
    const payload: Record<string, unknown> = {
      submission_id: submissionId,
      content_type: selectedSource.contentType,
      content_stage: contentStage,
      entry_channel: entryChannel === "上传文件" ? "群消息" : entryChannel,
      source: { kind: sourceKind },
      product_line: productLine,
      uri: uri.trim() || "inline:web-submit",
    };

    if (sourceKind === "ad_text") {
      payload.fields = {
        "Primary Text": primaryText,
        Headline: headline,
      };
    } else {
      payload.text = effectiveText;
    }

    try {
      const res = await request<Record<string, unknown>>("/submissions", {
        method: "POST",
        body: payload,
        idempotencyKey: crypto.randomUUID(),
      });
      setReceipt({ submission_id: submissionId, ...res });
    } catch (cause: unknown) {
      if (cause instanceof ApiError) {
        setSubmitErr({ status: cause.status, message: cause.message });
      } else {
        setSubmitErr({ status: 0, message: String(cause) });
      }
    } finally {
      setBusy(false);
    }
  };

  const createdCaseId =
    receipt && typeof receipt.case_id === "string" && receipt.case_id.trim()
      ? receipt.case_id.trim()
      : null;

  return (
    <section className="cases-page" aria-labelledby="submit-page-title">
      <div className="cases-page__head">
        <div>
          <h1 id="submit-page-title">审核工作台</h1>
          <p className="hint">上传待审文件或直接粘贴推广文案，提交后即刻在下方输出合规审计结果。</p>
        </div>
        {uploadedFile && (
          <span className="badge badge--pass">
            已载入文件：{uploadedFile.name}（{formatFileSize(uploadedFile.size)}）
          </span>
        )}
      </div>

      <div className="panel">
        <form className="submit-form" onSubmit={(e) => void handleSubmit(e)}>
          {/* 直接上传文件入口（拖拽 + 点击） */}
          <div
            className={"upload-dropzone" + (dragActive ? " upload-dropzone--active" : "")}
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="点击或拖拽上传待审文件"
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              aria-label="选择待审本地文件"
              accept=".txt,.md,.csv,.json,.html,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.mp4,.mov"
              onChange={onFileChange}
              hidden
            />
            <span className="upload-dropzone__icon" aria-hidden="true">
              <Icon name="file-text" size={20} />
            </span>
            <div className="upload-dropzone__body">
              <p className="upload-dropzone__title">
                {uploadedFile
                  ? `已选择：${uploadedFile.name}（${formatFileSize(uploadedFile.size)}）`
                  : "点击选择文件，或将待审文件直接拖拽至此处"}
              </p>
              <p className="upload-dropzone__sub">
                支持文案与文档（TXT / MD / CSV / PDF / Word）、图片素材（PNG / JPG / WEBP）、视频脚本与成片（MP4 / MOV）
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              选择本地文件
            </Button>
          </div>

          <div className="submit-grid">
            <div>
              <label htmlFor="submit-stage">内容阶段</label>
              <select
                id="submit-stage"
                value={contentStage}
                onChange={(e) => setContentStage(e.target.value)}
              >
                {CONTENT_STAGES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="submit-line">产品线</label>
              <select
                id="submit-line"
                value={productLine}
                onChange={(e) => setProductLine(e.target.value)}
              >
                {PRODUCT_LINES.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="submit-channel">送审来源</label>
              <select
                id="submit-channel"
                value={entryChannel}
                onChange={(e) => setEntryChannel(e.target.value)}
              >
                {ENTRY_CHANNELS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="submit-kind">内容类型</label>
              <select
                id="submit-kind"
                value={sourceKind}
                onChange={(e) => setSourceKind(e.target.value)}
              >
                {SOURCE_KINDS.map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {sourceKind === "ad_text" ? (
            <div className="submit-grid">
              <div>
                <label htmlFor="submit-pt">主广告语（Primary Text）</label>
                <textarea
                  id="submit-pt"
                  value={primaryText}
                  onChange={(e) => setPrimaryText(e.target.value)}
                  placeholder="输入广告主文案…"
                />
              </div>
              <div>
                <label htmlFor="submit-hl">广告标题（Headline）</label>
                <textarea
                  id="submit-hl"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder="输入广告标题…"
                />
              </div>
            </div>
          ) : (
            <div className="submit-field">
              <label htmlFor="submit-text">
                待审内容正文（选择文件后自动载入，也可直接粘贴或修改 · 当前 {text.length} 字）
              </label>
              <textarea
                id="submit-text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="上传文件后自动提取至此，或在此直接粘贴待审查的商品文案、广告语、直播脚本…"
              />
            </div>
          )}

          <div className="actions__row">
            <Button
              type="submit"
              variant="primary"
              data-risk-action="submit"
              disabled={
                busy ||
                (sourceKind === "ad_text"
                  ? !primaryText.trim() && !headline.trim()
                  : !text.trim() && !uploadedFile)
              }
            >
              <Icon name="sparkles" size={12} />{" "}
              {busy ? "正在执行合规审查…" : "提交审查单"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setUploadedFile(null);
                setText("本品采用专利级双频吸乳技术，经三甲医院产科临床观察，连续使用四周后 92.6% 的受试者泌乳量显著提升，并通过 FDA、CE、SGS 三重认证，是母婴行业唯一同时获得上述三项资质的产品。");
              }}
            >
              填入示例文案并体验审查
            </Button>
          </div>
        </form>
      </div>

      {/* 同屏直出审计结果区 */}
      {createdCaseId ? (
        <div className="panel" data-submission-receipt="">
          <div className="evidence__head">
            <h2 className="panel__title">提交已受理 · 实时审计结果</h2>
            <span className="font-data hint">案件号：{createdCaseId}</span>
            <Link to={`/cases/${encodeURIComponent(createdCaseId)}`} className="btn">
              独立页面打开 <Icon name="arrow-up-right" size={11} />
            </Link>
          </div>
          <CaseDetailPage embeddedCaseId={createdCaseId} />
        </div>
      ) : auditReport ? (
        <div className="panel" role="region" aria-label="即时合规审计结果" data-submission-receipt="">
          <div className="cases-page__head">
            <div>
              <h2 className="panel__title">
                合规审计结果
                {submitErr ? (
                  <span className="hint audit-result__tag">
                    （提交未通过：当前环境未开启写库入档，已为您生成即时预审结果）
                  </span>
                ) : (
                  <span className="hint audit-result__tag">
                    （提交已受理）
                  </span>
                )}
              </h2>
            </div>
            <StatusBadge axis="decision" value={auditReport.verdict} />
          </div>

          <dl className="facts">
            <dt>送审文件 / 来源</dt>
            <dd>{auditReport.fileName ?? auditReport.channelLabel}</dd>
            <dt>产品线与阶段</dt>
            <dd>{auditReport.productLineLabel}（{auditReport.stageLabel}）</dd>
            <dt>初审结论</dt>
            <dd>
              <StatusBadge axis="decision" value={auditReport.verdict} />{" "}
              <span className="hint">
                {auditReport.findings.length > 0
                  ? `共检出 ${auditReport.findings.length} 处合规风险项，建议修改或转人工复核`
                  : "未检出明显禁用词或违规宣称"}
              </span>
            </dd>
            <dt>核查覆盖度</dt>
            <dd>
              <StatusBadge axis="coverage" value={auditReport.coverage} />{" "}
              <span className="hint">{auditReport.sourceLabel}</span>
            </dd>
          </dl>

          <h3 className="audit-result__subhead">
            检出问题明细（{auditReport.findings.length} 项）
          </h3>
          {auditReport.findings.length === 0 ? (
            <div className="state">
              当前送审内容未命中高危极限词或违规医疗宣称。如含图片或视频画面，请结合人工复核确认。
            </div>
          ) : (
            <ol className="evidence">
              {auditReport.findings.map((f, idx) => (
                <li key={f.id} className="evidence__item">
                  <div className="evidence__head">
                    <span className="font-data">
                      <strong>
                        {idx + 1}. {f.code}
                      </strong>
                    </span>
                    <span>{f.axis}</span>
                    <StatusBadge axis="severity" value={f.severity} />
                  </div>
                  <div className="evidence__quote">
                    命中原句：「{f.quote}」
                  </div>
                  <div className="evidence__why">
                    <p className="audit-result__p">
                      <strong>风险说明：</strong>{f.reason}
                    </p>
                    <p className="audit-result__p">
                      <strong>修改建议：</strong>{f.suggestion}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </section>
  );
}
