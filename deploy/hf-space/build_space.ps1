# Assemble the Hugging Face Space folder for the hosted demo.
# Usage (repo root): ./deploy/hf-space/build_space.ps1 [-Out D:\Documents\DUT_LEARN\dutlearn-space]
# Copies only what the image needs. Never copies .env, private/, evals data or student data.
param([string]$Out = 'D:\Documents\DUT_LEARN\dutlearn-space')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path

if (Test-Path $Out) {
    # Keep the Space's own .git so the folder can be pushed again.
    Get-ChildItem $Out -Force | Where-Object { $_.Name -ne '.git' } | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory $Out | Out-Null
}

function Copy-Tree($from, $to, [string[]]$excludeDirs, [string[]]$excludeFiles) {
    $args = @($from, $to, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($excludeDirs) { $args += '/XD'; $args += $excludeDirs }
    if ($excludeFiles) { $args += '/XF'; $args += $excludeFiles }
    & robocopy @args | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $from" }
}

Copy-Tree "$repo\services\api" "$Out\services\api" @('.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'tests', '.codex-build') @('.env', '.env.*')
Copy-Tree "$repo\apps\web" "$Out\apps\web" @('node_modules', 'dist', '.codex-build') @('.env', '.env.*')
Copy-Tree "$repo\deploy\hf-space" "$Out\deploy\hf-space" @() @()
Copy-Tree "$repo\data\materials" "$Out\data\materials" @() @()
Copy-Item "$repo\deploy\hf-space\Dockerfile" "$Out\Dockerfile"
Copy-Item "$repo\deploy\hf-space\README.md" "$Out\README.md"
Set-Content -Path "$Out\.gitattributes" -Value '*.pdf filter=lfs diff=lfs merge=lfs -text' -Encoding ascii

# Guard: nothing secret or private may be in the Space folder.
$bad = Get-ChildItem $Out -Recurse -Force -File | Where-Object {
    $_.FullName -notmatch '\\\.git\\' -and ($_.Name -like '.env*' -or $_.FullName -match '\\private\\|\\evals\\')
}
if ($bad) { throw "Refusing: sensitive files in Space folder: $($bad.FullName -join ', ')" }
$size = (Get-ChildItem $Out -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.git\\' } | Measure-Object Length -Sum).Sum
Write-Host ("Space folder ready: {0} ({1:N1} MB)" -f $Out, ($size / 1MB))
exit 0
