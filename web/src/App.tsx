import { useCallback, useState } from "react";
import { DemoNotice } from "./components/DemoNotice";
import { Footer } from "./components/Footer";
import { Result } from "./components/Result";
import { UrlForm } from "./components/UrlForm";
import { ApiError, postTriage, type TriageResult } from "./lib/api";
import fixtures from "./lib/fixtures.json";

type View =
  | { kind: "idle" }
  | { kind: "loading"; url: string }
  | { kind: "error"; error: ApiError }
  | { kind: "done"; result: TriageResult };

/** `?fixture=fast|senior|uncertain|cascade` renderiza um resultado gravado, sem API. */
function fixtureFromQuery(): TriageResult | null {
  const name = new URLSearchParams(window.location.search).get("fixture");
  const all = fixtures as unknown as Record<string, TriageResult>;
  return name && name in all ? all[name] : null;
}

export function App() {
  const [view, setView] = useState<View>(() => {
    const fx = fixtureFromQuery();
    return fx ? { kind: "done", result: fx } : { kind: "idle" };
  });

  const run = useCallback(async (url: string) => {
    setView({ kind: "loading", url });
    try {
      setView({ kind: "done", result: await postTriage(url) });
    } catch (e) {
      const error = e instanceof ApiError ? e : new ApiError("unexpected", "Algo deu errado.", 0);
      setView({ kind: "error", error });
    }
  }, []);

  return (
    <div className="page">
      <header className="masthead">
        <p className="eyebrow">jev-o-matic · lab v2</p>
        <h1>Triagem de pull request com o jev</h1>
        <p className="lede">
          Cole um PR público. O <strong>jev</strong> responde perguntas tipadas sobre o diff em cerca de meio segundo, o{" "}
          <strong>código</strong> decide a via de revisão, e só a dúvida vai pro <strong>LLM</strong>.
        </p>
      </header>

      <DemoNotice />
      <UrlForm busy={view.kind === "loading"} onSubmit={run} />

      <main aria-live="polite">
        {view.kind === "idle" && (
          <p className="empty">O resultado aparece aqui: via de revisão, decisões com confiança, e o que cada etapa custou.</p>
        )}
        {view.kind === "loading" && (
          <div className="card loading" role="status">
            <span className="spinner" aria-hidden="true" />
            Buscando o PR no GitHub e perguntando ao jev…
          </div>
        )}
        {view.kind === "error" && (
          <div className="card error" role="alert">
            <strong>Não deu.</strong> {view.error.message}
            <span className="meta"> ({view.error.code})</span>
          </div>
        )}
        {view.kind === "done" && <Result result={view.result} />}
      </main>

      <Footer versions={view.kind === "done" ? view.result.versions : null} />
    </div>
  );
}
