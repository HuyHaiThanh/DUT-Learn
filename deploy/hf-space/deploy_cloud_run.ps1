# Deploy the hosted demo image to Google Cloud Run (build runs in Cloud Build).
# Usage (repo root, after `gcloud auth login`):
#   ./deploy/hf-space/deploy_cloud_run.ps1 -Project <gcp-project-id> [-Region asia-southeast1]
# Reads from the repo-root .env (never printed): DEMO_NEON_URL, DUT_LLM_API_KEY.
param(
    [Parameter(Mandatory = $true)][string]$Project,
    [string]$Region = 'asia-southeast1',
    [string]$Service = 'dutlearn',
    [string]$LlmBaseUrl = 'https://api.groq.com/openai/v1',
    [string]$LlmModel = 'qwen/qwen3.8-27b',
    [string]$SpaceDir = 'D:\Documents\DUT_LEARN\dutlearn-space'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$gcloud = (Get-Command gcloud -ErrorAction SilentlyContinue).Source
if (-not $gcloud) { $gcloud = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" }

function Read-DotEnv([string]$name) {
    $line = Get-Content "$repo\.env" | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if (-not $line) { throw "$name missing in .env" }
    return ($line -replace "^\s*$name\s*=", '').Trim().Trim('"').Trim("'")
}

# Neon: use the direct endpoint (the pooler keeps session settings such as an
# empty search_path left behind by pg_restore) and the psycopg driver.
$neon = Read-DotEnv 'DEMO_NEON_URL'
$dbUrl = ($neon -replace '^postgres(ql)?://', 'postgresql+psycopg://') -replace '-pooler\.', '.'
$apiKey = Read-DotEnv 'DUT_LLM_API_KEY'

& "$repo\deploy\hf-space\build_space.ps1" -Out $SpaceDir
if ($LASTEXITCODE -ne 0) { throw 'build_space failed' }

$envFile = Join-Path ([IO.Path]::GetTempPath()) ("dutlearn-env-{0}.yaml" -f [guid]::NewGuid())
try {
    $yaml = @(
        "DUT_DATABASE_URL: '$($dbUrl.Replace("'", "''"))'"
        "DUT_LLM_BASE_URL: '$LlmBaseUrl'"
        "DUT_LLM_API_KEY: '$($apiKey.Replace("'", "''"))'"
        "DUT_LLM_MODEL: '$LlmModel'"
    ) -join "`n"
    [IO.File]::WriteAllText($envFile, $yaml)

    & $gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project $Project
    if ($LASTEXITCODE -ne 0) { throw 'enabling APIs failed' }

    # One instance at most: bounded cost, and the LLM client is single-slot anyway.
    & $gcloud run deploy $Service --source $SpaceDir --project $Project --region $Region `
        --port 7860 --memory 2Gi --cpu 1 --cpu-boost --min-instances 0 --max-instances 1 `
        --concurrency 20 --timeout 300 --allow-unauthenticated --env-vars-file $envFile --quiet
    if ($LASTEXITCODE -ne 0) { throw 'gcloud run deploy failed' }
} finally {
    Remove-Item $envFile -Force -ErrorAction SilentlyContinue
}

$url = & $gcloud run services describe $Service --project $Project --region $Region --format 'value(status.url)'
Write-Host "Deployed: $url"
Write-Host (Invoke-RestMethod "$url/api/health" -TimeoutSec 120 | ConvertTo-Json -Compress)
