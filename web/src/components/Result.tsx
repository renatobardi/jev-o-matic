import { useMemo, useState } from "react";
import type { Decision, TriageResult } from "../lib/api";
import { int } from "../lib/format";
import { verdict as localVerdict, runtimeFiles } from "../lib/verdict";
import { DecisionList } from "./DecisionList";
import { SentPanel } from "./SentPanel";
import { ThresholdSlider } from "./ThresholdSlider";
import { Trace } from "./Trace";
import { VerdictBadge } from "./VerdictBadge";

/** As respostas do jev, desfazendo o que o LLM substituiu. */
function jevOnly(decisions: Record<string, Decision>): Record<string, Decision> {
  return Object.fromEntries(
    Object.entries(decisions).map(([k, d]) => [k, d.original ? { ...d, ...d.original, source: "jev" as const, rationale: null, original: null } : d]),
  );
}

export function Result({ result }: { result: TriageResult }) {
  const { pr } = result;
  const serverT = result.verdict.t;
  const [t, setT] = useState(serverT);
  const jev = useMemo(() => jevOnly(result.decisions), [result.decisions]);
  const runtime = runtimeFiles(result.categories);
  const local = useMemo(() => localVerdict(jev, pr.changed_files, t, runtime), [jev, pr.changed_files, t, runtime]);
  const simulated = t !== serverT;

  return (
    <article className="result">
      <header className="card pr-head">
        <p className="meta">
          <a href={pr.html_url} target="_blank" rel="noreferrer">
            {pr.slug}
          </a>{" "}
          · {pr.author} · {pr.state}
          {pr.draft && " · draft"}
        </p>
        <h2>{pr.title}</h2>
        <p className="meta">
          {int(pr.changed_files)} {pr.changed_files === 1 ? "arquivo" : "arquivos"} ·{" "}
          <span className="add">+{int(pr.additions)}</span> <span className="del">−{int(pr.deletions)}</span>
          {result.cached && " · resultado em cache"}
        </p>
      </header>

      <VerdictBadge
        verdict={simulated ? { ...local, escalated: [], jev_lane: null } : result.verdict}
        simulated={simulated}
      />
      <ThresholdSlider t={t} serverT={serverT} wouldEscalate={local.uncertain.length} onChange={setT} />
      <DecisionList decisions={simulated ? jev : result.decisions} verdict={simulated ? local : result.verdict} />
      <Trace trace={result.trace} />
      <SentPanel sent={result.sent} />
    </article>
  );
}
