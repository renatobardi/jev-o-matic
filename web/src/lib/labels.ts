// Interface text. Keys are the API's (questions.py / verdict.py).

import type { Lane } from "./api";

export const LANE: Record<Lane, { title: string; blurb: string }> = {
  fast: { title: "Fast merge", blurb: "Low risk: one reviewer, no ceremony." },
  normal: { title: "Normal review", blurb: "The standard code review flow." },
  senior: { title: "Senior review", blurb: "Touches a sensitive area: needs someone experienced." },
};

export const DECISION: Record<string, string> = {
  change_type: "Kind of change",
  risk: "Production risk",
  touches_auth_security: "Touches security logic",
  touches_data_schema: "Changes persisted data structure",
  breaking_api: "Breaks users of a public interface",
  touches_infra_ci: "Touches build, CI or deploy",
  has_tests: "Ships tests for what it changes",
  description_explains_why: "Description explains why",
};

export const CHOICE: Record<string, string> = {
  feature: "feature",
  bugfix: "bugfix",
  refactor: "refactor",
  mixed: "mixed",
  deps: "dependencies",
  docs: "docs",
  config_infra: "config / infra",
  tests_only: "tests only",
};

export const RISK_LEVEL = ["none", "contained", "severe"];

export const REASON: Record<string, string> = {
  touches_auth_security: "touches security logic",
  touches_data_schema: "changes data structure",
  breaking_api: "breaks a public interface",
  risk_severe: "severe risk",
  type_docs: "docs only",
  type_tests_only: "tests only",
  type_deps: "dependencies only",
  no_risk_flags: "no risk signal",
  risk_none: "does not alter production",
  small: "small PR",
  too_many_files_for_fast: "too many files for the fast lane",
  no_runtime_files: "no production code files",
  runtime_files_block_fast: "production code in the diff",
  uncertain_decisions: "some decisions are uncertain",
};

export const OMIT_REASON: Record<string, string> = {
  lockfile: "lockfile",
  vendored: "third-party code",
  build_output: "build output",
  minified: "minified",
  snapshot: "test snapshot",
  generated: "generated",
  binary: "binary",
  no_patch: "no diff available",
  removed: "file removed",
  budget: "did not fit the budget",
  github_file_cap: "beyond GitHub's file cap",
};

export const STAGE: Record<string, string> = {
  github: "GitHub",
  jev: "Jev",
  code: "Code",
  llm: "LLM",
};
