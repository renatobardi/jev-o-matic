import { useState, type FormEvent } from "react";
import { EXAMPLES } from "../lib/examples";

const LOOKS_LIKE_PR = /^https:\/\/(www\.)?github\.com\/[^/]+\/[^/]+\/pull\/\d+/;

export function UrlForm({ busy, onSubmit }: { busy: boolean; onSubmit: (url: string) => void }) {
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const value = url.trim();
    // Validação leve: a API é a autoridade (api/github.py).
    if (!LOOKS_LIKE_PR.test(value)) {
      setHint("Precisa ser a URL de um PR: https://github.com/owner/repo/pull/123");
      return;
    }
    setHint(null);
    onSubmit(value);
  }

  function pick(example: string) {
    setUrl(example);
    setHint(null);
    onSubmit(example);
  }

  return (
    <section className="form-block">
      <form className="url-form" onSubmit={submit} noValidate>
        <label htmlFor="pr-url" className="sr-only">
          URL do pull request
        </label>
        <input
          id="pr-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://github.com/owner/repo/pull/123"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          aria-invalid={hint !== null}
          aria-describedby={hint ? "pr-url-hint" : undefined}
        />
        <button type="submit" disabled={busy}>
          {busy ? "Triando…" : "Triar"}
        </button>
      </form>
      {hint && (
        <p id="pr-url-hint" className="hint">
          {hint}
        </p>
      )}
      <div className="examples">
        <span className="meta">ou tente:</span>
        {EXAMPLES.map((ex) => (
          <button key={ex.url} type="button" className="chip" disabled={busy} onClick={() => pick(ex.url)}>
            {ex.label}
          </button>
        ))}
      </div>
    </section>
  );
}
