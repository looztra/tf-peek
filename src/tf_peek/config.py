"""Configuration models and loading logic for tf-peek."""

from pathlib import Path

import tomllib
from pydantic import BaseModel, Field


class PeekConfig(BaseModel):
    """Configuration for tf-peek execution."""

    summarize: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)


def load_config(config_path: Path | None = None) -> PeekConfig:
    """Load the peek configuration from a toml file."""
    path = config_path or Path("peek_config.toml")

    if not path.exists():
        return PeekConfig()

    with path.open("rb") as f:
        data = tomllib.load(f)

    filters = data.get("filters", {})
    return PeekConfig(summarize=filters.get("summarize", []), ignore=filters.get("ignore", []))
