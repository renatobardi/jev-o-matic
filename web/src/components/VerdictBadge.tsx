import type { TriageResult } from "../lib/api";
import { DECISION, LANE, REASON } from "../lib/labels";

export function VerdictBadge({ verdict }: { verdict: TriageResult["verdict"] }) {
  const lane = LANE[verdict.lane];
  const reasons = verdict.reasons.filter((r) => r !== "uncertain_decisions");
  return (
    <section className={`card verdict lane-${verdict.lane}`} aria-label="Veredito">
      <p className="eyebrow">veredito · decidido em código</p>
      <h3>{lane.title}</h3>
      <p>{lane.blurb}</p>
      {reasons.length > 0 && (
        <ul className="tags">
          {reasons.map((r) => (
            <li key={r}>{REASON[r] ?? r}</li>
          ))}
        </ul>
      )}
      {verdict.uncertain.length > 0 && (
        <p className="uncertain-note">
          O jev não teve confiança ≥ {verdict.t.toLocaleString("pt-BR")} em:{" "}
          {verdict.uncertain.map((k) => DECISION[k] ?? k).join(", ")}. Por isso a via ficou no lado seguro — é o ponto em
          que a cascata chama o LLM.
        </p>
      )}
    </section>
  );
}
