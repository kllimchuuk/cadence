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


@pytest.fixture
def hook(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = load_hook()
    monkeypatch.setattr(module, "run_checks", lambda: pytest.fail("checks ran"))
    monkeypatch.setattr(module, "dirty_paths", lambda: [])
    monkeypatch.setattr(module, "staged_paths", lambda: [])
    return module


def run_main(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    tool_name: str = "Bash",
) -> int:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    try:
        hook.main()
    except SystemExit as exit_info:
        return exit_info.code
    return 0


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "feat: x"',
        "git add backend/src/a.py && git commit -m x",
        "git -C /repo commit -m x",
        "cd backend; git commit -m x",
        "cd backend\ngit commit -m x",
        "cd backend && \\\n  git commit -m x",
        "   git commit -m x",
        "git -c user.name=x commit -m x",
        "git --no-pager commit -m x",
        "GIT_EDITOR=true git commit -m x",
        "env git commit -m x",
        "{ git commit -m x; }",
        "git commit -m \"$(printf 'a\\nb')\"",
    ],
)
def test_commit_commands_are_detected(command: str) -> None:
    assert "commit" in [call[0] for call in load_hook().git_calls(command)]


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git log --format='%h %s'",
        "git show HEAD:docs/commit.md",
        "echo git-commit",
        "git add backend/src/commit.py",
        'git log --grep="x; git commit"',
        "git commit-tree HEAD^{tree}",
    ],
)
def test_other_commands_are_not_commits(command: str) -> None:
    assert "commit" not in [call[0] for call in load_hook().git_calls(command)]


@pytest.mark.parametrize(
    "command",
    ["ls", "git status --short", "git add backend/src/a.py"],
)
def test_harmless_commands_pass_without_checks(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 0


def test_other_tools_pass(hook: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_main(hook, monkeypatch, "git commit -m x", tool_name="Read") == 0


def test_script_runs_standalone() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "git add .",
        "git add ./",
        "git add -- .",
        "git add :/",
        "git add -A",
        "git add --all",
        "git add -u",
        "git add --update",
        "git add -f backend/src/a.py",
        "git add --force backend/src/a.py",
        "git add backend/.env",
        "git add .env",
        "git add .claude/settings.local.json",
        "git add 'backend/src/*.py'",
        "cd backend && git add -A",
    ],
)
def test_mass_or_secret_staging_is_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git add .claude/settings.json",
        "git add backend/src/a.py backend/tests/test_a.py",
        "git add backend/.env.example",
        "git add docs/",
    ],
)
def test_explicit_paths_can_be_staged(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 0


@pytest.mark.parametrize(
    "command",
    [
        "git commit --amend",
        'git commit -m "fix" --amend',
        "git commit --no-edit --amend",
        "git commit -a -m x",
        "git commit -m x -a",
        "git commit -qam x",
        "git commit -am x",
        "git commit --all -m x",
    ],
)
def test_amend_and_commit_all_are_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "a change"',
        "git commit -m all",
        "git commit -mall",
        'git commit -q -m "x" -m "Co-Authored-By: a"',
    ],
)
def test_message_text_is_not_read_as_flags(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr(hook, "run_checks", lambda: None)

    assert run_main(hook, monkeypatch, command) == 0


@pytest.mark.parametrize(
    "command",
    [
        "git switch -f main",
        "git switch --force main",
        "git switch --discard-changes main",
        "git switch -c feat/x --discard-changes",
    ],
)
def test_switch_that_drops_work_is_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


def test_switch_to_a_new_branch_passes(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_main(hook, monkeypatch, "git switch -c feat/x origin/main") == 0


@pytest.mark.parametrize(
    "staged",
    [["backend/.env"], [".env"], [".claude/settings.local.json"]],
)
def test_commit_with_a_staged_secret_is_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, staged: list[str]
) -> None:
    monkeypatch.setattr(hook, "staged_paths", lambda: staged)

    assert run_main(hook, monkeypatch, "git commit -m x") == 2


def test_commit_with_unstaged_backend_changes_is_blocked(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(hook, "dirty_paths", lambda: ["backend/src/x/helpers.py"])

    assert run_main(hook, monkeypatch, "git commit -m x") == 2
    assert "backend/src/x/helpers.py" in capsys.readouterr().err


def test_commit_is_blocked_when_a_check_fails(
    hook: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(hook, "run_checks", lambda: "pytest failed:\n1 failed")

    assert run_main(hook, monkeypatch, "git commit -m x") == 2
    assert "Blocked by the commit gate" in capsys.readouterr().err


def test_commit_passes_when_checks_are_green(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hook, "run_checks", lambda: None)

    assert run_main(hook, monkeypatch, "git commit -m x") == 0


def test_missing_check_binary_blocks_the_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = load_hook()
    monkeypatch.setattr(hook, "dirty_paths", lambda: [])
    monkeypatch.setattr(hook, "staged_paths", lambda: [])
    monkeypatch.setattr(hook, "checks", lambda: [["/nonexistent/black", "--check"]])

    assert run_main(hook, monkeypatch, "git commit -m x") == 2


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


@pytest.mark.parametrize(
    "command",
    ['git commit -m "unbalanced', "git add 'a.py"],
)
def test_unparsable_git_command_is_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git commit --amen -m x",
        "git commit --am -m x",
        "git commit --al -m x",
        "git add --forc backend/src/a.py",
        "git add --upd",
        "git add --pathspec-from-file=list.txt",
        "git add --pathspec-from-file list.txt",
        "git commit --pathspec-from-file=list.txt -m x",
        "git switch --discard main",
        "git switch --forc main",
    ],
)
def test_abbreviated_and_file_fed_options_are_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x backend/src/a.py",
        "git commit -m x -- backend/src/a.py",
        "git commit -o -m x backend/src/a.py",
        "git commit --only -m x",
        "git commit -i -m x backend/src/a.py",
        "git commit --include -m x",
    ],
)
def test_commit_limited_to_paths_is_blocked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git commit --mess x",
        "git commit -uall -m x",
        "git commit -q --no-verify --author 'A <a@b.c>' -m x",
        "git commit -q -m \"$(cat <<'EOF'\nfix: x\n\nCo-Authored-By: A <a@b.c>\nEOF\n)\"",
        'git commit -q -m "fix: address review\n\nCo-Authored-By: A <a@b.c>"',
    ],
)
def test_ordinary_commits_pass(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr(hook, "run_checks", lambda: None)

    assert run_main(hook, monkeypatch, command) == 0


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x 2>/dev/null --amend",
        "git commit -m x > out backend/a.py",
        "git commit -m x >/dev/null backend/src/a.py",
        "git add a.py > out .",
        "git add a.py 2>&1 -A",
    ],
)
def test_arguments_after_a_redirection_are_still_checked(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    assert run_main(hook, monkeypatch, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x 2>&1 | tail -20",
        "git commit -m x 2>/dev/null",
        "git commit -m x &> out",
        "git commit -q -m x >> log.txt",
        "git commit -F - <<'EOF'\nfix: x\nEOF",
    ],
)
def test_redirections_are_not_read_as_paths(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setattr(hook, "run_checks", lambda: None)

    assert run_main(hook, monkeypatch, command) == 0


def test_invalid_event_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = load_hook()
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    with pytest.raises(SystemExit) as exit_info:
        hook.main()

    assert exit_info.value.code == 2


def git(repository: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repository, check=True, capture_output=True)


def test_git_queries_report_staged_unstaged_and_untracked_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hook = load_hook()
    git(tmp_path, "init", "-q")
    (tmp_path / "backend").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "backend" / "tracked.py").write_text("a = 1\n")
    (tmp_path / "backend" / "staged.py").write_text("b = 1\n")
    git(tmp_path, "add", "backend/tracked.py", "backend/staged.py")
    (tmp_path / "backend" / "tracked.py").write_text("a = 2\n")
    (tmp_path / "backend" / "new.py").write_text("c = 1\n")
    (tmp_path / "docs" / "notes.md").write_text("x\n")
    monkeypatch.setattr(hook, "REPOSITORY", tmp_path)

    assert hook.staged_paths() == ["backend/staged.py", "backend/tracked.py"]
    assert sorted(hook.dirty_paths()) == ["backend/new.py", "backend/tracked.py"]
