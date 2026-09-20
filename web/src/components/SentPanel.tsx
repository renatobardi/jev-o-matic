import type { TriageResult } from "../lib/api";
import { int } from "../lib/format";
import { OMIT_REASON } from "../lib/labels";

export function SentPanel({ sent }: { sent: TriageResult["sent"] }) {
  const partial = sent.files_omitted.length > 0 || sent.files_truncated.length > 0 || sent.body_truncated;
  return (
    <details className="card sent">
      <summary>
        <span className="eyebrow">what was sent to Jev</span>
        <span className="meta">
          ~{int(sent.tokens_est)} tokens · {sent.files_included.length} of {int(sent.files_total)}{" "}
          {sent.files_total === 1 ? "file" : "files"}
          {partial && " · partial view"}
        </span>
      </summary>
      <p className="meta">
        Budget of {int(sent.budget_tokens)} tokens for the diff. Patches go in by path risk order; the verdict only covers
        what the model saw.
      </p>
      {sent.body_truncated && <p className="meta">The PR description was truncated.</p>}
      <FileList title="Included" files={sent.files_included.map((p) => ({ path: p, note: sent.files_truncated.includes(p) ? "truncated" : "" }))} />
      <FileList title="Omitted" files={sent.files_omitted.map((o) => ({ path: o.path, note: OMIT_REASON[o.reason] ?? o.reason }))} />
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
