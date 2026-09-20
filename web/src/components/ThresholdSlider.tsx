import { pct } from "../lib/format";
import { T_MAX, T_MIN } from "../lib/verdict";

interface Props {
  t: number;
  serverT: number;
  wouldEscalate: number;
  onChange: (t: number) => void;
}

/** Mexer aqui não chama a API: o veredito é recalculado no browser com as respostas do jev. */
export function ThresholdSlider({ t, serverT, wouldEscalate, onChange }: Props) {
  const simulated = t !== serverT;
  return (
    <section className="card slider" aria-label="Confidence threshold">
      <div className="slider-head">
        <label htmlFor="threshold" className="eyebrow">
          confidence threshold
        </label>
        <output htmlFor="threshold" className="slider-value">
          {pct(t)}
        </output>
      </div>
      <input
        id="threshold"
        type="range"
        min={T_MIN}
        max={T_MAX}
        step={0.05}
        value={t}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <p className="meta">
        {simulated ? (
          <>
            Simulation with the jev answers only.{" "}
            {wouldEscalate > 0
              ? `At ${pct(t)}, ${wouldEscalate} ${wouldEscalate === 1 ? "decision" : "decisions"} would go to the LLM.`
              : `At ${pct(t)}, the LLM would not be called.`}{" "}
            <button type="button" className="link" onClick={() => onChange(serverT)}>
              back to the real result ({pct(serverT)})
            </button>
          </>
        ) : (
          "Below it, a jev decision does not set the lane. Drag to watch the funnel change — no new call."
        )}
      </p>
    </section>
  );
}
