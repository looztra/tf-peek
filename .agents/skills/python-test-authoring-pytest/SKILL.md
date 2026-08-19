---
name: python-test-authoring-pytest
description: Write and update tests with this repository family's pytest conventions (tests/ mirror layout, tuple parametrize with ids, conftest fixtures, pytest-mock, strict markers, snapshot goldens). Use when creating or editing tests or fixtures.
---

Use this skill when authoring or refactoring anything under `tests/`.

## Workflow

1. Mirror the module under test: `tests/test_<module>.py` for `src/<package>/<module>.py`. Where
   `tests/__init__.py` exists, `tests` is an importable package — import shared helpers as
   `from tests.<helper_module> import …`.
2. Reuse the repository's existing test builders/helper module instead of duplicating fixture
   literals; add new shared builders there.
3. Parametrize with tuple parameter names (even for a single parameter) and
   `pytest.param(..., id="…")` for every case; `marks=pytest.mark.xfail` for known defects.
4. Put shared fixtures in the nearest `conftest.py` (`tests/conftest.py` for unit scope, the
   suite's own `conftest.py` for a sub-suite); create the file when it does not exist yet.
5. Write `@pytest.fixture` without parentheses when it takes no arguments
   (`[lint.flake8-pytest-style] fixture-parentheses = false`), and
   `@pytest.fixture(name="…", scope="…")` when you need explicit naming or a wider scope.
6. Mock with `pytest-mock`: `mocker` typed as `MockerFixture`, `mocker.patch(..., autospec=True)`,
   `mocker.patch.object` for attributes, `mocker.patch.dict` for env-style mappings, and
   `assert_called_once_with` for call assertions.
7. Assert failures with `pytest.raises(SomeError, match="…")` — always with `match`.
8. Use `tmp_path` for filesystem work; never write outside it.
9. New markers must be declared in `pytest.ini` (`--strict-markers` is on); a whole-directory
   suite can auto-apply its marker from a `pytest_collection_modifyitems` hook in its `conftest.py`.
10. When the project keeps committed snapshot/golden files, regenerate them with the project's
    snapshot-update command and review the resulting diff as code before committing.

For the full rule list, read `references/pytest-rules.md`.
