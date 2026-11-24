---
name: verify
description: Runs the real Cadence backend and drives it end to end (register, the read endpoints, and optionally one live practice conversation over the WebSocket). Use after the checks pass and before committing any change to behavior in backend/src, and whenever asked to confirm a change works in the running app rather than only in tests. Not needed for docs-only or test-only changes.
---

# Verify the running app

Tests can pass while the app is broken: a missing migration on the dev database, a dependency wired wrong in `main.py`, a cookie that never arrives. This skill boots the backend and uses it like a client. Run every step from `backend/`.

1. **Database.** `docker compose ps` must show `db` healthy; otherwise `docker compose up -d` from the repository root. Then compare `PYTHONPATH=$PWD/src .venv/bin/alembic current` with `.venv/bin/alembic heads`; if they differ, run `alembic upgrade head` and say so in the report.
2. **Boot.** Start `PYTHONPATH=$PWD/src .venv/bin/uvicorn main:app --port 8001 --app-dir src` in the background, logging to a file in the scratchpad. Port 8001 keeps the owner's dev server on 8000 free. Wait until `curl -s http://localhost:8001/docs` answers.
3. **Drive.** Run `.venv/bin/python -I ../.claude/skills/verify/smoke.py`. It checks that `/auth/me` is 401 without a cookie, registers a fresh `verify+<timestamp>@example.com` user, and expects 200 from `/auth/me`, `/scenarios`, `/scenarios/recommendation`, `/sessions`, `/weaknesses` and `/progress`.
4. **Conversation.** If the change touches `realtime/`, `orchestration/`, `llm/`, `analysis/`, `persona/`, `weaknesses/` or `scenarios/`, add `--conversation`. It opens a practice session, sends one learner turn, ends the session and waits for `session_ended` with `completed`, then `analysis_ready` or `analysis_failed`. This calls Gemini for real and costs tokens.
5. **Read the log.** On any failure open the server log and find the traceback before touching code. A provider timeout (`LLMUnavailableError`) is an environment problem, not a pass: report the step as not verified.
6. **Stop** the server.

The script leaves the registered user in the dev database; that is expected.

If verification still fails after three rounds of fixes, stop and hand over to the owner with what you tried. Report what you ran and every status line the script printed under "Numbers"; never report a step as passed if it did not run.
