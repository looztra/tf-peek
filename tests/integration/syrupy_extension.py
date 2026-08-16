"""Syrupy extension that writes goldens as plain, readable ``.md`` files.

syrupy's default ``AmberSnapshotExtension`` serialises into a single ``.ambr``
file per test module, which defeats the point of a golden here: the whole
value is a reviewer reading the diff in a PR.
"""

from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


class MarkdownSnapshotExtension(SingleFileSnapshotExtension):
    """One golden per snapshot, written as a standalone ``.md`` file."""

    _write_mode = WriteMode.TEXT
    file_extension = "md"
