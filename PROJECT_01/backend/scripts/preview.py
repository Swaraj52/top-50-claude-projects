"""One-command local preview: fresh demo data + the built UI at http://127.0.0.1:8001

    python PROJECT_01/backend/scripts/preview.py            (from anywhere)
    python PROJECT_01/backend/scripts/preview.py --tz Europe/London --port 8001

Uses a separate database (data/demo.db) so your real data is never touched, and
re-creates the demo account on every start so "today" always has something in it.
Demo sign-in details are documented at the top of scripts/seed_demo.py.
Requires the frontend to be built once: `cd PROJECT_01/frontend && npm run build`.
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
    parser = argparse.ArgumentParser(description="Run Daybook with demo data")
    parser.add_argument("--tz", default="Asia/Kolkata", help="timezone of the demo user")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if not (PROJECT_DIR / "frontend" / "dist" / "index.html").exists():
        print("The UI is not built yet. Run:  cd PROJECT_01/frontend && npm install && npm run build")
        return 1

    import uvicorn

    from app.main import create_app
    from scripts import seed_demo

    sys.argv = [sys.argv[0], "--tz", args.tz]
    seed_demo.main()
    print(f"Preview running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
