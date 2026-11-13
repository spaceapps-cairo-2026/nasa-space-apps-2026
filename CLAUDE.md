# Team rules for every Claude session

Read this whole file before doing anything. It is loaded automatically by Claude Code.

## What we are building

- The chosen challenge and the problem statement live in `docs/CHALLENGE.md`.
- The one sentence pitch lives at the top of `docs/PITCH.md`.
- If either is still a template, STOP and ask the human which challenge we picked.
- Background research (rules, judging criteria, past winners, competition) is in `docs/RESEARCH.md`.
- Data sources and how to get them: `docs/DATA.md`. Statistics and AI spec: `docs/METHODS.md`. Read METHODS before writing any analysis code.

## Lanes: who owns what

| Lane | Account | Branch | Owns (may edit) | Must not edit |
|---|---|---|---|---|
| A: Integrator + ML | Mohammed, account 1 | `lane/a-ml` | `ml/`, `contracts/`, `CLAUDE.md`, `docs/DECISIONS.md` | `app/` |
| B: API + App | Mohammed, account 2 | `lane/b-app` | `api/`, `app/` | `ml/`, `data/` |
| C: Data + Science + Story | Friend's account | `lane/c-data` | `data/`, `docs/RESEARCH.md`, `docs/PITCH.md`, `docs/REFERENCES.md`, `demo/` | `app/`, `ml/` |

Everyone may append to `TASKS.md` and `docs/LOG.md`.

## The rules

1. **Stay in your lane.** Need a change in someone else's folder? Add a line to `TASKS.md` under their lane starting with `REQUEST:`. Do not edit their files.
2. **`contracts/` is the law.** Every shape that crosses a lane boundary is defined in `contracts/prediction.schema.json` and `contracts/api.md`. Only lane A changes them, and must bump `version` in the schema and write the change in `docs/DECISIONS.md`.
3. **Mock first.** `contracts/fixtures/*.json` are valid example outputs. The app and API must work with `MOCK=1` before the real model exists. Never block on another lane.
4. **Small commits, push often, integrate by pull request.** Commit every 30 to 60 minutes on your lane branch and push it. Keep one open pull request (PR) per lane into `main` (`/handoff` creates it). GitHub runs the tests on every push (the "check" workflow). Only lane A merges PRs, and only when "check" is green.
5. **Green before push.** Run `python run.py check` before every push. A red `main` is an emergency.
6. **No big files, no secrets.** `data/raw/` and `data/cache/` are gitignored. Tokens go in `.env` (gitignored).
7. **Cite as you go.** Every dataset, library, image, and AI tool used goes into `docs/REFERENCES.md` the moment you use it. Space Apps requires all external resources to be listed.
8. **Leave a trail.** When you finish a task, tick it in `TASKS.md` and add one line to `docs/LOG.md`: `HH:MM | lane | what changed`.
9. **Boring and working beats clever and broken.** No new framework or library after Saturday 13:00 without lane A's OK.
10. **Statistics honesty.** Never call something significant unless the corrected Mann-Kendall test AND the FDR q-value pass. Say "not proven", never "no change". Never claim causes; say "consistent with".
11. **Ask the human when unsure about scope.** Do not invent product features that are not in `docs/CHALLENGE.md`.

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
- Frontend is plain HTML + JS with CDN libraries (Leaflet, Plotly). No build step.
- Never use long dashes in any user facing text, slides, or docs.

## Where things live
- Project: `D:\nasa_space_apps` (lane B worktree on Mohammed's laptop: `D:\nasa_space_apps_b_app`)
- Python packages: the global Python install. No virtual environment; `python run.py ...` uses the Python that runs it.
- Everything else for the project (data, caches, worktrees) stays on D: inside the project folders.
- Team setup guide: `docs/TEAM_SETUP.md`
