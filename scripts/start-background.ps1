param(
    [int]$Port = 8765,
    [switch]$Lazy
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')

$RuntimeDir = Join-Path $ProjectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

try {
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
    if ($Health.status -eq 'ok' -and $Health.api_version -eq 2) {
        $Health.pid | Set-Content -Encoding ascii (Join-Path $RuntimeDir 'laya-server.pid')
        Write-Host "Laya is already running (PID $($Health.pid), model loaded: $($Health.model_loaded))."
        exit 0
    }
} catch {
    # No healthy local service is listening yet.
}

$Arguments = @('-u', (Join-Path $ProjectRoot 'laya_local.py'), 'serve', '--port', $Port)
if ($Lazy) { $Arguments += '--lazy' }

$Process = Start-Process `
    -FilePath $ProjectPython `
    -ArgumentList $Arguments `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $RuntimeDir 'laya-server.stdout.log') `
    -RedirectStandardError (Join-Path $RuntimeDir 'laya-server.stderr.log') `
    -PassThru

$Process.Id | Set-Content -Encoding ascii (Join-Path $RuntimeDir 'laya-server.pid')

$Deadline = (Get-Date).AddSeconds(600)
do {
    if ($Process.HasExited) {
        throw "Laya exited during startup. See .runtime\laya-server.stderr.log"
    }
    Start-Sleep -Milliseconds 250
    try {
        $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
        if ($Health.status -eq 'ok' -and $Health.api_version -eq 2) {
            $Health.pid | Set-Content -Encoding ascii (Join-Path $RuntimeDir 'laya-server.pid')
            Write-Host "Laya started in the background (PID $($Health.pid), model loaded: $($Health.model_loaded))."
            exit 0
        }
    } catch {
        # Continue polling while the model is loading.
    }
} while ((Get-Date) -lt $Deadline)

throw "Laya did not become healthy within 600 seconds."
