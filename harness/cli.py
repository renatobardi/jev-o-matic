"""uv run lab <n>  → roda labs/<n>_*/run.py"""

import importlib
import sys
from pathlib import Path

LABS = Path(__file__).resolve().parent.parent / "labs"


def main() -> None:
    avail = sorted(p.name for p in LABS.iterdir() if p.is_dir() and (p / "run.py").exists())
    if len(sys.argv) < 2:
        print("uso: uv run lab <n>\nlabs:", *avail, sep="\n  ")
        raise SystemExit(1)
    n = sys.argv[1].zfill(2)
    match = [a for a in avail if a.startswith(n)]
    if not match:
        raise SystemExit(f"lab {n} não existe. disponíveis: {avail}")
    importlib.import_module(f"labs.{match[0]}.run").main()


if __name__ == "__main__":
    main()
