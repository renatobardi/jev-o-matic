import type { TriageResult } from "../lib/api";

export function Footer({ versions }: { versions: TriageResult["versions"] | null }) {
  return (
    <footer className="footer">
      <a href="https://github.com/renatobardi/jev-o-matic" target="_blank" rel="noreferrer">
        github.com/renatobardi/jev-o-matic
      </a>
      {versions && (
        <span className="meta">
          questions {versions.questions} · {versions.jev_model}
          {versions.llm_model && ` · ${versions.llm_model}`} · api {versions.api}
        </span>
      )}
    </footer>
  );
}
