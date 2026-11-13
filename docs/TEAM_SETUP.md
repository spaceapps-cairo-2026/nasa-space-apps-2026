# Team setup: one org, one repo, every Claude account in parallel

## The shape

```
GitHub organization (free)
└── nasa-space-apps-2026 (private repo, public before final submission)
    ├── main            only lane A merges here, through pull requests, tests must be green
    ├── lane/a-ml       ML + integration     -> Mohammed, Claude account 1, D:\nasa_space_apps
    ├── lane/b-app      API + app            -> Mohammed, Claude account 2, D:\nasa_space_apps_b_app
    └── lane/c-data     data + science + story -> teammate, own Claude account, D:\nasa_space_apps
```

Every push runs the tests on GitHub (`.github/workflows/check.yml`). A red check means: do not merge.

### More than 3 people?
- 4th person: second Claude window on lane C, working only on `docs/PITCH.md`, `demo/` and slides.
- 5th and 6th: pair with lane A (validation, `ml/model_card.md`) or lane B (Methods page in the app).
- Two people in one lane must split files, never edit the same file at the same time.

## One time: team lead (Mohammed)

1. Create the organization (free plan): https://github.com/account/organizations/new?plan=free
2. Install GitHub CLI if missing: `winget install --id GitHub.cli`, then open a NEW PowerShell.
3. In a new PowerShell window:
   ```powershell
   cd D:\
   powershell -ExecutionPolicy Bypass -File "D:\Projects\NASA Space Apps 2026\scripts\setup_team.ps1"
   ```
   It moves the project to `D:\nasa_space_apps`, installs packages into the global Python, tests, downloads the climate data, creates the org repo, pushes, creates the `spaceapps` team, and invites teammates by GitHub username.

## One time: each teammate

1. Accept the GitHub invite (email or github.com notifications).
2. Install Git, Python 3.10+, GitHub CLI (`winget install --id GitHub.cli`), Claude Code. Run `gh auth login` once.
3. One paste:
   ```powershell
   gh repo clone spaceapps-cairo-2026/nasa-space-apps-2026 D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1
   ```
   Pick your lane when asked.

## Mohammed's second Claude account (lane B, same laptop, same time)

```powershell
cd D:\nasa_space_apps
powershell -ExecutionPolicy Bypass -File .\scripts\second_account.ps1 lane/b-app
```
First time only: type `/login` inside Claude and sign in with account 2. It keeps its login in `D:\claude-accounts\account2`.

## Daily rhythm for every Claude session

1. Open PowerShell in your folder, run `claude`, type `/sync A` (or B / C).
2. Work only inside your lane's folders (see CLAUDE.md).
3. Every 30 to 60 minutes: commit + push your lane branch.
4. Before you stop, sleep, or hit the usage limit: `/handoff`. It pushes, updates TASKS.md and LOG.md, and opens your pull request.
5. Lane A merges green pull requests at 13:00, 16:00, 20:00, 02:00, 10:00, 14:00. Everyone then runs `/sync`.

## When a Claude account hits its usage limit
Run `/handoff` in that window. Continue the same lane in claude.ai chat (paste the handoff note) for planning or text, or switch the lane to another free account for a few hours.

## What lives where
| Thing | Location |
|---|---|
| Project | `D:\nasa_space_apps` |
| Python packages | the global Python install (no virtual environment) |
| NASA data (in git) | `data\processed\power_monthly.parquet` and raw `data\cache\power\` |
| Big or login-only data (not in git) | `data\cache\appeears\`, `data\raw\`; share via Google Drive |
| Second Claude login | `D:\claude-accounts\account2` |

Python itself, Git, GitHub CLI and Claude Code stay installed where they already are.
