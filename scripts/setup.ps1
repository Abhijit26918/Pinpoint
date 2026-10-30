# Rebuild everything this folder needs from a fresh clone (Windows PowerShell).
# Idempotent: safe to re-run. Requires Python >= 3.11, git, and Docker Desktop running.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# 1. project venv, pinned dev dependencies, package installed in editable mode
if (-not (Test-Path .venv)) { python -m venv .venv }
.venv\Scripts\python -m pip install -q -r requirements-dev.lock
.venv\Scripts\python -m pip install -q -e . --no-deps

# 2. GitChameleon 2.0 harness at the commit this project was built against
$bench = "external\GitChameleonBenchmark"
if (-not (Test-Path $bench)) {
    git clone https://github.com/mrcabbage972/GitChameleonBenchmark $bench
    git -C $bench checkout 3a1b604
}

# 3. benchmark image + the volume that holds the per-problem venvs
docker pull mrcabbage972/gitchameleon:latest
docker volume create gc_venvs | Out-Null

# 4. API keys: copy the template once, then fill in .env by hand
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created .env - add your keys." }

Write-Host "Done. Build per-problem environments with: python scripts\subset_env_ids.py (see docs/03-eval-plan.md)."
