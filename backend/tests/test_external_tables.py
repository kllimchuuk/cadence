from core.external_tables import is_externally_managed_table


def test_langgraph_checkpoint_tables_are_externally_managed() -> None:
    assert is_externally_managed_table("checkpoints")
    assert is_externally_managed_table("checkpoint_writes")


def test_an_application_table_sharing_the_prefix_is_not_externally_managed() -> None:
    assert not is_externally_managed_table("checkpoint_notes")
    assert not is_externally_managed_table("learning_sessions")
    assert not is_externally_managed_table(None)
