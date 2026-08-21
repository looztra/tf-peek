"""Tests for tf_peek models."""

import pytest

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


def test_change_replace_paths_tolerates_an_explicit_null() -> None:
    """An explicit `null` parses to "no forcing paths", as every sibling marker field does.

    A lost causation hint must never cost the whole report, so the field fails open the same way
    `action_reason` does.
    """
    change = Change.model_validate({"actions": ["delete", "create"], "replace_paths": None})
    assert change.replace_paths == []


def test_change_replace_paths_accepts_an_unexpected_step_type() -> None:
    """An unexpected step type degrades to a rendered subscript instead of failing the parse."""
    change = Change.model_validate({"actions": ["delete", "create"], "replace_paths": [["settings", 1.5]]})
    assert change.replace_paths == [["settings", 1.5]]


def test_resource_change_action_reason_defaults_to_none() -> None:
    """A resource change that omits `action_reason` defaults to `None`."""
    change = Change(actions=["delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.action_reason is None


def test_replacement_mechanism_destroy_first() -> None:
    """`["delete", "create"]` destroys the object before creating its replacement."""
    change = Change(actions=["delete", "create"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.replacement_mechanism == "destroy_first"


def test_replacement_mechanism_create_first() -> None:
    """`["create", "delete"]` (create_before_destroy) creates the replacement first."""
    change = Change(actions=["create", "delete"])
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.replacement_mechanism == "create_first"


@pytest.mark.parametrize("actions", [["create"], ["delete"], ["update"], ["no-op"], []], ids=str)
def test_replacement_mechanism_is_none_for_non_replacements(actions: list[str]) -> None:
    """Action order says nothing about a non-replacement, so the property reports that, not raises."""
    change = Change(actions=actions)
    rc = ResourceChange(address="foo", type="bar", name="baz", change=change)
    assert rc.replacement_mechanism is None
