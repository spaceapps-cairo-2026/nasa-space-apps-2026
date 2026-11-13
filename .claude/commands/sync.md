---
description: Pull latest main, read the board, and pick my next task
---
Do these steps in order and report briefly:

1. Run `git fetch origin` then `git merge origin/main` on my current lane branch. If there are conflicts in files outside my lane, take the version from main. If conflicts are inside my lane, show them to me and stop.
2. Read `CLAUDE.md`, `PROJECT_PLAN.md`, `TASKS.md`, the last 15 lines of `docs/LOG.md`, and `docs/DECISIONS.md`.
3. Tell me in at most 6 lines: what changed since my last sync (especially anything in `contracts/`), any `REQUEST:` lines addressed to my lane, and the single next task you recommend for my lane: an unclaimed task in my lane's section of `TASKS.md` whose `needs:` are already on `main` (or can be built on fixtures). Give its id, e.g. B3.
4. Run `python run.py check` and report pass or fail.

My lane is given in $ARGUMENTS (A, B, or C). If empty, infer it from the branch name (`lane/a-*`, `lane/b-*`, `lane/c-*`).
