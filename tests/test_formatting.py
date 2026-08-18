"""Tests for tf_peek.formatting."""

import pytest

from tf_peek.formatting import _json_default


def test_json_default_rejects_non_sentinel_objects() -> None:
    """``_json_default`` only knows how to serialize ``_DisplaySentinel``; anything else raises."""
    with pytest.raises(TypeError, match="not JSON serializable: object"):
        _json_default(object())
