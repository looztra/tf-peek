## 1. `--version` flag

- [ ] 1.1 Add an eager `--version`/`-V` option to the `generate` command in `src/tf_peek/main.py`
      that reads the installed version via `importlib.metadata.version("tf-peek")`, prints it, and
      exits `0` before `json_path` is validated
- [ ] 1.2 Add a test asserting `tf-peek --version` and `tf-peek -V` print the installed version and
      exit `0` without requiring `json_path`
- [ ] 1.3 Add a regression test asserting `tf-peek generate plan.json` still exits non-zero
      (guards against silently reintroducing the broken subcommand shape)

## 2. Documentation corrections (drop `generate`)

- [ ] 2.1 Fix `README.md`: `tf-peek generate plan.json` → `tf-peek plan.json`
- [ ] 2.2 Fix `docs/tutorial/first-report.md`: all `tf-peek generate ...` invocations
- [ ] 2.3 Fix `docs/how-to/generate-a-report.md`: all `tf-peek generate ...` invocations
- [ ] 2.4 Fix `docs/how-to/install.md`: `tf-peek generate --help` → `tf-peek --help`
- [ ] 2.5 Fix `docs/reference/cli.md`: usage synopsis and all example invocations; verify/correct
      the documented exit-code-1 "configuration error" claim against actual behavior while in this
      file
- [ ] 2.6 Fix `docs/architecture/03-endpoints-and-dependencies.md`: usage line and diagram label
- [ ] 2.7 Document the new `--version`/`-V` flag in `docs/reference/cli.md`

## 3. Architecture doc correction

- [ ] 3.1 Rewrite the "Filter resources" step of
      `docs/architecture/01-architecture-overview.md` to describe the current tier-classification
      pipeline (`silent`/`normal`/`critical` via `resource-tier-config`) instead of the retired
      `config.ignore`/`config.summarize` model, cross-checking against
      `openspec/specs/resource-tier-config/spec.md` for accuracy

## 4. Project metadata

- [ ] 4.1 Fix `pyproject.toml` `description` field to describe tf-peek (visible on the PyPI project
      page)
- [ ] 4.2 Fix `AGENTS.md` lines 3 and 7: replace `yamkix` references with `tf-peek` /
      `looztra/tf-peek`

## 5. Verification

- [ ] 5.1 Run `poe lint:all`
- [ ] 5.2 Run `poe test` (full suite, including the new `--version` and regression tests)
- [ ] 5.3 Manually run `tf-peek --version`, `tf-peek -V`, and `tf-peek generate plan.json` against a
      sample plan to confirm behavior matches the spec scenarios
- [ ] 5.4 Grep the repo for any remaining `tf-peek generate` occurrences to confirm none were missed
