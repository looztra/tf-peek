"""Tests for tf_peek main logic."""

from tf_peek.main import calculate_diff, get_emoji


def test_get_emoji() -> None:
    """Test get_emoji returns correct emojis."""
    assert get_emoji("create") == "➕"  # noqa: RUF001
    assert get_emoji("update") == "🛠️"
    assert get_emoji("delete") == "➖"  # noqa: RUF001
    assert get_emoji("replace") == "⚠️"
    assert get_emoji("no-op") == "🔹"
    assert get_emoji("unknown") == "❓"


def test_calculate_diff_simple() -> None:
    """Test comparing basic flat dictionaries."""
    before = {"attr1": "old_val", "attr2": "same"}
    after = {"attr1": "new_val", "attr2": "same"}
    unknown = None

    diff = calculate_diff(before, after, unknown)

    # attr2 should not be in the diff since it hasn't changed
    assert "attr2" not in diff
    # attr1 should show the change
    assert diff["attr1"] == {"before": "old_val", "after": "new_val"}


def test_calculate_diff_no_difference() -> None:
    """Test comparing identical state."""
    before = {"attr1": "val"}
    after = {"attr1": "val"}

    diff = calculate_diff(before, after, None)
    assert not diff


def test_calculate_diff_known_after_apply() -> None:
    """Test handling of values known after apply."""
    before = {"id": None, "name": "foo"}
    after = {"name": "foo"}
    unknown = {"id": True}

    diff = calculate_diff(before, after, unknown)

    assert "name" not in diff
    assert diff["id"] == {"before": None, "after": "(known after apply) ⏳"}
