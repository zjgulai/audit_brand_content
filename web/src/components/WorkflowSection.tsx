import type { IntentInference, JudgmentReceipt, WorkflowTiming } from "../api/client";

/**
 * 工作流读数（2026-10-28）：耗时 / 阶段推断 / 执行回执。
 *
 * ## 为什么这三件事放一起
 *
 * 它们回答同一个问题：**这份判定是怎么产出的**。
 * 审核员看到「REVIEW」之后，下一个问题通常是「机器到底做了什么」——
 * 而这三条正是那个问题的三个面：跑了多久、阶段是不是猜的、用了哪几个 skill。
 *
 * ## ★ 三态必须在界面上分得开
 *
 * `workflow_timing` 的 `null`、`intent_inference` 的 `untested`、
 * 以及整块 `receipt` 缺失 —— 这三种「没有」的意思完全不同：
 *
 * | 界面要说的 | 实际含义 |
 * |---|---|
 * | 「未测」 | 有这一步，但没采到读数 |
 * | 「已声明」 | 调用方明确给了阶段，无需推断 |
 * | 「未留回执」 | 这个案件是旧版本产生的，那时还没写回执 |
 *
 * 全都渲染成一句话「暂无数据」会把三者混成一个 —— 而它们的处理方式不同：
 * 第一种要查采集，第二种什么都不用做，第三种不用管。
 */

/** 毫秒读数的显示口径。★ `null` 不渲染成 `0ms`。 */
function ms(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "未测";
  if (value < 1) return "<1 ms";
  if (value < 1000) return `${value.toFixed(1)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

const STAGE_LABEL: Record<string, string> = {
  brief: "推广脚本 / 提纲",
  final_content: "发布前成稿",
};

export interface WorkflowSectionProps {
  timing?: WorkflowTiming | null;
  inference?: IntentInference | null;
  receipt?: JudgmentReceipt | null;
}

export default function WorkflowSection({
  timing,
  inference,
  receipt,
}: WorkflowSectionProps) {
  // ★ 三块全空时不渲染整节：一则不占版面，二则「这一节存在但全是空」
  //   本身就是一句含混的话（见文件头那张表）。
  const hasAny = Boolean(timing || inference || receipt);
  if (!hasAny) return null;

  return (
    <>
      <h2>工作流</h2>

      {/* ── 耗时 ───────────────────────────────────────────────────── */}
      <dl className="facts" data-workflow-timing="">
        <dt>判定耗时</dt>
        <dd>
          {timing && timing.status === "ok" ? (
            <>
              <strong className="font-data">{ms(timing.total_ms)}</strong>
              <span className="hint">
                （{timing.step_count ?? 0} 步求和）
              </span>
            </>
          ) : timing ? (
            // ★ 有读数但是 untested：必须说「没测到」+ 原因，
            //   不许渲染成 0 —— 「没测」与「很快」长得一样是本项目的老病。
            <>
              <span className="badge badge--untested">未测</span>{" "}
              <span className="hint">{timing.reason || "没有可用的耗时读数"}</span>
            </>
          ) : (
            <span className="hint">这份案件没有耗时读数</span>
          )}
        </dd>

        {timing && timing.status === "ok" && (timing.slowest ?? []).length > 0 ? (
          <>
            <dt>最慢的几步</dt>
            <dd>
              <ul className="workflow-steps">
                {(timing.slowest ?? []).map((s) => (
                  <li key={s.name}>
                    <span>{s.name}</span>
                    <span className="font-data">{ms(s.duration_ms)}</span>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        ) : null}
      </dl>

      {/* ── 阶段推断 ────────────────────────────────────────────────── */}
      {inference ? (
        <dl className="facts" data-intent-inference="">
          <dt>内容阶段</dt>
          <dd>
            {inference.status === "inferred" ? (
              <>
                <span className="badge badge--pending">推断</span>{" "}
                <strong>{STAGE_LABEL[String(inference.value)] ?? inference.value}</strong>
                {inference.confidence === "low" ? (
                  <span className="hint">（置信度低：只命中一条信号）</span>
                ) : null}
              </>
            ) : inference.status === "absent" ? (
              <>
                <strong>
                  {STAGE_LABEL[String(inference.declared)] ?? inference.declared ?? "已声明"}
                </strong>{" "}
                <span className="hint">（调用方申报，未推断）</span>
              </>
            ) : (
              <>
                <span className="badge badge--untested">未能判断</span>{" "}
                <span className="hint">{inference.reason || "没有可推断的信号"}</span>
              </>
            )}
          </dd>
          {inference.status === "inferred" && (inference.evidence ?? []).length > 0 ? (
            <>
              <dt>推断依据</dt>
              <dd>
                <ul className="workflow-evidence">
                  {(inference.evidence ?? []).map((e, i) => (
                    <li key={`${e.hit}-${i}`}>
                      <span className="font-data">「{e.hit}」</span>
                      {e.why ? <span className="hint">{e.why}</span> : null}
                    </li>
                  ))}
                </ul>
              </dd>
            </>
          ) : null}
        </dl>
      ) : null}

      {/* ── 执行回执 ────────────────────────────────────────────────── */}
      <dl className="facts" data-workflow-receipt="">
        <dt>执行的 skill</dt>
        <dd className="font-data">
          {typeof receipt?.skill === "string" && receipt.skill.trim() ? (
            receipt.skill
          ) : (
            <span className="hint">未留回执</span>
          )}
        </dd>
        <dt>回执步骤</dt>
        <dd>
          {Array.isArray(receipt?.steps) && receipt.steps.length > 0 ? (
            <span className="font-data">{receipt.steps.length} 步已记录</span>
          ) : (
            <span className="hint">回执里没有步骤明细</span>
          )}
        </dd>
      </dl>

      {/* ★ 关于「推断值今天不改变判定」——这句话必须出现在界面上。
          实测（tools/verify_intent_infer.py 的 G4）：36 条规则里
          content_stage 的消费计数是 0。也就是说这个推断目前只是**标注**，
          不参与任何判断。不说这一句，看到「推断：推广脚本」的人会以为
          判定标准跟着变了。 */}
      {inference && inference.status === "inferred" ? (
        <p className="hint workflow-note">
          阶段推断只是标注：当前规则集**没有任何规则消费它**，不改变判定结论。
        </p>
      ) : null}
    </>
  );
}
