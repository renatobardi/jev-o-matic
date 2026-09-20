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
    <section className="card slider" aria-label="Threshold de confiança">
      <div className="slider-head">
        <label htmlFor="threshold" className="eyebrow">
          threshold de confiança
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
            Simulação só com as respostas do jev.{" "}
            {wouldEscalate > 0
              ? `Com ${pct(t)}, ${wouldEscalate} ${wouldEscalate === 1 ? "decisão iria" : "decisões iriam"} pro LLM.`
              : `Com ${pct(t)}, o LLM não seria acionado.`}{" "}
            <button type="button" className="link" onClick={() => onChange(serverT)}>
              voltar pro resultado real ({pct(serverT)})
            </button>
          </>
        ) : (
          "Abaixo dele, a decisão do jev não define a via. Arraste pra ver o funil mudar — sem nova chamada."
        )}
      </p>
    </section>
  );
}
