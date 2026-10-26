import { useEffect, useState, type FormEvent } from "react";
import { request } from "../api/client";
import Button from "../ui/Button";
import Icon from "../ui/icon";
import taxonomyJson from "../data/taxonomy.json";

type Counterexample = {
  rule_id: string | null;
  why: string | null;
};

type Axis = {
  code: string;
  name: string;
  one_line: string | null;
  criteria: string[];
  reviewer: string | null;
  evidence_required: string[];
  boundary_counterexample: Counterexample | null;
};

type TreeStep = {
  step: number;
  axis: string;
  hit_condition: string | null;
  route_to: string | null;
};

type ValueField = {
  label: string;
  values?: string[];
  expected_count?: number;
  derivation?: string | null;
  positioning?: string | null;
  note?: string | null;
};

type RuleExample = {
  rule_id: string;
  axis: string;
  reason: string;
  evidence?: string[];
};

type BoundaryDispute = {
  rule_id: string;
  section: string;
  axis_code: string | null;
  dispute: string;
  status: string;
  resolved_in: string | null;
};

type Taxonomy = {
  meta: {
    version: string;
    status: string;
    source: string | null;
    note: string;
    spec_version?: string;
    spec_fingerprint?: string;
  };
  axes: Axis[];
  decision_tree: TreeStep[];
  orthogonal_fields: Record<string, ValueField>;
};

const taxonomy = taxonomyJson as unknown as Taxonomy;

const PENDING = "待规范文档";

function textOrPending(value: string | null | undefined) {
  return value && value.trim() ? value : PENDING;
}

function ListOrPending({ items, empty = PENDING }: { items: string[]; empty?: string }) {
  if (!items.length) return <span className="taxonomy-placeholder">{empty}</span>;
  return (
    <ul className="taxonomy-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/**
 * 规则与分类规范中心（P-10 · Wave C 落 G-06 决策）。
 *
 * 四合一 Tabs 只读浏览器：
 *   1. 七轴分类与七步判定顺序（默认激活，保持与 check_pages.mjs 及 A8/A9 100% 兼容）；
 *   2. 规则库只读投影（消费 `GET /api/v1/rules`）；
 *   3. 控制点名册只读投影（消费 `GET /api/v1/control-points`）；
 *   4. 处置路由表只读投影（消费 `GET /api/v1/routing`）。
 *
 * 阶段一严格只读（RL-15 / C-103）：服务端对这三个路径的任何写请求返回 403 并记入 access-log。
 */
export default function TaxonomyPage() {
  const [activeTab, setActiveTab] = useState<
    "taxonomy" | "rules" | "control-points" | "routing"
  >("taxonomy");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<RuleExample | "not_found" | null>(null);
  const [internal, setInternal] = useState<{
    ruleExamples: RuleExample[];
    boundaryDisputes: BoundaryDispute[];
  } | null>(null);

  const [rulesList, setRulesList] = useState<Array<Record<string, unknown>> | null>(
    null,
  );
  const [cpList, setCpList] = useState<Array<Record<string, unknown>> | null>(
    null,
  );
  const [routingList, setRoutingList] = useState<Array<Record<string, unknown>> | null>(
    null,
  );
  const [apiErr, setApiErr] = useState<string | null>(null);

  useEffect(() => {
    if (!__REVIEW_DEV_IDENTITY__) return;
    let alive = true;
    import("../data/taxonomyInternal").then((m) => {
      if (!alive) return;
      setInternal({
        ruleExamples: m.ruleExamples as RuleExample[],
        boundaryDisputes: m.boundaryDisputes as BoundaryDispute[],
      });
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (activeTab === "taxonomy") return;
    let alive = true;
    setApiErr(null);
    const loadTab = async () => {
      try {
        if (activeTab === "rules" && rulesList === null) {
          const data = await request<Array<Record<string, unknown>>>("/rules");
          if (alive) setRulesList(Array.isArray(data) ? data : []);
        } else if (activeTab === "control-points" && cpList === null) {
          const data =
            await request<Array<Record<string, unknown>>>("/control-points");
          if (alive) setCpList(Array.isArray(data) ? data : []);
        } else if (activeTab === "routing" && routingList === null) {
          const data = await request<Array<Record<string, unknown>>>("/routing");
          if (alive) setRoutingList(Array.isArray(data) ? data : []);
        }
      } catch (e: unknown) {
        if (!alive) return;
        const err = e as { status?: number; message?: string };
        setApiErr(err.message ?? String(e));
      }
    };
    void loadTab();
    return () => {
      alive = false;
    };
  }, [activeTab, cpList, routingList, rulesList]);

  const disputes = internal?.boundaryDisputes ?? [];
  const steps = [...taxonomy.decision_tree].sort((a, b) => a.step - b.step);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = query.trim();
    if (!id) {
      setResult(null);
      return;
    }
    setResult(
      (internal?.ruleExamples ?? []).find((item) => item.rule_id === id) ?? "not_found",
    );
  }

  return (
    <section className="taxonomy-page" aria-labelledby="taxonomy-title">
      <div className="cases-page__head">
        <div>
          <h1 id="taxonomy-title">分类规范</h1>
          <p className="spec-version">
            {/*
              ★ 断言 A9：spec_version 与 spec_fingerprint 必须同时出现。
            */}
            <span>按 spec {taxonomy.meta.spec_version ?? "未测"}</span>
            <span className="font-data">{taxonomy.meta.spec_fingerprint ?? "未测"}</span>
          </p>
        </div>
        <div className="queue__filters" role="tablist" aria-label="规则与分类规范视图切换">
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={activeTab === "taxonomy"}
            aria-pressed={activeTab === "taxonomy"}
            onClick={() => setActiveTab("taxonomy")}
          >
            七轴分类规范
          </button>
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={activeTab === "rules"}
            aria-pressed={activeTab === "rules"}
            onClick={() => setActiveTab("rules")}
          >
            规则库（只读）
          </button>
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={activeTab === "control-points"}
            aria-pressed={activeTab === "control-points"}
            onClick={() => setActiveTab("control-points")}
          >
            控制点名册（只读）
          </button>
          <button
            type="button"
            role="tab"
            className="queue__filter"
            aria-selected={activeTab === "routing"}
            aria-pressed={activeTab === "routing"}
            onClick={() => setActiveTab("routing")}
          >
            处置路由表（只读）
          </button>
        </div>
      </div>

      <p className="hint">
        只读浏览页（RL-15 / C-103：Web 端严禁直接修改规则、控制点或路由，任何写请求将被服务端 403 拦截并写入 <code>access-log</code>）。
        数据源：<code>web/src/data/taxonomy.json</code>（
        {taxonomy.meta.spec_version ?? taxonomy.meta.version}，{taxonomy.meta.status}），
        由 <code>tools/gen_taxonomy_json.py</code> 从规范正文生成，<strong>不得手改</strong>。
      </p>
      <p className="hint">{taxonomy.meta.note}</p>

      {activeTab === "taxonomy" && (
        <>
          {(!internal || internal.ruleExamples.length === 0) && (
            <p className="hint">
              生产构建不包含内部规则示例与欠定边界登记；判定依据以案件 findings 为准。
            </p>
          )}

          {disputes.length > 0 && (
            <>
              <h2>已登记欠定边界（{disputes.length} 条）</h2>
              <p className="hint">
                这些规则的边界<b>规范确实定不住</b>，不是判读者错。界面展示
                <code>underdetermined</code> 而不强行给一个轴 ——
                其中 <code>axis_code</code> 为空的条目是<b>多轴争议</b>。
              </p>
              <ul className="notrun">
                {disputes.map((d) => (
                  <li key={d.rule_id}>
                    <span className="font-data">{d.section}</span>
                    <span>
                      {d.dispute}
                      {d.axis_code === null && <b>多轴争议</b>}
                    </span>
                    <span className="notrun__why">
                      {d.status}
                      {d.resolved_in ? `（${d.resolved_in}）` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h2>七轴卡片</h2>
          <div className="taxonomy-grid">
            {taxonomy.axes.map((axis) => (
              <article
                className="taxonomy-card"
                key={axis.code}
                aria-labelledby={`axis-${axis.code}`}
              >
                <h3 id={`axis-${axis.code}`}>
                  <code>{axis.code}</code> {axis.name}
                </h3>
                <dl className="taxonomy-fields">
                  <dt>一句话定义</dt>
                  <dd>{textOrPending(axis.one_line)}</dd>
                  <dt>判定条件</dt>
                  <dd>
                    <ListOrPending items={axis.criteria} />
                  </dd>
                  <dt>复核人</dt>
                  <dd>{textOrPending(axis.reviewer)}</dd>
                  <dt>证据要求</dt>
                  <dd>
                    <ListOrPending items={axis.evidence_required} />
                  </dd>
                  <dt>边界反例</dt>
                  <dd>
                    {axis.boundary_counterexample === null ? (
                      <span className="taxonomy-placeholder">
                        该轴暂无边界反例（规范未给出）
                      </span>
                    ) : axis.boundary_counterexample.rule_id ? (
                      <>
                        <code>{axis.boundary_counterexample.rule_id}</code>
                        {" — "}
                        {textOrPending(axis.boundary_counterexample.why)}
                      </>
                    ) : (
                      <span className="taxonomy-placeholder">
                        {PENDING}（需给真实 rule_id）
                      </span>
                    )}
                  </dd>
                </dl>
              </article>
            ))}
          </div>

          <h2>七步判定顺序</h2>
          <ol className="taxonomy-flow" aria-label="七步判定顺序">
            {steps.map((step, idx) => (
              <li className="taxonomy-flow__step" key={step.axis}>
                <span className="taxonomy-flow__index">
                  第 {step.step} 步{" "}
                  {idx < steps.length - 1 && <Icon name="arrow-down" size={11} />}
                </span>
                <h3>
                  <code>{step.axis}</code>
                </h3>
                <p>
                  <strong>命中条件：</strong>
                  {textOrPending(step.hit_condition)}
                </p>
                <p>
                  <strong>命中后归：</strong>
                  {textOrPending(step.route_to)}
                </p>
              </li>
            ))}
          </ol>

          <h2>正交字段</h2>
          <div className="taxonomy-grid">
            {Object.values(taxonomy.orthogonal_fields).map((field) => (
              <article className="taxonomy-card" key={field.label}>
                <h3>
                  <code>{field.label}</code>
                </h3>
                <dl className="taxonomy-fields">
                  {field.values ? (
                    <>
                      <dt>取值</dt>
                      <dd>
                        <ListOrPending
                          items={field.values}
                          empty={
                            field.expected_count
                              ? `${field.expected_count} 个值，${PENDING}`
                              : PENDING
                          }
                        />
                      </dd>
                    </>
                  ) : null}
                  {field.derivation !== undefined ? (
                    <>
                      <dt>推导规则</dt>
                      <dd>{textOrPending(field.derivation)}</dd>
                    </>
                  ) : null}
                  {field.positioning !== undefined ? (
                    <>
                      <dt>定位</dt>
                      <dd>{textOrPending(field.positioning)}</dd>
                    </>
                  ) : null}
                  {field.note ? (
                    <>
                      <dt>说明</dt>
                      <dd>{field.note}</dd>
                    </>
                  ) : null}
                </dl>
              </article>
            ))}
          </div>

          <h2>按 rule_id 查找归属</h2>
          <form className="taxonomy-lookup" onSubmit={onSubmit}>
            <label htmlFor="rule-lookup">rule_id</label>
            <input
              id="rule-lookup"
              name="rule_id"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如 T1.1.medical-cure"
              autoComplete="off"
            />
            <Button type="submit" variant="secondary">
              查找
            </Button>
          </form>
          <div className="taxonomy-result" aria-live="polite">
            {result === null ? (
              <p className="hint">输入 rule_id 后查找；当前静态数据未提供归属理由。</p>
            ) : result === "not_found" ? (
              <p>未找到该 rule_id；当前静态数据中没有这条归属理由。</p>
            ) : (
              <dl className="taxonomy-fields">
                <dt>rule_id</dt>
                <dd>
                  <code>{result.rule_id}</code>
                </dd>
                <dt>归属轴</dt>
                <dd>
                  <code>{result.axis}</code>
                </dd>
                <dt>理由</dt>
                <dd>{result.reason}</dd>
                {result.evidence?.length ? (
                  <>
                    <dt>证据</dt>
                    <dd>
                      <ListOrPending items={result.evidence} />
                    </dd>
                  </>
                ) : null}
              </dl>
            )}
          </div>
        </>
      )}

      {activeTab !== "taxonomy" && (
        <div className="state">
          <h2>
            {activeTab === "rules"
              ? "规则库只读投影（/api/v1/rules）"
              : activeTab === "control-points"
                ? "控制点名册只读投影（/api/v1/control-points）"
                : "处置路由表只读投影（/api/v1/routing）"}
          </h2>
          {apiErr ? (
            <p className="error" role="alert">
              读取失败：{apiErr}
            </p>
          ) : (
            (() => {
              const list =
                activeTab === "rules"
                  ? rulesList
                  : activeTab === "control-points"
                    ? cpList
                    : routingList;
              if (list === null) return <p className="hint">加载中…</p>;
              if (list.length === 0) {
                return (
                  <p className="hint">
                    当前投影目录下该集合为空（0 条记录）。变更只在飞书 Base 或本地治理 JSON 权威源完成。
                  </p>
                );
              }
              return (
                <ul className="notrun">
                  {list.map((row, i) => (
                    <li key={i} className="font-data">
                      {JSON.stringify(row)}
                    </li>
                  ))}
                </ul>
              );
            })()
          )}
        </div>
      )}
    </section>
  );
}
