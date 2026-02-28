"""Pydantic models representing the terraform plan structure."""

from typing import Any

from pydantic import BaseModel, Field


class Change(BaseModel):
    """Represents a change block within a resource change."""

    actions: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_unknown: dict[str, Any] | None = None


class ResourceChange(BaseModel):
    """Represents a terraform resource change."""

    address: str
    module_address: str = "root"
    type: str
    name: str
    change: Change

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


class TerraformPlan(BaseModel):
    """Represents the root of a terraform plan JSON."""

    resource_changes: list[ResourceChange] = Field(default_factory=list)
