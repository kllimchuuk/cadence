#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
COMMIT = re.compile(r"(?:^|[;&|(]\s*)git(?:\s+-C\s+\S+)?\s+commit\b")
TAIL_LINES = 40


def is_commit(command: str) -> bool:
    return bool(COMMIT.search(command))


def checks() -> list[list[str]]:
    venv = BACKEND / ".venv" / "bin"
    return [
        [str(venv / "black"), "--check", "-q", "src", "tests", "migrations"],
        [str(venv / "flake8"), "src", "tests", "migrations"],
        [str(venv / "pytest"), "-q", "-x", "-p", "no:cacheprovider"],
    ]


def run_checks() -> str | None:
    environment = {**os.environ, "PYTHONPATH": str(BACKEND / "src")}
    for command in checks():
        result = subprocess.run(
            command,
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip().splitlines()
            tail = "\n".join(output[-TAIL_LINES:])
            return f"{Path(command[0]).name} failed:\n{tail}"
    return None


def main() -> None:
    event = json.load(sys.stdin)
    if event.get("tool_name") != "Bash":
        return
    if not is_commit(event.get("tool_input", {}).get("command", "")):
        return
    failure = run_checks()
    if failure is not None:
        print(
            "Blocked by the commit gate: every commit must be green "
            f"(black --check, flake8, pytest). {failure}",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
