# Local Laya resource usage

This measurement used the same warm Laya service process (PID 3592) as the Codex pilot on a 12th Gen Intel Core i3-12100 (4 physical cores, 8 logical processors) with 31.78 GB system RAM.

## Resident process

- Private memory while idle: 2,946.62 MB
- Working set while idle: 1,697.36 MB
- Idle CPU over a three-second sample: 0.0% of the machine
- Initial model load: 22.43 seconds

These memory figures cover the complete Python/Laya inference process, including its runtime and loaded checkpoint. They are the operational cost of keeping Laya ready; they must not be described as model weights alone.

## Warm inference

| Workload | Questions | Inference | CPU time | Average CPU, whole machine | Peak private memory | Peak working set |
|---|---:|---:|---:|---:|---:|---:|
| Binary | 1 | 141.14 ms | 640.62 ms | 56.7% | 2,967.74 MB | 1,701.25 MB |
| Mixed | 4 | 602.48 ms | 2,578.12 ms | 53.5% | 3,026.92 MB | 1,721.21 MB |
| Mixed | 12 | 2,678.04 ms | 10,046.88 ms | 46.9% | 3,134.83 MB | 1,791.01 MB |

CPU time can exceed wall time because inference uses several cores. “Average CPU, whole machine” divides core-equivalent utilization by all eight logical processors. Sampling and PowerShell job overhead make these engineering measurements, not laboratory-grade energy measurements.

Reproduce with:

```powershell
.\scripts\start-background.ps1
.\scripts\benchmark-resources.ps1
```
