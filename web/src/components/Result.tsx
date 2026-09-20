import type { TriageResult } from "../lib/api";
import { int } from "../lib/format";
import { DecisionList } from "./DecisionList";
import { SentPanel } from "./SentPanel";
import { Trace } from "./Trace";
import { VerdictBadge } from "./VerdictBadge";

export function Result({ result }: { result: TriageResult }) {
  const { pr } = result;
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

      <VerdictBadge verdict={result.verdict} />
      <DecisionList decisions={result.decisions} verdict={result.verdict} />
      <Trace trace={result.trace} />
      <SentPanel sent={result.sent} />
    </article>
  );
}
