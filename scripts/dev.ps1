$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
if (-not $env:COMPOSE_PROJECT_NAME) { $env:COMPOSE_PROJECT_NAME = 'dut_t04' }
if (-not $env:DUT_DB_PORT) { $env:DUT_DB_PORT = '5433' }
if (-not $env:DUT_DATABASE_URL) {
    $env:DUT_DATABASE_URL = "postgresql+psycopg://dutlearn:dutlearn@127.0.0.1:$($env:DUT_DB_PORT)/dutlearn"
}
Push-Location $repo
try {
    docker compose -f infra/docker-compose.yml up -d --wait db
    if ($LASTEXITCODE -ne 0) { throw 'Docker database startup failed' }
    Push-Location services/api
    try {
        uv sync --frozen
        if ($LASTEXITCODE -ne 0) { throw 'uv sync failed' }
        uv run alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    } finally { Pop-Location }
} finally { Pop-Location }
Write-Host "API: cd '$repo/services/api'; uv run uvicorn app.main:app --reload"
Write-Host "Web: cd '$repo/apps/web'; npm ci; npm run dev"
