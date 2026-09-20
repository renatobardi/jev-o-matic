"""Dataset do lab 09 (#39): ~55 PRs públicos reais, com o state CONGELADO por head sha.

Congelar o state (o que o jev vê: título, descrição, lista de arquivos, patches dentro do orçamento)
torna o lab reprodutível sem GitHub e imune a force-push. O rótulo humano é feito lendo o diff
completo no GitHub, não o state — se o orçamento cortou o que importava, isso é erro do sistema.

`hint` é o estrato pelo qual o PR foi BUSCADO (palavra no título). NÃO é rótulo (lição do
werkzeug#3252). Serve só pra estratificar a amostra e o split.

`split` é fixado aqui, antes de qualquer run: dentro de cada estrato, ordena por sha256(url) e
alterna treino/teste. Wording novo só pode olhar o treino (lição do lab 04).

Fora da amostra: os 19 PRs usados pra ajustar o pr-v2 (api/scripts/wording_compare.py) e os
repos deles, pra não contaminar o teste.

Autocontido: roda dentro do container da api, que tem GITHUB_TOKEN (scripts/ops/build-prs-dataset.sh):
    docker compose exec -T api python - < datasets/build_prs.py > datasets/prs_v1.jsonl
    python3 datasets/build_prs.py --stats   # distribuição do que foi gravado
Progresso vai pra stderr; o JSONL, pra stdout."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

VERSION = "prs_v1"
G = "https://github.com/"

# (hint, "owner/repo#n") — 59 candidatos; o que falhar no fetch fica de fora e é reportado.
PRS: list[tuple[str, str]] = [
    ("docs", "vitejs/vite#23235"),
    ("docs", "rails/rails#58535"),
    ("docs", "tokio-rs/axum#3842"),
    ("docs", "tokio-rs/axum#3847"),
    ("deps", "saleor/saleor#19712"),
    ("deps", "saleor/saleor#19600"),
    ("deps", "caddyserver/caddy#8028"),
    ("deps", "medusajs/medusa#16764"),
    ("deps", "expressjs/express#7390"),
    ("bugfix", "tokio-rs/axum#3886"),
    ("bugfix", "tokio-rs/axum#3848"),
    ("bugfix", "expressjs/express#7459"),
    ("bugfix", "gin-gonic/gin#4805"),
    ("bugfix", "gin-gonic/gin#4819"),
    ("bugfix", "vitejs/vite#23437"),
    ("feature", "medusajs/medusa#16801"),
    ("feature", "medusajs/medusa#16853"),
    ("feature", "mastodon/mastodon#40572"),
    ("feature", "gin-gonic/gin#4830"),
    ("feature", "gin-gonic/gin#4655"),
    ("security", "mastodon/mastodon#36115"),
    ("security", "saleor/saleor#19527"),
    ("security", "caddyserver/caddy#7894"),
    ("security", "caddyserver/caddy#7756"),
    ("security", "rails/rails#56580"),
    ("security", "rails/rails#54434"),
    ("migration", "mastodon/mastodon#40264"),
    ("migration", "mastodon/mastodon#39686"),
    ("migration", "saleor/saleor#19697"),
    ("migration", "saleor/saleor#18842"),
    ("migration", "medusajs/medusa#16351"),
    ("infra", "vitejs/vite#23394"),
    ("infra", "vitejs/vite#23051"),
    ("infra", "mastodon/mastodon#38772"),
    ("infra", "mastodon/mastodon#39014"),
    ("infra", "saleor/saleor#19057"),
    ("refactor", "rails/rails#58420"),
    ("refactor", "rails/rails#58239"),
    ("refactor", "tokio-rs/axum#3743"),
    ("refactor", "tokio-rs/axum#3332"),
    ("refactor", "gin-gonic/gin#4529"),
    ("money", "saleor/saleor#19746"),
    ("money", "saleor/saleor#19552"),
    ("money", "medusajs/medusa#16722"),
    ("money", "medusajs/medusa#16228"),
    ("concurrency", "rails/rails#57363"),
    ("concurrency", "rails/rails#57478"),
    ("concurrency", "caddyserver/caddy#4274"),
    ("breaking", "vitejs/vite#19255"),
    ("breaking", "vitejs/vite#19349"),
    ("breaking", "rails/rails#56777"),
    ("breaking", "rails/rails#56518"),
    ("tests", "expressjs/express#7037"),
    ("tests", "gin-gonic/gin#4699"),
    ("tests", "gin-gonic/gin#4571"),
    ("delete", "mastodon/mastodon#40394"),
    ("delete", "mastodon/mastodon#40063"),
    ("delete", "saleor/saleor#19574"),
    ("delete", "saleor/saleor#19312"),
]


def _url(slug: str) -> str:
    repo, n = slug.split("#")
    return f"{G}{repo}/pull/{n}"


def _splits() -> dict[str, str]:
    """Estratificado e determinístico: independe da ordem da lista e do que o fetch devolver."""
    out: dict[str, str] = {}
    i = 0  # contador corre entre estratos: estrato ímpar não dá sempre o PR extra pro treino
    for hint in sorted({h for h, _ in PRS}):
        slugs = sorted(
            (s for h, s in PRS if h == hint), key=lambda s: hashlib.sha256(s.encode()).hexdigest()
        )
        for s in slugs:
            out[s] = "train" if i % 2 == 0 else "test"
            i += 1
    return out


async def build() -> None:
    from dataclasses import asdict

    from jevomatic_api.github import fetch_pr, parse_pr_url
    from jevomatic_api.state import build_state, runtime_files

    splits, ok = _splits(), 0
    for i, (hint, slug) in enumerate(PRS, 1):
        try:
            pr = await fetch_pr(parse_pr_url(_url(slug)))
        except Exception as e:  # noqa: BLE001 — registra e segue; o PR fica fora do dataset
            print(f"✗ {slug}: {e}", file=sys.stderr)
            continue
        built = build_state(pr)
        row = {
            "id": f"p{i:03d}",
            "slug": slug,
            "url": _url(slug),
            "hint": hint,
            "split": splits[slug],
            "title": pr.title,
            "head_sha": pr.head_sha,
            "files_changed": pr.changed_files,
            "additions": pr.additions,
            "deletions": pr.deletions,
            "categories": built.categories,
            "runtime_files": runtime_files(built.categories),
            "sent": asdict(built.sent),
            "state": built.state,
        }
        print(json.dumps(row, ensure_ascii=False))
        ok += 1
        print(
            f"✓ {row['id']} {slug} [{hint}/{row['split']}] {pr.changed_files} arq", file=sys.stderr
        )
    print(f"{ok}/{len(PRS)} gravados", file=sys.stderr)


def stats() -> None:
    path = Path(__file__).resolve().parent / f"{VERSION}.jsonl"
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    print(f"{path.name}: {len(rows)} PRs · {len({r['slug'].split('#')[0] for r in rows})} repos")
    print("split:", dict(Counter(r["split"] for r in rows)))
    print(f"{'estrato':<12} train test")
    for hint in sorted({r["hint"] for r in rows}):
        c = Counter(r["split"] for r in rows if r["hint"] == hint)
        print(f"  {hint:<10} {c['train']:>5} {c['test']:>4}")
    print("repos:", dict(Counter(r["slug"].split("#")[0] for r in rows).most_common()))
    sizes = sorted(r["files_changed"] for r in rows)
    trunc = sum(1 for r in rows if r["sent"]["files_omitted"] or r["sent"]["files_truncated"])
    print(
        f"arquivos por PR: mediana {sizes[len(sizes) // 2]}, máx {sizes[-1]} · {trunc} com algo omitido/truncado no state"
    )
    print(
        f"sem código de produção (fast possível): {sum(1 for r in rows if r['runtime_files'] == 0)}"
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--stats"]:
        stats()
    else:
        asyncio.run(build())
