---
name: invariants-check
description: Checklist of the Cadence invariants (SPEC §5) with concrete things to look for in code and tests. Use when reviewing a diff, before committing changes to repositories, the session graphs, weakness or persona logic, analysis, the WebSocket layer or the LLM client, or when asked whether a change is safe.
---

# Invariant checklist

For each item answer pass, fail or not touched, and point at the code or test that proves it. The source is `docs/SPEC.md` §5; tests are listed in §12.

| ID | Look for | Red flag |
|---|---|---|
| I1 | Every learner-owned repository query has `.where(Model.user_id == user_id)`; every service call passes the authenticated user's id. | A repository method on a learner aggregate with no `user_id`; `user_id` read from a request body or a path; a lookup by `id` alone. |
| I2 | Weakness state changes live in `weaknesses/service.py` as plain functions of structured results. | The LLM schema carrying a "mastered" or "state" field that is stored as is; a prompt asking the model to decide mastery. |
| I3 | Transitions follow `new -> active -> probation -> mastered`; clean uses are counted per separate session; an error on a `mastered` item reopens it. | A clean streak counted twice within one session; a skipped state; a relapse that leaves `mastered`. |
| I4 | Only the transcript and the structured analysis are stored. | Audio bytes or blobs in a model, a log line, a checkpoint or a temp file. |
| I5 | The conversation finishes and is `COMPLETED` before analysis runs; analysis carries its own `analysis_status`. | The conversation graph awaiting analysis; an analysis exception changing the session status. |
| I6 | `conversing` reads the system prompt and context from graph state only. | A repository or session call inside `conversing`; context rebuilt per turn. |
| I7 | Evidence is checked against the learner's turns; an unquoted item is dropped with a log line. | A finding, goal, fact or focus point stored or sent to the client with unchecked `evidence`; evidence satisfied by words only the assistant said. |
| I8 | `skill_key` is validated against the closed vocabulary for its category. | A free-form key persisted; a key accepted under another category. |
| I9 | Provider 429, 5xx and timeouts raise `LLMUnavailableError`; the node `RetryPolicy` covers it and `LLMResponseError`. | A raw provider exception reaching a node or the socket; a retry that repeats a database write. |
| I10 | The recommendation is advice computed in the service; the scenario list stays fully selectable. | A scenario rejected because it is not the recommended one. |

Structure and safety checks that apply to every diff:

- A router containing logic, or a service building `XRepositoryImpl(session)` by hand instead of `Depends(get_x_repository)`.
- A repository that is not an ABC plus an `Impl`, or exposes generic CRUD it does not need.
- An error that is not an `AppException` subclass with a code, or a bare `pass` stub.
- A settings field with a default, or a model name that encodes a tier.
- A second Alembic migration in one PR; a model missing from `core/registry.py`; a migration that does not match the models.
- A comment in Python code (including one that explains why).
- Secrets, API keys, provider response bodies or full transcripts in log lines or error responses.
- A new dependency without a `docs/DECISIONS.md` entry.
- Behavior change without a test, or a test that cannot fail. For every new test name the bug that would make it fail.
- A docs file that no longer matches the code (SPEC, DECISIONS, `CLAUDE.md`).
