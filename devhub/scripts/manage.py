"""Local-only commands, with configuration loaded before importing the app."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
os.chdir(root)
values = {**dotenv_values(root / ".env"), **dotenv_values(root / ".local/database.env")}
for key, value in values.items():
    if value is not None:
        os.environ.setdefault(key, value)
parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["migrate", "test", "serve", "worker", "check-schema"])
args, extra = parser.parse_known_args()
if args.command == "migrate":
    for key in ("DATABASE_URL", "TEST_DATABASE_URL"):
        if os.getenv(key):
            subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
                env=dict(os.environ, DATABASE_URL=os.environ[key]),
                check=True,
            )
elif args.command == "test":
    if not os.getenv("TEST_DATABASE_URL"):
        raise SystemExit("Set TEST_DATABASE_URL to an isolated PostgreSQL database first")
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *(extra or ["-q"])], env=os.environ))
elif args.command == "check-schema":
    raise SystemExit(subprocess.call([sys.executable, "scripts/check_migrations.py"]))
elif args.command == "serve":
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "devhub.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
                *extra,
            ]
        )
    )
else:
    raise SystemExit(subprocess.call([sys.executable, "-m", "devhub.worker", *extra]))
