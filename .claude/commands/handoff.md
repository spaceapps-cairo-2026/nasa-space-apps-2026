---
description: Write a handoff note before I sleep or my usage window runs out
---
1. Commit and push all work on my lane branch with a clear message (run `python run.py check` first; if red, commit anyway on the lane branch but say so in the note).
   Then make sure a pull request from my lane branch into `main` exists: run `gh pr view` and, if there is none, `gh pr create --base main --fill`.
2. Append to `docs/LOG.md` a block:
   `HH:MM | lane | HANDOFF` then: what is done, what is half done (file + function), the exact next step, and any blocker.
3. Update my lane's checkboxes in `TASKS.md`.
4. Print the note so I can paste it into the team chat.
