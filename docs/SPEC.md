# SPEC: Cadence

Version 2026-11-24. This file is the source of truth for what Cadence does and why. A change to any line in §3 "Fixed decisions" or §5 "Invariants" is a decision, not an implementation detail: record it in `docs/DECISIONS.md` first and get the owner's approval.

## 1. Goal and scope

An agent-powered web application for practising spoken English through realistic voice conversations with an AI agent. A real product, not a thesis. The owner also uses it to build in-demand AI-engineering skills (agentic pipelines, RAG, MCP, structured output, session memory); a technology is added when a ticket needs it, not upfront.

Core loop:

1. The user picks a scenario (job interview, stand-up, client call, ...) and talks to a role-playing voice agent. Audio in, audio out; not a text chat with a voice bolted on.
2. After the session the agent extracts what actually happened: grammar mistakes, vocabulary gaps, how much of the conversation the user carried.
3. That result is carried into the next session instead of starting cold.

Multi-user, each user with their own progress and session history. Voice (STT/TTS) is the product, but it is built last, wrapped around the already-working text pipeline (§10).

## 2. Explicitly not doing

- Pronunciation scoring (phoneme level, forced alignment): a separate acoustic-modelling problem, orthogonal to the agentic-LLM differentiator.
- A separate vocabulary or sentence-building stage; the agent is the whole product.
- A separate onboarding or level self-assessment: the first session is a diagnostic scenario through the same lifecycle.
- A content admin or scenario table: scenarios and personas are static Python config.
- Live grammar corrections during a conversation.
- Retaining raw audio.
- End-to-end speech-to-speech models: the cascade goes through a text layer.
- LangSmith, a separate vector database (Qdrant, Weaviate), a multi-layer guardrail stack, fine-tuning or LoRA, LiteLLM, Kubernetes or vLLM, CrewAI and AutoGen. Re-open only with a new concrete reason, recorded in DECISIONS.

## 3. Fixed decisions

| Area | Decision | Rationale |
|---|---|---|
| Pipeline | Cascaded STT -> LLM -> TTS through a text layer over WebSocket | the analysis and memory steps need the transcript anyway; cascade is the production default for cost, debuggability and compliance |
| Build order | Full text-only pipeline (LangGraph, RAG, MCP) first, in its target shape; voice is a later ticket that does not change the conversation service | no stripped-down version to rewrite |
| Orchestration | LangGraph at the session level, two graphs | one reply is one LLM call; the session lifecycle is the stateful graph |
| Checkpointer | Postgres checkpointer on the conversation graph only | a session survives a restart or resumes between turns |
| RAG | pgvector in the same Postgres, two corpora; plain vector search first, hybrid (full-text + RRF) and a cross-encoder re-ranker later | no second vector database |
| MCP | Self-built `cadence-mcp-server`; graph nodes are its clients | tools: `search_scenario_content`, `search_grammar_reference`, `get_active_weaknesses`, `get_persona_memory` |
| LLM | Google Gemini through `LLMClientFactory`; Flash tier for every node, a node moves to Pro only after a real quality gap shows | a Google AI Pro subscription has no API access; Pro models are not in the free API tier since 2026-04-01 |
| Data | `LearningSession`, `SessionAnalysis`, `WeaknessRecord`, `PersonaMemory`, `SessionProgress`; one repository per aggregate | static scenario content is config, not a table |
| Backend | Python, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 16 with pgvector, `black` + `flake8`, `pytest` | house style from `~/cash-money` |
| Frontend | React 19, TypeScript, Vite, Tailwind v4, shadcn/ui (base-nova, Base UI), simple feature folders under `src/features/` | mirrors the backend modules |
| Code structure | Feature packages with router, service and repository (ABC + Impl) | see §11 |

## 4. Contracts

**WebSocket** `/practice/sessions/ws` (transport in `realtime/`).

Server messages: `session_started`; per reply `assistant_delta`* then `assistant_done`; `session_ended {status}`; for a completed session `analysis_ready {focus_points}` or `analysis_failed`; then close. `assistant_done.content` is the authoritative full reply: a node retry after a mid-stream failure re-streams deltas from the start.

Each user turn resumes the graph from `interrupt()`. `end_session` asks for a graceful wind-down. A per-user active-session limit and an idle timeout apply.

**HTTP surface (dashboard reads).** `GET /scenarios`, `GET /sessions`, `GET /sessions/{id}`, `GET /weaknesses`, `GET /progress`, plus the auth routes. `user_id` comes only from authentication.

## 5. Invariants

These are what must stay true. Every change keeps a test for the ones it touches (§12).

| ID | Invariant |
|---|---|
| I1 | Every session, analysis, weakness record, persona-memory row and progress row is scoped by `user_id`; the repository query filters by it; no request reads another user's rows. |
| I2 | The LLM only classifies what happened in the transcript (an error, a clean usage). Whether a weakness changes state, including `mastered`, is decided by plain Python. |
| I3 | A weakness moves `new -> active -> probation -> mastered`; `mastered` needs several clean uses across separate sessions; a relapse reopens a mastered item. |
| I4 | No raw audio is retained: only the transcript and the structured analysis. |
| I5 | The conversation never waits on, or fails because of, the analysis: a failed analysis never turns a completed session into an incomplete one. |
| I6 | `Conversing` does not touch the database; the briefing builds the system prompt once into graph state. |
| I7 | Every skill observation, new persona fact and finding is stored or reported with a quoted `evidence` excerpt that appears in the learner's own turns; unquoted items are dropped. |
| I8 | A weakness `skill_key` comes from the closed vocabulary; free-form keys are rejected. |
| I9 | Transient provider failures (429, 5xx, timeout) become `LLMUnavailableError` and are retried by the node retry policy; they never leak raw. |
| I10 | The next-scenario recommendation follows active weaknesses but never blocks a free choice from the fixed list. |

## 6. Data model and lifecycle

Session lifecycle: choose or continue a scenario, briefing, live conversation (the agent stays in role), end, post-session analysis, a report of 2-3 focus points, memory update. A graceful in-character wind-down when the user asks to stop; an abrupt disconnect is marked incomplete, not failed.

`LearningSession.analysis_status` is `pending`, `completed` or `failed`; null for in-progress and incomplete sessions.

`SessionAnalysis` holds the typed result (`analysis/schemas.py`): grammar findings, vocabulary findings, task completion against the scenario's goal checklist, `skill_observations`, `new_facts`, `focus_points`. Skill observations and new facts are persisted with their evidence.

Scenarios (fixed v1 list): job interview, daily stand-up, client call, small talk or networking, presentation Q&A, an everyday phone booking call. Each carries a role, a goal checklist, a difficulty and a recurring persona that references earlier sessions inside the dialogue.

Feedback dimensions for v1: grammar accuracy, vocabulary range and gaps, fluency, task completion. Progress is computed from stored `SessionProgress` rows, with the trend on the fly.

## 7. Graphs

- **Conversation graph (hot path), checkpointed:** `briefing -> conversing (loop, interrupt per turn) -> wrap_up -> finish_session`. Briefing loads the whole context once. Replies are streamed. Today `wrap_up` is a fixed line.
- **Post-session graph (cold path), no checkpointer, run by `SessionAnalysisRunner`:** `session_analysis -> weakness_state_update -> persona_memory_update`, reading the finished transcript from the database and carrying its own status.
- LLM calls run under a per-call timeout (`LLM_TIMEOUT_SECONDS`); the node `RetryPolicy` retries `LLMUnavailableError` and `LLMResponseError`.
- `LLMClient` is `stream(system_instruction, messages)` plus `generate_structured(system_instruction, messages, schema)` with typed `ChatMessage` and `MessageRole`. The analysis sends the transcript as one JSON user message.

## 8. RAG

Two corpora, both solving a real problem: (1) authentic scenario content per scenario type, so the agent does not improvise from nothing; (2) a grammar reference, so the report explains errors from a real reference and not from the model's memory. Ingestion is committed in batches with retry. The corpus owns the closed `skill_key` vocabulary.

## 9. MCP

On the hot path (`briefing`) the four tools are deterministic calls made by the node itself, not LLM tool calling, which would double reply latency. LLM-driven tool calling belongs only in the cold `session_analysis`.

## 10. Roadmap

Built and merged into `main`: auth (email and password, Google OAuth), the domain layer, the session graphs with a Postgres checkpointer, the WebSocket endpoint, the split of conversation from analysis, pgvector RAG grounding and the closed skill vocabulary, evidence verification, and the dashboard read API (PR #11).

| Slice | Content | Done when |
|---|---|---|
| S1 | `cadence-mcp-server` with the four tools; nodes become MCP clients | the tools are served over MCP and the briefing and analysis call them; I1 test for each tool |
| S2 | Frontend: practice screen and dashboard | a user can run a session and see the weakness profile and trend |
| S3 | Voice: STT in, TTS out around the conversation service; vendor chosen when this slice starts | a spoken session produces the same transcript and analysis |
| S4 | DeepEval and RAGAS, Langfuse tracing, a light guardrail in `Conversing` | golden-transcript regression and per-node cost and latency are measured |

Deferred until a real trigger, not scheduled: episodic persona memory, an in-character LLM wrap-up, a reconnect window through the checkpointer, token usage for Langfuse, recovery of analyses left `pending` by a server shutdown, hybrid search and re-ranker.

## 11. Repository layout and rules

Flat feature packages under `backend/src`, run with `PYTHONPATH=src`: `auth`, `users`, `practice`, `analysis`, `weaknesses`, `persona`, `progress`, `rag`, `scenarios`, `llm`, `orchestration`, `realtime`, `core`.

1. A feature package holds `models.py`, `repository.py`, `service.py`, `schemas.py`, `exceptions.py` and `router.py` only when it exposes HTTP.
2. Router -> service -> repository. Routers hold no logic, even `/health`. Services receive repositories through `Depends(get_x_repository)`, never by building `XRepositoryImpl(session)` in a dependency.
3. A repository is an `ABC` plus an `Impl` class, one pair per aggregate, exposing only the domain methods that aggregate needs. A generic CRUD base is used only where two repositories need identical semantics.
4. Learner-owned repositories filter by `user_id` inside the query. Unscoped bulk reads live only on `UserRepository`.
5. Errors are `AppException` subclasses with a code and a message.
6. Settings fields have no defaults; model names never encode a tier.
7. One Alembic migration per PR: a further schema change edits the PR's migration.
8. Every model is imported in `core/registry.py`.
9. Tests build the schema with `alembic upgrade head` against `TEST_DATABASE_URL` (a database ending in `_test`), each test inside a rolled-back transaction.
10. Code has no comments at all (`test_no_comments.py`). Reasons go to this SPEC, DECISIONS, the PR or the commit message.

## 12. Acceptance tests

| Invariant | Test |
|---|---|
| I1 | `test_a_session_is_not_visible_to_another_user`, `test_a_weakness_is_not_visible_to_another_user`, `test_a_persona_memory_is_not_visible_to_another_user`, `test_an_analysis_is_not_visible_to_another_user`, `test_progress_is_not_visible_to_another_user`; the AST guard `test_repositories_scope_by_user.py` |
| I2, I3 | `test_enough_clean_sessions_advance_active_to_probation_to_mastered`, `test_an_error_reopens_a_mastered_weakness` |
| I5 | `test_a_failed_analysis_leaves_the_conversation_completed` |
| I7 | `test_analysis_evidence.py`, e.g. `test_facts_are_checked_and_unquoted_items_are_dropped` |
| I8 | `test_skill_keys.py`, `test_recording_an_error_with_an_unknown_skill_key_is_rejected` |
| I4, I6, I9, I10 | not yet pinned by a named test; the first review of each slice that touches them adds one |

Other checks: `black --check`, `flake8` and the whole `pytest` suite are green.

## 13. Open questions

STT and TTS vendor (candidates: Deepgram, AssemblyAI, OpenAI for STT; OpenAI TTS, ElevenLabs for TTS): decided when S3 starts.
