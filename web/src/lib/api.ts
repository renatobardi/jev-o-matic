// Espelho de api/src/jevomatic_api/schemas.py — o contrato do POST /api/triage.

export type Lane = "fast" | "normal" | "senior";

export interface Decision {
  type: "noul" | "choice" | "score";
  value: number | string;
  confidence: number;
  probabilities: Record<string, number> | null;
  source: "jev" | "llm";
  /** Só quando source === "llm": justificativa em texto puro. */
  rationale?: string | null;
  /** O que o jev tinha dito, quando o LLM respondeu no lugar. */
  original?: { value: number | string; confidence: number; probabilities: Record<string, number> | null } | null;
}

export interface Stage {
  stage: "github" | "jev" | "code" | "llm";
  latency_ms: number;
  cost: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  skipped: boolean;
  note: string | null;
}

export interface TriageResult {
  pr: {
    slug: string;
    title: string;
    author: string;
    author_association: string;
    state: string;
    draft: boolean;
    labels: string[];
    additions: number;
    deletions: number;
    changed_files: number;
    head_sha: string;
    html_url: string;
  };
  decisions: Record<string, Decision>;
  verdict: { lane: Lane; reasons: string[]; uncertain: string[]; t: number; escalated?: string[]; jev_lane?: Lane | null };
  sent: {
    tokens_est: number;
    budget_tokens: number;
    files_total: number;
    files_included: string[];
    files_truncated: string[];
    files_omitted: { path: string; reason: string }[];
    body_truncated: boolean;
    file_list_truncated: boolean;
  };
  trace: Stage[];
  versions: { questions: string; jev_model: string; llm_model?: string | null; api: string };
  categories: Record<string, number>;
  cached: boolean;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

/** A API sempre responde `{error: {code, message}}`; qualquer outra coisa (proxy, rede) vira erro genérico. */
export async function parseError(res: Response): Promise<ApiError> {
  try {
    const body: unknown = await res.json();
    const err = (body as { error?: { code?: unknown; message?: unknown } }).error;
    if (err && typeof err.code === "string" && typeof err.message === "string") {
      return new ApiError(err.code, err.message, res.status);
    }
  } catch {
    // corpo não é JSON
  }
  return new ApiError("unexpected", `O servidor respondeu ${res.status}.`, res.status);
}

export async function postTriage(url: string, fetcher: typeof fetch = fetch): Promise<TriageResult> {
  let res: Response;
  try {
    res = await fetcher("/api/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    throw new ApiError("network", "Não consegui falar com o servidor.", 0);
  }
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as TriageResult;
}
