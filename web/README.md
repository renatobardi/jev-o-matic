# jevomatic-web

Página única do jev-o-matic v2 (PR Triage). React 19 + Vite + TypeScript, bun, oxlint, CSS puro com tokens.

```bash
bun install
bun run dev        # http://localhost:5173 — /api é repassado pro uvicorn em :8000
bun run build && bun run lint && bun test src
```

Sem API rodando, `?fixture=fast|senior|uncertain` renderiza um resultado real gravado do smoke do M1.
