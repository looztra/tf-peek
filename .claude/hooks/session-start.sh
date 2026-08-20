#!/bin/bash
set -euo pipefail

# Claude Code on the web only: local sessions are expected to install tools
# themselves via their own package manager of choice.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# SessionStart hooks make env changes outlive the hook by appending export
# statements to $CLAUDE_ENV_FILE, which Claude Code runs as a preamble before
# every later Bash command. Append, never truncate, so other hooks' values
# survive. https://code.claude.com/docs/en/hooks
persist_env() {
  printf '%s\n' "$1" >>"${CLAUDE_ENV_FILE:?CLAUDE_ENV_FILE is unset, cannot persist environment}"
}

# This repo's openspec-*/opsx:* skills (.claude/skills/openspec-*) shell out
# to a bare `openspec` command. The real CLI is published as
# @fission-ai/openspec on npm -- the unscoped `openspec` package on npm is an
# unrelated, unmaintained placeholder and must not be installed instead.
# Pinned to the major version verified against these skills; bump deliberately.
npm install -g "@fission-ai/openspec@^1.9.0"

# mise owns every tool this repo's gates need, from the same .mise.toml that
# jdx/mise-action reads in CI, so this hook only has to obtain a mise binary,
# run `mise install`, and put mise's shims on PATH.
#
# https://mise.run redirects to GitHub Releases, which some sandboxes block.
# mise's npm distribution is the same precompiled binary served from
# registry.npmjs.org (its preinstall pulls @jdxcode/mise-<os>-<arch> from npm,
# never from GitHub), so it works wherever the openspec install above works.
if ! command -v mise >/dev/null 2>&1; then
  curl -fsS https://mise.run | sh || npm install -g mise
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v mise >/dev/null 2>&1; then
  echo "session-start: could not install mise from mise.run or from npm" >&2
  exit 1
fi

# mise's pipx: backend shells out to uvx, so some uv has to exist before
# `mise install` runs. The web container bakes one in; bootstrap from PyPI if
# it ever doesn't. This is only a bootstrap: mise then installs .mise.toml's
# pinned uv, whose shim wins on PATH from the activation below -- the same uv
# CI resolves .python-version with.
if ! command -v uv >/dev/null 2>&1; then
  pip install --user --quiet uv
fi

# Non-interactive: never stop to ask whether this repo's config is trusted.
# The value is a path prefix, so it covers .mise.toml and .mise.sandbox.toml.
export MISE_TRUSTED_CONFIG_PATHS="$project_dir"

# .mise.toml resolves most tools through aqua, which downloads GitHub release
# assets; some sandboxes only allow PyPI, npm and the Go module proxy.
# .mise.sandbox.toml remaps those tools onto reachable backends at the same
# pinned versions, and MISE_ENV=sandbox layers it over .mise.toml. Try the
# CI-identical path first and fall back only when it actually fails: no
# network probe has to guess what this particular sandbox permits.
#
# MISE_ENV has to persist for the session, not just for this hook: a shim
# resolves its tool version from the config, so a later `shellcheck` call with
# MISE_ENV unset would look for the aqua build that was never installed.
if mise install -C "$project_dir"; then
  echo "session-start: installed .mise.toml tools using the default backends"
else
  echo "session-start: default mise backends unreachable, retrying via .mise.sandbox.toml" >&2
  export MISE_ENV=sandbox
  mise install -C "$project_dir"
  persist_env "export MISE_ENV=sandbox"
fi

# Use mise's own shims rather than symlinking tool binaries by hand: shims are
# what mise documents for non-interactive shells, and mise's PATH activation
# cannot work here because it needs a shell rc plus a prompt hook, while the
# Bash tool spawns non-interactive shells that never read ~/.bashrc.
# `mise activate bash --shims` emits exactly the one PATH export we need, with
# the shims directory already resolved (MISE_DATA_DIR included).
# https://mise.jdx.dev/dev-tools/shims.html#shims-vs-path
shims_export="$(mise activate bash --shims)"
eval "$shims_export"
persist_env "$shims_export"

# .pre-commit-config.yaml's editorconfig-checker-system hook invokes `ec`,
# which is the name of the upstream release asset and therefore of the aqua
# shim. The Go module .mise.sandbox.toml falls back to names the very same
# command `editorconfig-checker` and ships no `ec`, so bridge the name when
# only that one is present. ~/.local/bin is already on PATH for every Bash
# call, and the shims directory must not be written to -- mise deletes
# anything it did not create there on the next reshim.
if ! command -v ec >/dev/null 2>&1 && command -v editorconfig-checker >/dev/null 2>&1; then
  mkdir -p "$HOME/.local/bin"
  ln -sf "$(command -v editorconfig-checker)" "$HOME/.local/bin/ec"
fi

# Pre-warm the interpreter `.python-version` requests so the first `uv run` in
# the session doesn't pay the download cost mid-command.
uv python install "$(cat "$project_dir/.python-version")"
