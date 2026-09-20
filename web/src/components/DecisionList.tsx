import type { Decision } from "../lib/api";
import { decisionDetail, decisionValue, pct } from "../lib/format";
import { DECISION } from "../lib/labels";
import { ThresholdSlider } from "./ThresholdSlider";

interface Props {
  decisions: Record<string, Decision>;
  verdict: { uncertain: string[]; t: number };
  serverT: number;
  onThreshold: (t: number) => void;
}

function LlmRow({ label, name, d }: { label: string; name: string; d: Decision }) {
  const was: Decision = { ...d, ...d.original, source: "jev" };
  return (
    <li className="decision is-llm" data-row>
      <div className="decision-main">
        <span className="decision-label">{label}</span>
        <span className="decision-value">
          {decisionValue(name, d)} <span className="badge badge-llm">LLM</span>
        </span>
      </div>
      <p className="rationale">
        <s>Jev: {decisionValue(name, was)}</s> at {pct(was.confidence)} confidence{d.rationale && ` · ${d.rationale}`}
      </p>
    </li>
  );
}

function JevRow({ label, name, d, t, uncertain }: { label: string; name: string; d: Decision; t: number; uncertain: boolean }) {
  const low = d.confidence < t;
  return (
    <li className={uncertain ? "decision is-uncertain" : "decision"} data-row>
      <div className="decision-main">
        <span className="decision-label">{label}</span>
        <span className="decision-value">
          {decisionValue(name, d)} {uncertain && <span className="badge badge-escalate">→ LLM</span>}
        </span>
      </div>
      <div
        className={low ? "bar is-low" : "bar"}
        role="meter"
        aria-label={`Confidence in ${label}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(d.confidence * 100)}
      >
        <span className="bar-fill" style={{ width: pct(d.confidence) }} />
        <span className="bar-mark" style={{ left: pct(t) }} aria-hidden="true" />
      </div>
      <div className="decision-meta meta">
        <span>
          confidence <span className={low ? "conf is-low" : "conf"}>{pct(d.confidence)}</span>
        </span>
        <span>{decisionDetail(d)}</span>
      </div>
    </li>
  );
}

export function DecisionList({ decisions, verdict, serverT, onThreshold }: Props) {
  const simulated = verdict.t !== serverT;
  const n = verdict.uncertain.length;
  return (
    <section className="card decisions-card" aria-label="Decisions">
      <div className="decisions-head">
        <p className="eyebrow">Jev decisions · one call, {Object.keys(decisions).length} questions</p>
        <ThresholdSlider t={verdict.t} onChange={onThreshold} />
      </div>
      <ul className="decisions" data-list>
        {Object.entries(decisions).map(([key, d]) => {
          const label = DECISION[key] ?? key;
          return d.source === "llm" && d.original ? (
            <LlmRow key={key} label={label} name={key} d={d} />
          ) : (
            <JevRow key={key} label={label} name={key} d={d} t={verdict.t} uncertain={verdict.uncertain.includes(key)} />
          );
        })}
      </ul>
      <p className="meta legend">
        {simulated ? (
          <>
            Simulation with the Jev answers only.{" "}
            {n > 0
              ? `At ${pct(verdict.t)}, ${n} ${n === 1 ? "decision" : "decisions"} would go to the LLM.`
              : `At ${pct(verdict.t)}, the LLM would not be called.`}{" "}
            <button type="button" className="link" onClick={() => onThreshold(serverT)}>
              back to the real result ({pct(serverT)})
            </button>
          </>
        ) : (
          <>
            The mark is the threshold ({pct(verdict.t)}). Amber: below it, the decision does not set the lane. “→ LLM”: it
            could still change the lane — that is what the cascade escalates. Drag the threshold to watch the funnel change,
            no new call.
          </>
        )}
      </p>
    </section>
  );
}
