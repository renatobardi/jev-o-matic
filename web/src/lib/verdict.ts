// Port de api/src/jevomatic_api/verdict.py. As duas implementações rodam a MESMA tabela de casos
// (api/tests/verdict_cases.json) — mudou a regra num lado, o teste do outro quebra.

import type { Lane } from "./api";

export interface AnswerLike {
  value: number | string;
  confidence: number;
  probabilities: Record<string, number> | null;
}

export interface LocalVerdict {
  lane: Lane;
  reasons: string[];
  uncertain: string[];
  t: number;
}

export const DEFAULT_T = 0.7;
export const T_MIN = 0.5;
export const T_MAX = 0.95;
const FLAGS = ["touches_auth_security", "touches_data_schema", "breaking_api"];
const FAST_TYPES = ["docs", "tests_only", "deps"];
const FAST_MAX_FILES = 25;
const FAST_RUNNER_UP = 0.3;
const SEVERE_MIN_PROB = 0.3;

/** `round()` do Python arredonda metade pro par (0.5 → 0, 1.5 → 2); Math.round não. */
function pyRound(v: number): number {
  const floor = Math.floor(v);
  const diff = v - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

const RUNTIME_CATEGORIES = ["security", "schema", "api", "source"];

/** Arquivos de código de produção, a partir do `categories` que a API devolve. */
export function runtimeFiles(categories: Record<string, number>): number {
  return RUNTIME_CATEGORIES.reduce((n, c) => n + (categories[c] ?? 0), 0);
}

/** Só o que ainda pode mudar a via: flag incerto sempre; risk e change_type só se importam. */
function uncertainKeys(decisions: Record<string, AnswerLike>, t: number, fastReachable: boolean): string[] {
  const unsure = (k: string) => decisions[k].confidence < t;
  const out = FLAGS.filter(unsure);
  const couldBeSevere = ((decisions.risk.probabilities ?? {})["2"] ?? 0) >= SEVERE_MIN_PROB;
  if (unsure("risk") && (couldBeSevere || fastReachable)) out.push("risk");
  if (unsure("change_type") && fastReachable) out.push("change_type");
  return out;
}

export function verdict(
  decisions: Record<string, AnswerLike>,
  filesChanged: number,
  t: number = DEFAULT_T,
  runtime: number = 0,
): LocalVerdict {
  const v: LocalVerdict = { lane: "normal", reasons: [], uncertain: [], t };
  const risk = decisions.risk;
  const ctype = decisions.change_type;
  const sure = (k: string) => decisions[k].confidence >= t;
  const riskLevel = pyRound(risk.value as number);
  const riskSevere = sure("risk") && riskLevel === 2;

  const hot = FLAGS.filter((k) => sure(k) && (decisions[k].value as number) >= 0.5);
  if (hot.length > 0 || riskSevere) {
    v.lane = "senior";
    v.reasons = [...hot, ...(riskSevere ? ["risk_severe"] : [])];
    return v;
  }

  const allCold = FLAGS.every((k) => sure(k) && (decisions[k].value as number) < 0.5);
  const small = filesChanged <= FAST_MAX_FILES;
  const probs = ctype.probabilities ?? {};
  const isFastType = FAST_TYPES.includes(ctype.value as string);
  const nearFast = isFastType || FAST_TYPES.some((o) => (probs[o] ?? 0) >= FAST_RUNNER_UP);
  const noRuntime = runtime === 0;
  const fastReachable = allCold && small && nearFast && noRuntime;

  v.uncertain = uncertainKeys(decisions, t, fastReachable);

  if (sure("change_type") && isFastType && allCold && small && noRuntime && sure("risk") && riskLevel === 0) {
    v.lane = "fast";
    v.reasons = [`type_${ctype.value as string}`, "no_risk_flags", "risk_none", "small", "no_runtime_files"];
    return v;
  }

  if (isFastType && !small) v.reasons.push("too_many_files_for_fast");
  if (isFastType && !noRuntime) v.reasons.push("runtime_files_block_fast");
  if (v.uncertain.length > 0) v.reasons.push("uncertain_decisions");
  return v;
}
