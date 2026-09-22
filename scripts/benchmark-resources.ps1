param(
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $ProjectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Get-LayaHealth {
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3
}

function Get-ProcessMemory([int]$ProcessId) {
    $Process = Get-Process -Id $ProcessId
    [pscustomobject]@{
        PrivateMB = [math]::Round($Process.PrivateMemorySize64 / 1MB, 2)
        WorkingSetMB = [math]::Round($Process.WorkingSet64 / 1MB, 2)
    }
}

function Measure-LayaRequest([string]$Name, [string]$InputFile, [int]$ProcessId, [int]$LogicalProcessors) {
    $ProcessBefore = Get-Process -Id $ProcessId
    $CpuBeforeMs = $ProcessBefore.TotalProcessorTime.TotalMilliseconds
    $LastCpuMs = $CpuBeforeMs
    $PeakCorePercent = 0.0
    $PeakPrivateMB = $ProcessBefore.PrivateMemorySize64 / 1MB
    $PeakWorkingSetMB = $ProcessBefore.WorkingSet64 / 1MB
    $Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $LastSampleMs = 0.0

    $Job = Start-Job -ScriptBlock {
        param($RequestPath, $RequestPort)
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$RequestPort/predict" -ContentType 'application/json; charset=utf-8' -InFile $RequestPath -TimeoutSec 120
    } -ArgumentList $InputFile, $Port

    while ($Job.State -in @('NotStarted', 'Running')) {
        Start-Sleep -Milliseconds 50
        $Process = Get-Process -Id $ProcessId
        $NowMs = $Stopwatch.Elapsed.TotalMilliseconds
        $CpuNowMs = $Process.TotalProcessorTime.TotalMilliseconds
        $IntervalMs = $NowMs - $LastSampleMs
        if ($IntervalMs -gt 0) {
            $CorePercent = (($CpuNowMs - $LastCpuMs) / $IntervalMs) * 100
            $PeakCorePercent = [math]::Max($PeakCorePercent, $CorePercent)
        }
        $PeakPrivateMB = [math]::Max($PeakPrivateMB, $Process.PrivateMemorySize64 / 1MB)
        $PeakWorkingSetMB = [math]::Max($PeakWorkingSetMB, $Process.WorkingSet64 / 1MB)
        $LastCpuMs = $CpuNowMs
        $LastSampleMs = $NowMs
    }

    $Response = Receive-Job -Job $Job
    Remove-Job -Job $Job
    $ProcessAfter = Get-Process -Id $ProcessId
    $FinalNowMs = $Stopwatch.Elapsed.TotalMilliseconds
    $FinalCpuMs = $ProcessAfter.TotalProcessorTime.TotalMilliseconds
    $FinalIntervalMs = $FinalNowMs - $LastSampleMs
    if ($FinalIntervalMs -gt 0) {
        $FinalCorePercent = (($FinalCpuMs - $LastCpuMs) / $FinalIntervalMs) * 100
        $PeakCorePercent = [math]::Max($PeakCorePercent, $FinalCorePercent)
    }
    $PeakPrivateMB = [math]::Max($PeakPrivateMB, $ProcessAfter.PrivateMemorySize64 / 1MB)
    $PeakWorkingSetMB = [math]::Max($PeakWorkingSetMB, $ProcessAfter.WorkingSet64 / 1MB)
    $CpuUsedMs = $ProcessAfter.TotalProcessorTime.TotalMilliseconds - $CpuBeforeMs
    $InferenceMs = [double]$Response.deployment.inference_ms
    $AverageCorePercent = if ($InferenceMs -gt 0) { ($CpuUsedMs / $InferenceMs) * 100 } else { 0 }

    [pscustomobject]@{
        Test = $Name
        Questions = @($Response.answers.PSObject.Properties).Count
        InferenceMs = [math]::Round($InferenceMs, 2)
        CpuTimeMs = [math]::Round($CpuUsedMs, 2)
        AverageCorePercent = [math]::Round($AverageCorePercent, 1)
        AverageMachinePercent = [math]::Round($AverageCorePercent / $LogicalProcessors, 1)
        PeakPrivateMB = [math]::Round($PeakPrivateMB, 2)
        PeakWorkingSetMB = [math]::Round($PeakWorkingSetMB, 2)
    }
}

try {
    $Health = Get-LayaHealth
} catch {
    & (Join-Path $PSScriptRoot 'start-background.ps1') -Port $Port -Lazy
    $Health = Get-LayaHealth
}

$ServerPid = [int]$Health.pid
$LogicalProcessors = [Environment]::ProcessorCount
$ReportPath = Join-Path $RuntimeDir 'resource-benchmark.json'
$ExistingReport = if (Test-Path -LiteralPath $ReportPath) { Get-Content -Raw $ReportPath | ConvertFrom-Json } else { $null }
$Baseline = if (-not $Health.model_loaded) {
    Get-ProcessMemory -ProcessId $ServerPid
} elseif ($ExistingReport -and $ExistingReport.ProcessId -eq $ServerPid) {
    $ExistingReport.IdleBeforeModel
} else {
    $null
}

if (-not $Health.model_loaded) {
    $Warmup = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/predict" -ContentType 'application/json; charset=utf-8' -InFile (Join-Path $ProjectRoot 'examples\benchmark-single.json') -TimeoutSec 120
    Start-Sleep -Seconds 1
    $Health = Get-LayaHealth
} else {
    $Warmup = $null
}

$Loaded = Get-ProcessMemory -ProcessId $ServerPid
$IdleCpuStart = (Get-Process -Id $ServerPid).TotalProcessorTime.TotalMilliseconds
$IdleStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
Start-Sleep -Seconds 3
$IdleCpuEnd = (Get-Process -Id $ServerPid).TotalProcessorTime.TotalMilliseconds
$IdleStopwatch.Stop()
$IdleCorePercent = (($IdleCpuEnd - $IdleCpuStart) / $IdleStopwatch.Elapsed.TotalMilliseconds) * 100
$Tests = @(
    Measure-LayaRequest -Name '1 binary question' -InputFile (Join-Path $ProjectRoot 'examples\benchmark-single.json') -ProcessId $ServerPid -LogicalProcessors $LogicalProcessors
    Measure-LayaRequest -Name '4 mixed questions' -InputFile (Join-Path $ProjectRoot 'examples\ticket-de.json') -ProcessId $ServerPid -LogicalProcessors $LogicalProcessors
    Measure-LayaRequest -Name '12 mixed questions' -InputFile (Join-Path $ProjectRoot 'examples\benchmark-batch.json') -ProcessId $ServerPid -LogicalProcessors $LogicalProcessors
)

$Report = [pscustomobject]@{
    Timestamp = (Get-Date).ToString('o')
    ProcessId = $ServerPid
    Processor = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name).Trim()
    PhysicalCores = (Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum
    LogicalProcessors = $LogicalProcessors
    SystemRamGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1MB, 2)
    IdleBeforeModel = $Baseline
    IdleWithModel = $Loaded
    IncrementalModelPrivateMB = if ($Baseline) { [math]::Round($Loaded.PrivateMB - $Baseline.PrivateMB, 2) } else { $null }
    IncrementalModelWorkingSetMB = if ($Baseline) { [math]::Round($Loaded.WorkingSetMB - $Baseline.WorkingSetMB, 2) } else { $null }
    InitialLoadSeconds = $Health.initial_load_seconds
    IdleCpuCorePercent = [math]::Round($IdleCorePercent, 2)
    IdleCpuMachinePercent = [math]::Round($IdleCorePercent / $LogicalProcessors, 2)
    Tests = $Tests
}

$Report | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 $ReportPath
$Report | ConvertTo-Json -Depth 8
