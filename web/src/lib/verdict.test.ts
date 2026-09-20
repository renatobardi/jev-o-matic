import { expect, test } from "bun:test";
import cases from "../../../api/tests/verdict_cases.json";
import { verdict, type AnswerLike } from "./verdict";

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
