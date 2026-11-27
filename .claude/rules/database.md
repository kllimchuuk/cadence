---
paths:
  - "backend/migrations/**"
  - "backend/alembic.ini"
  - "backend/src/core/database.py"
  - "backend/src/core/registry.py"
  - "backend/src/**/models.py"
  - "backend/tests/conftest.py"
  - "backend/tests/helpers.py"
  - "backend/src/config.py"
  - "backend/.env.example"
  - "docker-compose.yml"
---

# Database and migrations

- `docker compose up -d` from the repository root brings up Postgres 16 with pgvector on **127.0.0.1:5433**; the standard port is taken by a local brew `postgresql@14`. `DATABASE_URL` and `TEST_DATABASE_URL` point at 5433.
- One Alembic migration per PR; a further schema change edits the PR's migration instead of adding a second one. Every model is imported in `src/core/registry.py`.
- Tests build their schema by dropping, recreating and running `alembic upgrade head` against `TEST_DATABASE_URL`, never `Base.metadata.create_all`, so a missing migration fails the suite. Each test runs inside a connection-level transaction that is rolled back afterwards.
- `TEST_DATABASE_URL` must name a database ending in `_test` and differ from `DATABASE_URL`; `pytest_configure` aborts otherwise, because the suite drops every table it is pointed at.
- Never pass a database URL through `alembic.Config.set_main_option`: `ConfigParser` treats `%` as interpolation. The URL travels via `config.attributes["sqlalchemy.url"]`.
