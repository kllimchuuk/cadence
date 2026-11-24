import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
HOOK = REPOSITORY / ".claude" / "hooks" / "format_python.py"
BACKEND = REPOSITORY / "backend"


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("format_python", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "path",
    [
        BACKEND / "src" / "main.py",
        BACKEND / "tests" / "conftest.py",
    ],
)
def test_backend_python_files_are_formatted(path: Path) -> None:
    assert load_hook().target(str(path)) == path


@pytest.mark.parametrize(
    "path",
    [
        REPOSITORY / "CLAUDE.md",
        REPOSITORY / ".claude" / "hooks" / "commit_gate.py",
        BACKEND / "src" / "missing_module.py",
        Path("/tmp/elsewhere.py"),
    ],
)
def test_other_files_are_left_alone(path: Path) -> None:
    assert load_hook().target(str(path)) is None


def test_hook_ignores_files_outside_the_backend() -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(HOOK)}}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
