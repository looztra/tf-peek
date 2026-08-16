"""Shared fixtures for the integration test suite.

Everything collected under ``tests/integration/`` is automatically marked
``integration`` — the directory is the source of truth, so a test cannot be
added here and miss the marker.
"""

from collections.abc import Sequence
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from tests.integration.syrupy_extension import MarkdownSnapshotExtension

_PACKAGE_ROOT = Path(__file__).parent


def pytest_collection_modifyitems(items: Sequence[pytest.Item]) -> None:
    """Auto-apply the ``integration`` marker to every test in this package."""
    for item in items:
        if _PACKAGE_ROOT in Path(item.fspath).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:  # pylint: disable=redefined-outer-name
    """Write goldens with the readable single-file Markdown extension."""
    return snapshot.use_extension(MarkdownSnapshotExtension)
