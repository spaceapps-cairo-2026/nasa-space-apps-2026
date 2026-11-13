# Run by EACH teammate after cloning:
#   gh repo clone ORG/nasa-space-apps-2026 D:\nasa_space_apps
#   powershell -ExecutionPolicy Bypass -File D:\nasa_space_apps\scripts\join_team.ps1
#
# Installs packages into your global Python, runs tests, downloads the Egypt climate data
# into the project folder, installs /sync and /handoff, and switches you to your lane branch.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

foreach ($t in "git", "python", "gh") { if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { throw "$t is not installed." } }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Write-Warning "Claude Code (claude) not found. Install it before the event." }

Write-Host "`n== Python packages (global Python)" -ForegroundColor Cyan
if ((python -c "import sys; print(sys.version_info >= (3,10))") -ne "True") { throw "Python 3.10+ needed." }
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
python run.py check
if ($LASTEXITCODE -ne 0) { throw "Tests failed. Tell the team lead." }
python run.py power

New-Item -ItemType Directory -Force .claude\commands | Out-Null
Copy-Item scripts\claude-commands\*.md .claude\commands\ -Force

Write-Host "`n== Your lane" -ForegroundColor Cyan
Write-Host "  A = ML + integration   B = API + app   C = data + science + story"
$lane = (Read-Host "Which lane are you (A/B/C)").ToUpper()
$branch = @{ "A" = "lane/a-ml"; "B" = "lane/b-app"; "C" = "lane/c-data" }[$lane]
if (-not $branch) { throw "Type A, B or C." }
git fetch origin
git checkout -B $branch "origin/$branch"
if (-not (git config user.name))  { git config --global user.name  (Read-Host "Your name for git") }
if (-not (git config user.email)) { git config --global user.email (Read-Host "Your GitHub email") }

Write-Host "`nREADY on branch $branch." -ForegroundColor Green
Write-Host "Start working:  cd $Root; claude      then type:  /sync $lane"
