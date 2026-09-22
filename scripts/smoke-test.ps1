$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')

$Output = & $ProjectPython (Join-Path $ProjectRoot 'laya_local.py') predict --input (Join-Path $ProjectRoot 'examples\ticket-de.json')
if ($LASTEXITCODE -ne 0) {
    throw "Laya prediction failed with exit code $LASTEXITCODE"
}

$Result = $Output | ConvertFrom-Json
if ($Result.answers.abteilung.choice -ne 'abrechnung') {
    throw "Expected department 'abrechnung', got '$($Result.answers.abteilung.choice)'"
}
if ($Result.answers.erstattung_gefordert.noul -lt 0.5) {
    throw "Expected refund probability above 0.5, got $($Result.answers.erstattung_gefordert.noul)"
}

[pscustomobject]@{
    status = 'passed'
    checkpoint = $Result.deployment.checkpoint
    device = $Result.deployment.device
    department = $Result.answers.abteilung.choice
    refund_probability = $Result.answers.erstattung_gefordert.noul
    inference_ms = $Result.deployment.inference_ms
} | Format-List

