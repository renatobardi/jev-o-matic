// Texto de interface. As chaves são as da API (questions.py / verdict.py).

import type { Lane } from "./api";

export const LANE: Record<Lane, { title: string; blurb: string }> = {
  fast: { title: "Merge rápido", blurb: "Baixo risco: um revisor, sem cerimônia." },
  normal: { title: "Revisão normal", blurb: "Fluxo padrão de code review." },
  senior: { title: "Revisão sênior", blurb: "Toca em área sensível: precisa de alguém experiente." },
};

export const DECISION: Record<string, string> = {
  change_type: "Tipo de mudança",
  risk: "Risco em produção",
  touches_auth_security: "Mexe em lógica de segurança",
  touches_data_schema: "Muda estrutura de dados persistidos",
  breaking_api: "Quebra quem usa a interface pública",
  touches_infra_ci: "Mexe em build, CI ou deploy",
  has_tests: "Traz testes do que muda",
  description_explains_why: "Descrição explica o porquê",
};

export const CHOICE: Record<string, string> = {
  feature: "feature",
  bugfix: "bugfix",
  refactor: "refactor",
  mixed: "misto",
  deps: "dependências",
  docs: "docs",
  config_infra: "config / infra",
  tests_only: "só testes",
};

export const RISK_LEVEL = ["nenhum", "contido", "severo"];

export const REASON: Record<string, string> = {
  touches_auth_security: "mexe em lógica de segurança",
  touches_data_schema: "muda estrutura de dados",
  breaking_api: "quebra interface pública",
  risk_severe: "risco severo",
  type_docs: "só documentação",
  type_tests_only: "só testes",
  type_deps: "só dependências",
  no_risk_flags: "nenhum sinal de risco",
  risk_none: "não altera produção",
  small: "PR pequeno",
  too_many_files_for_fast: "arquivos demais pra via rápida",
  no_runtime_files: "nenhum arquivo de código de produção",
  runtime_files_block_fast: "tem código de produção no diff",
  uncertain_decisions: "há decisões incertas",
};

export const OMIT_REASON: Record<string, string> = {
  lockfile: "lockfile",
  vendored: "código de terceiros",
  build_output: "saída de build",
  minified: "minificado",
  snapshot: "snapshot de teste",
  generated: "gerado",
  binary: "binário",
  no_patch: "sem diff disponível",
  removed: "arquivo removido",
  budget: "não coube no orçamento",
  github_file_cap: "além do teto do GitHub",
};

export const STAGE: Record<string, string> = {
  github: "GitHub",
  jev: "jev",
  code: "Código",
  llm: "LLM",
};
