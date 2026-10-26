import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, request } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import Button from "../ui/Button";
import Icon from "../ui/icon";

/**
 * 内容提交单（P-01 · Wave C 落 G-04 决策）。
 *
 * 1. 强制「内容阶段 / 产品线 / 入口渠道」三必填校验（PRD v2.0 §7.2）；
 * 2. 四维取值域严格对齐 `base/contract.py`；
 * 3. 选择 unsupported 通道（NAS / 上传文件 / 文档）或图片/视频浅档时，立即给出明确引导；
 * 4. 既可作为独立页 `/submit` 打开，也可在 `AppShell` 顶栏通过「+ 提交审查」抽屉唤起。
 */

const CONTENT_STAGES = [
  { value: "final_content", label: "发布前完整内容（final_content）" },
  { value: "brief", label: "简要 / 脚本方案（brief）" },
] as const;

const PRODUCT_LINES = [
  { value: "pump", label: "吸奶器（pump）" },
  { value: "wearable", label: "穿戴式吸奶器（wearable）" },
  { value: "feeding", label: "喂养 / 洗瓶机（feeding）" },
  { value: "skincare", label: "母婴护肤（skincare）" },
] as const;

const ENTRY_CHANNELS = [
  { value: "群消息", label: "飞书群消息", unsupported: false },
  { value: "飞书文档链接", label: "飞书云文档链接", unsupported: false },
  { value: "落地页 URL", label: "独立站 / 落地页 URL", unsupported: false },
  { value: "多维表批量", label: "飞书多维表批量", unsupported: false },
  { value: "NAS", label: "NAS 共享盘（阶段一暂不支持）", unsupported: true },
  { value: "上传文件", label: "直接上传文件（阶段一暂不支持）", unsupported: true },
] as const;

const SOURCE_KINDS = [
  { value: "free_text", contentType: "文本", label: "自由文本（free_text）", tier: "深档" },
  { value: "ad_text", contentType: "文本", label: "结构化广告语（Primary Text + Headline）", tier: "深档" },
  { value: "image", contentType: "图片", label: "图片素材（OCR + 视觉候选）", tier: "浅档" },
  { value: "video", contentType: "视频", label: "视频素材（ASR + 关键帧）", tier: "浅档" },
  { value: "文档", contentType: "文档", label: "Word / PDF 文档（阶段一未接）", tier: "未接" },
] as const;

export interface SubmitPageProps {
  embeddedInDrawer?: boolean;
  onCloseDrawer?: () => void;
}

export default function SubmitPage({
  embeddedInDrawer = false,
  onCloseDrawer,
}: SubmitPageProps = {}) {
  const [contentStage, setContentStage] = useState<string>("final_content");
  const [productLine, setProductLine] = useState<string>("pump");
  const [entryChannel, setEntryChannel] = useState<string>("群消息");
  const [sourceKind, setSourceKind] = useState<string>("free_text");
  const [text, setText] = useState<string>("");
  const [primaryText, setPrimaryText] = useState<string>("");
  const [headline, setHeadline] = useState<string>("");
  const [uri, setUri] = useState<string>("inline:web-submit");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<Record<string, unknown> | null>(null);
  const [submitErr, setSubmitErr] = useState<{
    status: number;
    message: string;
  } | null>(null);

  const selectedSource =
    SOURCE_KINDS.find((k) => k.value === sourceKind) ?? SOURCE_KINDS[0];
  const selectedChannel =
    ENTRY_CHANNELS.find((c) => c.value === entryChannel) ?? ENTRY_CHANNELS[0];
  const isUnsupported =
    selectedChannel.unsupported ||
    sourceKind === "文档" ||
    (sourceKind !== "free_text" && sourceKind !== "ad_text");

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setReceipt(null);
    setSubmitErr(null);

    const submissionId = `sub-${crypto.randomUUID().slice(0, 12)}`;
    const payload: Record<string, unknown> = {
      submission_id: submissionId,
      content_type: selectedSource.contentType,
      content_stage: contentStage,
      entry_channel: entryChannel,
      source: { kind: sourceKind },
      product_line: productLine,
      uri: uri.trim() || "inline:web-submit",
    };

    if (sourceKind === "free_text") {
      payload.text = text;
    } else if (sourceKind === "ad_text") {
      payload.fields = {
        "Primary Text": primaryText,
        Headline: headline,
      };
    } else {
      payload.text = text;
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

  const HeadingTag = embeddedInDrawer ? "h2" : "h1";

  return (
    <section
      className={embeddedInDrawer ? "submit-drawer-body" : "cases-page"}
      aria-labelledby="submit-page-title"
    >
      <div className="cases-page__head">
        <div>
          <HeadingTag id="submit-page-title">提交内容审查</HeadingTag>
          <p className="hint">内容阶段、产品线、入口渠道为必填。</p>
        </div>
        {embeddedInDrawer && onCloseDrawer && (
          <Button variant="secondary" onClick={onCloseDrawer}>
            关闭抽屉
          </Button>
        )}
      </div>

      <div className="panel">
        <h2 className="panel__title">提交单</h2>
      <form className="submit-form" onSubmit={(e) => void handleSubmit(e)}>
        <div className="submit-grid">
          <div>
            <label htmlFor="submit-stage">1. 内容阶段（必填）</label>
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
            <label htmlFor="submit-line">2. 产品线（必填）</label>
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
            <label htmlFor="submit-channel">3. 入口渠道（必填）</label>
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
            <label htmlFor="submit-kind">4. 载体形态（source.kind）</label>
            <select
              id="submit-kind"
              value={sourceKind}
              onChange={(e) => setSourceKind(e.target.value)}
            >
              {SOURCE_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}（{k.tier}）
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* 浅档与 unsupported 显式预警（PRD v2.0 §6.3 / §8.4） */}
        {selectedSource.tier === "浅档" && (
          <div className="state state--warn" role="note">
            <StatusBadge axis="coverage" value="partial" />{" "}
            <strong>浅档审查声明</strong>：图片与视频在第一阶段仅覆盖 OCR/ASR 提取文本，
            <strong>不做区域级像素审计或画面构图判断</strong>，产出结论必带{" "}
            <code>coverage=partial</code> 声明且永不直接输出裸 PASS。
          </div>
        )}

        {isUnsupported && (
          <div className="state state--warn" role="note">
            <strong>通道或载体受限提示</strong>：当前所选通道/载体在{" "}
            <code>submission_router</code> 或在线入库服务中登记为{" "}
            <code>rejected_unsupported</code>（不会静默成功或丢弃，提交后将返回明确拒绝原因）。
          </div>
        )}

        <div className="submit-field">
          <label htmlFor="submit-uri">来源定位符（source.uri）</label>
          <input
            id="submit-uri"
            type="text"
            value={uri}
            onChange={(e) => setUri(e.target.value)}
            placeholder="例如 https://momcozy.com/products/... 或 inline:web-submit"
          />
        </div>

        {sourceKind === "ad_text" ? (
          <div className="submit-grid">
            <div>
              <label htmlFor="submit-pt">Primary Text（主广告语）</label>
              <textarea
                id="submit-pt"
                value={primaryText}
                onChange={(e) => setPrimaryText(e.target.value)}
                placeholder="输入广告主文案（将按 fields-pipe-v1 规范以 ' | ' 拼接）…"
              />
            </div>
            <div>
              <label htmlFor="submit-hl">Headline（标题）</label>
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
              待审正文内容（当前 {text.length} 字符）
            </label>
            <textarea
              id="submit-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="粘贴待审查的完整发布前文案内容…"
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
                : !text.trim())
            }
          >
            <Icon name="plus" size={12} />{" "}
            {busy ? "提交并执行预审中…" : "提交审查单"}
          </Button>
        </div>
      </form>
      </div>

      {submitErr && (
        <div className="state state--error" role="alert">
          <h2>
            提交未通过（HTTP {submitErr.status || "网络异常"}）
          </h2>
          <p>{submitErr.message}</p>
          {submitErr.status === 501 && (
            <p className="hint">当前环境未开放提交写入。</p>
          )}
        </div>
      )}

      {receipt && (
        <div className="state" role="status" data-submission-receipt="">
          <h2>受理回执（Submission Receipt）</h2>
          <dl className="facts">
            <dt>submission_id</dt>
            <dd className="font-data">{String(receipt.submission_id ?? "未测")}</dd>
            <dt>case_id</dt>
            <dd className="font-data">
              {receipt.case_id ? (
                <Link
                  to={`/cases/${encodeURIComponent(String(receipt.case_id))}`}
                  onClick={onCloseDrawer}
                >
                  {String(receipt.case_id)}
                </Link>
              ) : (
                "未建案"
              )}
            </dd>
            <dt>ir_id</dt>
            <dd className="font-data">{String(receipt.ir_id ?? "未测")}</dd>
            <dt>机器预审标签</dt>
            <dd>
              <StatusBadge
                axis="decision"
                value={
                  receipt.decision &&
                  typeof receipt.decision === "object" &&
                  "state" in receipt.decision
                    ? String((receipt.decision as { state?: string }).state)
                    : undefined
                }
              />
            </dd>
          </dl>
        </div>
      )}
    </section>
  );
}
