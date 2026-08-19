# Python module rules

## Layout

- Production code lives under `src/<package>/`; tests under `tests/`.
- Every package directory contains an explicit `__init__.py`.
- Non-Python assets used by the package (templates, data files) live inside the package directory so
  they ship with the wheel.
- Console entry points declared in `[project.scripts]` must stay importable without side effects.

## Style and documentation

- Follow PEP 8 and PEP 257.
- Google docstring convention, enforced by Ruff pydocstyle.
- Module docstring mandatory in `src/` (`D100`/`D104` are only ignored under `tests/`).
- Multi-line docstring with `Args:`, `Returns:`, `Raises:` for any function that raises or whose
  behaviour is not obvious from the signature; one-liners elsewhere.
- Comments only for non-obvious design choices; put rationale in the docstring by preference.

## Typing

- Hints on all parameters and return values (`ANN001`, `ANN201`, `ANN204`).
- Builtin generics (`list[str]`, `dict[str, Any]`) and PEP 604 unions; no
  `from __future__ import annotations` (`target-version` in `ruff_defaults.toml` is new enough).
- `ty check` runs inside `poe lint:all`; treat its findings as blocking.

## Linting authority

- Ruff runs with `select = ["ALL"]` in `ruff_defaults.toml`, globally ignoring `B008`, `COM812`,
  `CPY`, `FBT`, `ISC001`; line length 119.
- `ruff_defaults.toml` is template-owned — never edit it. Project-specific ignores go in the
  `[lint] ignore` list of `ruff.toml`, which must keep its `extend = "ruff_defaults.toml"` directive.
- `.pylintrc` deliberately disables the ~200 rules Ruff implements (`line-too-long`,
  `import-outside-toplevel`, `missing-*-docstring`, `invalid-name`, …), including every
  `too-many-*` design/complexity check. So a docstring or import finding comes from Ruff; pylint
  only adds what Ruff cannot do (e.g. `redefined-outer-name`, `c-extension-no-member`,
  cyclic-import and duplicate-code analysis).
- Suppress with a rule id and a reason on the same line: `# noqa: PLR2004 — documented exit code`,
  `# pylint: disable=redefined-outer-name`. Prefer fixing, or naming a constant, over suppressing.

## Style preferences

- f-strings for formatting; never `%` or `.format()` chains; no f-strings inside logging calls.
- Keyword arguments for multi-argument calls when readability improves.
- Reuse the module's existing error/exit idiom rather than adding a second one.
