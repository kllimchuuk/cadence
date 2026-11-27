---
name: spec-slice
description: Work loop for implementing one slice of the Cadence roadmap (SPEC §10). Use when starting or continuing a slice or PR, adding a feature package, or when the user says "next slice" or names one. Covers reading the spec, branching, test first, implementation rules, checks and the local commits.
---

# Implementing a slice

Follow these steps in order. The slice list is in `docs/SPEC.md` §10; the rules behind it are in `CLAUDE.md`.

1. **Read.** Open the slice in SPEC §10 and every section it names (§4 contracts, §5 invariants, §6-§9 behavior, §11 layout rules, §12 tests). Database and frontend rules load from `.claude/rules/` when you touch those files. If the SPEC is silent or wrong, stop and report "Decision needed" with a recommendation; do not guess.
2. **Branch.** Run `git fetch origin`, then cut the branch from `origin/main`, named by commit type (`feat/mcp-server`). Never on `main`. Do not create a branch the owner did not ask for.
3. **Test first.** Write the failing test for the behavior in `backend/tests/test_<module>.py`, against the real test database with fakes from `tests/fakes.py`. Run it and see it fail for the right reason.
4. **Implement.** The smallest code that passes, following SPEC §11:
   - a feature package with `models`, `repository` (ABC + Impl), `service`, `schemas`, `exceptions`, and `router` only if it exposes HTTP;
   - learner-owned queries filter by `user_id`; routers hold no logic;
   - one Alembic migration per PR, edited rather than added to;
   - no comments.
5. **Check.** From `backend/`: `PYTHONPATH=$PWD/src .venv/bin/pytest`, `.venv/bin/black --check src tests migrations`, `.venv/bin/flake8 src tests migrations`. Everything green before committing; the commit gate hook runs the same three and blocks a red commit. A flaky test is never retried, slept around or skipped: find the cause, or delete the test and say why in the PR.
6. **Verify.** For a change to behavior in `backend/src`, run the `verify` skill against the running app. Report a step that could not run as not verified.
7. **Document.** If the change deviates from SPEC or settles a choice, add the entry to `docs/DECISIONS.md` and edit the SPEC in the same commit.
8. **Commit locally.** Stage by explicit path. Two to four larger commits, each green on its own. One-line subject, then a `Co-Authored-By` trailer naming the model that wrote the change, e.g. `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, amend or reset history.
9. **Review.** Run `git fetch origin`, then the `reviewer` subagent on the branch (`model: opus`), and pass it the commit SHA. Fix its findings in one `fix: address review` commit, each with a test that failed first, then run it again with the earlier findings listed. A review of an older commit does not count.
10. **Learn.** If the owner's PR review catches something the reviewer missed, and the same pattern has shown up in at least two PRs, add it to "Lessons from missed findings" in `invariants-check`. Delete entries that no longer apply.
11. **Hand over.** Show `git log --stat origin/main..HEAD`, then report in the `report` skill's shape. The owner pushes and opens the PR.

If a check or verification still fails after three rounds of fixes, stop and say what you tried instead of looping.
