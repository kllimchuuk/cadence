---
name: invariants-check
description: Checklist of the Cadence invariants (SPEC §5) with concrete things to look for in code and tests. Use when reviewing a diff, before committing changes to repositories, the session graphs, weakness or persona logic, analysis, the WebSocket layer or the LLM client, or when asked whether a change is safe.
---

# Invariant checklist

Start from `git diff origin/main...HEAD --name-only`. Check an invariant in depth only when a changed path matches its trigger; mark the others "not touched" and name the trigger that did not fire. For each checked item answer pass or fail and point at the code or test that proves it. The source is `docs/SPEC.md` §5; tests are listed in §12.

| ID | Triggered by a change in | Look for | Red flag |
|---|---|---|---|
| I1 | any `repository.py`, `*/dependencies.py`, `*/router.py`, `auth/` | Every learner-owned repository query has `.where(Model.user_id == user_id)`; every service call passes the authenticated user's id. | A repository method on a learner aggregate with no `user_id`; `user_id` read from a request body or a path; a lookup by `id` alone. |
| I2 | `weaknesses/`, `analysis/schemas.py`, `orchestration/nodes/weakness_state_update.py`, `orchestration/prompts.py` | Weakness state changes live in `weaknesses/service.py` as plain functions of structured results. | The LLM schema carrying a "mastered" or "state" field that is stored as is; a prompt asking the model to decide mastery. |
| I3 | `weaknesses/` | Transitions follow `new -> active -> probation -> mastered`; clean uses are counted per separate session; an error on a `mastered` item reopens it. | A clean streak counted twice within one session; a skipped state; a relapse that leaves `mastered`. |
| I4 | `realtime/`, any `models.py`, `orchestration/state.py`, logging calls | Only the transcript and the structured analysis are stored. | Audio bytes or blobs in a model, a log line, a checkpoint or a temp file. |
| I5 | `orchestration/analysis_runner.py`, `orchestration/session_runner.py`, `orchestration/graph.py`, `realtime/websocket.py`, `analysis/` | The conversation finishes and is `COMPLETED` before analysis runs; analysis carries its own `analysis_status`. | The conversation graph awaiting analysis; an analysis exception changing the session status. |
| I6 | `orchestration/nodes/conversing.py`, `orchestration/graph.py`, `orchestration/context.py` | `conversing` reads the system prompt and context from graph state only. | A repository or session call inside `conversing`; context rebuilt per turn. |
| I7 | `analysis/`, `persona/`, `orchestration/nodes/session_analysis.py`, `orchestration/nodes/persona_memory_update.py`, `progress/` | Evidence is checked against the learner's turns; an unquoted item is dropped with a log line. | A finding, goal, fact or focus point stored or sent to the client with unchecked `evidence`; evidence satisfied by words only the assistant said. |
| I8 | `weaknesses/skill_keys.py`, `analysis/schemas.py`, `weaknesses/service.py` | `skill_key` is validated against the closed vocabulary for its category. | A free-form key persisted; a key accepted under another category. |
| I9 | `llm/`, `orchestration/graph.py`, any node's retry policy | Provider 429, 5xx and timeouts raise `LLMUnavailableError`; the node `RetryPolicy` covers it and `LLMResponseError`. | A raw provider exception reaching a node or the socket; a retry that repeats a database write. |
| I10 | `scenarios/`, `realtime/` | The recommendation is advice computed in the service; the scenario list stays fully selectable. | A scenario rejected because it is not the recommended one. |

Structure and safety checks that apply to every diff:

- A router containing logic (loops, conditions, reshaping the response), a model carrying derived properties or calculations, or a service building `XRepositoryImpl(session)` by hand instead of `Depends(get_x_repository)`.
- A repository that is not an ABC plus an `Impl`, or exposes generic CRUD it does not need.
- An error that is not an `AppException` subclass with a code, or a bare `pass` stub.
- A settings field with a default, or a model name that encodes a tier.
- A second Alembic migration in one PR; a model missing from `core/registry.py`; a migration that does not match the models.
- A comment in Python code (including one that explains why).
- A public class with a leading underscore; a module whose purpose is not obvious from its name and is not explained in the PR.
- Secrets, API keys, provider response bodies or full transcripts in log lines or error responses.
- A new dependency without a `docs/DECISIONS.md` entry.
- Behavior change without a test, or a test that cannot fail. For every new test name the bug that would make it fail.
- A test made to pass by a retry, a `sleep` or a skip instead of a fixed cause.
- A docs file that no longer matches the code (SPEC, DECISIONS, `CLAUDE.md`, `.claude/rules/`).

## Lessons from missed findings

A pattern goes here when the owner's PR review or a revert caught something this checklist missed, it appeared in at least two PRs, and it can be spotted from a diff. Each line names the PRs it came from. When an entry no longer applies, delete it.

None yet. The owner's conventions from the reviews of PR #7 and PR #11 are already in the structure list above.
