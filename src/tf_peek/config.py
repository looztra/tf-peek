"""Configuration models and loading logic for tf-peek."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import tomllib
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from .models import ResourceChange

_DEFAULT_CRITICAL_ON: list[str] = ["delete", "replace"]


class ResourceRule(BaseModel):
    """A single resource classification rule.

    Exactly one of ``match_type`` or ``match_pattern`` must be provided.
    ``match_type`` is an exact match against ``rc.type``.
    ``match_pattern`` is a ``re.search`` regex matched against ``rc.address``.
    """

    match_type: str | None = None
    match_pattern: str | None = None
    tier: Literal["silent", "normal", "critical"] = "normal"
    detail: Literal["full", "summary"] = "full"
    critical_on: list[str] = Field(default_factory=lambda: list(_DEFAULT_CRITICAL_ON))

    @model_validator(mode="after")
    def validate_match_keys(self) -> "ResourceRule":
        """Validate that exactly one match key is set and the pattern is valid regex."""
        has_type = self.match_type is not None
        has_pattern = self.match_pattern is not None
        if has_type and has_pattern:
            msg = "A resource rule must have exactly one of 'match_type' or 'match_pattern', not both."
            raise ValueError(msg)
        if not has_type and not has_pattern:
            msg = "A resource rule must have exactly one of 'match_type' or 'match_pattern'."
            raise ValueError(msg)
        if self.match_pattern is not None:
            try:
                re.compile(self.match_pattern)
            except re.error as exc:
                msg = f"Invalid regex pattern '{self.match_pattern}': {exc}"
                raise ValueError(msg) from exc
        return self


# Sentinel default rule used when no configured rule matches a resource.
_DEFAULT_RULE = ResourceRule.model_construct(
    match_type=None,
    match_pattern=None,
    tier="normal",
    detail="full",
    critical_on=list(_DEFAULT_CRITICAL_ON),
)


class PeekConfig(BaseModel):
    """Configuration for tf-peek execution."""

    resources: list[ResourceRule] = Field(default_factory=list)


def resolve_tier(rc: "ResourceChange", config: PeekConfig) -> ResourceRule:
    """Resolve the first matching ResourceRule for a resource change.

    Resolution order:
    1. ``match_pattern`` rules evaluated in config order via ``re.search`` on ``rc.address``.
    2. ``match_type`` rules evaluated in config order via exact equality on ``rc.type``.
    3. Falls back to ``_DEFAULT_RULE`` (tier=normal, detail=full).

    Args:
        rc: The resource change to classify.
        config: The loaded peek configuration.

    Returns:
        The first matching ResourceRule, or the default rule if none match.
    """
    for rule in config.resources:
        if rule.match_pattern is not None and re.search(rule.match_pattern, rc.address):
            return rule
    for rule in config.resources:
        if rule.match_type is not None and rule.match_type == rc.type:
            return rule
    return _DEFAULT_RULE


def load_config(config_path: Path | None = None) -> PeekConfig:
    """Load the peek configuration from a TOML file.

    Args:
        config_path: Path to the TOML config file. Defaults to ``peek_config.toml``
            in the current working directory.

    Returns:
        A ``PeekConfig`` instance. Returns an empty config if the file does not exist.
    """
    path = config_path or Path("peek_config.toml")

    if not path.exists():
        return PeekConfig()

    with path.open("rb") as f:
        data = tomllib.load(f)

    rules_data = data.get("resources", [])
    return PeekConfig(resources=rules_data)
