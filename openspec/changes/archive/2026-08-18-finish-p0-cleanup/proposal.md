## Why

The capability & market analysis (`docs/studies/2026-08-15-capability-and-market-analysis.md`) rated
P0 "correctness & safety" as blocking everything else. Six of nine P0 items have since shipped
(sensitive-value masking, deterministic ordering, value hardening, the integration harness). Three
remain, and none of the six shipped items is safe to call "done" while they're open:

- **D6**: every documented invocation (`tf-peek generate plan.json`) has never worked. Typer
  collapses a single-command app, so the real invocation is `tf-peek [OPTIONS] JSON_PATH`. The first
  command in the tutorial fails today.
- **M8**: no `--version` flag — table stakes for a CLI, and it makes bug reports harder to triage.
- Project-metadata rot: `pyproject.toml`'s PyPI-visible description is still the uv scaffold
  placeholder, `AGENTS.md` still describes this repo as `yamkix` (a copy-paste artifact), and
  `docs/architecture/01-architecture-overview.md` still documents the `config.ignore` /
  `config.summarize` filtering model that the tier system superseded.

Decided during exploration: drop `generate` entirely rather than wire it up via `add_typer` — nobody
can be depending on an invocation that has never worked, and it matches what typer already does
today (zero behavior change, only doc corrections). Version numbering is left to release-please's
conventional-commit inference rather than pinned here.

## What Changes

- **BREAKING**: remove `generate` from every documented invocation. The CLI keeps its existing bare
  positional shape (`tf-peek JSON_PATH [OPTIONS]`) — this is a **docs-only** correction, not a code
  change, since typer already ignores `generate` as a command name today.
- Add a `--version` flag (and `-V` short form, matching typer/click convention) that prints the
  installed package version and exits.
- Fix `pyproject.toml`'s `description` field to describe tf-peek instead of the scaffold placeholder.
- Fix `AGENTS.md` to reference `tf-peek` / `looztra/tf-peek` instead of `yamkix`.
- Rewrite the "Filter resources" step of `docs/architecture/01-architecture-overview.md` to describe
  the current tier-classification pipeline (`silent` / `normal` / `critical`, `critical_on`) instead
  of the retired `config.ignore` / `config.summarize` model.
- Correct all six other doc sites that show `tf-peek generate`: `README.md`,
  `docs/tutorial/first-report.md`, `docs/how-to/generate-a-report.md`, `docs/how-to/install.md`,
  `docs/reference/cli.md`, `docs/architecture/03-endpoints-and-dependencies.md`.

## Capabilities

### New Capabilities

- `cli-invocation`: the top-level CLI surface — bare positional invocation
  (`tf-peek JSON_PATH [OPTIONS]`, no subcommand), and `--version`/`-V` behavior. Not currently
  covered by any existing spec; the 8 existing capabilities all describe report *content*, not the
  invocation contract.

### Modified Capabilities

_None._ No existing spec describes CLI invocation or versioning, so there is nothing to amend —
only a new capability to add. The `pyproject.toml`, `AGENTS.md`, and architecture-doc fixes are pure
metadata/documentation corrections with no behavioral requirement to specify.

## Impact

- **Code**: `src/tf_peek/main.py` — add a `--version` option (reads the installed distribution
  version, e.g. via `importlib.metadata.version`).
- **Tests**: new coverage asserting `tf-peek --version` / `-V` prints the version and exits 0, and
  that bare invocation with no subcommand still works (regression guard against a future
  `generate`-shaped reintroduction).
- **Docs**: `README.md`, `AGENTS.md`, `docs/tutorial/first-report.md`,
  `docs/how-to/generate-a-report.md`, `docs/how-to/install.md`, `docs/reference/cli.md`,
  `docs/architecture/01-architecture-overview.md`, `docs/architecture/03-endpoints-and-dependencies.md`.
- **Packaging**: `pyproject.toml` description field (renders on the PyPI project page).
- **No changes** to report content, tiering, masking, or rendering behavior — this change is CLI
  surface and project metadata only.
