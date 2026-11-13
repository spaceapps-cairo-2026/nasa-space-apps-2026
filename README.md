# Space Apps 2026 Cairo: Earth System Trend Detective

A 3D Earth that shows how NASA measurements changed since 2001, where, how fast and how sure we are, and turns those trends into farming decisions.

1. **What we build:** `PROJECT_PLAN.md` (single source of truth)
2. **Who does what, in which order:** `TASKS.md`
3. **Team rules for people and Claude:** `CLAUDE.md`
4. **Which dataset is for what:** `data/README.md`

```
data/  (lane C)  ->  NASA POWER grids + points, crop table
ml/    (lane A)  ->  trend, viability, crop, projection engines -> ml/outputs/
api/   (lane B)  ->  FastAPI serving ml/outputs/ and live point trends
app/   (lane B)  ->  globe, maps, charts, tabs, methods page, tour
```

Every lane can work from minute one because `contracts/fixtures/` holds valid fake output.

## Quick start
In PowerShell, from the repo folder:
```powershell
python run.py setup
python run.py check        # tests green
python run.py mock         # open http://localhost:8000
```

## Team setup (first time)
See `docs/TEAM_SETUP.md`. Short version: lead runs `scripts/setup_team.ps1` once; each teammate runs
`gh repo clone spaceapps-cairo-2026/nasa-space-apps-2026 D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1`

## Running two accounts on one laptop
In PowerShell:
```powershell
# terminal 1: account 1, D:\nasa_space_apps, lane A
cd D:\nasa_space_apps; git checkout lane/a-ml; claude

# terminal 2: account 2, separate worktree + separate login, lane B
.\scripts\second_account.ps1 lane/b-app   # first time: /login with account 2
```

## Rhythm
- Every session starts with `/sync` and ends with `/handoff`.
- Integration merges into `main` at 13:00, 16:00, 20:00, 02:00, 10:00, 14:00 (lane A).
- Feature freeze Sun 14:00. First submission Sun 20:00. Deadline Sun 23:59.
