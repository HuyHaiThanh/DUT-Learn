$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
Push-Location (Join-Path $repo 'services/api')
try {
    Invoke-Checked uv @('run', 'ruff', 'check', '.')
    Invoke-Checked uv @('run', 'mypy', 'app')
    Invoke-Checked uv @('run', 'pytest')
} finally { Pop-Location }
Push-Location (Join-Path $repo 'apps/web')
try {
    Invoke-Checked npm.cmd @('run', 'lint')
    Invoke-Checked npm.cmd @('run', 'typecheck')
    Invoke-Checked npm.cmd @('test')
    Invoke-Checked npm.cmd @('run', 'build')
} finally { Pop-Location }
