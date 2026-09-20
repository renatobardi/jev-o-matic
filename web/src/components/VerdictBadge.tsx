import type { TriageResult } from "../lib/api";
import { DECISION, LANE, REASON } from "../lib/labels";

export function VerdictBadge({ verdict, simulated }: { verdict: TriageResult["verdict"]; simulated: boolean }) {
  const lane = LANE[verdict.lane];
  const reasons = verdict.reasons.filter((r) => r !== "uncertain_decisions");
  const escalated = verdict.escalated ?? [];
  const names = (keys: string[]) => keys.map((k) => DECISION[k] ?? k).join(", ");
  return (
    <section className={`card verdict lane-${verdict.lane}`} aria-label="Verdict">
      <p className="eyebrow">verdict · decided in code{simulated && " · simulation"}</p>
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
          <strong>Cascade:</strong> jev was uncertain about {names(escalated)} and the LLM answered instead.
          {verdict.jev_lane && verdict.jev_lane !== verdict.lane
            ? ` With jev alone, the lane would be “${LANE[verdict.jev_lane].title}”.`
            : " The lane did not change."}
        </p>
      )}
      {verdict.uncertain.length > 0 && (
        <p className="uncertain-note">
          No confidence ≥ {verdict.t.toLocaleString("en-US")} on: {names(verdict.uncertain)}. The lane stays on the safe side
          {simulated ? " — this is what the cascade would send to the LLM." : " (the LLM did not answer)."}
        </p>
      )}
    </section>
  );
}
