import { pct } from "../lib/format";
import { T_MAX, T_MIN } from "../lib/verdict";

/** Compacto, no cabeçalho das decisões. Mexer aqui não chama a API: o veredito é recalculado no
 * browser com as respostas do jev. */
export function ThresholdSlider({ t, onChange }: { t: number; onChange: (t: number) => void }) {
  return (
    <label className="threshold eyebrow">
      threshold
      <input
        type="range"
        min={T_MIN}
        max={T_MAX}
        step={0.05}
        value={t}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <output className="threshold-value">{pct(t)}</output>
    </label>
  );
}
