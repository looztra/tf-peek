---
name: commit-and-push
description: Safely review git changes, create one or more semantic commits with mandatory scopes, and push the current branch. Use when the user asks to commit changes, push a branch, prepare commits for a PR, or perform a commit-and-push workflow with git.
license: Apache-2.0
metadata:
  last-updated: 2026-07-20
---

# Commit And Push

- Determine the current branch (`git branch --show-current`) and the repository's default branch (`git remote show origin | grep "HEAD branch"`). If the current branch equals the default branch, stop immediately and inform the user that commits should not be made directly to the protected branch.
- Review the full scope of changes: `git status` for uncommitted changes, and if local commits already exist ahead of the default branch, `git log origin/<default-branch>..HEAD --oneline` and `git diff origin/<default-branch>..HEAD --stat` to see what's already committed.
- If there are uncommitted changes (staged or unstaged):
  - Before deciding what to commit, distinguish between changes made by the agent in this session and changes that were already present before the session began (pre-existing or user-authored). For any file with pre-existing changes that the agent did not touch, explicitly ask the user whether to include those changes in the commit or leave them unstaged — do not assume either way.
  - Commit only files that are explicitly staged or clearly related to the change being made. Never commit unrelated work-in-progress, ignored files, secrets/credentials, or ambiguous files — if inclusion is ambiguous, ask the user which files to include.
  - Create one commit per logical change, using semantic commit message conventions with a mandatory scope (for example `fix(scope): ...`, `feat(scope): ...`) and the appropriate type (fix, feat, refactor, chore, etc.).
- After committing, push the changes to the remote repository using git push, unless explicitly instructed not to do so. If git push fails because no upstream branch is set, use git push --set-upstream origin <current-branch-name> and report this action to the user. If git push fails for any other reason, report the exact error output to the user and do not attempt to force-push or alter remote state without explicit instruction.
