param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ResolvedInput = if ([System.IO.Path]::IsPathRooted($InputFile)) { $InputFile } else { Join-Path $ProjectRoot $InputFile }

try {
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
} catch {
    & (Join-Path $PSScriptRoot 'start-background.ps1') -Port $Port
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
}

if ($Health.status -ne 'ok') {
    throw "The Laya service is not healthy."
}

$Result = Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:$Port/predict" `
    -ContentType 'application/json; charset=utf-8' `
    -InFile $ResolvedInput `
    -TimeoutSec 120
$Result | ConvertTo-Json -Depth 20

