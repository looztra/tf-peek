"""Pydantic models representing the terraform plan structure."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Change(BaseModel):
    """Represents a change block within a resource change."""

    actions: list[str]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    after_unknown: bool | dict[str, Any] | list[Any] | None = None
    before_sensitive: bool | dict[str, Any] | list[Any] | None = None
    after_sensitive: bool | dict[str, Any] | list[Any] | None = None
    replace_paths: list[list[Any]] = Field(default_factory=list)

    @field_validator("replace_paths", mode="before")
    @classmethod
    def _tolerate_null_replace_paths(cls, value: object) -> object:
        """Treat an explicit ``null`` as "no forcing paths", matching every sibling marker field.

        ``before``/``after``/``after_unknown``/``before_sensitive``/``after_sensitive`` all accept an
        explicit null, and a lost causation hint must never cost the whole report: a plan that states
        nothing about forcing paths still renders. Step types stay unconstrained (``list[Any]``) for
        the same reason — the format spec says a step "will be a number or a string", but an
        unexpected step degrades to a JSON-encoded subscript in ``causation`` rather than failing the
        parse.
        """
        return [] if value is None else value


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
    def replacement_mechanism(self) -> Literal["destroy_first", "create_first"] | None:
        """Return which replacement mechanism Terraform will use, or None if this is no replacement.

        Reads ``change.actions`` positionally: ``["delete", "create"]`` destroys first (the default
        mechanism); ``["create", "delete"]`` creates first (``create_before_destroy``). Total by
        construction — ``is_replacement`` and ``simple_action`` test set membership and stay
        order-insensitive by design; this property is the one place action order is read, and it
        reports "not a replacement" rather than raising for the changes where order says nothing.
        """
        if not self.is_replacement:
            return None
        destroy_first = self.change.actions.index("delete") < self.change.actions.index("create")
        return "destroy_first" if destroy_first else "create_first"


class TerraformPlan(BaseModel):
    """Represents the root of a terraform plan JSON."""

    resource_changes: list[ResourceChange] = Field(default_factory=list)
