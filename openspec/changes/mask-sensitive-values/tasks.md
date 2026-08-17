## 1. Model

- [ ] 1.1 Add `before_sensitive: bool | dict[str, Any] | list[Any] | None = None` and
      `after_sensitive: bool | dict[str, Any] | list[Any] | None = None` to `models.Change`
      (`src/tf_peek/models.py`)

## 2. Masking logic

- [ ] 2.1 Add a helper (e.g. `_is_sensitive(marker: bool | dict | list | None) -> bool`) that
      recursively walks a sensitivity marker and returns `True` if any leaf is truthy — see
      design.md Decision D2
- [ ] 2.2 Extend `calculate_diff` to accept `before_sensitive` and `after_sensitive` params; for
      each key in `all_keys`, mask (`val_before = val_after = "(sensitive value)"`) when
      `_is_sensitive(before_sensitive.get(k))` or `_is_sensitive(after_sensitive.get(k))` is true
      — union of both sides per design.md Decision D3
- [ ] 2.3 Update the `calculate_diff` call site in `generate()` (`main.py`) to pass
      `rc.change.before_sensitive` / `rc.change.after_sensitive`

## 3. CLI

- [ ] 3.1 Add `--show-sensitive` boolean option to `generate()`, default `False`
- [ ] 3.2 When `--show-sensitive` is set, skip masking (pass `None`/skip the sensitive params so
      `calculate_diff` behaves as it does today)

## 4. Tests

- [ ] 4.1 Remove the `@pytest.mark.xfail` marker from
      `tests/integration/test_defects.py::test_sensitive_values_not_leaked` and confirm it passes
- [ ] 4.2 Add a fixture and test covering nested `dict`-shaped sensitivity markers (Decision D2) —
      assert the entire top-level attribute is masked when only a nested leaf is sensitive
- [ ] 4.3 Add a test covering the one-sided case (sensitive in `after_sensitive` but not
      `before_sensitive`, and vice versa) — Decision D3
- [ ] 4.4 Add a test covering `--show-sensitive`: same fixture as 4.1, flag passed, underlying
      values render unmasked
- [ ] 4.5 Add a fast in-process unit test for `calculate_diff`'s masking behavior directly
      (mirrors the existing `test_calculate_diff_returns_sorted_keys` style), covering flat,
      nested, and one-sided cases without going through the CLI

## 5. Docs

- [ ] 5.1 Document `--show-sensitive` in `docs/reference/cli.md`
- [ ] 5.2 Flip the `0.1` row's Status cell in
      `docs/studies/2026-08-15-capability-and-market-analysis.md` §7 from
      `🚧 In progress` to `✅ Done` once this change is merged

## 6. Verification

- [ ] 6.1 `make lint` and `make tests` pass
- [ ] 6.2 `make integration-tests` passes with no `xfail` regressions on the remaining D2–D5
      ledger entries (only D1's marker should be removed)
