param(
    [int]$Port = 8765,
    [switch]$Lazy
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')
$Arguments = @((Join-Path $ProjectRoot 'laya_local.py'), 'serve', '--port', $Port)
if ($Lazy) { $Arguments += '--lazy' }
& $ProjectPython @Arguments
exit $LASTEXITCODE

