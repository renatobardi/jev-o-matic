import { useMemo, useState } from "react";
import type { Decision, TriageResult } from "../lib/api";
import { verdict as localVerdict, runtimeFiles } from "../lib/verdict";
import { DecisionList } from "./DecisionList";
import { SentPanel } from "./SentPanel";
import { Trace } from "./Trace";
import { VerdictBadge } from "./VerdictBadge";

/** As respostas do jev, desfazendo o que o LLM substituiu. */
function jevOnly(decisions: Record<string, Decision>): Record<string, Decision> {
  return Object.fromEntries(
    Object.entries(decisions).map(([k, d]) => [k, d.original ? { ...d, ...d.original, source: "jev" as const, rationale: null, original: null } : d]),
  );
}

export function Result({ result, recorded = false }: { result: TriageResult; recorded?: boolean }) {
  const { pr } = result;
  const serverT = result.verdict.t;
  const [t, setT] = useState(serverT);
  const jev = useMemo(() => jevOnly(result.decisions), [result.decisions]);
  const runtime = runtimeFiles(result.categories);
  const local = useMemo(() => localVerdict(jev, pr.changed_files, t, runtime), [jev, pr.changed_files, t, runtime]);
  const simulated = t !== serverT;

  return (
    <article className="result">
      <VerdictBadge
        pr={pr}
        verdict={simulated ? { ...local, escalated: [], jev_lane: null } : result.verdict}
        simulated={simulated}
        cached={result.cached}
        recorded={recorded}
      />
      <div className="columns">
        <DecisionList
          decisions={simulated ? jev : result.decisions}
          verdict={simulated ? local : result.verdict}
          serverT={serverT}
          onThreshold={setT}
        />
        <aside className="side">
          <Trace trace={result.trace} />
          <SentPanel sent={result.sent} />
        </aside>
      </div>
    </article>
  );
}
