"""Pydantic models representing the terraform plan structure."""

from typing import Any

from pydantic import BaseModel, Field


class Change(BaseModel):
    """Represents a change block within a resource change."""

    actions: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_unknown: bool | dict[str, Any] | list[Any] | None = None
    before_sensitive: bool | dict[str, Any] | list[Any] | None = None
    after_sensitive: bool | dict[str, Any] | list[Any] | None = None
    replace_paths: list[list[str | int]] = Field(default_factory=list)


class ResourceChange(BaseModel):
    """Represents a terraform resource change."""

    address: str
    module_address: str = "root"
    type: str
    name: str
    change: Change
    action_reason: str | None = None

    @property
    def is_replacement(self) -> bool:
        """Return True if the resource is being replaced (deleted and recreated)."""
        return "create" in self.change.actions and "delete" in self.change.actions

    @property
    def simple_action(self) -> str:
        """Return a simplified action string for the resource."""
        if self.is_replacement:
            return "replace"
        return self.change.actions[0] if self.change.actions else "no-op"

    @property
    def destroy_before_create(self) -> bool:
        """Return True if the replacement destroys the existing object before creating its replacement.

        Reads ``change.actions`` positionally: ``["delete", "create"]`` destroys first (the
        default mechanism); ``["create", "delete"]`` creates first (``create_before_destroy``).
        Only meaningful when ``is_replacement`` is True. ``is_replacement`` and ``simple_action``
        test set membership and stay order-insensitive by design; this property is the one place
        action order is read.
        """
        return self.change.actions.index("delete") < self.change.actions.index("create")


class TerraformPlan(BaseModel):
    """Represents the root of a terraform plan JSON."""

    resource_changes: list[ResourceChange] = Field(default_factory=list)
