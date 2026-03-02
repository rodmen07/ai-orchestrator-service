from app.main import normalize_tasks


def test_normalize_tasks_removes_leading_numbers_and_bullets() -> None:
    result = normalize_tasks([
        "1. First task",
        "2) Second task",
        "- Third task",
        "   ",
    ])

    assert result == ["First task", "Second task", "Third task"]
