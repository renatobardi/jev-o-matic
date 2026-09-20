import { useState, type FormEvent } from "react";
import { EXAMPLES } from "../lib/examples";

const LOOKS_LIKE_PR = /^https:\/\/(www\.)?github\.com\/[^/]+\/[^/]+\/pull\/\d+/;

interface Props {
  busy: boolean;
  onSubmit: (url: string) => void;
  onExample: (example: (typeof EXAMPLES)[number]) => void;
}

export function UrlForm({ busy, onSubmit, onExample }: Props) {
  const [url, setUrl] = useState("");
  const [hint, setHint] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const value = url.trim();
    // Validação leve: a API é a autoridade (api/github.py).
    if (!LOOKS_LIKE_PR.test(value)) {
      setHint("It has to be a pull request URL: https://github.com/owner/repo/pull/123");
      return;
    }
    setHint(null);
    onSubmit(value);
  }

  function pick(example: (typeof EXAMPLES)[number]) {
    setUrl(example.url);
    setHint(null);
    onExample(example);
  }

  return (
    <section className="form-block">
      <form className="url-form" onSubmit={submit} noValidate>
        <label htmlFor="pr-url" className="sr-only">
          Pull request URL
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
          {busy ? "Triaging…" : "Triage"}
        </button>
      </form>
      {hint && (
        <p id="pr-url-hint" className="hint">
          {hint}
        </p>
      )}
      <div className="examples">
        <span className="meta">or try:</span>
        {EXAMPLES.map((ex) => (
          <button key={ex.url} type="button" className="chip" disabled={busy} onClick={() => pick(ex)}>
            {ex.label}
          </button>
        ))}
      </div>
    </section>
  );
}
