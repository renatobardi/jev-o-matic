import type { TriageResult } from "../lib/api";
import { int, pct } from "../lib/format";
import { DECISION, LANE, REASON } from "../lib/labels";

interface Props {
  pr: TriageResult["pr"];
  verdict: TriageResult["verdict"];
  simulated: boolean;
  cached: boolean;
  recorded: boolean;
}

/** Um card só, tingido pela cor da via: o PR à esquerda, o veredito à direita. */
export function VerdictBadge({ pr, verdict, simulated, cached, recorded }: Props) {
  const lane = LANE[verdict.lane];
  const reasons = verdict.reasons.filter((r) => r !== "uncertain_decisions");
  const escalated = verdict.escalated ?? [];
  const names = (keys: string[]) => keys.map((k) => DECISION[k] ?? k).join(", ");
  return (
    <section className={`card verdict lane-${verdict.lane}`} aria-label="Verdict">
      <div className="verdict-pr">
        <p className="meta">
          <a href={pr.html_url} target="_blank" rel="noreferrer">
            {pr.slug}
          </a>{" "}
          · {pr.author} · {pr.state}
          {pr.draft && " · draft"}
        </p>
        <h2>{pr.title}</h2>
        <p className="meta">
          {int(pr.changed_files)} {pr.changed_files === 1 ? "file" : "files"} · <span className="add">+{int(pr.additions)}</span>{" "}
          <span className="del">−{int(pr.deletions)}</span>
          {cached && " · cached result"}
          {recorded && " · recorded result of a real run"}
        </p>
      </div>
      <div className="verdict-lane">
        <p className="eyebrow">verdict · decided in code{simulated && " · simulation"}</p>
        <div className="lane-line">
          <h3>{lane.title}</h3>
          <span className="lane-blurb">{lane.blurb}</span>
        </div>
        {reasons.length > 0 && (
          <ul className="tags">
            {reasons.map((r) => (
              <li key={r}>{REASON[r] ?? r}</li>
            ))}
          </ul>
        )}
        {escalated.length > 0 && (
          <p className="verdict-note">
            <strong>Cascade:</strong> Jev was uncertain about {names(escalated)} and the LLM answered instead.
            {verdict.jev_lane && verdict.jev_lane !== verdict.lane
              ? ` With Jev alone, the lane would be “${LANE[verdict.jev_lane].title}”.`
              : " The lane did not change."}
          </p>
        )}
        {escalated.length === 0 && verdict.uncertain.length > 0 && (
          <p className="verdict-note">
            <strong>Uncertain:</strong> no confidence ≥ {pct(verdict.t)} on {names(verdict.uncertain)}. The lane stays on the
            safe side
            {simulated ? " — this is what the cascade would send to the LLM." : " (the LLM did not answer)."}
          </p>
        )}
      </div>
    </section>
  );
}
