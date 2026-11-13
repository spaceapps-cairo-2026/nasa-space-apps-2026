# ONE TIME, run by Mohammed (team lead) on his laptop.
#
# What it does:
#   1. Moves the project to D:\nasa_space_apps
#   2. Checks the tools (git, global Python 3.10+, gh)
#   3. Installs packages into the global Python, runs tests, downloads the Egypt climate data
#   4. Creates the git repo with the 3 lane branches
#   5. Creates the private repo inside your GitHub ORGANIZATION, pushes everything
#   6. Creates a team in the org with write access and invites your teammates
#
# Before running: create the organization (free) at
#   https://github.com/account/organizations/new?plan=free
#
# Run from a NEW PowerShell window (not one opened inside the project folder):
#   cd D:\
#   powershell -ExecutionPolicy Bypass -File "D:\Projects\NASA Space Apps 2026\scripts\setup_team.ps1"

$ErrorActionPreference = "Stop"
$Old = "D:\Projects\NASA Space Apps 2026"
$New = "D:\nasa_space_apps"
$Repo = "nasa-space-apps-2026"

function Step($t) { Write-Host "`n== $t" -ForegroundColor Cyan }

Step "1/6 Moving project to $New"
Set-Location D:\
if ((Test-Path $Old) -and -not (Test-Path $New)) {
    try { Move-Item $Old $New }
    catch {
        Write-Warning "Move blocked (a program has the old folder open). Copying instead."
        robocopy $Old $New /E /NFL /NDL /NJH /NJS | Out-Null
        Write-Warning "Copied. Delete '$Old' yourself later."
    }
}
if (-not (Test-Path "$New\run.py")) { throw "Project not found at $New." }
Set-Location $New
foreach ($f in "data\fetch.py", "ml\predict.py", "ml\train.py", "scripts\second_account.sh") { Remove-Item $f -ErrorAction SilentlyContinue }

Step "2/6 Checking tools"
foreach ($t in "git", "python", "gh") {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) {
        if ($t -eq "gh") { throw "GitHub CLI missing. Install: winget install --id GitHub.cli   then open a NEW PowerShell and rerun." }
        throw "$t is not installed."
    }
}
if ((python -c "import sys; print(sys.version_info >= (3,10))") -ne "True") { throw "Python 3.10+ needed." }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Write-Warning "Claude Code (claude) not found. Install it before tomorrow." }

Step "3/6 Packages (global Python) + tests + data"
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
python run.py check
if ($LASTEXITCODE -ne 0) { throw "Tests failed. Send the output to Claude." }
python run.py power
New-Item -ItemType Directory -Force .claude\commands | Out-Null
Copy-Item scripts\claude-commands\*.md .claude\commands\ -Force

Step "4/6 Git repo + lane branches"
if (-not (Test-Path .git)) { git init -q -b main }
if (-not (git config user.name))  { git config --global user.name  (Read-Host "Your name for git") }
if (-not (git config user.email)) { git config --global user.email (Read-Host "Your GitHub email") }
git add -A
git commit -q -m "Team setup: Egypt Trend Detective skeleton, data plan, methods, CI"
foreach ($b in "lane/a-ml", "lane/b-app", "lane/c-data") {
    if (git branch --list $b) { git branch -f $b main } else { git branch $b }
}

Step "5/6 GitHub organization repo"
gh auth status
if ($LASTEXITCODE -ne 0) { gh auth login -s "workflow,admin:org" }
else { gh auth refresh -h github.com -s "workflow,admin:org" }
$Org = Read-Host "GitHub organization name (exactly as in its URL)"
$remotes = @(git remote)
if ($remotes -contains "origin") {
    $url = git remote get-url origin
    if ($url -notmatch "github.com[:/]$Org/") { git remote rename origin old-origin; Write-Warning "Old remote kept as 'old-origin' ($url)." }
}
if (-not (@(git remote) -contains "origin")) {
    gh repo create "$Org/$Repo" --private --source . --remote origin --description "NASA Space Apps 2026 Cairo: Egypt Trend Detective"
    if ($LASTEXITCODE -ne 0) { throw "Repo creation failed. Does the organization '$Org' exist and are you an owner?" }
}
git push -u origin main
git push origin lane/a-ml lane/b-app lane/c-data --force-with-lease

Step "6/6 Team + invites"
gh api -X POST "orgs/$Org/teams" -f name="spaceapps" -f privacy="closed" | Out-Null
gh api -X PUT "orgs/$Org/teams/spaceapps/repos/$Org/$Repo" -f permission="push" | Out-Null
$names = Read-Host "Teammates' GitHub usernames, comma separated (Enter to skip)"
foreach ($n in ($names -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    gh api -X PUT "orgs/$Org/teams/spaceapps/memberships/$n" -f role="member" | Out-Null
    Write-Host "Invited $n (they must accept the email / github.com invite)"
}

Write-Host "`nDONE. Repo: https://github.com/$Org/$Repo" -ForegroundColor Green
Write-Host "Teammates join with (one paste):" -ForegroundColor Green
Write-Host "  gh repo clone $Org/$Repo D:\nasa_space_apps; powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1"
Write-Host "Your second Claude account: .\scripts\second_account.ps1 lane/b-app"
