"""Tests for tf_peek config."""

from pathlib import Path

from tf_peek.config import PeekConfig, load_config


def test_load_config_default() -> None:
    """Test loading config when file does not exist or is None."""
    config = load_config(None)
    assert isinstance(config, PeekConfig)
    assert config.summarize == []
    assert config.ignore == []

    config = load_config(Path("non_existent_file.toml"))
    assert config.summarize == []
    assert config.ignore == []


def test_load_config_with_file(tmp_path: Path) -> None:
    """Test loading config from a valid TOML file."""
    config_file = tmp_path / "config.toml"
    config_content = """
    [filters]
    summarize = ["aws_iam_role", "aws_iam_policy"]
    ignore = ["aws_s3_bucket"]
    """
    config_file.write_text(config_content)

    config = load_config(config_file)
    assert config.summarize == ["aws_iam_role", "aws_iam_policy"]
    assert config.ignore == ["aws_s3_bucket"]
