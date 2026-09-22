param(
    [string]$InputFile = 'examples\ticket-de.json'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')
$ResolvedInput = if ([System.IO.Path]::IsPathRooted($InputFile)) { $InputFile } else { Join-Path $ProjectRoot $InputFile }
& $ProjectPython (Join-Path $ProjectRoot 'laya_local.py') predict --input $ResolvedInput
exit $LASTEXITCODE

