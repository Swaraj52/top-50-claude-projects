"""One-command local preview: demo data + the built UI at http://127.0.0.1:8007

    python PROJECT_07/backend/scripts/preview.py            (from anywhere, with the backend venv)

Uses a separate database (data/demo.db) so a real desk is never touched, and re-creates the demo
account on every start. Demo sign-in details are at the top of scripts/seed_demo.py.
No build step: the UI is server-rendered.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import DATA_DIR  # noqa: E402

os.environ.setdefault("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'demo.db').as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Switchboard with demo data")
    parser.add_argument("--port", type=int, default=8007)
    args = parser.parse_args()
    import uvicorn

    from app.main import create_app
    from scripts import seed_demo

    seed_demo.seed()
    app = create_app()
    print(f"Switchboard on http://127.0.0.1:{args.port}  (demo: {seed_demo.DEMO_EMAIL} / {seed_demo.DEMO_PASSWORD})")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
