"""Tests for the ``python -m tf_peek`` entrypoint."""

import runpy
from typing import Protocol
from unittest.mock import MagicMock


class _Mocker(Protocol):
    """Subset of pytest-mock's fixture used by this test."""

    def patch(self, target: str) -> MagicMock:
        """Patch a dotted target and return its mock."""


def test_module_entrypoint_invokes_cli_app(mocker: _Mocker) -> None:
    """Running the package module delegates to the Typer CLI application."""
    app = mocker.patch("tf_peek.cli.app")

    runpy.run_module("tf_peek", run_name="__main__")

    app.assert_called_once_with()
