import type { TriageResult } from "../lib/api";
import { int } from "../lib/format";
import { OMIT_REASON } from "../lib/labels";

export function SentPanel({ sent }: { sent: TriageResult["sent"] }) {
  const partial = sent.files_omitted.length > 0 || sent.files_truncated.length > 0 || sent.body_truncated;
  return (
    <details className="card sent">
      <summary>
        <span className="eyebrow">o que foi enviado ao jev</span>
        <span className="meta">
          ~{int(sent.tokens_est)} tokens · {sent.files_included.length} de {int(sent.files_total)}{" "}
          {sent.files_total === 1 ? "arquivo" : "arquivos"}
          {partial && " · visão parcial"}
        </span>
      </summary>
      <p className="meta">
        Orçamento de {int(sent.budget_tokens)} tokens pro diff. Os patches entram por ordem de risco do caminho; o veredito
        vale só pro que o modelo viu.
      </p>
      {sent.body_truncated && <p className="meta">A descrição do PR foi truncada.</p>}
      <FileList title="Incluídos" files={sent.files_included.map((p) => ({ path: p, note: sent.files_truncated.includes(p) ? "truncado" : "" }))} />
      <FileList title="Omitidos" files={sent.files_omitted.map((o) => ({ path: o.path, note: OMIT_REASON[o.reason] ?? o.reason }))} />
    </details>
  );
}

function FileList({ title, files }: { title: string; files: { path: string; note: string }[] }) {
  if (files.length === 0) return null;
  return (
    <>
      <h4>
        {title} ({files.length})
      </h4>
      <ul className="files">
        {files.map((f) => (
          <li key={f.path}>
            <code>{f.path}</code>
            {f.note && <span className="meta"> — {f.note}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
