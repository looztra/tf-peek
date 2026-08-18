"""Tests for tf_peek.diff."""

from tf_peek.diff import KNOWN_AFTER_APPLY, SENSITIVE_VALUE, DisplaySentinel, calculate_diff


def test_calculate_diff_simple() -> None:
    """Test comparing basic flat dictionaries."""
    before = {"attr1": "old_val", "attr2": "same"}
    after = {"attr1": "new_val", "attr2": "same"}
    diff = calculate_diff(before, after, None)
    assert "attr2" not in diff
    assert diff["attr1"] == {"before": "old_val", "after": "new_val"}


def test_calculate_diff_no_difference() -> None:
    """Test comparing identical state."""
    diff = calculate_diff({"attr1": "val"}, {"attr1": "val"}, None)
    assert not diff


def test_calculate_diff_known_after_apply() -> None:
    """Test handling of values known after apply."""
    diff = calculate_diff({"id": None, "name": "foo"}, {"name": "foo"}, {"id": True})
    assert "name" not in diff
    assert diff["id"] == {"before": None, "after": KNOWN_AFTER_APPLY}


def test_calculate_diff_bare_bool_after_unknown_false() -> None:
    """A bare ``false`` ``after_unknown`` marks every attribute known."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, False)
    assert diff["attr"] == {"before": "old", "after": "new"}


def test_calculate_diff_bare_bool_after_unknown_true() -> None:
    """A bare ``true`` ``after_unknown`` marks every known key unknown."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, True)
    assert diff["attr"] == {"before": "old", "after": KNOWN_AFTER_APPLY}


def test_calculate_diff_masks_flat_sensitive() -> None:
    """A flat bool sensitivity marker masks the attribute's value on both sides."""
    before = {"password": "hunter2"}
    after = {"password": "s3cr3t!"}
    diff = calculate_diff(before, after, None, {"password": True}, {"password": True})
    assert diff["password"] == {"before": SENSITIVE_VALUE, "after": SENSITIVE_VALUE}


def test_calculate_diff_masks_nested_sensitive() -> None:
    """A truthy marker anywhere in a nested subtree masks the whole top-level attribute."""
    before = {"settings": {"tier": "small", "credentials": {"password": "hunter2"}}}
    after = {"settings": {"tier": "large", "credentials": {"password": "hunter2"}}}
    before_sensitive = {"settings": {"tier": False, "credentials": {"password": True}}}
    after_sensitive = {"settings": {"tier": False, "credentials": {"password": True}}}
    diff = calculate_diff(before, after, None, before_sensitive, after_sensitive)
    assert diff["settings"] == {"before": SENSITIVE_VALUE, "after": SENSITIVE_VALUE}


def test_calculate_diff_masks_one_sided_sensitive() -> None:
    """Sensitivity flagged on only one side still masks both before and after."""
    before = {"token": "was-plaintext"}
    after = {"token": "now-secret"}
    diff = calculate_diff(before, after, None, {"token": False}, {"token": True})
    assert diff["token"] == {"before": SENSITIVE_VALUE, "after": SENSITIVE_VALUE}


def test_calculate_diff_masks_non_boolean_truthy_sensitive() -> None:
    """An unexpected but truthy marker shape fails closed and still masks the value.

    Terraform emits booleans today; narrowing the predicate to `is True` would
    render the value in plaintext the moment it emits anything else.
    """
    before = {"token": "was-plaintext"}
    after = {"token": "now-secret"}
    diff = calculate_diff(before, after, None, None, {"token": {"nested": 1}})
    assert diff["token"] == {"before": SENSITIVE_VALUE, "after": SENSITIVE_VALUE}


def test_calculate_diff_unresolvable_after_unknown_marker_leaves_value_unchanged() -> None:
    """A marker shape that isn't ``true``/``false``/``None``/dict/list is ignored, not applied."""
    diff = calculate_diff({"attr": "old"}, {"attr": "new"}, {"attr": "not-a-real-marker"})
    assert diff["attr"] == {"before": "old", "after": "new"}


def test_display_sentinel_hash_and_repr() -> None:
    """``DisplaySentinel`` is hashable and reprs with its text for debugging."""
    sentinel = DisplaySentinel("(known after apply) ⏳")
    assert hash(sentinel) == hash(("DisplaySentinel", "(known after apply) ⏳"))
    assert repr(sentinel) == "DisplaySentinel('(known after apply) ⏳')"
