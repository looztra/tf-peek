## Context

`generate()`'s plan-loading block is three lines (`src/tf_peek/cli.py:100-103`):

```python
config = load_config(config_file)
with json_path.open() as f:
    plan = TerraformPlan(**json.load(f))
```

`json_path: Path = typer.Argument(...)` is required. `TerraformPlan` (`src/tf_peek/models.py:41-44`)
is a Pydantic `BaseModel`. Nothing here is caught; any failure propagates to Typer's default
Rich-based uncaught-exception handler. See `proposal.md` for why this is being fixed alongside
stdin, not separately, and `specs/cli-invocation/spec.md` for the resulting requirements.

## Goals / Non-Goals

**Goals:**
- `tf-peek -` / `python -m tf_peek -` read the plan from stdin.
- File and stdin sources decode as UTF-8 deterministically, independent of locale.
- Every plan-loading failure (bad path, bad bytes, bad JSON, bad structure) produces one stderr
  line and exit `1` — no traceback, on either source.

**Non-Goals:**
- Auto-detecting stdin when `JSON_PATH` is omitted (rejected option; see Decisions).
- Reading `--config` from stdin, or any other stream multiplexing.
- Changing exit code semantics that already exist and are already covered by tests (e.g. the
  `--fail-on-critical-on` invalid-action usage error stays exit `2`, untouched by this change).
- Rewriting `_gate_triggered` or anything downstream of a successfully parsed `TerraformPlan`.

## Decisions

**1. Trigger: literal `-` sentinel, argument stays required.**
Rejected auto-detect-on-omission (`typer.Argument` becoming `Optional[Path]`, falling back to
`sys.stdin.isatty()`): it turns "forgot the argument" from a clean usage error into either a hang
(interactive terminal, stdin never closes) or a silent empty-plan failure (stdin redirected from
`/dev/null` in a cron/systemd context, which is not a tty but also isn't the plan). The explicit
sentinel keeps `JSON_PATH` required and its absence a usage error in every environment, matching
`cat -`, `tar -f -`, `git diff --no-index -`.

Rejected `typer.FileText` / `click.File` (Typer/click's built-in `-` handling): click validates
File-typed arguments during parsing, so a missing/unreadable path becomes a `click.UsageError` →
exit `2`. `docs/reference/cli.md` documents file-not-found under exit `1` ("Runtime error"), not
exit `2` ("Usage error... malformed positional input") — a nonexistent path is syntactically valid
input that refers to nothing, not malformed syntax. Using `click.File` either breaks that
documented split or requires overriding click's exception class, which erases the "less code"
appeal it would otherwise have. Manual sentinel detection keeps loading errors on one exception
path, controlled by us, exit `1`, matching the existing `_version_callback` pattern
(`cli.py:36-40`).

**2. Encoding: explicit UTF-8 on both file and stdin reads.**
`Path.open()` and `sys.stdin`'s default text wrapping both use the ambient locale encoding unless
told otherwise. File reads change from `json_path.open()` to `json_path.open(encoding="utf-8")` (or
`json_path.read_text(encoding="utf-8")`). Stdin reads use `sys.stdin.buffer.read().decode("utf-8")`
rather than reading `sys.stdin` directly in text mode, since `sys.stdin`'s text-mode encoding is
locale-dependent even when an explicit `encoding=` isn't threaded through click's own stream
helpers. This mirrors the write side's existing explicit `encoding="utf-8"` on `--output`
(`cli.py:115`), which carries a comment about exactly this class of failure.

**3. A single acquisition point, one exception-handling boundary.**
Introduce one helper that returns the plan JSON as a `str` regardless of source (`Path("-")` →
stdin bytes decoded UTF-8; otherwise → file read UTF-8), and wrap *both* that read and the
subsequent `json.loads` / `TerraformPlan(**...)` construction in a single `try/except` in
`generate()`. Rationale: the spec requires identical failure behavior across sources, and a shared
boundary is the only way to guarantee that without duplicating the except-and-format logic per
source.

**4. Exceptions caught, and how each maps to a one-line diagnostic:**

| Exception | Cause | Message shape |
| :--- | :--- | :--- |
| `OSError` (covers `FileNotFoundError`, `PermissionError`, `IsADirectoryError`) | Bad file path | `tf-peek: cannot read plan '<path>': <os error>` |
| `UnicodeDecodeError` | Non-UTF-8 bytes, either source | `tf-peek: plan is not valid UTF-8: <detail>` |
| `json.JSONDecodeError` | Syntactically invalid JSON | `tf-peek: plan is not valid JSON: <detail>` |
| `TypeError` | Valid JSON, but not an object (e.g. a bare JSON array or string) — `TerraformPlan(**json.loads(...))` raises `TypeError` when unpacking a non-mapping | `tf-peek: plan JSON must be an object, got <type>` |
| `pydantic.ValidationError` | Valid JSON object, wrong/missing fields | `tf-peek: plan does not match the expected structure: <first error, count of rest>` |

All five raise `typer.Exit(code=1)` after writing to stderr via `typer.echo(..., err=True)` —
no traceback, matching `_version_callback`. `ValidationError` can carry many field errors; the
diagnostic surfaces the first (`exc.errors()[0]`) plus a count of the rest, keeping it one line
without discarding that more detail exists (`pydantic`'s full `str(exc)` remains available to
anyone who reproduces with `--show-sensitive`-style manual debugging, just not dumped by default).

**5. Empty stdin is not special-cased.**
`b"".decode("utf-8")` succeeds (empty string), so an empty pipe reaches `json.loads("")`, which
raises `json.JSONDecodeError("Expecting value", ...)` — already covered by the JSON-decode branch.
No separate "empty input" check needed; it falls out of the existing exception mapping for free.

## Risks / Trade-offs

- **[Risk] A literal file named `-` becomes unreachable via the bare argument.** → Standard,
  accepted Unix trade-off; document it in `docs/reference/cli.md` (`./-` works around it).
- **[Risk] `pydantic.ValidationError.errors()[0]` message wording is somewhat implementation-tied
  to the current model shape** (e.g. if `models.py` gains stricter field types later, the exact
  wording of the "first error" shifts). → Acceptable: the spec requirement is "a diagnostic and
  exit 1", not a specific wording; tests should assert on exit code and the presence of a
  recognizable substring, not the full Pydantic message.
- **[Risk] Reading `sys.stdin.buffer.read()` blocks until EOF if stdin is an interactive terminal
  and the user typed `tf-peek -` by mistake.** → Accepted per Decision 1: matches `cat -`
  convention; `Ctrl-D` (or `Ctrl-Z` on Windows) ends input as usual. Not treated as an error case
  because it isn't one — the user explicitly asked for stdin.

## Migration Plan

No data migration. Behavior-only change, additive for stdin, and a strict tightening (uncaught
crash → clean exit 1) for the error paths — no currently-passing invocation's exit code changes.
Rollout is a normal merge; no feature flag needed given the size and the fact every new branch is
covered by new tests before merge (see `tasks.md`).
