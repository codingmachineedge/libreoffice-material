# Repository agent instructions

## Shared repository completion memory

- Every task that changes this repository must end with all intended task work committed and pushed.
- Review every local and remote branch, linked worktree, and stash before cleanup. Preserve useful work in commits, integrate every completed branch or worktree into the default branch, and verify each source tip is an ancestor of the pushed remote default branch.
- Never delete a branch, worktree, stash, or checkout that contains uncommitted, unmerged, or unpushed work.
- After remote proof, remove merged temporary branches, linked worktrees, their on-disk directories, stale worktree metadata, and redundant stashes.
- The final handoff target is a clean default checkout, no staged, unstaged, untracked, or stashed task work, and zero divergence from the remote default branch. Preserve and report unrelated pre-existing work instead of discarding it.
- Record significant completion and cleanup decisions in a repository-tracked handoff or memory file and push that update.
- Never force-push unless the user explicitly requests a history rewrite and the consequences have been reviewed.

## Documentation synchronization

- Keep `ROADMAP.md`, `README.md`, and the project wiki (`docs/` evidence pages
  and the `site/` documentation surface) updated in step with each milestone as
  work proceeds — never let a source milestone land without its matching
  documentation update in the same push.
- Documentation must preserve the project's honesty contract: distinguish
  implemented source from build/runtime-verified behavior, and never claim a
  build, screenshot, or accessibility result that has not actually been produced.

## Verification harness and git workflow

- Runtime/interaction verification must be driven through the low-level
  computer-use MCP server at `../lowlevel-computer-use-mcp` (sibling of this
  repo in the GitHub folder; entry point
  `lowlevel_computer_use_mcp.server:main`, also vendored under
  `../desktop-material/vendor/`). Use its headless/off-screen desktop mode to
  exercise a built LibreOffice binary rather than the developer's live session.
- Git push every task that builds (or, for source-only slices, every task whose
  standalone validator and regression suite pass). Do not leave verified work
  unpushed.
- When finished, merge all completed work into the default branch `main`, verify
  each source tip is an ancestor of the pushed remote default, then delete the
  merged temporary branches and linked worktrees and their on-disk directories.
  Never delete a branch, worktree, or stash that still holds uncommitted,
  unmerged, or unpushed work.
