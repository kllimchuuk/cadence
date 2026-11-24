#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
BACKEND = REPOSITORY / "backend"
CHECKED_PATHS = ("backend", ".claude/hooks")
TAIL_LINES = 40

SEPARATORS = {"&&", "||", ";", ";;", "|", "|&", "&", "(", ")", ">", ">>", "<"}
WRAPPERS = {"env", "command", "time", "nohup", "{", "}", "!"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
GLOBAL_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}

SECRET_NAMES = {".env", "settings.local.json"}
MASS_PATHSPECS = {".", "./", "..", ":", ":/"}
ADD_FORBIDDEN_LONG = {
    "--all",
    "--update",
    "--force",
    "--no-ignore-removal",
    "--pathspec-from-file",
}
ADD_FORBIDDEN_SHORT = set("Auf")
COMMIT_FORBIDDEN_LONG = {
    "--amend",
    "--all",
    "--only",
    "--include",
    "--pathspec-from-file",
}
COMMIT_FORBIDDEN_SHORT = set("aoi")
COMMIT_SHORT_WITH_VALUE = set("mFCct")
COMMIT_SHORT_WITH_ATTACHED_VALUE = set("uS")
COMMIT_LONG_WITH_VALUE = {
    "--message",
    "--file",
    "--reuse-message",
    "--reedit-message",
    "--template",
    "--author",
    "--date",
    "--fixup",
    "--squash",
    "--trailer",
    "--cleanup",
}
SWITCH_FORBIDDEN_LONG = {"--force", "--discard-changes"}


def tokens(command: str) -> list[str]:
    text = command.replace("\\\n", " ").replace("\n", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def segments(words: list[str]) -> list[list[str]]:
    result: list[list[str]] = [[]]
    for word in words:
        if word in SEPARATORS:
            result.append([])
        else:
            result[-1].append(word)
    return [segment for segment in result if segment]


def git_calls(command: str) -> list[tuple[str, list[str]]]:
    calls = []
    for segment in segments(tokens(command)):
        words = list(segment)
        while words and (words[0] in WRAPPERS or ASSIGNMENT.match(words[0])):
            words.pop(0)
        if not words or Path(words[0]).name != "git":
            continue
        rest = words[1:]
        while rest and rest[0].startswith("-"):
            option = rest.pop(0)
            if option in GLOBAL_OPTIONS_WITH_VALUE and rest:
                rest.pop(0)
        if rest:
            calls.append((rest[0], rest[1:]))
    return calls


def is_secret(path: str) -> bool:
    return Path(path).name in SECRET_NAMES


def abbreviates(argument: str, options: set[str]) -> bool:
    name = argument.split("=")[0]
    return len(name) > 2 and any(option.startswith(name) for option in options)


def add_problem(arguments: list[str]) -> str | None:
    paths_only = False
    for argument in arguments:
        if argument == "--":
            paths_only = True
        elif not paths_only and argument.startswith("--"):
            if abbreviates(argument, ADD_FORBIDDEN_LONG):
                return f"git add {argument} stages more than the named paths"
        elif not paths_only and argument.startswith("-") and len(argument) > 1:
            if ADD_FORBIDDEN_SHORT & set(argument[1:]):
                return f"git add {argument} stages more than the named paths"
        elif argument in MASS_PATHSPECS or argument.startswith(":"):
            return f"pathspec {argument!r} is not an explicit path"
        elif "*" in argument or "?" in argument:
            return f"pathspec {argument!r} is a glob, not an explicit path"
        elif is_secret(argument):
            return f"{argument} must never be staged"
    return None


def commit_problem(arguments: list[str]) -> str | None:
    partial = (
        "commits something other than the staged tree the checks run on; "
        "stage exactly what the commit needs and commit without paths"
    )
    remaining = iter(arguments)
    for argument in remaining:
        if argument == "--":
            if next(remaining, None) is not None:
                return f"git commit with paths {partial}"
            break
        if argument.startswith("--"):
            if abbreviates(argument, {"--amend"}):
                return "git commit --amend rewrites history; ask the owner"
            if abbreviates(argument, COMMIT_FORBIDDEN_LONG):
                return f"git commit {argument.split('=')[0]} {partial}"
            if abbreviates(argument, COMMIT_LONG_WITH_VALUE) and "=" not in argument:
                next(remaining, None)
        elif argument.startswith("-") and len(argument) > 1:
            flags = argument[1:]
            for index, flag in enumerate(flags):
                if flag in COMMIT_FORBIDDEN_SHORT:
                    return f"git commit -{flag} {partial}"
                if flag in COMMIT_SHORT_WITH_ATTACHED_VALUE:
                    break
                if flag in COMMIT_SHORT_WITH_VALUE:
                    if index == len(flags) - 1:
                        next(remaining, None)
                    break
        else:
            return f"git commit with paths {partial}"
    return None


def switch_problem(arguments: list[str]) -> str | None:
    for argument in arguments:
        if (
            argument.startswith("--") and abbreviates(argument, SWITCH_FORBIDDEN_LONG)
        ) or (
            argument.startswith("-")
            and not argument.startswith("--")
            and "f" in argument[1:]
        ):
            return f"git switch {argument} discards uncommitted work; ask the owner"
    return None


PROBLEMS = {"add": add_problem, "commit": commit_problem, "switch": switch_problem}


def git_lines(*arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def staged_paths() -> list[str]:
    return git_lines("diff", "--cached", "--name-only")


def dirty_paths() -> list[str]:
    return git_lines("diff", "--name-only", "--", *CHECKED_PATHS) + git_lines(
        "ls-files", "--others", "--exclude-standard", "--", *CHECKED_PATHS
    )


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


def commit_state_problem() -> str | None:
    secrets = [path for path in staged_paths() if is_secret(path)]
    if secrets:
        return f"staged files that must never be committed: {', '.join(secrets)}"
    dirty = dirty_paths()
    if dirty:
        return (
            "files under backend/ or .claude/hooks/ are changed but not staged, so "
            f"the checks would not see the commit as it is: {', '.join(dirty)}. "
            "Stage them in a separate command before committing, or ask the owner"
        )
    failure = run_checks()
    if failure is not None:
        return f"every commit must be green (black --check, flake8, pytest). {failure}"
    return None


def inspect(command: str) -> str | None:
    calls = git_calls(command)
    for subcommand, arguments in calls:
        check = PROBLEMS.get(subcommand)
        problem = check(arguments) if check else None
        if problem is not None:
            return problem
    if any(subcommand == "commit" for subcommand, _ in calls):
        return commit_state_problem()
    return None


def main() -> None:
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name") != "Bash":
            return
        command = event.get("tool_input", {}).get("command", "")
        if "git" not in command:
            return
        problem = inspect(command)
    except Exception as error:
        problem = (
            f"the guard could not check this command ({type(error).__name__}: "
            f"{error}); split it into simpler commands"
        )
    if problem is not None:
        print(f"Blocked by the commit gate: {problem}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
