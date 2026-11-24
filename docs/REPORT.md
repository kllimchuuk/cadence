# Report

Stage reports in the shape of the `report` skill, newest first. A figure appears only with the command it came from.

## How I worked with AI

Cases where the agent's first attempt was wrong and a test, a review or the owner caught it. One line each: what was wrong, how it was caught, what changed.

- **2026-11-24, workflow.** The rules for working with the agent lived only as text in `CLAUDE.md`, including "never run git" and "no comments". Nothing enforced them. They now have `.claude/settings.json` denials and guard tests, see DECISIONS 2026-11-24.
