# Team rules for every Claude session

Read this whole file before doing anything. It is loaded automatically by Claude Code.

## What we are building

**Read `PROJECT_PLAN.md` first. It is the single source of truth (features F0 to F6, lanes, decisions D1 to D9).**
If anything in other docs conflicts with PROJECT_PLAN.md, PROJECT_PLAN.md wins.
**Then read `TASKS.md`:** the task list, who claimed what, and which tasks must wait for others (`needs:`).

- The one sentence pitch lives at the top of `docs/PITCH.md`.
- Algorithms are NOT fixed in advance. When you reach a decision listed in PROJECT_PLAN.md section 9, propose options with evidence on our data, let the human choose, and record it in `docs/DECISIONS.md`.
- Background research (rules, judging criteria, past winners, competition) is in `docs/RESEARCH.md`.
- Data sources and how to get them: `docs/DATA.md`. Candidate statistics methods and lessons so far: `docs/METHODS.md`. Read METHODS before writing any analysis code.

## Lanes: who owns what

| Lane | Who | Branch | Owns (may edit) | Must not edit |
|---|---|---|---|---|
| A: Integrator + analysis | Mohammed, account 1 | `lane/a-ml` | `ml/`, `contracts/`, `CLAUDE.md`, `PROJECT_PLAN.md`, `docs/DECISIONS.md`, `docs/METHODS.md` | `app/` |
| B: API + App | Mohammed, account 2 | `lane/b-app` | `api/`, `app/` | `ml/`, `data/` |
| C: Data + Science + Story | teammates | `lane/c-data` (or `lane/c-<task>` per person) | `data/`, `docs/DATA.md`, `docs/RESEARCH.md`, `docs/PITCH.md`, `docs/REFERENCES.md`, `demo/` | `app/`, `ml/` |

Everyone may edit their own lane's section of `TASKS.md` (claim, tick) and append to `docs/LOG.md`. Before starting a task, check its `needs:` in `TASKS.md`; if a needed task is not on `main` yet, build on the fixtures in `contracts/fixtures/`.

## The rules

1. **Stay in your lane.** Need a change in someone else's folder? Add a line to `TASKS.md` under their lane starting with `REQUEST:`. Do not edit their files.
2. **`contracts/` is the law.** Every shape that crosses a lane boundary is defined in `contracts/prediction.schema.json` and `contracts/api.md`. Only lane A changes them, and must bump `version` in the schema and write the change in `docs/DECISIONS.md`.
3. **Mock first.** `contracts/fixtures/*.json` are valid example outputs. The app and API must work with `MOCK=1` before the real model exists. Never block on another lane.
4. **Small commits, push often, integrate by pull request.** Commit every 30 to 60 minutes on your lane branch and push it. Keep one open pull request (PR) per lane into `main` (`/handoff` creates it). GitHub runs the tests on every push (the "check" workflow). Only lane A merges PRs, and only when "check" is green.
5. **Green before push.** Run `python run.py check` before every push. A red `main` is an emergency.
6. **Small data yes, big files and secrets no.** Small public datasets are committed so everyone has the same data: `data/cache/power/` and `data/processed/`. Never commit a file over 20 MB, `data/raw/`, other `data/cache/` folders (AppEEARS), or anything needing a login; share those via Google Drive. Tokens go in `.env` (gitignored).
7. **Cite as you go.** Every dataset, library, image, and AI tool used goes into `docs/REFERENCES.md` the moment you use it. Space Apps requires all external resources to be listed.
8. **Leave a trail.** When you finish a task, tick it in `TASKS.md` and add one line to `docs/LOG.md`: `HH:MM | lane | what changed`.
9. **Boring and working beats clever and broken.** No new framework or library after Saturday 13:00 without lane A's OK.
10. **Statistics honesty.** Never call something significant unless the trend test chosen in decision D1 AND the FDR q-value pass (until D1 is made: corrected Mann-Kendall, see METHODS). Say "not proven", never "no change". Never claim causes; say "consistent with".
11. **Ask the human when unsure about scope.** Do not invent product features that are not in `PROJECT_PLAN.md`.

## Commands

Everyone is on Windows. Run every command as `python run.py <cmd>` in PowerShell.

- `python run.py setup` install Python deps
- `python run.py mock` run API + app on fixtures at http://localhost:8000
- `python run.py api` run API on real model outputs
- `python run.py power` download Egypt climate grids (no login)
- `python run.py appeears submit|status|download` MODIS request (needs EARTHDATA_USERNAME / EARTHDATA_PASSWORD)
- `python run.py trends` compute trends into ml/outputs/predictions.json
- `python run.py check` run contract tests and API tests
- The app's libraries are bundled in `app/vendor/`, so it works with no internet (only the map tiles need internet)
- `/sync` (slash command) pull main, read TASKS and LOG, pick my next task
- `/handoff` (slash command) write a handoff note before the human sleeps or the usage window runs out

## Style

- Python 3.10+, type hints, small functions.
- Frontend is plain HTML + JS, no build step. Libraries (Plotly, the map library and the globe library chosen in D3) are bundled in `app/vendor/`.
- Never use long dashes in any user facing text, slides, or docs.

## Where things live
- Project: `D:\nasa_space_apps` (lane B worktree on Mohammed's laptop: `D:\nasa_space_apps_b_app`)
- Python packages: the global Python install. No virtual environment; `python run.py ...` uses the Python that runs it.
- Everything else for the project (data, caches, worktrees) stays on D: inside the project folders.
- Team setup guide: `docs/TEAM_SETUP.md`
