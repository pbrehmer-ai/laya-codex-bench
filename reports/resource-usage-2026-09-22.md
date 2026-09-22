# Laya runtime resource benchmark — 2026-09-22

Measured on the same Windows machine used for the integration benchmarks.

## Recommended always-on mode

- Checkpoint: `multilingual`
- Process: persistent local CPU service, PID `2168`
- CPU: Intel Core i3-12100, 4 physical / 8 logical processors
- System RAM: 31.78 GB
- Cold load: 22.55 s
- Idle CPU after load: 0.0%
- Python service before model load: 13.55 MB private / 22.02 MB working set
- Increment attributable to the loaded model and runtime: **1,933.53 MB private / 1,626.79 MB working set**
- Loaded idle total: 1,947.08 MB private / 1,648.81 MB working set

| Probe | Questions | Laya inference | Process CPU time | Mean CPU, one-core scale | Mean whole-machine CPU | Peak private | Peak working set |
|---|---:|---:|---:|---:|---:|---:|---:|
| Binary | 1 | 112.07 ms | 640.62 ms | 571.6% | 71.5% | 1,979.54 MB | 1,652.66 MB |
| Mixed | 4 | 531.53 ms | 2,546.88 ms | 479.2% | 59.9% | 2,037.91 MB | 1,672.10 MB |
| Mixed | 12 | 2,408.38 ms | 9,921.88 ms | 412.0% | 51.5% | 2,139.69 MB | 1,744.12 MB |

`Mean CPU, one-core scale` can exceed 100% because PyTorch uses several cores. `Mean whole-machine CPU` divides that value by eight logical processors. These are process-only CPU measurements during inference, not total system load.

## Three-checkpoint benchmark mode

The checkpoint-selection run kept `english`, `multilingual`, and `typed-decisions` in one PID. Cold loading took 90.96 seconds. After the complete benchmark suite, Windows reported about 49.8 GB of private committed memory and had paged most of the process out, leaving an observed working set near 0.95–1.43 GB. Post-paging probes took 1.37–3.41 seconds.

That mode exists to compare checkpoints without reloading between cases. It is not the recommended always-on configuration for this 31.78 GB machine.

## Method

`scripts/benchmark-resources.ps1` samples only the Laya Python PID. It records `TotalProcessorTime`, private bytes, and working-set bytes before, during, and after three local API requests. The lazy start separates the lightweight HTTP process from the loaded model. Results are single-run operational measurements, not cross-hardware performance claims.
