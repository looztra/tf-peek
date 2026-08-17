## Context

`main.py` defines a single `@app.command()` function `generate` on a bare `typer.Typer()` app.
Typer's documented behavior: a `Typer` app with exactly one registered command collapses to that
command being invoked directly, without its name, unless `no_args_is_help`/multi-command wiring
opts back in. Every doc site currently shows `tf-peek generate plan.json`, which typer has never
actually accepted. See `proposal.md` - Why for the decision to drop `generate` rather than wire it
up as a real subcommand.

## Goals / Non-Goals

**Goals:**
- Make every documented invocation match what the CLI actually accepts today.
- Add `--version`/`-V` without introducing a second command or changing the single-command shape.
- Fix the three stale project-metadata sites called out in the proposal (`pyproject.toml`
  description, `AGENTS.md` repo name, `docs/architecture/01` filtering model) as part of the same
  P0-cleanup pass.

**Non-Goals:**
- Restructuring the CLI into multiple subcommands (e.g. for a future `tf-peek init --provider gcp`
  from P1) - out of scope here, revisit if/when that lands.
- Deciding a target version number - left to release-please's conventional-commit inference.
- Any change to report content, tiering, masking, or rendering.

## Decisions

**Drop `generate`, keep the function name internally.** The typer command function can keep its
Python name `generate` (it's an internal implementation detail, not part of the spec) - only the
*documented invocation* changes, from `tf-peek generate plan.json` to `tf-peek plan.json`. No code
change is required for this half of the change; it is a documentation correction across 6 files.
Alternative considered (wiring `generate` up via `app.add_typer`) was rejected during exploration:
it would commit the CLI to a subcommand shape before P1's `--fail-on-critical` decides whether that
flag needs its own subcommand too, and nothing is currently depending on the broken invocation.

**Implement `--version` via `importlib.metadata.version("tf-peek")`, not a hardcoded string.**
Reads the installed distribution's version at runtime, so it never drifts from what
release-please/hatch actually published - the same approach `pip`, `ruff`, and most PyPI CLIs use.
Alternative considered: a `__version__` constant in `__init__.py` - rejected because it requires a
second place to update on every release, which is exactly the kind of drift D6 punished elsewhere in
this codebase (docs describing behavior the code doesn't have).

**`--version`/`-V` is eager and bypasses `JSON_PATH` validation.** Implemented as a typer
`is_eager=True` callback option on the existing `generate` function, consistent with typer's own
documented pattern for version flags. This is why the spec requires `tf-peek --version` to work
without a `JSON_PATH` argument even though `json_path` is otherwise a required positional argument.

## Risks / Trade-offs

**[Risk]** Removing `generate` from docs is a breaking change for any external user who has, despite
D6, found a working invocation and scripted around it (e.g. by wrapping `tf-peek` in a shell function
that always prepends `generate` and silently ignores the resulting error). → **Mitigation**: the
study's own reproduction confirms `tf-peek generate plan.json` exits non-zero with an "unexpected
extra argument" error today, so no working script depends on it; changelog entry calls this out
explicitly for release-please's changelog generation to surface it as a fix, not silently.

**[Risk]** `importlib.metadata.version` raises `PackageNotFoundError` when running from an editable
checkout without the package installed (e.g. `python -m tf_peek.main` against a raw source tree
outside `uv run`/an installed venv). → **Mitigation**: project is `uv`-managed and always run via
an installed (editable or built) distribution per `AGENTS.md`; this is the same constraint every
other `importlib.metadata`-based CLI accepts, and CI/dev workflows already install the package
before invoking it.

## Migration Plan

Docs-only + additive CLI flag - no data migration. Deploy as a normal merge; release-please picks up
the `fix:`/`docs:` commits and infers the appropriate version bump. No rollback concerns beyond a
normal revert.
