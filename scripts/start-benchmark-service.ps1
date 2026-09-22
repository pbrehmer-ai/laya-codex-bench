param([int]$Port = 8765)

$ErrorActionPreference = 'Stop'
$env:LAYA_PRELOAD_MODELS = 'english,multilingual,typed-decisions'
& (Join-Path $PSScriptRoot 'start-background.ps1') -Port $Port
