# Run a SECOND Claude account on the same laptop, on its own lane, at the same time.
#
# - git worktree: a second checkout of the repo (D:\nasa_space_apps_b_app for lane/b-app) on
#   another branch, so the two Claude sessions never edit the same files on disk.
# - CLAUDE_CONFIG_DIR: a separate Claude Code settings/login folder (D:\claude-accounts\account2),
#   so this window logs in with account 2 while your normal window stays on account 1.
# - Python packages come from the global Python install (no virtual environment).
#
# Usage, from D:\nasa_space_apps in PowerShell:
#   .\scripts\second_account.ps1 lane/b-app
#   First time only: type /login inside Claude and sign in with account 2.
# If PowerShell blocks scripts:  Set-ExecutionPolicy -Scope Process Bypass

param([string]$Branch = "lane/b-app")

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$wt = "D:\nasa_space_apps_" + ($Branch -replace "^lane/", "" -replace "[/-]", "_")

git fetch origin
if (-not (Test-Path $wt)) {
    if (git branch --list $Branch) { git worktree add $wt $Branch }
    else { git worktree add -b $Branch $wt "origin/$Branch" }
}
New-Item -ItemType Directory -Force "$wt\.claude\commands" | Out-Null
Copy-Item "$Root\scripts\claude-commands\*.md" "$wt\.claude\commands\" -Force

$env:CLAUDE_CONFIG_DIR = "D:\claude-accounts\account2"
New-Item -ItemType Directory -Force $env:CLAUDE_CONFIG_DIR | Out-Null
Set-Location $wt
Write-Host "Worktree: $wt  (branch $Branch)  Claude login folder: $env:CLAUDE_CONFIG_DIR" -ForegroundColor Green
claude
