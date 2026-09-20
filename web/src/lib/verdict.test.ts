import { expect, test } from "bun:test";
import cases from "../../../api/tests/verdict_cases.json";
import type { TriageResult } from "./api";
import fixtures from "./fixtures.json";
import { runtimeFiles, verdict, type AnswerLike } from "./verdict";

type Raw = [number | string, number, Record<string, number>?];
interface Case {
  name: string;
  files: number;
  runtime?: number;
  t: number;
  lane: string;
  uncertain: string[];
  d: Record<string, Raw>;
}

const toAnswers = (d: Case["d"]): Record<string, AnswerLike> =>
  Object.fromEntries(Object.entries(d).map(([k, [value, confidence, probabilities]]) => [k, { value, confidence, probabilities: probabilities ?? null }]));

// A mesma tabela que valida o verdict.py: as duas implementações não podem divergir.
for (const c of cases as unknown as Case[]) {
  test(`veredito: ${c.name}`, () => {
    const v = verdict(toAnswers(c.d), c.files, c.t, c.runtime ?? 0);
    expect([v.lane, v.uncertain]).toEqual([c.lane, c.uncertain]);
  });
}

test("a tabela compartilhada não está vazia", () => {
  expect((cases as unknown[]).length).toBeGreaterThanOrEqual(15);
});

// Os fixtures do ?fixture= são respostas gravadas da API: o veredito gravado tem que ser o que o
// verdict.ts calcula das respostas do jev (o `uncertain` é derivado à mão no capture-fixtures.sh).
for (const [name, fx] of Object.entries(fixtures as unknown as Record<string, TriageResult>)) {
  test(`fixture ${name}: veredito do jev bate com o verdict.ts`, () => {
    const jev = Object.fromEntries(Object.entries(fx.decisions).map(([k, d]) => [k, d.original ? { ...d, ...d.original } : d]));
    const v = verdict(jev, fx.pr.changed_files, fx.verdict.t, runtimeFiles(fx.categories));
    expect(v.lane).toBe(fx.verdict.jev_lane ?? fx.verdict.lane);
    if ((fx.verdict.escalated ?? []).length === 0) expect(v.uncertain).toEqual(fx.verdict.uncertain);
  });
}
