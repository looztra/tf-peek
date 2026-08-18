## 1. Revert the exact-patch pin

- [x] 1.1 `.python-version`: `3.14.7` → `3.14` (back to the floating pin this branch started from).
- [x] 1.2 Delete `openspec/changes/archive/2026-08-18-pin-exact-python-3.14-patch` (superseded by this
      change).

## 2. Verification (in the container that originally reproduced the bug)

- [x] 2.1 Confirmed the container's `uv` (`0.8.17`, dated `Mar 31` on disk) cannot resolve 3.14 GA at
      all: `uv python install 3.14.7` → `No download found for request:
      cpython-3.14.7-linux-x86_64-gnu`.
- [x] 2.2 `pip install --user --upgrade uv` → `uv 0.12.5`; `uv python list` now shows
      `cpython-3.14.7-linux-x86_64-gnu` as a download candidate.
- [x] 2.3 With `.python-version` reverted to the floating `3.14` and no other project change,
      `uv python install 3.14` fetches `3.14.7` and `uv run pytest -q` passes all 83 tests — the
      floating pin was never the problem once `uv` itself is current.
- [ ] 2.4 Not reproducible from this branch alone: confirm the PR #100 hook commit
      (`.claude/hooks/session-start.sh` upgrading `uv` and pre-warming `.python-version`) lands and a
      fresh Claude Code on the web session on this repo no longer hits the pydantic/3.14 rc regression.
