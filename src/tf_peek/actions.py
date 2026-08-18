"""Terraform action vocabulary shared by the report and the CLI."""

from enum import Enum


class Action(str, Enum):
    """A Terraform action that can be selected for the ``--fail-on-critical-on`` gate.

    Members' values must stay in sync with ``ACTION_ORDER`` — a test asserts the two match
    verbatim so they can't silently drift.
    """

    create = "create"
    update = "update"
    delete = "delete"
    replace = "replace"


ACTION_ORDER = ["delete", "replace", "update", "create"]


def get_emoji(action: str) -> str:
    """Return an emoji representation of a terraform action."""
    mapping = {"create": "➕", "update": "🛠️", "delete": "➖", "replace": "⚠️", "no-op": "🔹"}  # noqa: RUF001
    return mapping.get(action, "❓")
