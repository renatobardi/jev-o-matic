import type { TriageResult } from "../lib/api";
import { DECISION, LANE, REASON } from "../lib/labels";

export function VerdictBadge({ verdict, simulated }: { verdict: TriageResult["verdict"]; simulated: boolean }) {
  const lane = LANE[verdict.lane];
  const reasons = verdict.reasons.filter((r) => r !== "uncertain_decisions");
  const escalated = verdict.escalated ?? [];
  const names = (keys: string[]) => keys.map((k) => DECISION[k] ?? k).join(", ");
  return (
    <section className={`card verdict lane-${verdict.lane}`} aria-label="Veredito">
      <p className="eyebrow">veredito · decidido em código{simulated && " · simulação"}</p>
      <h3>{lane.title}</h3>
      <p>{lane.blurb}</p>
      {reasons.length > 0 && (
        <ul className="tags">
          {reasons.map((r) => (
            <li key={r}>{REASON[r] ?? r}</li>
          ))}
        </ul>
      )}
      {escalated.length > 0 && (
        <p className="uncertain-note">
          <strong>Cascata:</strong> o jev ficou incerto em {names(escalated)} e o LLM respondeu no lugar.
          {verdict.jev_lane && verdict.jev_lane !== verdict.lane
            ? ` Só com o jev, a via seria “${LANE[verdict.jev_lane].title}”.`
            : " A via não mudou."}
        </p>
      )}
      {verdict.uncertain.length > 0 && (
        <p className="uncertain-note">
          Sem confiança ≥ {verdict.t.toLocaleString("pt-BR")} em: {names(verdict.uncertain)}. A via fica no lado seguro
          {simulated ? " — é o que a cascata mandaria pro LLM." : " (o LLM não respondeu)."}
        </p>
      )}
    </section>
  );
}
