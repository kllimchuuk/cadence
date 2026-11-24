import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "commit_gate.py"


def load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("commit_gate", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_hook(command: str, tool_name: str = "Bash") -> subprocess.CompletedProcess[str]:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "feat: x"',
        "git add backend/src/a.py && git commit -m x",
        "git -C /repo commit -m x",
        "cd backend; git commit -m x",
    ],
)
def test_commit_commands_are_detected(command: str) -> None:
    assert load_hook().is_commit(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git log --format='%h %s'",
        "git show HEAD:docs/commit.md",
        "echo git-commit",
        "git add backend/src/commit.py",
    ],
)
def test_other_commands_are_not_commits(command: str) -> None:
    assert not load_hook().is_commit(command)


@pytest.mark.parametrize(
    "command",
    ["git status --short", "git add backend/src/a.py"],
)
def test_non_commit_commands_pass_without_running_checks(command: str) -> None:
    result = run_hook(command)

    assert result.returncode == 0
    assert result.stderr == ""


def test_other_tools_pass() -> None:
    assert run_hook("git commit -m x", tool_name="Read").returncode == 0


def test_failing_check_is_reported_with_its_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = load_hook()
    monkeypatch.setattr(
        hook,
        "checks",
        lambda: [[sys.executable, "-c", "print('boom'); raise SystemExit(1)"]],
    )

    failure = hook.run_checks()

    assert failure is not None
    assert "boom" in failure


def test_passing_checks_report_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = load_hook()
    monkeypatch.setattr(hook, "checks", lambda: [[sys.executable, "-c", "pass"]])

    assert hook.run_checks() is None


def test_commit_is_blocked_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    hook = load_hook()
    monkeypatch.setattr(hook, "run_checks", lambda: "pytest failed:\n1 failed")
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as exit_info:
        hook.main()

    assert exit_info.value.code == 2
    assert "Blocked by the commit gate" in capsys.readouterr().err


def test_commit_passes_when_checks_are_green(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = load_hook()
    monkeypatch.setattr(hook, "run_checks", lambda: None)
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    hook.main()
