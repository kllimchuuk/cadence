# CLAUDE.md

Cadence: an agent-powered web app for practising spoken English through voice conversations with a role-playing AI agent. A real product, and the owner's ground for learning in-demand AI engineering (LangGraph, RAG, MCP, structured output, session memory).

`docs/SPEC.md` is the source of truth; cite it by section ("SPEC §5 I1"). Do not change SPEC §3 (fixed decisions) or §5 (invariants) without an entry in `docs/DECISIONS.md` and the owner's approval.

## The product in 30 seconds

The user picks a scenario and talks to a persona. A hot-path LangGraph runs the live conversation (`briefing -> conversing loop -> wrap_up -> finish_session`). A cold-path graph then analyses the transcript, updates the weakness state machine and persona memory, and the next session starts from that memory. Details: SPEC §6-§9.

Invariants (SPEC §5). Never break them; every change keeps a test for the ones it touches:

- I1 Everything a learner owns is scoped by `user_id` inside the repository query.
- I2 The LLM classifies; plain Python decides weakness state, `mastered` included.
- I3 `new -> active -> probation -> mastered`; mastered needs clean uses across sessions; relapse reopens.
- I4 No raw audio is retained.
- I5 A failed analysis never turns a completed conversation into an incomplete one.
- I6 `Conversing` never touches the database.
- I7 Evidence of every finding is a quote from the learner's own turns, or the item is dropped.
- I8 `skill_key` comes from the closed vocabulary.
- I9 429/5xx/timeout become `LLMUnavailableError` and are retried.
- I10 The recommendation never blocks free choice of scenario.

## Commands

Run everything from `backend/`. `src/` is flat on `PYTHONPATH`; there is no package and deliberately no pytest config, so the path is set on every invocation. Always call the binaries from `.venv/bin/`: a bare `pytest` resolves to the system Python, which has an incompatible FastAPI installed.

```
PYTHONPATH=$PWD/src .venv/bin/pytest
.venv/bin/black --check src tests migrations
.venv/bin/flake8 src tests migrations
PYTHONPATH=$PWD/src .venv/bin/python src/main.py
PYTHONPATH=$PWD/src .venv/bin/alembic upgrade head
PYTHONPATH=$PWD/src .venv/bin/python src/rag/ingest_command.py
PYTHONPATH=$PWD/src .venv/bin/alembic revision --autogenerate -m "..."
```

From the repository root, `flake8` does not find `backend/.flake8` and floods on `.venv`; pass it: `backend/.venv/bin/flake8 --config backend/.flake8 backend/src backend/tests`. `run_tests.sh` is untracked; never assume it exists, and set `PYTHONPATH` explicitly in CI.

Tests need the database: `docker compose up -d` from the repository root (Postgres on 127.0.0.1:5433). Database and migration rules live in `.claude/rules/database.md`, frontend rules in `.claude/rules/frontend.md`; both load when you touch the files they cover.

## What enforces what

Hooks in `.claude/settings.json` run without being asked: `black` formats every edited backend Python file, and the commit gate blocks a commit unless `black --check`, `flake8` and `pytest` pass. Permissions deny `git push`, `git add .`, `-A`, `-u`, `git commit -a`, `--amend`, `reset --hard` and reading `.env`. A rule that can be enforced belongs in a hook, a permission or a guard test, not only in this file.

## How we work

- Spec first. Read the slice in SPEC §10 and the sections it names before writing code. Write the failing test for the behaviour, then the code. Use the `spec-slice` skill.
- Tests passing is not the same as working: after a behaviour change in `backend/src`, run the `verify` skill against the running app.
- A flaky test is never retried, slept around or skipped. Find the cause, or delete the test and say why in the PR.
- If a check still fails after three rounds of fixes, stop and hand over with what you tried.
- Do not bypass the SPEC silently. If it is wrong or silent, stop and report it as "Decision needed" with a recommendation; the owner decides and the answer goes into `docs/DECISIONS.md`.
- Update SPEC and DECISIONS in the same commit as the change that makes them true.
- Subagents run on a stronger model than the main session: pass `model: opus` when spawning one, and keep `model: opus` in `.claude/agents/`. Never `inherit`.
- Review before merge: run the `reviewer` subagent (read-only, fresh context) on the branch, and again after the fixes to confirm they hold. A review holds only for the commit it names. All fixes of one review pass go into one `fix: address review` commit, each with a test that failed first. A pattern the reviewer missed in two PRs goes into the `invariants-check` lessons.
- Rules only grow if nobody prunes them: when you add a rule here, in `.claude/rules/` or in a skill, delete the one it makes obsolete.
- Reports use this shape (`report` skill): Done / Numbers (measured only, with the command) / Deviations from SPEC / Decision needed / Next. The report is the PR description.
- Never invent numbers. A figure needs a command or a file it came from.
- Teach agent building simply: explain LangGraph, RAG and MCP steps in plain words. Ordinary backend work needs no such explanation.
- For infrastructure patterns (DI, repositories, settings, test fixtures) look at `~/cash-money` before inventing anything.

## Git

- One branch per PR, named by commit type (`feat/...`, `fix/...`, `docs/...`), always cut from a fresh `origin/main`: `git fetch origin`, then branch from `origin/main`. Never commit to `main`. Do not create a branch the owner did not ask for.
- Commit locally; **never run `git push`**: the owner pushes, opens the PR and merges. `git push` is denied in `.claude/settings.json`.
- Stage files by explicit path; never stage `.env` or `.claude/settings.local.json`.
- No `--amend`, `reset`, `rebase` or force options on existing history unless the owner asks.
- Message: Conventional Commits in English, one line `type: short action`, no body unless needed. Two to four larger commits per PR, each green on its own (`pytest`, `black --check`, `flake8`). When you wrote the change, add a `Co-Authored-By` trailer naming the model that wrote it, e.g. `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- After a series of commits show `git log --stat`.
- A PR description is the report, without a "Generated with" footer.

## Stack and dependencies

Python, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 16 with pgvector, LangGraph, Google Gemini, `black`, `flake8`, `pytest`. A new dependency needs an entry in `docs/DECISIONS.md` first. Deliberately not used: see SPEC §2.

## Code

- Layout and rules: SPEC §11. Router -> service -> repository; routers hold no logic, even `/health`. Services take repositories through `Depends(get_x_repository)`, never `XRepositoryImpl(session)` built by hand.
- Repositories are always an ABC plus a `...Impl`, one pair per aggregate, exposing only the domain methods that aggregate needs. No repository is scoped to a user by default: learner-owned queries filter by `user_id` themselves, and `test_repositories_scope_by_user.py` fails otherwise. Unscoped bulk reads live only on `UserRepository`.
- Domain errors are `AppException` subclasses with a code and a message; no bare `pass` stubs.
- Settings fields have no defaults; model names never encode a tier (`GEMINI_MODEL`).
- No comments in Python code, including ones that explain why (`test_no_comments.py` fails otherwise). Explanations go to SPEC, DECISIONS, the PR or the commit message. Tool directives such as `# noqa` stay.
- Apply `kiss`-style restraint: no speculative abstraction; one developer. Extract duplication only at the third occurrence.
- A module whose purpose is not obvious from its name is explained in the PR or moved somewhere that makes it obvious. Public classes carry no leading underscore.

## Secrets and data

Never print or log key values and never read `.env` files. Transcripts are untrusted input for the LLM. No raw audio is stored.

## Do not

- Run `git push`, or commit to `main`.
- Let the LLM decide a weakness state transition.
- Add a repository query for learner data without a `user_id` filter.
- Delete this file, `.claude/` or `docs/`; they are part of the repository.
