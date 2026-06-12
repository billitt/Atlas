"""Tests for protocol security helpers."""

from protocols.auth import auth_headers, bearer_authorized


def test_auth_headers_empty_when_no_token() -> None:
    assert auth_headers(None) == {}


def test_auth_headers_bearer_format() -> None:
    assert auth_headers("secret") == {"Authorization": "Bearer secret"}


def test_bearer_authorized_when_auth_disabled() -> None:
    assert bearer_authorized(None, None) is True
    assert bearer_authorized("Bearer anything", None) is True


def test_bearer_authorized_rejects_missing_or_wrong_token() -> None:
    assert bearer_authorized(None, "expected") is False
    assert bearer_authorized("Bearer wrong", "expected") is False
    assert bearer_authorized("Bearer expected", "expected") is True
