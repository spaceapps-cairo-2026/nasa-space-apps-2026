"""Task runner for the team (Windows, PowerShell).

Usage:
    python run.py setup      install Python packages
    python run.py fixtures   regenerate fake data in contracts/fixtures
    python run.py mock       API + app on fake data   -> http://localhost:8000
    python run.py api        API + app on real model output
    python run.py check      run all tests (do this before every push)
    python run.py power      build the Egypt climate table (already in git; add --force to re-download)
    python run.py world      download NASA POWER climate grids for the whole world (hours; add --status)
    python run.py gistemp    NASA global temperature table for validation (add --force to re-download)
    python run.py crops      FAO ECOCROP crop requirements table (add --force to re-download)
    python run.py appeears   check the MODIS AppEEARS request (add: submit / status / download)
    python run.py trends     compute the Egypt trend maps and the world overview, print a report (lane A)
    python run.py nasa-check our trends vs NASA GISTEMP stations and GPCP rain (no login, writes ml/outputs/nasa_check.json)
    python run.py crosscheck compare our numbers with NASA Giovanni files in data/raw/giovanni (docs/CROSSCHECK.md)
    python run.py crop-model run the trained crop model on the Egypt grid -> ml/outputs/farming_EGY.json (about 3 minutes); add SAU for Saudi Arabia
    python run.py farming-check   check the farming outlook file a model wrote, before the app reads it (add a path)
    python run.py package    build dist/cropshift_backend.zip for the UI merge
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Uses whichever Python ran this file (the global install). No virtual environment.
PY = sys.executable


def sh(args: list[str], env_extra: dict | None = None) -> int:
    env = {**os.environ, **(env_extra or {})}
    print(">", " ".join(args))
    return subprocess.call(args, env=env)


COMMANDS = {
    "setup": lambda: sh([PY, "-m", "pip", "install", "-r", "requirements.txt"]),
    "fixtures": lambda: sh([PY, "ml/make_fixtures.py"]),
    "mock": lambda: sh([PY, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"], {"MOCK": "1"}),
    "api": lambda: sh([PY, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"], {"MOCK": "0"}),
    "check": lambda: sh([PY, "-m", "pytest", "-q"]),
    "power": lambda: sh([PY, "data/power_fetch.py", *sys.argv[2:]]),
    "world": lambda: sh([PY, "data/power_world_fetch.py", *sys.argv[2:]]),
    "gistemp": lambda: sh([PY, "data/gistemp_fetch.py", *sys.argv[2:]]),
    "crops": lambda: sh([PY, "data/crops_build.py", *sys.argv[2:]]),
    "appeears": lambda: sh([PY, "data/appeears_request.py", *(sys.argv[2:] or ["check"])]),
    "trends": lambda: sh([PY, "ml/live.py"]),
    "crosscheck": lambda: sh([PY, "ml/crosscheck.py"]),
    "nasa-check": lambda: sh([PY, "ml/nasa_check.py"]),
    "crop-model": lambda: sh([PY, "ml/crop_outlook.py", *sys.argv[2:]]),
    "farming-check": lambda: sh([PY, "ml/check_farming.py", *sys.argv[2:]]),
    "package": lambda: sh([PY, "scripts/package_backend.py"]),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.exit(COMMANDS[sys.argv[1]]())
