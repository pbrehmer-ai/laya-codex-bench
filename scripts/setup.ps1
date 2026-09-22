$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')

$ToolsDir = Join-Path $ProjectRoot '.tools'
$UvExe = Join-Path $ToolsDir 'uv.exe'
if (-not (Test-Path -LiteralPath $UvExe)) {
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
    $UvZip = Join-Path $ToolsDir 'uv.zip'
    $UvExpanded = Join-Path $ToolsDir 'uv-dist'
    curl.exe -L 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -o $UvZip
    Expand-Archive -LiteralPath $UvZip -DestinationPath $UvExpanded -Force
    Copy-Item -LiteralPath (Join-Path $UvExpanded 'uv.exe') -Destination $UvExe -Force
}

& $UvExe python install 3.12
& $UvExe sync --project $ProjectRoot
Write-Host "Laya environment ready in $ProjectRoot"

