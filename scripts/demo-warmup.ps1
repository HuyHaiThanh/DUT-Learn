# Warm up the demo stack: keep the LLM resident on the GPU and load the
# embedding model inside the API process, so the first question in a demo
# does not pay the cold-start cost (~90 s measured on 2026-11-22).
# Usage (repo root, API already running on 127.0.0.1:8000):
#   ./scripts/demo-warmup.ps1 [-ApiBase http://127.0.0.1:8000/api] [-KeepAlive 3h]
param(
    [string]$ApiBase = 'http://127.0.0.1:8000/api',
    [string]$OllamaBase = 'http://127.0.0.1:11434',
    [string]$Model = 'qwen2.5:7b-instruct',
    [string]$KeepAlive = '3h',
    [string]$Email = 'sv2@dutlearn.local',
    [string]$Password = $(if ($env:DUT_DEMO_PASSWORD) { $env:DUT_DEMO_PASSWORD } else { 'dutlearn-dev' })
)
$ErrorActionPreference = 'Stop'

function Step($msg) { Write-Host "==> $msg" }

Step 'Checking API health'
$health = Invoke-RestMethod "$ApiBase/health" -TimeoutSec 15
if (-not $health.db -or -not $health.llm) { throw "Health check failed: db=$($health.db) llm=$($health.llm)" }

Step "Loading $Model into GPU memory (keep_alive=$KeepAlive)"
$sw = [Diagnostics.Stopwatch]::StartNew()
$body = @{ model = $Model; prompt = 'OK'; stream = $false; keep_alive = $KeepAlive; options = @{ num_ctx = 4096; num_predict = 1 } } | ConvertTo-Json
Invoke-RestMethod "$OllamaBase/api/generate" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 300 | Out-Null
Write-Host "    LLM ready in $([math]::Round($sw.Elapsed.TotalSeconds, 1)) s"

Step 'Asking one question through the API (loads the embedding model)'
$headers = @{ 'X-DUT-CSRF' = '1' }
$login = @{ email = $Email; password = $Password } | ConvertTo-Json
$resp = Invoke-WebRequest "$ApiBase/auth/login" -Method Post -Body $login -ContentType 'application/json' -Headers $headers -UseBasicParsing
# With DUT_COOKIE_SECURE=true the session cookie is marked Secure, which the
# client would not send back over plain http to localhost; pass it explicitly.
$value = (@($resp.Headers['Set-Cookie']) -join ',') -replace '(?s)^.*?dut_session=([^;]+).*$', '$1'
if (-not $value -or $value -match '[;,\s]') { throw 'Login did not return a session cookie' }
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$session.Cookies.Add((New-Object System.Net.Cookie('dut_session', $value, '/', ([Uri]$ApiBase).Host)))
$classes = Invoke-RestMethod "$ApiBase/classes" -WebSession $session
$classList = @($classes)
if ($classes.PSObject.Properties.Name -contains 'items') { $classList = @($classes.items) }
if ($classList.Count -eq 0) { throw "Account $Email has no class" }
$ask = @{ class_id = $classList[0].id; lesson_id = $null; material_id = $null; page_index = $null; session_id = $null; mode = 'answer'; question = 'Biến là gì?' } | ConvertTo-Json
$sw.Restart()
$answer = Invoke-RestMethod "$ApiBase/tutor/ask" -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($ask)) -ContentType 'application/json; charset=utf-8' -Headers $headers -WebSession $session -TimeoutSec 180
$secs = [math]::Round($sw.Elapsed.TotalSeconds, 1)
Write-Host "    Tutor answered (status=$($answer.status), citations=$(@($answer.citations).Count)) in $secs s"

Step 'GPU check'
try {
    $util = (& nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader) -join ' '
    Write-Host "    GPU: $util"
} catch { Write-Host '    nvidia-smi not available' }
& ollama ps
# Each API request sends Ollama's default keep_alive (30 min), which overrides
# the value above; the server-wide setting is what keeps the model resident.
Write-Host "    Note: start Ollama with `$env:OLLAMA_KEEP_ALIVE='$KeepAlive' so API calls do not shorten residency to 30 min."
if ($secs -gt 10) {
    Write-Warning "Warm answer took $secs s (expected a few seconds). Close games/apps using the GPU, then run this script again."
} else {
    Write-Host 'Warm-up done. The warm-up question is saved in the history of the warm-up account; use a different student account for the demo.'
}
