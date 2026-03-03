import os

from app.main import (
    get_non_negative_int_env,
    get_positive_float_env,
    normalize_tasks,
    should_retry_status,
)


def test_normalize_tasks_removes_leading_numbers_and_bullets() -> None:
    result = normalize_tasks([
        "1. First task",
        "2) Second task",
        "- Third task",
        "   ",
    ])

    assert result == ["First task", "Second task", "Third task"]


def test_should_retry_status_for_transient_codes() -> None:
    assert should_retry_status(429) is True
    assert should_retry_status(503) is True
    assert should_retry_status(500) is True


def test_should_retry_status_for_non_transient_codes() -> None:
    assert should_retry_status(400) is False
    assert should_retry_status(401) is False
    assert should_retry_status(404) is False


def test_get_positive_float_env_defaults_for_invalid() -> None:
    key = "TEST_POSITIVE_FLOAT"
    os.environ.pop(key, None)
    assert get_positive_float_env(key, 2.0) == 2.0

    os.environ[key] = "0"
    assert get_positive_float_env(key, 2.0) == 2.0

    os.environ[key] = "invalid"
    assert get_positive_float_env(key, 2.0) == 2.0


def test_get_non_negative_int_env_defaults_for_invalid() -> None:
    key = "TEST_NON_NEG_INT"
    os.environ.pop(key, None)
    assert get_non_negative_int_env(key, 3) == 3

    os.environ[key] = "-1"
    assert get_non_negative_int_env(key, 3) == 3

    os.environ[key] = "invalid"
    assert get_non_negative_int_env(key, 3) == 3
