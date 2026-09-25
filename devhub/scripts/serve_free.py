"""Supervise the web API and an optional worker in a single sleeping free instance.

Migrations run separately with an owner credential. No secrets are logged.
"""

import os
import signal
import subprocess
import sys
import time


def main():
    port = int(os.getenv("PORT", "10000"))
    if not 1024 <= port <= 65535:
        raise SystemExit("PORT must be an unprivileged TCP port")
    processes = []
    stopping = False

    def stop(*args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        api_env = dict(os.environ, PROCESS_ROLE="api")
        api_env.pop("WORKER_DATABASE_URL", None)
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "devhub.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(port),
                    "--no-access-log",
                    "--no-proxy-headers",
                ],
                env=api_env,
            )
        )
        if os.getenv("WORKER_DATABASE_URL"):
            worker_env = dict(
                os.environ, PROCESS_ROLE="worker", DATABASE_URL=os.environ["WORKER_DATABASE_URL"]
            )
            for key in ("WORKER_DATABASE_URL", "OIDC_CLIENT_SECRET", "OPENAI_API_KEY"):
                worker_env.pop(key, None)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "devhub.worker",
                        "--interval",
                        "60",
                    ],
                    env=worker_env,
                )
            )
        while not stopping and all(process.poll() is None for process in processes):
            time.sleep(1)
        return 0 if stopping else 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
