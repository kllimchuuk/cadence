from alembic import command
from alembic.script import ScriptDirectory

from tests.helpers import alembic_config, schema_diff, table_names


def test_migrations_apply_to_an_empty_database_and_roll_back(
    throwaway_database: str,
) -> None:
    config = alembic_config(throwaway_database)

    command.upgrade(config, "head")

    assert "users" in table_names(throwaway_database)

    command.downgrade(config, "base")

    assert "users" not in table_names(throwaway_database)


def test_the_migrated_schema_matches_the_models(migrated_schema: str) -> None:
    assert schema_diff(migrated_schema) == []


def test_the_migration_history_has_a_single_head(database_url: str) -> None:
    heads = ScriptDirectory.from_config(alembic_config(database_url)).get_heads()

    assert len(heads) == 1, heads
