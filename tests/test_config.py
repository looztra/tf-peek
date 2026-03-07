"""Tests for tf_peek config."""

from pathlib import Path

import pytest

from tf_peek.config import PeekConfig, ResourceRule, load_config, resolve_tier
from tf_peek.models import Change, ResourceChange

# ---------------------------------------------------------------------------
# ResourceRule validation
# ---------------------------------------------------------------------------


def test_resource_rule_valid_match_type() -> None:
    """A rule with only match_type is valid."""
    rule = ResourceRule(match_type="null_resource", tier="silent")
    assert rule.match_type == "null_resource"
    assert rule.tier == "silent"
    assert rule.detail == "full"
    assert rule.critical_on == ["delete", "replace"]


def test_resource_rule_valid_match_pattern() -> None:
    """A rule with only match_pattern is valid when the pattern compiles."""
    rule = ResourceRule(match_pattern=r"module\.prod\..*\.aiven_pg", tier="critical")
    assert rule.match_pattern == r"module\.prod\..*\.aiven_pg"
    assert rule.tier == "critical"


def test_resource_rule_missing_match_key_raises() -> None:
    """A rule with neither match_type nor match_pattern raises ValueError."""
    with pytest.raises(ValueError, match="exactly one of"):
        ResourceRule(tier="silent")


def test_resource_rule_both_match_keys_raises() -> None:
    """A rule with both match_type and match_pattern raises ValueError."""
    with pytest.raises(ValueError, match="not both"):
        ResourceRule(match_type="aiven_pg", match_pattern=r"aiven_pg", tier="critical")


def test_resource_rule_invalid_regex_raises() -> None:
    """An invalid regex in match_pattern raises ValueError at parse time."""
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        ResourceRule(match_pattern="[unclosed")


def test_resource_rule_defaults() -> None:
    """Default tier is normal, default detail is full, default critical_on is delete+replace."""
    rule = ResourceRule(match_type="some_resource")
    assert rule.tier == "normal"
    assert rule.detail == "full"
    assert rule.critical_on == ["delete", "replace"]


def test_resource_rule_critical_on_custom() -> None:
    """critical_on can be overridden."""
    rule = ResourceRule(match_type="aiven_pg", tier="critical", critical_on=["delete", "replace", "update"])
    assert rule.critical_on == ["delete", "replace", "update"]


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_no_file() -> None:
    """Returns empty PeekConfig when file does not exist."""
    config = load_config(Path("non_existent_file.toml"))
    assert isinstance(config, PeekConfig)
    assert config.resources == []


def test_load_config_none_path() -> None:
    """Returns empty PeekConfig when path is None and default file missing."""
    config = load_config(None)
    assert config.resources == []


def test_load_config_valid_resources(tmp_path: Path) -> None:
    """Parses [[resources]] array-of-tables correctly."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text(
        """
[[resources]]
match_type = "null_resource"
tier = "silent"

[[resources]]
match_type = "aiven_pg"
tier = "critical"
critical_on = ["delete", "replace", "update"]

[[resources]]
match_type = "google_project_iam_member"
tier = "normal"
detail = "summary"
"""
    )
    config = load_config(config_file)
    expected_rule_count = 3
    assert len(config.resources) == expected_rule_count

    r0 = config.resources[0]
    assert r0.match_type == "null_resource"
    assert r0.tier == "silent"

    r1 = config.resources[1]
    assert r1.match_type == "aiven_pg"
    assert r1.tier == "critical"
    assert r1.critical_on == ["delete", "replace", "update"]

    r2 = config.resources[2]
    assert r2.match_type == "google_project_iam_member"
    assert r2.tier == "normal"
    assert r2.detail == "summary"


def test_load_config_match_pattern(tmp_path: Path) -> None:
    """Parses match_pattern rules correctly."""
    config_file = tmp_path / "peek_config.toml"
    config_file.write_text(
        r"""
[[resources]]
match_pattern = 'module\.prod\..*\.aiven_pg'
tier = "critical"
"""
    )
    config = load_config(config_file)
    assert config.resources[0].match_pattern == r"module\.prod\..*\.aiven_pg"
    assert config.resources[0].tier == "critical"


# ---------------------------------------------------------------------------
# resolve_tier — match resolution
# ---------------------------------------------------------------------------


def _rc(rtype: str, address: str | None = None) -> ResourceChange:
    """Helper to build a minimal ResourceChange."""
    return ResourceChange(
        address=address or rtype,
        type=rtype,
        name="test",
        change=Change(actions=["create"]),
    )


def test_resolve_tier_exact_type_match() -> None:
    """match_type matches via exact equality on rc.type."""
    config = PeekConfig(resources=[ResourceRule(match_type="aiven_pg", tier="critical")])
    rule = resolve_tier(_rc("aiven_pg"), config)
    assert rule.tier == "critical"


def test_resolve_tier_no_partial_type_match() -> None:
    """match_type does NOT match on prefix — exact equality only."""
    config = PeekConfig(resources=[ResourceRule(match_type="aiven_p", tier="critical")])
    rule = resolve_tier(_rc("aiven_pg"), config)
    assert rule.tier == "normal"  # falls back to default


def test_resolve_tier_pattern_matches_address() -> None:
    """match_pattern matches via re.search on rc.address."""
    config = PeekConfig(resources=[ResourceRule(match_pattern=r"aiven_postgresql\[.*-pgsource.*\]", tier="critical")])
    address = 'module.stack.module.aiven_postgresql["cfurmaniak-sbox-a2cv-pgsource"].aiven_pg.service'
    rule = resolve_tier(_rc("aiven_pg", address=address), config)
    assert rule.tier == "critical"


def test_resolve_tier_pattern_no_match() -> None:
    """match_pattern that does not match falls through to default."""
    config = PeekConfig(resources=[ResourceRule(match_pattern=r"module\.prod\..*\.aiven_pg", tier="critical")])
    rule = resolve_tier(_rc("aiven_pg", address="module.staging.aiven_pg.service"), config)
    assert rule.tier == "normal"


def test_resolve_tier_pattern_takes_priority_over_type() -> None:
    """match_pattern wins over match_type even if match_type comes first in config."""
    config = PeekConfig(
        resources=[
            ResourceRule(match_type="aiven_pg", tier="normal"),
            ResourceRule(match_pattern=r"module\.prod\..*\.aiven_pg", tier="critical"),
        ]
    )
    address = "module.prod.resources.aiven_pg.service"
    rule = resolve_tier(_rc("aiven_pg", address=address), config)
    assert rule.tier == "critical"


def test_resolve_tier_first_match_type_wins() -> None:
    """When two match_type rules match, the first one wins."""
    config = PeekConfig(
        resources=[
            ResourceRule(match_type="null_resource", tier="silent"),
            ResourceRule(match_type="null_resource", tier="normal"),
        ]
    )
    rule = resolve_tier(_rc("null_resource"), config)
    assert rule.tier == "silent"


def test_resolve_tier_no_match_returns_default() -> None:
    """Returns default rule (normal/full) when nothing matches."""
    config = PeekConfig(resources=[ResourceRule(match_type="aiven_pg", tier="critical")])
    rule = resolve_tier(_rc("google_storage_bucket"), config)
    assert rule.tier == "normal"
    assert rule.detail == "full"
    assert rule.critical_on == ["delete", "replace"]
