"""Host the app on a Hugging Face Space (Docker, free, public https link).

    python run.py space stage                     copy what the server needs into dist/hf_space/ (no upload)
    python run.py space test                      stage, then run the staged copy at http://localhost:7860 (real data)
    python run.py space deploy <user>/<space>     stage and upload with the huggingface_hub package
    python run.py space push <user>/<space>       stage and push with git + Git LFS (when PyPI is blocked)
    python run.py space push <user>/<space> gradio   same, for a Space created with the free Gradio SDK
    python run.py space model <user>/<model-repo>    upload the crop model (weights, numpy runtime, card) to a model repo

Before the first deploy: make a free account on huggingface.co and create a token with "write" access
(Settings > Access Tokens). For `deploy`: run `hf auth login` once (or put HF_TOKEN=... in .env); the Space
is created if it does not exist. For `push`: create the Space first on the website (SDK: Docker, Blank);
git asks for your Hugging Face user name and the token as the password.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "dist" / "hf_space"

# Tracked files under these folders (git ls-files), so nothing secret or half-made gets uploaded.
TRACKED = ["api/", "app/", "contracts/", "data/", "ml/"]
SKIP_TRACKED = ["ml/crop_model/training/", "data/raw/"]
# Untracked local caches that make the demo fast and keep it working if NASA is slow:
# world trend summaries (ml/outputs/world_*.json) and NASA tiles / points already downloaded.
EXTRA_GLOBS = ["ml/outputs/world_*.json", "data/cache/power_world/**/*.npz", "data/cache/power_point/**/*"]


def _writable_retry(func, path, _exc) -> None:
    """git marks its object files read only; make them writable and try again."""
    os.chmod(path, 0o700)
    func(path)


def _empty(folder: Path) -> None:
    """Empty a folder but keep it (on Windows a terminal sitting in it would block removing the folder itself)."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.iterdir():
        if not old.is_dir():
            old.unlink()
        elif sys.version_info >= (3, 12):
            shutil.rmtree(old, onexc=_writable_retry)
        else:
            shutil.rmtree(old, onerror=_writable_retry)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", *TRACKED], cwd=ROOT, capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if not any(f.startswith(s) for s in SKIP_TRACKED)]


def stage(sdk: str = "docker") -> Path:
    _empty(STAGE)
    files = tracked_files()
    for pattern in EXTRA_GLOBS:
        files += [p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file()]
    for rel in sorted(set(files)):
        src = ROOT / rel
        if not src.is_file():
            continue
        dst = STAGE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copy2(ROOT / "requirements.txt", STAGE / "requirements.txt")
    shutil.copy2(ROOT / "deploy" / "Dockerfile", STAGE / "Dockerfile")
    shutil.copy2(ROOT / "deploy" / "app.py", STAGE / "app.py")
    readme = (ROOT / "deploy" / "SPACE_README.md").read_text(encoding="utf-8")
    if sdk == "gradio":
        # Free Gradio SDK: Hugging Face installs gradio, then runs app.py, which starts our own server on 7860.
        readme = readme.replace("sdk: docker\napp_port: 7860\n",
                                'sdk: gradio\nsdk_version: 5.9.1\npython_version: "3.11"\napp_file: app.py\n')
    (STAGE / "README.md").write_text(readme, encoding="utf-8")
    (STAGE / ".dockerignore").write_text("**/__pycache__\n**/*.pyc\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file())
    count = sum(1 for p in STAGE.rglob("*") if p.is_file())
    print(f"Staged {count} files, {size / 1e6:.0f} MB, in {STAGE}")
    return STAGE


def test() -> int:
    folder = stage()
    print("Running the staged copy on real data at http://localhost:7860 (Ctrl+C to stop)")
    return subprocess.call([sys.executable, "-m", "uvicorn", "api.main:app", "--port", "7860"],
                           cwd=folder, env={**os.environ, "MOCK": "0"})


def deploy(repo_id: str) -> int:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("Install the Hugging Face client first:  python -m pip install huggingface_hub")
        return 1
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    folder = stage()
    api = HfApi()
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    # delete_patterns="*": files removed here are removed on the Space too, so it always matches this copy.
    api.upload_folder(folder_path=folder, repo_id=repo_id, repo_type="space",
                      commit_message="Deploy from the team repository", delete_patterns="*")
    owner, name = repo_id.split("/", 1)
    print(f"Uploaded. Build log: https://huggingface.co/spaces/{repo_id}")
    print(f"Public link once built (a few minutes): https://{owner.lower()}-{name.lower().replace('_', '-')}.hf.space")
    return 0


LFS_PATTERNS = ["*.npz", "*.parquet", "*.png", "*.jpg", "*.jpeg", "*.ico", "*.woff", "*.woff2", "*.pdf"]


def _hf_token() -> str | None:
    """HF_TOKEN from the environment or the gitignored .env file (never printed)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    token = os.getenv("HF_TOKEN", "").strip()
    return token or None


def git(*args: str, cwd: Path = STAGE) -> int:
    print(">", "git", *args)
    env = None
    if args and args[0] == "push" and _hf_token():
        # Give git the token through a one-off credential helper that reads it from the environment,
        # so it never appears on screen, in a URL or in the saved git config.
        env = {**os.environ, "HF_TOKEN": _hf_token()}
        args = ("-c", "credential.helper=",
                "-c", 'credential.helper=!f() { echo username=hf_user; echo "password=$HF_TOKEN"; }; f', *args)
    return subprocess.call(["git", *args], cwd=cwd, env=env)


def push(repo_id: str, sdk: str = "docker") -> int:
    """Same as deploy, with plain git + Git LFS (no Python package needed). The Space must exist already:
    huggingface.co > New Space > SDK Docker > Blank. Git asks for your Hugging Face user name and a write token."""
    folder = stage(sdk)
    for p in folder.rglob("*.pyc"):
        p.unlink()
    (folder / ".gitattributes").write_text("".join(f"{p} filter=lfs diff=lfs merge=lfs -text\n" for p in LFS_PATTERNS),
                                           encoding="utf-8")
    url = f"https://huggingface.co/spaces/{repo_id}"
    steps = [("init", "-q", "-b", "main"), ("config", "core.autocrlf", "false"), ("lfs", "install", "--local"),
             ("add", "-A"),
             ("-c", "user.name=CropShift team", "-c", "user.email=team@cropshift.invalid",
              "commit", "-q", "-m", "Deploy from the team repository"),
             ("push", "--force", url, "main")]
    for step in steps:
        if git(*step) != 0:
            return 1
    owner, name = repo_id.split("/", 1)
    print(f"Pushed. Build log: {url}")
    print(f"Public link once built (a few minutes): https://{owner.lower()}-{name.lower().replace('_', '-')}.hf.space")
    return 0


MODEL_STAGE = ROOT / "dist" / "hf_model"
MODEL_FILES = {
    "ml/crop_model/crop_suitability_v3.npz": "crop_suitability_v3.npz",
    "ml/crop_model/crop_engine_v3.py": "crop_engine_v3.py",
    "ml/crop_model/metrics_v3.json": "metrics_v3.json",
    "ml/model_card.md": "MODEL_CARD_FULL.md",
    "deploy/MODEL_README.md": "README.md",
}


def push_model(repo_id: str) -> int:
    """Upload the crop model (weights + numpy runtime + card) to a free Hugging Face MODEL repo with git + LFS.
    Create it first on the website: huggingface.co/new (a model, not a Space)."""
    _empty(MODEL_STAGE)
    for src, dst in MODEL_FILES.items():
        shutil.copy2(ROOT / src, MODEL_STAGE / dst)
    (MODEL_STAGE / ".gitattributes").write_text("*.npz filter=lfs diff=lfs merge=lfs -text\n", encoding="utf-8")
    url = f"https://huggingface.co/{repo_id}"
    steps = [("init", "-q", "-b", "main"), ("config", "core.autocrlf", "false"), ("lfs", "install", "--local"),
             ("add", "-A"),
             ("-c", "user.name=CropShift team", "-c", "user.email=team@cropshift.invalid",
              "commit", "-q", "-m", "Crop suitability model v3.1 from the team repository"),
             ("push", "--force", url, "main")]
    for step in steps:
        if git(*step, cwd=MODEL_STAGE) != 0:
            return 1
    print(f"Pushed. Model page: {url}")
    return 0


def main(args: list[str]) -> int:
    if args[:1] == ["model"] and len(args) == 2 and "/" in args[1]:
        return push_model(args[1])
    if args[:1] == ["stage"]:
        stage()
        return 0
    if args[:1] == ["test"]:
        return test()
    if args[:1] in (["deploy"], ["push"]) and len(args) in (2, 3) and "/" in args[1]:
        sdk = args[2] if len(args) == 3 else "docker"
        if sdk not in ("docker", "gradio"):
            print("The Space type must be docker or gradio.")
            return 1
        return deploy(args[1]) if args[0] == "deploy" else push(args[1], sdk)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
