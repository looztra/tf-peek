"""Tests for tf_peek models."""

from tf_peek.models import Change, ResourceChange, TerraformPlan


def test_resource_change_is_replacement() -> None:
    """Test is_replacement property."""
    # When actions contain both create and delete
    change = Change(actions=["create", "delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.is_replacement is True

    # When actions contain only create
    change = Change(actions=["create"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.is_replacement is False


def test_resource_change_simple_action() -> None:
    """Test simple_action property."""
    # Replacement
    change = Change(actions=["create", "delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.simple_action == "replace"

    # Single action
    change = Change(actions=["create"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.simple_action == "create"

    # No actions
    change = Change(actions=[])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.simple_action == "no-op"


def test_terraform_plan_default() -> None:
    """Test creating a default TerraformPlan."""
    plan = TerraformPlan()
    assert plan.resource_changes == []


def test_change_replace_paths_defaults_empty() -> None:
    """A plan that omits `replace_paths` parses to an empty list, not `None`."""
    change = Change(actions=["delete", "create"])
    assert change.replace_paths == []


def test_change_replace_paths_preserves_supplied_value() -> None:
    """A supplied `replace_paths` value round-trips unchanged."""
    change = Change(actions=["delete", "create"], replace_paths=[["settings", 0, "tier"]])
    assert change.replace_paths == [["settings", 0, "tier"]]


def test_resource_change_action_reason_defaults_to_none() -> None:
    """A resource change that omits `action_reason` defaults to `None`."""
    change = Change(actions=["delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.action_reason is None


def test_resource_change_action_reason_preserves_unrecognized_value() -> None:
    """`action_reason` is an open string: an unrecognized code parses successfully."""
    change = Change(actions=["delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change, action_reason="a_future_code")
    assert rc.action_reason == "a_future_code"


def test_destroy_before_create_true_for_destroy_then_create() -> None:
    """`["delete", "create"]` destroys the object before creating its replacement."""
    change = Change(actions=["delete", "create"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.destroy_before_create is True
    assert rc.simple_action == "replace"


def test_destroy_before_create_false_for_create_before_destroy() -> None:
    """`["create", "delete"]` (create_before_destroy) creates the replacement first."""
    change = Change(actions=["create", "delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.destroy_before_create is False
    assert rc.simple_action == "replace"
