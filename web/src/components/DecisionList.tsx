import type { TriageResult } from "../lib/api";
import { decisionDetail, decisionValue, pct } from "../lib/format";
import { DECISION } from "../lib/labels";

export function DecisionList({ decisions, verdict }: Pick<TriageResult, "decisions" | "verdict">) {
  return (
    <section className="card" aria-label="Decisões do jev">
      <p className="eyebrow">decisões do jev · uma chamada, {Object.keys(decisions).length} perguntas</p>
      <ul className="decisions" data-list>
        {Object.entries(decisions).map(([key, d]) => {
          const uncertain = verdict.uncertain.includes(key);
          const low = d.confidence < verdict.t;
          return (
            <li key={key} className={uncertain ? "decision is-uncertain" : "decision"} data-row>
              <div className="decision-main">
                <span className="decision-label">{DECISION[key] ?? key}</span>
                <span className="decision-value">{decisionValue(key, d)}</span>
              </div>
              <div
                className={low ? "bar is-low" : "bar"}
                role="meter"
                aria-label={`Confiança em ${DECISION[key] ?? key}`}
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
                  {d.source === "llm" && " · respondida pelo LLM"}
                </span>
                <span>{decisionDetail(d)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="meta legend">A marca na barra é o threshold ({pct(verdict.t)}). Barra laranja: abaixo dele, a decisão não define a via. “Incerta”: além
        disso, ela ainda poderia mudar a via — é o que a cascata manda pro LLM.</p>
    </section>
  );
}
