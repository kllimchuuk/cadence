import importlib.util
import io
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


def run_main_with_black(
    monkeypatch: pytest.MonkeyPatch, returncode: int
) -> list[list[str]]:
    hook = load_hook()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess:
        calls.append(command)
        return subprocess.CompletedProcess(command, returncode, "", "cannot parse")

    path = BACKEND / "src" / "main.py"
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(path)}}
    monkeypatch.setattr(hook.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    hook.main()
    return calls


def test_edited_backend_file_is_passed_to_black(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = run_main_with_black(monkeypatch, returncode=0)

    assert calls == [
        [
            str(BACKEND / ".venv" / "bin" / "black"),
            "-q",
            str(BACKEND / "src" / "main.py"),
        ]
    ]


def test_black_failure_is_reported_to_the_agent(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_main_with_black(monkeypatch, returncode=123)

    assert exit_info.value.code == 2
    assert "cannot parse" in capsys.readouterr().err
