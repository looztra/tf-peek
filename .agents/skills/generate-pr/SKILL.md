---
name: generate-pr
description: Create or update a GitHub pull request from the current branch with semantic commit conventions, safe commit selection, template-compliant PR descriptions, and tool fallback (GitHub CLI then GitHub MCP server).
argument-hint: Branch or change summary to use for the PR
license: Apache-2.0
metadata:
  last-updated: 2026-07-22
---

# Generate Or Update Pull Request

## Outcome

Create a PR when none exists for the current branch, or update the existing PR title/description so it accurately represents all branch changes.

## When To Use

- Opening a PR for local branch changes
- Syncing an existing PR title/description after new commits
- Preparing a standards-compliant PR body from a repository template

## Procedure

1. Inspect repository state: verify `gh --version` and `gh auth status` (see PR Creation And Update Rules for the MCP fallback if `gh` is unavailable or unauthenticated).
2. Determine the current branch (`git branch --show-current`) and the default branch (`git remote show origin | grep "HEAD branch"`).
3. If current branch equals default branch, stop and tell the user a feature branch is required before creating a PR.
4. Invoke the `commit-and-push` skill to bring the branch up to date on the remote. It handles: the protected-branch check, reviewing the full diff scope against the default branch, safe commit selection (only staged/clearly-related files, never unrelated work-in-progress, ignored files, secrets, or ambiguous files — asking the user when ambiguous), one commit per logical change with conventional type + mandatory scope, and pushing with upstream fallback.
5. Check whether a PR already exists for the current branch (`gh pr view`).
6. Resolve the PR base branch carefully before creating/updating:
   - If a PR already exists, use its current base branch unless the user explicitly asks to change it.
   - If no PR exists, derive a base-branch candidate from branch context (for example branch upstream/merge target, release branch naming, or recent repo conventions) instead of defaulting directly to `main`.
   - Use the repository default branch only as a last-resort fallback when no better signal exists.
7. If the correct base branch is not obvious with high confidence, explicitly ask the user to validate the base branch before creating the PR.
8. If no PR exists, create one with the validated base branch.
9. If a PR exists, update title and description only when needed.

## Gathering Missing Information

Check first whether the following can be inferred from commit messages, branch name (e.g. `fix/issue-123`), or changed files: related issue number, problem/motivation, type of change, and test procedure. Only ask the user when it's genuinely missing — for example:

> I couldn't find a related issue number in the commit messages or branch name. What GitHub issue does this PR address? (Enter the issue number, or "N/A" for small fixes)

## PR Creation And Update Rules

1. Prefer GitHub CLI when available/authenticated.
2. If GitHub CLI is unavailable, use GitHub MCP tools.
3. If neither GitHub CLI nor GitHub MCP tools is available/authenticated, stop and instruct the user to run `gh auth login` (and install `gh` if missing) before retrying.
4. Never assume the repository default branch is the right PR base branch.
5. For new PR creation, determine base branch using this priority order:
   - Explicit user instruction
   - Existing PR metadata for the same head branch (if any)
   - Branch upstream/merge target metadata
   - Clear branch/release conventions in the repository
   - Repository default branch (last resort only)
6. If base branch inference is ambiguous, stop and explicitly ask the user to validate the base branch before creating the PR (for example: "I inferred `<candidate-base>` as the PR base. Can you confirm?").
7. PR title must follow semantic commit style with mandatory scope and describe the main change in the full PR, not just the last commit.
8. Update existing PR title/description when they do not reflect all branch commits, miss required template sections, or violate title convention.
9. Always pass the resolved base branch explicitly in PR creation commands (`gh pr create --base <resolved-base>` and MCP create-PR `base` field) instead of relying on tool defaults.
10. Write the PR body to a temporary file first (e.g. `gh pr create --title "..." --body-file /tmp/pr-body.md --base <resolved-base>`) rather than passing it inline via `--body` — this avoids shell-escaping issues with markdown, newlines, and checkboxes. Delete the temp file once the PR is created/updated.
11. If the user asks for a draft PR, add `--draft` to the `gh pr create` invocation.

## PR Description Rules

1. Use the repository PR template when one exists.
2. If no template is found, use this fallback structure: [Summary], [Changes], [Testing instructions].
3. Summarize all changes in the branch, not just the latest commit.
4. Group changes by type instead of listing each file.
5. Be concise and specific.
6. If required template fields need unknown information (for example related issue), stop and ask the user for the missing information instead of guessing.
7. In testing sections, include only manual/functional checks a reviewer can execute.
8. Do not include praise about CI/CD status, test counts, or coverage percentages.

## Accuracy And Safety Checks

- Never mark checkboxes for tasks not performed or verified by the current agent run.
- When updating an existing PR authored by others, preserve unchecked/checked state unless there is direct evidence the task was completed.
- Ensure the final PR text is consistent with branch contents and commit history.
- Never rebase, squash, or force-push without the user's explicit confirmation for that specific action — offer it as a suggestion when history looks messy, but do not perform it unilaterally.

## Error Handling

- **No commits ahead of the default branch**: tell the user there's nothing to submit and ask if they meant a different branch.
- **PR already exists**: show it (`gh pr view`) and proceed to update it instead of creating a new one.
- **Merge conflicts with the base branch**: report the conflict and let the user decide how to resolve it; do not resolve or rebase automatically.

## Post-Creation

After creating or updating the PR:

1. Display the PR URL.
2. Mention that CI checks will run automatically.
3. Offer optional follow-ups the user can request: adding reviewers (`gh pr edit --add-reviewer`) or labels (`gh pr edit --add-label`).

## Important Context

The agent may not be the original author of branch commits. It is still responsible for delivering a complete, accurate PR title and description aligned with repository standards.
