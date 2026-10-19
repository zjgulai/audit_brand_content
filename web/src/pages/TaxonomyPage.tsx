import { useState, type FormEvent } from "react";
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
  boundary_counterexample: Counterexample;
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

type Taxonomy = {
  meta: {
    version: string;
    status: string;
    source: string | null;
    note: string;
  };
  axes: Axis[];
  decision_tree: TreeStep[];
  orthogonal_fields: Record<string, ValueField>;
  rule_examples: RuleExample[];
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

export default function TaxonomyPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<RuleExample | "not_found" | null>(null);
  const steps = [...taxonomy.decision_tree].sort((a, b) => a.step - b.step);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = query.trim();
    if (!id) {
      setResult(null);
      return;
    }
    setResult(
      taxonomy.rule_examples.find((item) => item.rule_id === id) ?? "not_found",
    );
  }

  return (
    <section aria-labelledby="taxonomy-title">
      <h1 id="taxonomy-title">分类规范</h1>
      <p className="hint">
        只读浏览页。当前为页面骨架，轴定义、判定条件、复核人与反例待规范文档落盘后填充；
        数据源：<code>web/src/data/taxonomy.json</code>（{taxonomy.meta.version} ·{" "}
        {taxonomy.meta.status}）。
      </p>
      <p className="hint">{taxonomy.meta.note}</p>

      <h2>七轴卡片</h2>
      <div className="taxonomy-grid">
        {taxonomy.axes.map((axis) => (
          <article
            className="taxonomy-card"
            key={axis.code}
            aria-labelledby={`axis-${axis.code}`}
          >
            <h3 id={`axis-${axis.code}`}>
              <code>{axis.code}</code> · {axis.name}
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
                {axis.boundary_counterexample.rule_id ? (
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
        {steps.map((step) => (
          <li className="taxonomy-flow__step" key={step.axis}>
            <span className="taxonomy-flow__index">第 {step.step} 步</span>
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
                          ? `${field.expected_count} 个值 · ${PENDING}`
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
        <button type="submit">查找</button>
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
      <p className="hint">
        本页只读：不连接后端、不写数据；归属理由以规范文档落盘后的静态 JSON 为准。
      </p>
    </section>
  );
}
