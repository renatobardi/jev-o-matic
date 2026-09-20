// Public PRs, varied on purpose. `fixture` points at a RECORDED response in fixtures.json
// (scripts/ops/capture-fixtures.sh): clicking an example costs nothing and keeps working when the
// demo budget is spent. No fixture yet → the example runs live.
export const EXAMPLES: { label: string; url: string; fixture: string }[] = [
  { label: "docs translation", url: "https://github.com/fastapi/fastapi/pull/13000", fixture: "fast" },
  { label: "dependency bump", url: "https://github.com/fastapi/fastapi/pull/16289", fixture: "deps" },
  { label: "docs + refactor in security code", url: "https://github.com/pallets/werkzeug/pull/3252", fixture: "cascade" },
  { label: "CI workflow", url: "https://github.com/pallets/flask/pull/5945", fixture: "ci" },
  { label: "deprecated code removal", url: "https://github.com/pydantic/pydantic/pull/720", fixture: "senior" },
];
