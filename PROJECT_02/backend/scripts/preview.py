"""One-command local preview: a demo library + the built UI at http://127.0.0.1:8002

    python PROJECT_02/backend/scripts/preview.py            (from anywhere, with the backend venv)

Uses a separate database (data/demo.db) so your real library is never touched, and
re-creates the demo account on every start. Demo sign-in details are documented at the
top of scripts/seed_demo.py. Build the UI once first: cd PROJECT_02/frontend && npm run build
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import DATA_DIR, PROJECT_DIR  # noqa: E402

os.environ.setdefault("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'demo.db').as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stacks with demo data")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    if not (PROJECT_DIR / "frontend" / "dist" / "index.html").exists():
        print("The UI is not built yet. Run:  cd PROJECT_02/frontend && npm install && npm run build")
        return 1

    import uvicorn

    from app.main import create_app
    from scripts import seed_demo

    seed_demo.main()
    print(f"Preview running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
