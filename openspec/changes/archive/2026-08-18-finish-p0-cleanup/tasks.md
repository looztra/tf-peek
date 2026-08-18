## 1. `--version` flag

- [x] 1.1 Add an eager `--version`/`-V` option to the `generate` command in
      `src/tf_peek/main.py` that reads the installed version via
      `importlib.metadata.version("tf-peek")`, prints it to stdout, and exits `0` before
      `json_path` is validated. The flag is declared on `generate` (not on an app-level callback)
      because Typer 0.27 collapses single-command apps, and the design intent for this P0 cleanup
      is to keep the single-command shape — see design.md "Decision rejected" and "Risks" for why
      the structural move is deferred to the PR that adds a second command.
- [x] 1.2 Add a test asserting `tf-peek --version` and `tf-peek -V` print the installed version and
      exit `0` without requiring `json_path`. The test monkeypatches `_package_version` to a known
      sentinel so it asserts a real output contract, not the same API the implementation calls.
- [x] 1.3 Add a regression test asserting `tf-peek generate plan.json` exits with code `2` and the
      output mentions "unexpected extra argument" (guards against silently reintroducing the broken
      subcommand shape; the strict assertion also rejects a crash inside `generate` from passing).
- [x] 1.4 Make the `PackageNotFoundError` fallback honest: on metadata lookup failure, write a
      one-line diagnostic to stderr and exit `1`. Add the matching scenario to
      `specs/cli-invocation/spec.md` and the exit code to `docs/reference/cli.md`.
- [x] 1.5 Strengthen `test_version_callback_is_silent_during_resilient_parsing` to assert
      `capsys.readouterr().out == ""` so removing the `ctx.resilient_parsing` guard while leaving
      the `echo` cannot keep the test green.
- [x] 1.6 Defer the move of `--version` to an `@app.callback()` to whichever PR adds a second
      `@app.command()`. The risk is recorded in design.md; do not silently add a second command
      without addressing it.

## 2. Documentation corrections (drop `generate`)

- [x] 2.1 Fix `README.md`: `tf-peek generate plan.json` → `tf-peek plan.json`
- [x] 2.2 Fix `docs/tutorial/first-report.md`: all `tf-peek generate ...` invocations
- [x] 2.3 Fix `docs/how-to/generate-a-report.md`: all `tf-peek generate ...` invocations
- [x] 2.4 Fix `docs/how-to/install.md`: `tf-peek generate --help` → `tf-peek --help`
- [x] 2.5 Fix `docs/reference/cli.md`: usage synopsis and all example invocations; verified the
      documented exit-code-1 "configuration error" claim against actual behavior — `tf-peek` also
      emits exit `2` for usage errors (missing/unexpected arguments, unknown option), and the
      exit-code-2 row is now in the reference. The `cli-invocation` spec's `Legacy generate
      subcommand is rejected` scenario depends on this exit code.
- [x] 2.6 Fix `docs/architecture/03-endpoints-and-dependencies.md`: usage line and diagram label
- [x] 2.7 Document the new `--version`/`-V` flag in `docs/reference/cli.md`

## 3. Architecture doc corrections

- [x] 3.1 Rewrite pipeline step 5 of `docs/architecture/01-architecture-overview.md` to
      distinguish `silent`-tier resources (only counted, never rendered) from `summary`-detail
      resources (rendered as a title-only collapsible entry with no attribute diff). The previous
      rewrite conflated the two. Cross-checked against
      `openspec/specs/resource-tier-config/spec.md` and `templates/report.md.j2`.
- [x] 3.2 Rewrite the "Declarative configuration" Core Principle bullet of
      `docs/architecture/01-architecture-overview.md` to describe the tier-classification model
      (`silent` / `normal` / `critical`, plus `full` / `summary` detail) instead of the retired
      `filtering and summarization` vocabulary.
- [x] 3.3 Rewrite the data-flow mermaid diagram in
      `docs/architecture/03-endpoints-and-dependencies.md` to replace the retired
      `Filter resource_changes\nignore / summarize rules` node with the current
      `Classify actions` + `Classify tier` nodes. The previous patch edited the diagram's
      invocation label but left the stale model in place one line below, so the two architecture
      docs now contradict each other.
- [x] 3.4 Replace the option table in `docs/architecture/03-endpoints-and-dependencies.md` with a
      pointer to `docs/reference/cli.md`. The table was drifting from the reference (already
      omitted `--show-sensitive`; would also drift on `--version`) and the document's job is data
      flow, not option enumeration.

## 4. Project metadata

- [x] 4.1 Fix `pyproject.toml` `description` field to describe tf-peek (visible on the PyPI project
      page)
- [x] 4.2 Fix `AGENTS.md` lines 3 and 7: replace `yamkix` references with `tf-peek` /
      `looztra/tf-peek`

## 5. Verification

- [x] 5.1 Run `poe lint:all`
- [x] 5.2 Run `poe test` (full suite, including the new `--version` and regression tests)
- [x] 5.3 Manually run `tf-peek --version`, `tf-peek -V`, and `tf-peek generate plan.json` against a
      sample plan to confirm behavior matches the spec scenarios
- [x] 5.4 Grep the repo for any remaining `tf-peek generate` occurrences to confirm none were missed
- [x] 5.5 Run `pre-commit run --all-files markdownlint-cli2` (docs lint clean)
