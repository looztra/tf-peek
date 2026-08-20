## Why

CI pipelines that pipe `terraform show -json` output must currently write it to a temp file before
`tf-peek` can read it — the CLI only accepts a real file path (`JSON_PATH`). This forces an extra
step in every pipeline. Separately, that same file-loading code path has no error handling at all:
a missing file or malformed JSON crashes with an uncaught Python traceback (leaked via Typer's
default Rich exception renderer) instead of a clean diagnostic, and no test covers either failure
mode. Since stdin support requires rewriting the plan-loading code anyway, this is the point to fix
both together rather than reproduce the same untested-crash defect on a new code path.

## What Changes

- Support `tf-peek -` (and `python -m tf_peek -`) to read the plan JSON from stdin instead of a
  file, using the literal `-` sentinel — the standard Unix convention (`cat -`, `tar -`, `git diff
  --no-index -`). `JSON_PATH` remains a required positional argument; omitting it entirely stays a
  usage error (`exit 2`), unchanged.
- Pin plan-JSON reads to UTF-8 explicitly, for both the file path and the new stdin path — matching
  the explicit `encoding="utf-8"` already used on the `--output` write path (`cli.py:115`). Closes a
  latent locale-dependent decode failure (e.g. `LANG=C` containers) that predates this change and
  affects file-based invocation today.
- Wrap plan loading (open/read, `json.load`, `TerraformPlan(**...)` construction) in explicit error
  handling: `FileNotFoundError`, `PermissionError`, `UnicodeDecodeError`,
  `json.JSONDecodeError`, and Pydantic `ValidationError` each produce a one-line diagnostic on
  stderr and exit `1`, instead of an uncaught traceback. Mirrors the existing pattern in
  `_version_callback` (`cli.py:36-40`).
- **BREAKING**: none of the above changes documented exit codes (file-not-found and invalid-JSON
  both already exit `1` today, as an accident of Python's default uncaught-exception behavior); this
  change makes that exit code deliberate and tested rather than removing it. No currently-passing
  invocation changes behavior.

## Capabilities

### New Capabilities

(none — this extends the existing CLI invocation surface, it does not introduce a new capability
area)

### Modified Capabilities

- `cli-invocation`: adds the `-` stdin sentinel as a valid `JSON_PATH` value, and adds explicit,
  tested exit-`1` diagnostics for unreadable/malformed/invalid plan input (file and stdin alike),
  replacing today's undocumented uncaught-traceback behavior.

## Impact

- **Code**: `src/tf_peek/cli.py` — the `generate()` plan-loading block (`cli.py:100-103`) is
  rewritten to branch on the `-` sentinel, pin UTF-8, and catch load/parse/validation errors.
- **Tests**: `tests/test_cli.py` gains stdin-invocation coverage (via `CliRunner.invoke(...,
  input=...)`) and coverage for the three failure modes (missing file, malformed JSON, invalid
  plan structure) asserting a clean stderr diagnostic and `exit_code == 1`, both for file and stdin
  sources.
- **Docs**: `docs/reference/cli.md` (Synopsis, Arguments table, an stdin Example,
  `terraform show -json | tf-peek -`) and `docs/architecture/01-architecture-overview.md` (step 2,
  "Parse plan") get a short update to describe the stdin source and the deliberate error path.
- **Dependencies**: none. No new dependency; `rich` remains a transitive dependency of `typer`
  (used for its default exception renderer, which this change makes unreachable for plan-loading
  errors specifically — not removed, just no longer triggered on this path).
- **Non-goals**: reading `--config` from stdin (single-stream scope only); auto-detecting stdin
  when `JSON_PATH` is omitted (explicit `-` only, per this change's decision); config discovery
  changes (separate, unrelated backlog item).
