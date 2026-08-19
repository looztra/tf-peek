## 1. Plan-loading rewrite (`src/tf_peek/cli.py`)

- [ ] 1.1 Add a helper that returns the plan JSON as `str` given `json_path: Path`: read
      `sys.stdin.buffer.read().decode("utf-8")` when `json_path == Path("-")`, otherwise
      `json_path.open(encoding="utf-8")` / `read_text(encoding="utf-8")`.
- [ ] 1.2 Replace the `with json_path.open() as f: plan = TerraformPlan(**json.load(f))` block in
      `generate()` with a call into the helper from 1.1 followed by `json.loads` and
      `TerraformPlan(**...)`, all inside one `try` block.
- [ ] 1.3 Add the `except` clauses per the design.md table (`OSError`, `UnicodeDecodeError`,
      `json.JSONDecodeError`, `TypeError`, `pydantic.ValidationError`), each writing a one-line
      `typer.echo(..., err=True)` diagnostic and `raise typer.Exit(code=1) from None`.
- [ ] 1.4 Update the `json_path` argument's `help=` text to mention the `-` stdin sentinel.

## 2. Tests (`tests/test_cli.py`)

- [ ] 2.1 Add a stdin-happy-path test: `CliRunner().invoke(app, ["-"], input=plan_json_text)`
      produces the same report as the equivalent file-based invocation (reuse an existing fixture
      plan).
- [ ] 2.2 Add a stdin test for `python -m tf_peek -` (or confirm existing module-invocation test
      infra covers both entrypoints) per the "Module invocation supports stdin identically"
      scenario.
- [ ] 2.3 Add a test: `tf-peek` with **no** `JSON_PATH` at all still exits `2` (usage error),
      unaffected by the new stdin path.
- [ ] 2.4 Add failure-mode tests, each run twice — once via a file path, once via `-` on stdin —
      asserting `exit_code == 1`, a recognizable one-line diagnostic on stderr/output, and **no**
      traceback content (e.g. assert the literal string `"Traceback"` is absent):
  - [ ] 2.4.1 Nonexistent file path (file source only; stdin has no equivalent "missing" case).
  - [ ] 2.4.2 Malformed JSON (`{not valid json`).
  - [ ] 2.4.3 Empty input (empty file / empty stdin) — falls into the malformed-JSON branch per
        design.md Decision 5; assert it's handled, not that it's a distinct message.
  - [ ] 2.4.4 Valid JSON that isn't an object (e.g. `[]` or `"a string"`) — exercises the
        `TypeError` branch.
  - [ ] 2.4.5 Valid JSON object with a structurally wrong `resource_changes` (e.g. a string instead
        of a list) — exercises the `pydantic.ValidationError` branch.
- [ ] 2.5 Add a non-UTF-8-locale regression test for the "Non-ASCII plan content under a non-UTF-8
      locale" scenario: run with a forced non-UTF-8 environment (`LC_ALL=C`/`LANG=C` via
      `monkeypatch.setenv` and re-invoking in-process, or a subprocess invocation if the interpreter
      has already cached locale-derived stream encodings) against a plan containing a non-ASCII
      resource attribute value, for both file and stdin sources.

## 3. Documentation

- [ ] 3.1 `docs/reference/cli.md`: update the Synopsis to show `JSON_PATH | -`, add a row/note to
      the Arguments table describing the `-` stdin sentinel, add a `terraform show -json plan.tfplan
      | tf-peek -` entry to Examples, and add a short note under the existing exit-code-1 row
      confirming it now covers a deliberate, tested diagnostic (not just "whatever Python raises").
- [ ] 3.2 `docs/architecture/01-architecture-overview.md`: extend step 2 ("Parse plan") to note the
      plan is read from either a file or stdin (`-`), decoded as UTF-8 explicitly.

## 4. Verification

- [ ] 4.1 Run `poe lint:all` (ruff, pyright, pylint, ty) and `poe test`; both green.
- [ ] 4.2 Manually smoke-test `terraform show -json <planfile> | tf-peek -` (or an equivalent
      fixture plan piped via `cat fixture.json | tf-peek -`) and confirm the rendered report matches
      the file-based invocation byte-for-byte.
- [ ] 4.3 Manually smoke-test each failure mode from 2.4 against the built CLI (not just the test
      suite) to confirm the diagnostic is legible and no traceback reaches the terminal.
