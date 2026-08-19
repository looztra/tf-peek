---
name: python-module-conventions
description: Apply this repository family's Python implementation conventions (src layout, Google docstrings, full typing, Ruff-ALL compliance). Use when creating or editing Python production code or packages.
---

# Python module conventions

Use this skill when writing or editing Python production code.

## Workflow

1. Put production modules under `src/<package>/`; every package directory keeps an `__init__.py`.
   The importable package is the one on `pythonpath` in `pytest.ini` / built by
   `[tool.hatch.build.targets.wheel]` in `pyproject.toml`.
2. Keep all imports at module top level (Ruff `PLC0415`; note `.pylintrc` disables
   `import-outside-toplevel` because Ruff owns it). Use relative imports for siblings inside the
   package when that is the file's existing style.
3. Give every module a docstring. Docstrings are Google-style (`[lint.pydocstyle] convention =
   "google"`): one line for obvious helpers, `Args:`/`Returns:`/`Raises:` sections whenever the
   function raises, has non-obvious precedence, or encodes a product decision.
4. Type-hint every parameter and return value, including `-> None` and special methods (`ANN204`).
   Use builtin generics and PEP 604 unions (`dict[str, Any] | None`); do not add
   `from __future__ import annotations`.
5. Pass file encodings explicitly (`Path.read_text(encoding="utf-8")`) — Ruff `PLW1514` is preview-only
   and pylint's `unspecified-encoding` (W1514) is typically disabled, so no linter enforces this; it
   is on you.
6. Use f-strings for formatting, except inside logging calls (`G004`/`logging-fstring-interpolation`).
7. Match the surrounding module's I/O and error idiom: reuse the project's existing output and
   exit-code mechanism instead of introducing `print`, a new logger, or `sys.exit`.
8. Prefer small focused functions, explicit names, `_`-prefixed private helpers, and keyword
   arguments for multi-argument calls.
9. Before finishing, run the `python-quality-gates` skill.

For the full rule list, read `references/python-module-rules.md`.
