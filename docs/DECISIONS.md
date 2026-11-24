# Decisions

Each entry has a date, the decision, why, and what changed. The owner decides; proposals made by the AI agent are marked **recommendation** and apply once confirmed. Open questions live in `docs/SPEC.md` §13. Newest entries go at the bottom.

## 2026-11-24 - Working with the AI agent: adopt the helpdesk-ai-drafts workflow

Basis: owner's decision in the session of 2026-11-24, after an analysis of `~/helpdesk-ai-drafts` (`CLAUDE.md`, `.claude/`, `docs/`, git history).

1. **`docs/SPEC.md` is the source of truth; `docs/DECISIONS.md` is the decision log; both are tracked in git.**
   Why: until now the rules lived in a single `CLAUDE.md` mixing product, architecture and working rules, and the per-PR plan was replaced and lost with each PR. A numbered SPEC lets reviews and commits cite "SPEC §5 I1", and DECISIONS keeps why a choice was made.
   Changed: `docs/SPEC.md`, `docs/DECISIONS.md`, `CLAUDE.md` (now short, points to SPEC), `.gitignore`.
   Supersedes: the 2026-09-10 decision to work without `docs/`, and the standing choice to keep `CLAUDE.md` and `docs/` out of git. Those files were out of git so that no phase documents appeared in the repository; the reason no longer applies because SPEC and DECISIONS hold decisions, not a phase plan.
2. **The agent commits locally; the owner pushes.**
   Why: local commits are reversible, a push is not, and the owner reviews `git log --stat` before publishing. The agent never pushes, never amends or resets history, stages files by explicit path and branches from a fresh `origin/main`. `git push` is in `deny` in `.claude/settings.json`.
   Supersedes: "git is done by the developer, the agent gives commands as text".
3. **Commits carry `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` when the agent wrote the change.**
   Supersedes: the earlier rule of no attribution lines. The one-line subject and the habit of 2-4 larger commits per PR stay.
4. **A read-only `reviewer` subagent runs on every branch before merge, and again after the fixes.**
   Why: the author is biased towards the code they wrote; a fresh context with no conversation history catches what the author missed. It runs on Opus, with Bash restricted by a `PreToolUse` hook (`.claude/hooks/reviewer_readonly.py`), because a tool allowlist and a hook enforce while a prompt only requests. All fixes of one review pass go into one `fix: address review` commit, each with a test that failed first.
   Supersedes: "no subagent review without an explicit request". The cost concern behind that rule is answered by the reviewer's design: one agent, a preloaded checklist, a verify-before-report step and at most three unverified items. If one review pass costs more than it finds, narrow the checklist instead of dropping the review.
5. **Project-specific skills replace the eight generic ones.** `spec-slice` (the work loop), `invariants-check` (the SPEC §5 checklist) and `report` (the fixed report shape).
   Why: the model already knows SOLID, DRY and similar; their broad triggers fire on every task and they say nothing about this service. The few rules that matter live in `CLAUDE.md` "Code" and in guard tests. The old skills are kept in `~/cadence-archive/skills-generic`.
6. **Rules that can be checked by a machine are checked by a machine.** `test_no_comments.py` (no comments in Python), `test_repositories_scope_by_user.py` (every learner-owned repository method takes `user_id` and uses it), `test_reviewer_readonly_hook.py`. Settings in `.claude/settings.json` deny `git push`, force flags, `reset --hard`, `commit --amend` and reading `.env`.
   Why: a rule written only in `CLAUDE.md` is a request.
7. **Reports have a fixed shape** (Done / Numbers / Deviations from SPEC / Decision needed / Next); a number needs the command it came from. The PR description is the report.

## 2026-11-24 - Architecture choices carried over from `CLAUDE.md`

Basis: the architecture sections of the previous `CLAUDE.md`, recorded here so the reasons survive.

1. **LangGraph at the session level, in two graphs.** One reply is one LLM call and would not justify a framework; the session lifecycle is a stateful graph with conditional edges. Two graphs keep the live conversation from waiting on, or failing because of, the analysis.
2. **pgvector in the existing Postgres, no second vector database.** Plain vector search first; hybrid search (full-text plus Reciprocal Rank Fusion) and a cross-encoder re-ranker are a later upgrade over the same instance.
3. **A self-built MCP server, not a consumed one.** Hot-path tool calls are deterministic calls from the node, not LLM tool calling, which would double reply latency.
4. **Gemini through `LLMClientFactory`, Flash tier everywhere.** A node moves to Pro only after a real quality gap shows in practice, most likely `Conversing`.
5. **Weakness state is decided in Python.** The LLM classifies; it never decides "mastered". Free-form `skill_key`s would never accumulate enough clean uses, so keys come from a closed vocabulary.
6. **Not used, to avoid re-litigating:** LangSmith (use self-hosted Langfuse later), a separate vector database, a multi-layer guardrail stack, fine-tuning, LiteLLM (justified only by a live multi-provider fallback or centralised cost tracking), Kubernetes and vLLM.
7. **Planned, not yet built:** DeepEval and RAGAS, Langfuse, a light guardrail in `Conversing` that logs persona-breaking input without blocking it.

## 2026-11-25 - Tighten the agent workflow after a review of current practice

Basis: owner's decision in the session of 2026-11-25, after reading "Steering Claude Code" (claude.com, 2026-06-18), "How the Claude Code team thinks about verification" (claude.dev, 2026-11-16) and several 2026 guides on spec-driven development. What already matched (SPEC in the repository, one slice at a time, test first, one fresh reviewer, guard tests) stays as it is.

1. **A commit is gated, formatting is automatic.** A `PreToolUse` hook (`.claude/hooks/commit_gate.py`) runs `black --check`, `flake8` and `pytest` on every `git commit` and blocks it on a failure; a `PostToolUse` hook (`.claude/hooks/format_python.py`) runs `black` on every edited file under `backend/src`, `tests` and `migrations`. Both have tests.
   Why: "each commit green" and "run black" were requests in `CLAUDE.md`; a hook makes them happen every time. The suite runs in about 26 seconds, so a full run per commit is affordable.
2. **Mass staging is denied.** Permissions deny `git add .`, `-A`, `--all`, `-u`, `--update` and `git commit -a`, `-am`, `--all`. Staging by explicit path and committing stay with the agent; pushing stays with the owner (entry of 2026-11-24, item 2).
   Why: "never `git add .`" protected `.env` only as text.
3. **The reviewer judges a branch by the rules on `main`.** It reads `CLAUDE.md`, `.claude/rules/`, SPEC, DECISIONS and, when the diff touches it, the `invariants-check` checklist via `git show main:<path>`, and lists every change to a gate (`CLAUDE.md`, `.claude/`, SPEC §3 or §5, DECISIONS, guard tests) as tightening, loosening or moving a rule. A review names the commit it covers and does not count for a later one; a repeat pass starts from the earlier findings and the new commits.
   Why: a change that can edit the check judging it makes the check meaningless.
4. **A `verify` skill runs the real app.** It boots the backend on port 8001, registers a user, expects 200 from every read endpoint and, for changes on the conversation path, drives one practice session over the WebSocket. `spec-slice` runs it before committing a behavior change.
   Why: unit tests can pass while the app is broken. Its first run found the dev database one migration behind `head`.
5. **Path-scoped rules.** Database and migration rules moved to `.claude/rules/database.md`, frontend rules to `.claude/rules/frontend.md`; they load only when matching files are touched. `CLAUDE.md` keeps a pointer.
6. **The invariant checklist is triggered by the diff.** Each invariant names the paths that trigger it; the others are reported as not touched. A "Lessons from missed findings" section takes a pattern the owner's review caught when it appeared in at least two PRs and can be spotted from a diff, and entries that no longer apply are deleted.
7. **Flaky tests and stuck loops.** A flaky test is never retried, slept around or skipped; the cause is fixed or the test is deleted with a reason in the PR. A failing check gets three rounds of fixes, then the agent hands over.
8. **The commit trailer names the model that wrote the change**, e.g. `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
   Supersedes: item 3 of 2026-11-24, which named Sonnet 5.5 for every commit.
9. **Not adopted:** a commit gate that requires a review or verify run in the session, a stamp of the verification method on every commit, several reviewers in parallel, and Spec Kit or Kiro. For one developer they add process without catching more; the source itself finds tuning one reviewer better than stacking reviewers.
10. **Deferred:** property tests for the weakness state machine (I3) with Hypothesis need their own DECISIONS entry as a new dependency and go in a separate PR; LLM evals built from 20-50 real transcripts, with capability and regression sets kept apart, go into the evals slice.
