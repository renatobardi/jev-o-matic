import type { Decision } from "../lib/api";
import { decisionDetail, decisionValue, pct } from "../lib/format";
import { DECISION } from "../lib/labels";

interface Props {
  decisions: Record<string, Decision>;
  verdict: { uncertain: string[]; t: number };
}

export function DecisionList({ decisions, verdict }: Props) {
  return (
    <section className="card" aria-label="Decisões">
      <p className="eyebrow">decisões do jev · uma chamada, {Object.keys(decisions).length} perguntas</p>
      <ul className="decisions" data-list>
        {Object.entries(decisions).map(([key, d]) => {
          const label = DECISION[key] ?? key;
          if (d.source === "llm" && d.original) {
            const was: Decision = { ...d, ...d.original, source: "jev" };
            return (
              <li key={key} className="decision is-llm" data-row>
                <div className="decision-main">
                  <span className="decision-label">{label}</span>
                  <span className="decision-value">
                    {decisionValue(key, d)} <span className="badge">LLM</span>
                  </span>
                </div>
                {d.rationale && <p className="rationale">{d.rationale}</p>}
                <div className="decision-meta meta">
                  <span>
                    o jev tinha dito “{decisionValue(key, was)}” com confiança {pct(was.confidence)}
                  </span>
                  <span>{decisionDetail(was)}</span>
                </div>
              </li>
            );
          }
          const uncertain = verdict.uncertain.includes(key);
          const low = d.confidence < verdict.t;
          return (
            <li key={key} className={uncertain ? "decision is-uncertain" : "decision"} data-row>
              <div className="decision-main">
                <span className="decision-label">{label}</span>
                <span className="decision-value">{decisionValue(key, d)}</span>
              </div>
              <div
                className={low ? "bar is-low" : "bar"}
                role="meter"
                aria-label={`Confiança em ${label}`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(d.confidence * 100)}
              >
                <span className="bar-fill" style={{ width: pct(d.confidence) }} />
                <span className="bar-mark" style={{ left: pct(verdict.t) }} aria-hidden="true" />
              </div>
              <div className="decision-meta meta">
                <span>
                  confiança {pct(d.confidence)}
                  {uncertain && " · incerta"}
                </span>
                <span>{decisionDetail(d)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="meta legend">
        A marca na barra é o threshold ({pct(verdict.t)}). Barra laranja: abaixo dele, a decisão não define a via. “Incerta”: além
        disso, ela ainda poderia mudar a via — é o que a cascata manda pro LLM.
      </p>
    </section>
  );
}
