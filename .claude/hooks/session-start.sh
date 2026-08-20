#!/bin/bash
set -euo pipefail

# Claude Code on the web only: local sessions are expected to install tools
# themselves via their own package manager of choice.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# This repo's openspec-*/opsx:* skills (.claude/skills/openspec-*) shell out
# to a bare `openspec` command. The real CLI is published as
# @fission-ai/openspec on npm -- the unscoped `openspec` package on npm is an
# unrelated, unmaintained placeholder and must not be installed instead.
# Pinned to the major version verified against these skills; bump deliberately.
npm install -g "@fission-ai/openspec@^1.9.0"

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# The container image bakes in a pinned `uv` at build time. When that build
# predates a Python GA release, `uv`'s bundled python-build-standalone catalog
# doesn't know the GA build exists, so `uv run`/`uv python install` silently
# fall back to whatever pre-release is already cached locally (e.g.
# cpython-3.14.0rc2) instead of erroring or fetching the real release --
# tripping real interpreter regressions the GA release already fixed (see
# `.python-version` and pydantic/pydantic#12544). Upgrading `uv` here, once
# per session, keeps that catalog current without pinning this repo's
# `.python-version` to an exact patch that would need manual upkeep.
pip install --user --upgrade --quiet uv
# Pre-warm the interpreter `.python-version` requests so the first `uv run`
# in the session doesn't pay the download cost mid-command.
uv python install "$(cat "$project_dir/.python-version")"

# `pre-commit run --all-files` needs pre-commit itself plus the system
# binaries a few hooks shell out to (shellcheck, shfmt, editorconfig-checker
# aka `ec`). CI gets all of these from mise (jdx/mise-action), which reads
# .mise.toml as the single source of truth for versions.
#
# mise itself may or may not be reachable from a given session: its
# installer (mise.run) and most of its tool backends fetch prebuilt
# binaries straight from GitHub Releases, and that path has been blocked by
# this sandbox's network policy in some sessions (only
# pypi.org/files.pythonhosted.org, registry.npmjs.org and the Go module
# proxy were reachable there). That policy isn't guaranteed to be the same
# everywhere this hook runs, so probe it live: use mise directly when
# reachable (matches CI exactly), and only fall back to installing
# equivalent versions from the always-reachable backends (PyPI wheels, Go
# module proxy) when it isn't.
#
# NOTE: the mise branch below could not be exercised while writing this
# hook -- mise.run was blocked in that sandbox -- so it's unverified. If it
# misbehaves somewhere mise.run *is* reachable, tighten it up or report it.
mise_tool_version() {
  python3 -c "
import sys, tomllib
with open('$project_dir/.mise.toml', 'rb') as f:
    v = tomllib.load(f)['tools'][sys.argv[1]]
print(v['version'] if isinstance(v, dict) else v)
" "$1"
}

install_toolchain_via_mise() {
  if ! curl -fsS --max-time 5 -o /dev/null https://mise.run; then
    return 1
  fi
  if ! curl -fsS https://mise.run | sh; then
    return 1
  fi
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v mise >/dev/null 2>&1; then
    return 1
  fi

  # Mirrors CI's MISE_TRUSTED_CONFIG_PATHS so `mise install` doesn't stop to
  # ask for an interactive trust confirmation on this repo's .mise.toml.
  export MISE_TRUSTED_CONFIG_PATHS="$project_dir"
  if ! (cd "$project_dir" && mise install); then
    return 1
  fi

  mise_shims="$(cd "$project_dir" && mise where shims 2>/dev/null)"
  if [ -z "$mise_shims" ]; then
    return 1
  fi
  export PATH="$mise_shims:$PATH"
  # Persist for the rest of the session, not just this hook invocation.
  if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
    return 1
  fi
  echo "export PATH=\"$mise_shims:\$PATH\"" >>"$CLAUDE_ENV_FILE"

  for tool in pre-commit shellcheck shfmt ec; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      return 1
    fi
  done
}

install_toolchain_directly() {
  uv tool install --quiet "pre-commit==$(mise_tool_version 'pipx:pre-commit')" --with pre-commit-uv
  # The shellcheck-py package version is the upstream ShellCheck version plus
  # a packaging suffix (e.g. 0.11.0.1 for ShellCheck 0.11.x); .mise.toml
  # only pins the ShellCheck minor version, so match on that prefix.
  uv tool install --quiet "shellcheck-py==$(mise_tool_version shellcheck).*"

  export GOBIN="$HOME/.local/bin"
  go install "mvdan.cc/sh/v3/cmd/shfmt@v$(mise_tool_version shfmt)"
  # .mise.toml only pins the editorconfig-checker major version; `go
  # install` has no wildcard match, so track latest within that major (the
  # import path is already major-version-locked to v3).
  go install "github.com/editorconfig-checker/editorconfig-checker/v3/cmd/editorconfig-checker@latest"
  ln -sf "$GOBIN/editorconfig-checker" "$GOBIN/ec"
}

if install_toolchain_via_mise; then
  echo "pre-commit toolchain: installed via mise"
else
  echo "pre-commit toolchain: mise unreachable/unavailable, installing directly (PyPI + Go module proxy)"
  install_toolchain_directly
fi
