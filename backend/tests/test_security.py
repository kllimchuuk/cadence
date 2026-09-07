from core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    password_needs_rehash,
    verify_password,
)


def test_a_correct_password_verifies() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed)


def test_a_wrong_password_does_not_verify() -> None:
    hashed = hash_password("correct horse battery staple")

    assert not verify_password("wrong password", hashed)


def test_a_missing_hash_does_not_verify_and_does_not_raise() -> None:
    assert not verify_password("anything", None)


def test_the_password_is_never_stored_in_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")

    assert "correct horse battery staple" not in hashed


def test_two_hashes_of_the_same_password_differ() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first != second


def test_a_freshly_hashed_password_does_not_need_rehashing() -> None:
    hashed = hash_password("correct horse battery staple")

    assert not password_needs_rehash(hashed)


def test_session_tokens_are_unique_and_url_safe() -> None:
    first = generate_session_token()
    second = generate_session_token()

    assert first != second
    assert " " not in first


def test_hashing_a_session_token_is_deterministic() -> None:
    token = generate_session_token()

    assert hash_session_token(token) == hash_session_token(token)


def test_hashing_a_session_token_never_reveals_it() -> None:
    token = generate_session_token()

    assert token not in hash_session_token(token)
