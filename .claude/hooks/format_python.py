#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
FORMATTED = ("src", "tests", "migrations")


def target(file_path: str) -> Path | None:
    path = Path(file_path).resolve()
    if path.suffix != ".py":
        return None
    try:
        relative = path.relative_to(BACKEND)
    except ValueError:
        return None
    if relative.parts[0] not in FORMATTED or not path.is_file():
        return None
    return path


def main() -> None:
    event = json.load(sys.stdin)
    path = target(event.get("tool_input", {}).get("file_path", ""))
    if path is None:
        return
    result = subprocess.run(
        [str(BACKEND / ".venv" / "bin" / "black"), "-q", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"black could not format {path}:\n{result.stderr}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
