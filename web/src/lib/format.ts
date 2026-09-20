import type { Decision } from "./api";
import { CHOICE, RISK_LEVEL } from "./labels";

export function ms(v: number): string {
  if (v < 1) return "<1 ms";
  return v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1).replace(".", ",")} s`;
}

export function usd(v: number | null): string {
  if (v === null) return "—";
  if (v === 0) return "US$ 0";
  return `US$ ${v.toFixed(v < 0.01 ? 6 : 4).replace(".", ",")}`;
}

export function pct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function int(v: number): string {
  return v.toLocaleString("pt-BR");
}

/** Valor legível de uma decisão: noul vira sim/não/indefinido, score vira o nível mais próximo, choice vira o rótulo. */
export function decisionValue(key: string, d: Decision): string {
  if (d.type === "noul") {
    // lab 08: noul no meio da faixa significa "não sei", não "provavelmente sim"
    const p = d.value as number;
    return p >= 0.7 ? "sim" : p <= 0.3 ? "não" : "indefinido";
  }
  if (d.type === "score") {
    const level = Math.round(d.value as number);
    const name = key === "risk" ? (RISK_LEVEL[level] ?? String(level)) : String(level);
    return `${name} (${(d.value as number).toFixed(2).replace(".", ",")})`;
  }
  return CHOICE[d.value as string] ?? String(d.value);
}

/** Para noul, a probabilidade de "sim" é o dado bruto — o confidence é derivado dela. */
export function decisionDetail(d: Decision): string {
  if (d.type === "noul") return `p(sim) ${pct(d.value as number)}`;
  const probs = Object.entries(d.probabilities ?? {})
    .filter(([, p]) => p >= 0.05)
    .sort((a, b) => b[1] - a[1])
    .map(([k, p]) => `${CHOICE[k] ?? (d.type === "score" ? `nível ${k}` : k)} ${pct(p)}`);
  return probs.join(" · ");
}
