# Task for Claude Code: finish the project move and GitHub organization setup

You are running on Mohammed's Windows laptop. Do every step below yourself, verify each one, and only ask Mohammed when this file says "ASK". Use PowerShell syntax for commands. Never use long dashes in any text you write.

## Context (read first)

- Team project for NASA Space Apps 2026 Cairo (Sat 14 to Sun 15 Nov), challenge "Be An Earth System Trend Detective". Team is Windows only.
- The project currently lives in `D:\Projects\NASA Space Apps 2026`. It contains `CLAUDE.md`, `README.md`, `run.py`, `docs\`, `scripts\`, `data\`, `ml\`, `api\`, `app\`, `contracts\`, `tests\`. Read `CLAUDE.md` and `docs\TEAM_SETUP.md` before starting.
- It may or may not already be a git repo, and may or may not already have a GitHub remote. Check, do not assume.

## Hard rules

1. **Everything belonging to the project lives on the D: drive** under `D:\nasa_space_apps` (repo, data, caches, worktrees, the second Claude login folder). Nothing project related on C:.
2. **Python packages may stay on C:** (global Python install is fine). Do NOT create a virtual environment. If `D:\nasa_space_apps\.venv` exists, leave it alone but do not use it.
3. Never delete `data\cache` or `data\processed` contents (downloaded NASA data). Never commit them (they are gitignored).
4. Never commit secrets (`.env`, Earthdata passwords).
5. The GitHub repo must be **private** for now.

## Steps

### 1. Move the project
- If `D:\nasa_space_apps` does not exist: move `D:\Projects\NASA Space Apps 2026` to `D:\nasa_space_apps`. If the move is blocked because something has the folder open, copy with `robocopy /E`, verify file counts match, and tell Mohammed to delete the old folder himself.
- From now on work only in `D:\nasa_space_apps`.
- Delete these obsolete files if present: `data\fetch.py`, `ml\predict.py`, `ml\train.py`, `scripts\second_account.sh`.

### 2. Put protected files in place
These could not be written remotely, so copy them now:
- `scripts\claude-commands\*.md` to `.claude\commands\` (gives the `/sync` and `/handoff` slash commands)
- `scripts\github-workflows\check.yml` to `.github\workflows\check.yml` (runs the tests on GitHub on every push)

### 3. Simplify the scripts to use global Python (no venv)
Edit these so they use plain `python` and never create or use `.venv`:
- `scripts\join_team.ps1`: remove the venv creation and `$py` path; use `python -m pip install -r requirements.txt`, `python run.py check`, `python run.py power`. Keep `$env:PIP_CACHE_DIR` pointing inside the repo only if you want; otherwise remove it.
- `scripts\setup_team.ps1`: same change (it is a reference script now; you are doing its job by hand).
- `run.py`: remove the block that re-launches itself with a `.venv` python (the `for _venv in ...` loop) so it always uses the Python that ran it.
- `docs\TEAM_SETUP.md` and `CLAUDE.md`: remove mentions of `.venv` and `.pip-cache`; say packages use the global Python.
- `scripts\second_account.ps1`: keep it; make sure the worktree path is `D:\nasa_space_apps_b_app` and `CLAUDE_CONFIG_DIR` is `D:\claude-accounts\account2`.

### 4. Install and verify
- Check tools: `git --version`, `python --version` (must be 3.10 or newer), `gh --version`, `claude --version`. If `gh` is missing: `winget install --id GitHub.cli`, then tell Mohammed to restart the terminal and rerun you.
- `python -m pip install -r requirements.txt`
- `python run.py check` must print `5 passed, 1 skipped`. If not, fix the cause before continuing.
- `python run.py power` must end with a line containing `357 cells, 2001-01 to 2025-12`.
- `python run.py appeears check` must print four `OK` lines.

### 5. Git repo and lane branches
- If not a git repo: `git init -b main`.
- If `git config user.name` or `user.email` is empty: ASK Mohammed for them and set them globally.
- Commit everything (check `git status` first: no files from `data\cache`, `data\processed`, `.env`, `.venv` must be staged).
- Make sure branches `lane/a-ml`, `lane/b-app`, `lane/c-data` exist and point at the latest `main` commit.

### 6. GitHub organization repo
- ASK Mohammed for the organization name. It must already exist (organizations can only be created on the web at https://github.com/account/organizations/new?plan=free). If he has not created it yet, give him that link and wait.
- Log in with the scopes needed to push workflow files and manage the org: `gh auth status`; then `gh auth refresh -h github.com -s workflow,admin:org` (or `gh auth login -s workflow,admin:org` if not logged in). Mohammed completes the browser step.
- If a remote `origin` already exists and does not point to `github.com/<org>/`, rename it to `old-origin` and tell Mohammed.
- Create the repo: `gh repo create <org>/nasa-space-apps-2026 --private --source . --remote origin --description "NASA Space Apps 2026 Cairo: Egypt Trend Detective"`
- Push: `git push -u origin main`, then `git push origin lane/a-ml lane/b-app lane/c-data`.
- Verify on GitHub: `gh repo view <org>/nasa-space-apps-2026` and `gh api repos/<org>/nasa-space-apps-2026/branches --jq ".[].name"` shows all 4 branches.
- Verify the tests ran: `gh run list -R <org>/nasa-space-apps-2026 --limit 3`. Wait for the latest run and confirm it passed (`gh run watch` or re-check). If it failed, read the log (`gh run view --log-failed`) and fix.

### 7. Team and invites
- Create a team: `gh api -X POST orgs/<org>/teams -f name=spaceapps -f privacy=closed` (ignore "already exists").
- Give it write access: `gh api -X PUT orgs/<org>/teams/spaceapps/repos/<org>/nasa-space-apps-2026 -f permission=push`
- ASK Mohammed for each teammate's GitHub username, then for each: `gh api -X PUT orgs/<org>/teams/spaceapps/memberships/<username> -f role=member`
- Verify: `gh api orgs/<org>/teams/spaceapps/members --jq ".[].login"` plus pending invites `gh api orgs/<org>/invitations --jq ".[].login"`.

### 8. Second Claude account worktree (lane B on this laptop)
- Create the worktree: `git worktree add D:\nasa_space_apps_b_app lane/b-app`
- Copy `.claude\commands\*.md` into `D:\nasa_space_apps_b_app\.claude\commands\`.
- Create the folder `D:\claude-accounts\account2`.
- Do NOT launch Claude for account 2 yourself. Tell Mohammed to run, in a new PowerShell window:
  `cd D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File .\scripts\second_account.ps1 lane/b-app` and type `/login` with account 2 the first time.

### 9. Commit your own edits
- Commit the script/doc edits from step 3 on `main` with a clear message, push, then fast-forward the 3 lane branches to `main` and push them.
- Confirm the GitHub check is green on the final commit.

## Final report to Mohammed (keep it short)
1. Repo URL.
2. Branches on GitHub and whether the latest check passed.
3. Who was invited (pending or accepted).
4. The exact one-line command each teammate pastes to join (with the real org name):
   `gh repo clone <org>/nasa-space-apps-2026 D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1`
5. Anything that failed or that he must do by hand.
