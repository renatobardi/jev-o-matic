import type { Stage } from "../lib/api";
import { int, ms, usd } from "../lib/format";
import { STAGE } from "../lib/labels";

function meta(s: Stage): string {
  if (s.skipped) return s.note ?? "not called";
  return [s.cost !== null ? usd(s.cost) : null, s.input_tokens !== null ? `${int(s.input_tokens)} tokens` : null, s.note]
    .filter(Boolean)
    .join(" · ");
}

export function Trace({ trace }: { trace: Stage[] }) {
  const ran = trace.filter((s) => !s.skipped);
  const total = ran.reduce((a, s) => a + s.latency_ms, 0);
  const cost = ran.reduce((a, s) => a + (s.cost ?? 0), 0);
  return (
    <section className="card" aria-label="Stages">
      <p className="eyebrow">trace · Jev → code → LLM</p>
      {/* barra empilhada: largura proporcional à latência de cada etapa */}
      <div className="trace-bar" aria-hidden="true">
        {trace.map((s) => (
          <span
            key={s.stage}
            className={`stage-${s.stage}${s.skipped ? " is-skipped" : ""}`}
            style={{ flexGrow: s.skipped ? 0 : Math.max(s.latency_ms, 1) }}
          />
        ))}
      </div>
      <ol className="trace">
        {trace.map((s) => (
          <li key={s.stage} className={s.skipped ? "stage is-skipped" : "stage"}>
            <span className={`stage-dot stage-${s.stage}${s.skipped ? " is-skipped" : ""}`} aria-hidden="true" />
            <span className="stage-body">
              <span className="stage-name">{STAGE[s.stage] ?? s.stage}</span>
              <span className="meta">{meta(s)}</span>
            </span>
            <span className="stage-time">{s.skipped ? "—" : ms(s.latency_ms)}</span>
          </li>
        ))}
      </ol>
      <p className="meta">
        Total {ms(total)} · {usd(cost)}. GitHub counts toward the time, not toward the model cost.
      </p>
    </section>
  );
}
