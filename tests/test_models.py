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
