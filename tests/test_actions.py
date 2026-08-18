"""Tests for tf_peek.actions."""

from tf_peek.actions import ACTION_ORDER, Action, get_emoji
from tf_peek.models import Change, ResourceChange


def test_get_emoji() -> None:
    """Test get_emoji returns correct emojis."""
    assert get_emoji("create") == "➕"  # noqa: RUF001
    assert get_emoji("update") == "🛠️"
    assert get_emoji("delete") == "➖"  # noqa: RUF001
    assert get_emoji("replace") == "⚠️"
    assert get_emoji("no-op") == "🔹"
    assert get_emoji("unknown") == "❓"


def test_action_enum_values_match_action_order() -> None:
    """`Action` contains exactly the actions in `ACTION_ORDER`; CLI ordering is intentional."""
    assert {member.value for member in Action} == set(ACTION_ORDER)


def test_action_values_cover_simple_action_outcomes_reaching_gate() -> None:
    """Every ``simple_action`` that survives the no-op/read filter is selectable on the CLI.

    The scoped gate compares ``rc.simple_action`` (a bare string from ``models.py``) against
    ``Action`` member values. If ``simple_action`` ever yields a value outside ``Action`` (e.g. a
    future Terraform action), the scoped gate would silently under-gate. This pins the contract
    that the two value sets stay aligned for the actions that actually reach the tally.
    """
    selectable = {a.value for a in Action}
    # Each shape produces the simple_action shown; "no-op"/"read" are filtered before the tally
    # and are deliberately not selectable gate actions.
    cases = {
        "create": ["create"],
        "update": ["update"],
        "delete": ["delete"],
        "replace": ["delete", "create"],
    }
    for expected, actions in cases.items():
        rc = ResourceChange(
            address=f"t.{expected}",
            type="t",
            name=expected,
            change=Change(actions=actions),
        )
        assert rc.simple_action == expected
        assert rc.simple_action in selectable
