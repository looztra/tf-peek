## 1. Deterministic report ordering

- [x] 1.1 Audit every report-visible collection traversal and confirm it is explicitly ordered, stably sorted, or derived from Terraform plan-list order; do not alter the already-stable resource and action ordering.
- [x] 1.2 Traverse the complete changed-property union in ascending lexical order before constructing each resource diff.

## 2. Regression coverage

- [x] 2.1 Remove the strict `xfail` marker from the D2 multi-process hash-seed regression without weakening its byte-identity assertion.
- [x] 2.2 Remove the strict `xfail` marker from the D2 unit regression and retain its lexical diff-key assertion.
- [x] 2.3 Regenerate the integration golden snapshot only if deterministic property ordering changes its expected Markdown bytes.

## 3. Verification and documentation

- [x] 3.1 Run `poe lint:all`, `poe test`, and `make integration-tests`; all D2 regressions must pass and no remaining strict expected failure may unexpectedly pass.
- [x] 3.2 Mark P0 item 0.2 as complete in `docs/studies/2026-08-15-capability-and-market-analysis.md` after verification succeeds.
