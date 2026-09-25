"""Scan tracked DevHub sources using a reviewed baseline of local/test placeholders."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
files = (
    subprocess.check_output(
        ["git", "ls-files", "-z", "--", "devhub", ".github/workflows/devhub-*.yml"], cwd=root
    )
    .decode()
    .split("\0")
)
files = [name for name in files if name and name != "devhub/.secrets.baseline"]
raise SystemExit(
    subprocess.call(
        [
            str(Path(sys.executable).parent / "detect-secrets-hook"),
            "--baseline",
            "devhub/.secrets.baseline",
            *files,
        ],
        cwd=root,
    )
)
