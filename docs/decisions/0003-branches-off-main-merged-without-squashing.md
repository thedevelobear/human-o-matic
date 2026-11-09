# 0003. Work branches off `main` and merges without squashing

- **Status:** Accepted
- **Date:** 2026-11-08

- Each change is a branch made from `origin/main` with `--no-track`, named after its main commit type and topic (`feat/topic`, `fix/topic`), and merged into `main` through a PR.
- PRs are merged with a merge commit or a rebase merge, never squashed.
- A branch's commits are small, focused steps, but only its tip has to pass the checks. A writing agent runs the fast checks for what it touched once before it reports, and qa runs every check once, on the tip.
- CI runs on pushes to `main` and on every PR.

**Why:** `--no-track` stops a plain push from landing on `main`. Without squashing, each step stays revertible. CI and qa check the tip, which is what merges, so running the checks after every commit only repeats them.

**Consequences:** A commit in the middle of a branch may not pass on its own, so `git bisect` can stop on one that doesn't.
