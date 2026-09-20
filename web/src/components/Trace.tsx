import type { Stage } from "../lib/api";
import { int, ms, usd } from "../lib/format";
import { STAGE } from "../lib/labels";

export function Trace({ trace }: { trace: Stage[] }) {
  const ran = trace.filter((s) => !s.skipped);
  const total = ran.reduce((a, s) => a + s.latency_ms, 0);
  const cost = ran.reduce((a, s) => a + (s.cost ?? 0), 0);
  return (
    <section className="card" aria-label="Etapas">
      <p className="eyebrow">trilha · jev → código → LLM</p>
      <ol className="trace">
        {trace.map((s) => (
          <li key={s.stage} className={s.skipped ? "stage is-skipped" : "stage"}>
            <span className="stage-name">{STAGE[s.stage] ?? s.stage}</span>
            {s.skipped ? (
              <span className="meta">{s.note ?? "não acionado"}</span>
            ) : (
              <>
                <span className="stage-time">{ms(s.latency_ms)}</span>
                <span className="meta">
                  {s.cost !== null && usd(s.cost)}
                  {s.input_tokens !== null && ` · ${int(s.input_tokens)} tokens`}
                </span>
                {s.note && <span className="meta">{s.note}</span>}
              </>
            )}
          </li>
        ))}
      </ol>
      <p className="meta">
        Total {ms(total)} · {usd(cost)}. O GitHub entra na conta de tempo, não na do modelo.
      </p>
    </section>
  );
}
