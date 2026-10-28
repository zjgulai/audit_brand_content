import { useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { reviewWriteApi } from "../api/write-client";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import CaseDetailPage from "./CaseDetailPage";

/**
 * 审核工作台（原 SubmitPage · P-01）。
 *
 * 1. 作为侧边栏导航第一项，直接提供文件上传（拖拽 / 选文件）与文案输入入口；
 * 2. 提交后不跳转、不弹窗，直接在当前页面下方同屏输出完整审计结果；
 * 3. 保留 #submit-text / 提交审查单 契约锚点；结论**分两层**显示：
 *    真判定（已立案）在上、本地预检（**明确标注不是判定**）在下。
 *    ★ 2026-10-28 改：原先是二选一，且两者标题都像正式结论。
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

interface UploadedMedia {
  /** 服务端落盘路径 —— 提交时作为 `source.uri`。 */
  path: string;
  kind: "image" | "video";
  byteSize: number;
  sha256: string;
  displayName: string;
}

/** 上传的四态。★ `failed` 与 `done` 必须分开：读起来完全不同的是
 *  「没传上去」和「传上去了」，而它们的界面长得都像「有个文件名」。 */
type UploadState =
  | { phase: "idle" }
  | { phase: "uploading"; name: string }
  | { phase: "done"; media: UploadedMedia }
  | { phase: "failed"; name: string; message: string };

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
  // ★ 只有 uploadState 一个状态源。第一版还多留了一个 `uploadError` 字符串，
  //   结果它和状态机里的 `failed.message` 是同一个量 —— 两个口径各写一遍
  //   必然有一处忘了同步（AGENTS.md §2.4.8）。tsc 的 TS6133 正好指出了这一点。
  const [uploadState, setUploadState] = useState<UploadState>({ phase: "idle" });
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
    setUploadState({ phase: "uploading", name: file.name });

    // ★★ 图片 / 视频必须**真上传**。
    //
    //   改前这里只做了一件事：往正文里塞一句
    //   「【上传图片文件：xxx.png】请核查画面文字与视觉合规。」——
    //   那张图**从来没被任何人看过**，而后端早就接好了多模态。
    //   于是界面显示「审完了」，实际审的是一句占位文字。
    //   这是本项目最忌讳的形状：产出看起来正常、没有任何东西会红。
    //
    //   现在：上传 → 拿服务端路径 → 填进 `source.uri` → 走既有进件链。
    //   ★ 不按扩展名在前端判类型：服务端已按**魔数**确认过内容，
    //     前端再猜一次只会多一个可能与服务端不一致的口径。
    const lower = file.name.toLowerCase();
    const looksMedia =
      file.type.startsWith("image/") ||
      file.type.startsWith("video/") ||
      /\.(png|jpe?g|webp|gif|mp4|mov|webm|m4v)$/.test(lower);

    if (looksMedia) {
      try {
        const info = await reviewWriteApi.uploadMedia(file, file.name);
        setUploadState({
          phase: "done",
          media: {
            path: info.path,
            kind: info.kind,
            byteSize: info.byte_size,
            sha256: info.sha256,
            displayName: info.display_name,
          },
        });
        setSourceKind(info.kind);
        setUri(info.path);
        // 正文留空：图片/视频的正文由后端按能力边界决定（视频没有 ASR
        // 时正文就是空串）。前端塞占位文字会让「有没有正文」这件事失真。
        return;
      } catch (cause: unknown) {
        const message =
          cause instanceof ApiError
            ? `${cause.status} ${cause.message}`
            : String(cause);
        setUploadState({ phase: "failed", name: file.name, message });
        return;
      }
    }

    // 文本类文件：本地读正文（后端收的是 text，不需要上传原件）。
    setUploadState({ phase: "idle" });
    setSourceKind("free_text");
    setUri(`file://${file.name}`);
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

    // ★ 本地预检**先**跑：它要立刻给出反馈，不能等网络。
    //   但它**不是判定** —— 界面上必须与真判定分开显示（见下方两层结论）。
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
      // ★ 改前这里写的是 `entryChannel === "上传文件" ? "群消息" : entryChannel`
      //   —— 因为契约当时把「上传文件」标为 unsupported，只能借用别的通道。
      //   后果：网页传进来的内容，记录里写着「群消息」，来源统计从源头就是错的。
      //   现在上传通道已打开（contract.py），照实写。
      entry_channel: entryChannel,
      source: { kind: sourceKind },
      product_line: productLine,
      uri: uri.trim() || "inline:web-submit",
    };

    // ★ 媒体必须带**服务端路径**。没上传成功就不许提交 ——
    //   否则后端会 422（`source.uri` 是本地 `file://name`，不是可达路径），
    //   而那个 422 读起来像「参数错了」，实际是「文件根本没上去」。
    if (sourceKind === "image" || sourceKind === "video") {
      if (uploadState.phase !== "done") {
        setSubmitErr({
          status: 0,
          message:
            uploadState.phase === "failed"
              ? `文件未上传成功：${uploadState.message}`
              : "请先选择并等待文件上传完成。",
        });
        setBusy(false);
        return;
      }
      payload.uri = uploadState.media.path;
      payload.source = { kind: uploadState.media.kind };
    }

    if (sourceKind === "ad_text") {
      payload.fields = {
        "Primary Text": primaryText,
        Headline: headline,
      };
    } else if (effectiveText) {
      payload.text = effectiveText;
    }
    // ★ 媒体不塞 text：图片/视频的正文由后端按能力边界决定
    //   （视频没有 ASR 时正文就是空串）。前端填一句占位话会让
    //   「有没有正文」这件事失真，而报告里正是靠它说覆盖边界。

    try {
      const res = await reviewWriteApi.submit(payload, crypto.randomUUID());
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
          <p className="hint">
            上传待审文件或直接粘贴推广文案。提交后由后端规则引擎出具判定，
            本地预检只做粗筛、会单独标注。
          </p>
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
            className={
              "upload-dropzone" +
              (dragActive ? " upload-dropzone--active" : "") +
              (uploadState.phase === "done" ? " upload-dropzone--done" : "") +
              (uploadState.phase === "failed" ? " upload-dropzone--failed" : "")
            }
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
              <Icon
                name={uploadState.phase === "failed" ? "alert-triangle" : "file-text"}
                size={20}
              />
            </span>
            <div className="upload-dropzone__body">
              <p className="upload-dropzone__title">
                {uploadState.phase === "uploading"
                  ? `正在上传：${uploadState.name}…`
                  : uploadState.phase === "done"
                    ? `已上传：${uploadState.media.displayName}（${formatFileSize(uploadState.media.byteSize)}）`
                    : uploadState.phase === "failed"
                      ? `上传失败：${uploadState.name}`
                      : uploadedFile
                        ? `已选择：${uploadedFile.name}（${formatFileSize(uploadedFile.size)}）`
                        : "点击选择文件，或将待审文件直接拖拽至此处"}
              </p>
              <p className="upload-dropzone__sub">
                {uploadState.phase === "done"
                  ? `服务端已落盘 · ${uploadState.media.kind === "video" ? "视频" : "图片"} · 校验码 ${uploadState.media.sha256.slice(0, 12)}…`
                  : uploadState.phase === "failed"
                    ? uploadState.message
                    : "支持文案与文档（TXT / MD / CSV / PDF / Word）、图片素材（PNG / JPG / WEBP）、视频成片（MP4 / MOV）"}
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
          <p className="hint">
            提交后自动生成审查案件，审计结果将直接显示在本页下方。
          </p>
        </form>
      </div>

      {/* ── 第一层：真判定（有 case_id 才是真的）───────────────────────
           ★ 2026-10-28 改结构：改前这里是二选一（有 case_id 显示 CaseDetail，
             没有就显示本地预检），于是**两者永远不会同时出现**，
             而本地预检的措辞与真判定几乎一样（都叫「合规审计结果」）。
             结果：看的人以为预检就是判定。

             现在分成两层，标题就区分开：
               · 上：真判定（案件已建，来自后端）
               · 下：本地预检（**不是判定**，只做正则预筛，明确标注） */}
      {createdCaseId ? (
        <div className="panel" data-submission-receipt="">
          <div className="evidence__head">
            <h2 className="panel__title">判定结果 · 已立案</h2>
            <span className="font-data hint">案件号：{createdCaseId}</span>
            <Link to={`/cases/${encodeURIComponent(createdCaseId)}`} className="btn">
              独立页面打开 <Icon name="arrow-up-right" size={11} />
            </Link>
          </div>
          <CaseDetailPage embeddedCaseId={createdCaseId} />
        </div>
      ) : null}

      {submitErr && !createdCaseId ? (
        <div className="panel state state--error" role="alert">
          <h2 className="panel__title">提交未受理</h2>
          <p>
            {submitErr.status ? `HTTP ${submitErr.status} · ` : ""}
            {submitErr.message}
          </p>
          <p className="hint">
            下面显示的是**本地预检**结果（不是判定）。它不会进入案件库，
            也不代表任何正式结论。
          </p>
        </div>
      ) : null}

      {/* ── 第二层：本地预检 ──────────────────────────────────────────
           ★ 它必须**始终**看得出来不是判定：
             · 标题写「本地预检（不是判定）」；
             · 结论徽标旁边写明「仅供参考」。 */}
      {auditReport ? (
        <div
          className="panel panel--precheck"
          role="region"
          aria-label="本地预检结果（不是判定）"
          data-local-precheck=""
        >
          <div className="cases-page__head">
            <div>
              <h2 className="panel__title">
                本地预检（不是判定）
                <span className="hint audit-result__tag">
                  浏览器内 3 条正则粗筛，未经过后端规则引擎
                </span>
              </h2>
            </div>
          </div>

          <dl className="facts">
            <dt>送审文件 / 来源</dt>
            <dd>{auditReport.fileName ?? auditReport.channelLabel}</dd>
            <dt>产品线与阶段</dt>
            <dd>{auditReport.productLineLabel}（{auditReport.stageLabel}）</dd>
            <dt>预检命中</dt>
            <dd>
              <span className="hint">
                {auditReport.findings.length > 0
                  ? `粗筛命中 ${auditReport.findings.length} 处疑似风险表述`
                  : "未命中本地粗筛词表（不等于合规）"}
              </span>
            </dd>
          </dl>

          {auditReport.findings.length > 0 ? (
            <>
              <h3 className="audit-result__subhead">
                疑似风险提示（{auditReport.findings.length} 项）
              </h3>
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
                    <div className="evidence__quote">命中原句：「{f.quote}」</div>
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
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
