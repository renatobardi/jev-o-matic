import { useCallback, useState } from "react";
import { DemoNotice } from "./components/DemoNotice";
import { Footer } from "./components/Footer";
import { Result } from "./components/Result";
import { UrlForm } from "./components/UrlForm";
import { ApiError, postTriage, type TriageResult } from "./lib/api";
import type { EXAMPLES } from "./lib/examples";
import fixtures from "./lib/fixtures.json";

type View =
  | { kind: "idle" }
  | { kind: "loading"; url: string }
  | { kind: "error"; error: ApiError }
  | { kind: "done"; result: TriageResult; recorded: boolean };

const RECORDED = fixtures as unknown as Record<string, TriageResult>;

/** `?fixture=fast|senior|uncertain|cascade|deps|ci` renderiza um resultado gravado, sem API. */
function fixtureFromQuery(): TriageResult | null {
  const name = new URLSearchParams(window.location.search).get("fixture");
  return name && name in RECORDED ? RECORDED[name] : null;
}

// Erros em que a demo está funcionando como previsto: o título não pode soar como defeito.
const OUT_OF_BUDGET = new Set(["credits_exhausted", "budget_exhausted", "rate_limited"]);

export function App() {
  const [view, setView] = useState<View>(() => {
    const fx = fixtureFromQuery();
    return fx ? { kind: "done", result: fx, recorded: true } : { kind: "idle" };
  });

  const run = useCallback(async (url: string) => {
    setView({ kind: "loading", url });
    try {
      setView({ kind: "done", result: await postTriage(url), recorded: false });
    } catch (e) {
      const error = e instanceof ApiError ? e : new ApiError("unexpected", "Something went wrong.", 0);
      setView({ kind: "error", error });
    }
  }, []);

  // Exemplos mostram a resposta GRAVADA de um run real: custo zero e seguem funcionando com o
  // orçamento da demo esgotado. Sem gravação (ainda) → roda ao vivo.
  const runExample = useCallback(
    (example: (typeof EXAMPLES)[number]) => {
      const result = RECORDED[example.fixture];
      if (result) setView({ kind: "done", result, recorded: true });
      else void run(example.url);
    },
    [run],
  );

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead-main">
          <p className="eyebrow">Jev-o-matic · lab</p>
          <h1>Pull request triage with Jev</h1>
          <p className="lede">
            <strong>Jev</strong> answers typed questions about the diff in about half a second,{" "}
            <strong>code</strong> picks the review lane, and only the doubt goes to an <strong>LLM</strong>.
          </p>
        </div>
        <DemoNotice />
      </header>

      <UrlForm
        busy={view.kind === "loading"}
        onSubmit={run}
        onExample={runExample}
        activeUrl={view.kind === "done" ? view.result.pr.html_url : null}
      />

      <main aria-live="polite">
        {view.kind === "idle" && (
          <p className="empty">The result shows up here: review lane, decisions with confidence, and what each stage cost.</p>
        )}
        {view.kind === "loading" && (
          <div className="card loading" role="status">
            <span className="spinner" aria-hidden="true" />
            Fetching the PR from GitHub and asking Jev…
          </div>
        )}
        {view.kind === "error" && (
          <div className="card error" role="alert">
            <strong>{OUT_OF_BUDGET.has(view.error.code) ? "That is the limit." : "That did not work."}</strong> {view.error.message}
            <span className="meta"> ({view.error.code})</span>
          </div>
        )}
        {view.kind === "done" && (
          // key: trocar de PR zera o threshold simulado do resultado anterior
          <Result key={view.result.pr.html_url} result={view.result} recorded={view.recorded} />
        )}
      </main>

      <Footer versions={view.kind === "done" ? view.result.versions : null} />
    </div>
  );
}
