import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from users.models import DEFAULT_TIMEZONE, DEFAULT_UI_LANGUAGE
from users.repository import UserRepository, UserRepositoryImpl


@pytest.fixture
def repository(session: AsyncSession) -> UserRepository:
    return UserRepositoryImpl(session)


@pytest.mark.asyncio
async def test_a_user_row_is_created_and_read_back(
    session: AsyncSession, repository: UserRepository
) -> None:
    created = await repository.create(
        email="learner@cadence.test",
        first_name="Learner",
        last_name="One",
        nickname="learner",
        hashed_password="hashed",
    )
    await session.commit()
    session.expunge_all()

    read_back = await repository.get_by_id(created.id)

    assert read_back is not None
    assert read_back.email == "learner@cadence.test"
    assert read_back.first_name == "Learner"
    assert read_back.last_name == "One"
    assert read_back.hashed_password == "hashed"
    assert read_back.created_at is not None
    assert read_back.updated_at is not None


@pytest.mark.asyncio
async def test_a_user_is_read_by_email(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="by-email@cadence.test",
        first_name="By",
        last_name="Email",
        nickname="by-email",
        hashed_password="hashed",
    )
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_email("by-email@cadence.test")
    missing = await repository.get_by_email("nobody@cadence.test")

    assert found is not None
    assert missing is None


@pytest.mark.asyncio
async def test_an_email_is_stored_lowercase(
    session: AsyncSession, repository: UserRepository
) -> None:
    created = await repository.create(
        email="  Mixed.Case@Cadence.TEST  ",
        first_name="Mixed",
        last_name="Case",
        nickname="mixed-case",
        hashed_password="hashed",
    )
    await session.commit()

    assert created.email == "mixed.case@cadence.test"


@pytest.mark.asyncio
async def test_an_email_is_read_back_whatever_its_case(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="Reader@Cadence.test",
        first_name="Reader",
        last_name="User",
        nickname="reader",
        hashed_password="hashed",
    )
    await session.commit()
    session.expunge_all()

    assert await repository.get_by_email("READER@cadence.TEST") is not None


@pytest.mark.asyncio
async def test_the_same_email_in_another_case_is_still_taken(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="taken@cadence.test",
        first_name="Taken",
        last_name="A",
        nickname="taken-a",
        hashed_password="hashed",
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.create(
            email="Taken@Cadence.TEST",
            first_name="Taken",
            last_name="B",
            nickname="taken-b",
            hashed_password="another",
        )


@pytest.mark.asyncio
async def test_a_nickname_is_read_back_whatever_its_case(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="nick-reader@cadence.test",
        first_name="Nick",
        last_name="Reader",
        nickname="NickReader",
        hashed_password="hashed",
    )
    await session.commit()
    session.expunge_all()

    assert await repository.get_by_nickname("nickreader") is not None
    assert await repository.get_by_nickname("nobody") is None


@pytest.mark.asyncio
async def test_the_same_nickname_in_another_case_is_still_taken(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="nick-a@cadence.test",
        first_name="Nick",
        last_name="A",
        nickname="SameNick",
        hashed_password="hashed",
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.create(
            email="nick-b@cadence.test",
            first_name="Nick",
            last_name="B",
            nickname="samenick",
            hashed_password="another",
        )


@pytest.mark.asyncio
async def test_a_user_is_read_by_google_sub(
    session: AsyncSession, repository: UserRepository
) -> None:
    await repository.create(
        email="google-user@cadence.test",
        first_name="Google",
        last_name="User",
        nickname="google-user",
        google_sub="google-sub-123",
    )
    await session.commit()
    session.expunge_all()

    found = await repository.get_by_google_sub("google-sub-123")
    missing = await repository.get_by_google_sub("no-such-sub")

    assert found is not None
    assert found.hashed_password is None
    assert missing is None


@pytest.mark.asyncio
async def test_linking_a_google_account_sets_its_sub(
    session: AsyncSession, repository: UserRepository
) -> None:
    user = await repository.create(
        email="link-me@cadence.test",
        first_name="Link",
        last_name="Me",
        nickname="link-me",
        hashed_password="hashed",
    )
    await session.commit()

    await repository.link_google_account(user, "google-sub-456")
    await session.commit()
    session.expunge_all()

    linked = await repository.get_by_google_sub("google-sub-456")
    assert linked is not None
    assert linked.id == user.id


@pytest.mark.asyncio
async def test_the_database_refuses_a_mixed_case_email(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO users (id, email, first_name, last_name, "
                "nickname, hashed_password) "
                "VALUES (gen_random_uuid(), 'Bypass@Cadence.test', "
                "'Bypass', 'User', 'bypass', 'hashed')"
            )
        )


@pytest.mark.asyncio
async def test_a_new_user_gets_the_ukrainian_defaults(
    repository: UserRepository,
) -> None:
    user = await repository.create(
        email="defaults@cadence.test",
        first_name="Defaults",
        last_name="User",
        nickname="defaults",
        hashed_password="hashed",
    )

    assert user.ui_language == DEFAULT_UI_LANGUAGE
    assert user.timezone == DEFAULT_TIMEZONE


@pytest.mark.asyncio
async def test_the_database_applies_the_defaults_without_the_orm(
    session: AsyncSession,
) -> None:
    await session.execute(
        text(
            "INSERT INTO users (id, email, first_name, last_name, "
            "nickname, hashed_password) "
            "VALUES (gen_random_uuid(), 'raw@cadence.test', "
            "'Raw', 'User', 'raw', 'hashed')"
        )
    )

    row = (
        await session.execute(
            text(
                "SELECT ui_language, timezone FROM users "
                "WHERE email = 'raw@cadence.test'"
            )
        )
    ).one()

    assert row.ui_language == DEFAULT_UI_LANGUAGE
    assert row.timezone == DEFAULT_TIMEZONE


@pytest.mark.asyncio
async def test_created_at_is_stored_with_a_timezone(
    repository: UserRepository,
) -> None:
    user = await repository.create(
        email="timestamps@cadence.test",
        first_name="Timestamps",
        last_name="User",
        nickname="timestamps",
        hashed_password="hashed",
    )

    assert user.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_an_unknown_id_reads_back_as_none(repository: UserRepository) -> None:
    assert await repository.get_by_id(uuid.uuid4()) is None
