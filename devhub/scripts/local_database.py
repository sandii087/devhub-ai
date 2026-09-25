"""Start a development-only PostgreSQL instance without Docker.

Requires the optional local-postgres extra. This binary is a local convenience,
not the production PostgreSQL distribution. Data stays under .local/.
"""

from pathlib import Path

import pgserver
import os
import subprocess
import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
local = ROOT / ".local"
local.mkdir(exist_ok=True)
binary = Path(pgserver.__file__).parent / "pginstall" / "bin"
data = local / "postgres"
socket = Path(f"/private/tmp/devhub-pg-{os.getuid()}")
socket.mkdir(mode=0o700, exist_ok=True)
if not (data / "PG_VERSION").exists():
    subprocess.run([str(binary / "initdb"), "-D", str(data), "-U", "postgres", "-A", "trust"], check=True)
status = subprocess.run([str(binary / "pg_ctl"), "-D", str(data), "status"], capture_output=True)
if status.returncode:
    subprocess.run(
        [
            str(binary / "pg_ctl"),
            "-D",
            str(data),
            "-l",
            str(data / "log"),
            "-o",
            f"-h '' -k {socket} -p 55432",
            "-w",
            "start",
        ],
        check=True,
    )


def uri(database):
    return f"postgresql://postgres@/{database}?host={socket}&port=55432"


with psycopg.connect(uri("postgres"), autocommit=True) as conn:
    for database in ("devhub", "devhub_test"):
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
url = uri("devhub").replace("postgresql://", "postgresql+psycopg://")
test_url = uri("devhub_test").replace("postgresql://", "postgresql+psycopg://")
(local / "database.env").write_text(f"DATABASE_URL={url}\nTEST_DATABASE_URL={test_url}\n", encoding="utf-8")
print("Local PostgreSQL ready. Connection configuration: .local/database.env")
