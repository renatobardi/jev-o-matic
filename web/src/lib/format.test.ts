import { expect, test } from "bun:test";
import { ApiError, parseError, postTriage, type Decision } from "./api";
import { decisionDetail, decisionValue, ms, usd } from "./format";

const d = (type: Decision["type"], value: number | string, probabilities: Decision["probabilities"] = null): Decision => ({
  type, value, confidence: 0.9, probabilities, source: "jev",
});

test("ms e usd", () => {
  expect(ms(0.02)).toBe("<1 ms");
  expect(ms(484.2)).toBe("484 ms");
  expect(ms(1698)).toBe("1.7 s");
  expect(usd(null)).toBe("—");
  expect(usd(0)).toBe("$0");
  expect(usd(0.000142)).toBe("$0.000142");
});

test("valor legível por tipo", () => {
  expect(decisionValue("breaking_api", d("noul", 0.92))).toBe("yes");
  expect(decisionValue("has_tests", d("noul", 0.24))).toBe("no");
  expect(decisionValue("description_explains_why", d("noul", 0.58))).toBe("unclear");
  expect(decisionValue("touches_auth_security", d("noul", 0.75))).toBe("yes");
  expect(decisionValue("risk", d("score", 1.79))).toBe("severe (1.79)");
  expect(decisionValue("change_type", d("choice", "config_infra"))).toBe("config / infra");
});

test("detalhe: noul mostra p(sim); choice esconde opções < 5% e ordena", () => {
  expect(decisionDetail(d("noul", 0.75))).toBe("p(yes) 75%");
  expect(decisionDetail(d("choice", "docs", { refactor: 0.09, docs: 0.85, deps: 0.01 }))).toBe("docs 85% · refactor 9%");
  expect(decisionDetail(d("score", 1.1, { "0": 0.07, "1": 0.77, "2": 0.16 }))).toBe("level 1 77% · level 2 16% · level 0 7%");
});

test("erro da API: formato {error:{code,message}} e fallback", async () => {
  const ok = await parseError(new Response(JSON.stringify({ error: { code: "pr_not_found", message: "PR não encontrado ou privado." } }), { status: 404 }));
  expect([ok.code, ok.message, ok.status]).toEqual(["pr_not_found", "PR não encontrado ou privado.", 404]);
  const html = await parseError(new Response("<html>502</html>", { status: 502 }));
  expect([html.code, html.status]).toEqual(["unexpected", 502]);
});

test("postTriage: rede fora vira ApiError network", async () => {
  const down = (() => Promise.reject(new TypeError("fetch failed"))) as unknown as typeof fetch;
  const err = await postTriage("https://github.com/o/r/pull/1", down).catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect((err as ApiError).code).toBe("network");
});
