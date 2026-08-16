# How to contribute

## Prerequisites

### Mandatory

- [poetry](https://python-poetry.org/docs/#installation)

### Optional

- [Pre-Commit](https://pre-commit.com/#install)
- [asdf](https://asdf-vm.com/guide/getting-started.html)
- [ActionLint](https://github.com/rhysd/actionlint)
- [shfmt](https://github.com/mvdan/sh)
- [editorconfig-checker](https://github.com/editorconfig-checker/editorconfig-checker)

### Install the optional prequisites

- If you installed asdf, you can simply run:

```bash
for plugin in $(cut -d " " -f 1 < .tool-versions); do
  asdf plugin add "${plugin}"
done
asdf install
```

- This will:
  - install asdf plugins for this repository
  - install the version of tool required for this repository

## Hack

- run `make setup-venv` so that `poetry` inits a virtual environment with required dependencies (same as `poetry install --sync`)
- run `eval $(make echo-venv-activate-cmd)` to activate the virtual environment if needed

### Update the dependencies

Run `make update-requirements-file`, this will basically:

- run `poetry lock` to update the dependencies and the lock file
- update the `requirements.txt` file used by tox virutal environments (to save a call to poetry each time you run tox)

### Code

- run `make tests` to launch unit tests (same as `tox -e py3`)
- run `make lint` to launch linters (same as `tox -e linters`):
  - `black` (see the [pyproject.toml](pyproject.toml) for the black configuration)
  - `isort` (see the [pyproject.toml](pyproject.toml) for the isort configuration + the tox.ini because we configure isort with `--dont-order-by-type` that cannot be specified in a config file)
  - `flake8`
  - `pylint`

### Integration tests & golden files

- run `make integration-tests` to run the end-to-end suite (`tests/integration/`) on its own; it
  is also included in `make tests`
- `tests/integration/test_golden.py` renders `tests/integration/fixtures/kitchen-sink.json` and
  compares it against the committed golden at
  `tests/integration/__snapshots__/test_golden/test_kitchen_sink_report.md` — a plain, readable
  `.md` file, so its diff is the review artifact for changes to the rendering logic
- after a change that legitimately alters the rendered report, regenerate the golden with:

  ```bash
  uv run poe pytest:integration --snapshot-update
  ```

  then review the diff of the `.md` file like any other code change before committing it
- `tests/integration/test_defects.py` carries one `@pytest.mark.xfail(strict=True, ...)` per
  catalogued defect (see `docs/studies/2026-08-15-capability-and-market-analysis.md §4.1`); when a
  fix lands, remove its `xfail` marker — `strict=True` fails CI if you forget

### Pre-Commit

- If you want to run pre-commit before each commit, run once `make precommit-install`
- If you don't want to configure a pre-commit hook (your choice, pre-commit is run by the CICD anyway), you can run it when you want, use `make precommit-run`

### Configure your editor

#### VSCode

- It's a good idea to install the [EditorConfig for VSCode extension](https://marketplace.visualstudio.com/items?itemName=EditorConfig.EditorConfig)
- Your `settings.json` (user or workspace or project) should contain:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true,
    },
  },
  "python.formatting.provider": "black",
  "isort.args": [
    "--dont-order-by-type"
  ],
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,
  "files.trimFinalNewlines": true
}
```

#### Others

- Feel free to contribute any other editor configuration
