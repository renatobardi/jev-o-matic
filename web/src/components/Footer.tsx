import type { TriageResult } from "../lib/api";

const GITHUB = "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z";
const LINKEDIN = "M14.8 0H1.2C.54 0 0 .53 0 1.18v13.64C0 15.47.54 16 1.2 16h13.6c.66 0 1.2-.53 1.2-1.18V1.18C16 .53 15.46 0 14.8 0zM4.75 13.63H2.37V6h2.38v7.63zM3.56 4.96a1.38 1.38 0 1 1 0-2.75 1.38 1.38 0 0 1 0 2.75zm10.07 8.67h-2.37V9.92c0-.88-.02-2.02-1.23-2.02-1.23 0-1.42.96-1.42 1.96v3.77H6.24V6h2.28v1.04h.03c.32-.6 1.09-1.23 2.25-1.23 2.4 0 2.85 1.58 2.85 3.64v4.18z";

function Icon({ d }: { d: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export function Footer({ versions }: { versions: TriageResult["versions"] | null }) {
  return (
    <footer className="footer">
      <div className="footer-links">
        <a href="https://github.com/renatobardi/jev-o-matic" target="_blank" rel="noreferrer">
          <Icon d={GITHUB} />
          github.com/renatobardi/jev-o-matic
        </a>
        <a href="https://www.linkedin.com/in/renatobardi" target="_blank" rel="noreferrer">
          <Icon d={LINKEDIN} />
          linkedin.com/in/renatobardi
        </a>
      </div>
      {versions && (
        <span className="meta">
          questions {versions.questions} · {versions.jev_model}
          {versions.llm_model && ` · ${versions.llm_model}`} · api {versions.api}
        </span>
      )}
    </footer>
  );
}
