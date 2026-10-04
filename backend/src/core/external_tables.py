EXTERNALLY_MANAGED_TABLES = frozenset(
    {
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
        "checkpoint_migrations",
    }
)


def is_externally_managed_table(name: str | None) -> bool:
    return name in EXTERNALLY_MANAGED_TABLES
