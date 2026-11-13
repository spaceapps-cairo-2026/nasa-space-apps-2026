# Space Apps 2026: team repo

Three Claude accounts, three lanes, one contract. Read `CLAUDE.md` first.

```
data/  (lane C)  ->  data/processed/features.parquet
ml/    (lane A)  ->  ml/outputs/predictions.json   (must match contracts/prediction.schema.json)
api/   (lane B)  ->  serves the bundle at /api/*
app/   (lane B)  ->  map + chart + "why this score", served at /
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
`gh repo clone ORG/nasa-space-apps-2026 D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1`

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
