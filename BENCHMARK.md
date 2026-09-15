# V0.7 validation ? 2026-09-16

Measured locally on Windows ARM64, Python 3.12.10, with a running Uvicorn server and two batch workers. These timings are observations, not a direct speed comparison with the historical V0.6 environment or a Render deployment benchmark.

| Check | Result |
|---|---:|
| Python regression suite | 16 tests passed |
| Browser layout regression | 30 view/width combinations passed |
| Browser runtime errors | 0 |
| Optimizer, 1,728 candidates (first batch, including pool startup) | 2.299 s |
| Monte Carlo, 100 cases (reused pool) | 0.151 s |
| Coverage temporary propagation allocation | At most 65,536 satellite-time cells per chunk |

Coverage counts match the full-array reference across chunk boundaries. API tests reject the formerly accepted 60 ? 60 satellite, 168-hour, 5-second request before allocation. Work budgets are 10 million cells for Coverage and 2 million for pass timelines, based on their effective sampling intervals. Batch validation also bounds user/slot/run combinations.

Tests additionally verify horizon masking, zero-service states, shared integrated results, PA-efficiency effects down to 2%, seeded reproducibility, real process-pool reuse, calculation-error propagation, serial fallback and HTTP 503 admission control.

## Historical V0.6 audit

### Space Deep Tech Center V0.6 Performance Audit

Fresh-process benchmark in the current execution environment.

| Test | Result |
|---|---:|
| Thin `app.py` | 18 lines |
| Numerical `core/engine.py` | 1887 lines |
| FastAPI routes | 28 |
| Walker 24 h, 120 s, 128 satellites | 13.50 ms |
| Walker array | [721, 128, 3] |
| Full RF Payload, 16 users / 8 beams | 9.15 ms |
| Geometry-scheduled capacity in test case | 3.291 Gbps |
| Coverage, 3 regions / 24 h | 37.72 ms |
| Monte Carlo, 100 cases | 0.114 s |
| Optimizer, 1,728 cases | 1.096 s |

## Architecture changes
- `app.py` is now a thin FastAPI bootstrap.
- API wiring lives in `api/routes.py`.
- numerical and model functions live behind `core/engine.py`.
- parallel workers import `core.engine`, not `app`.
- Walker time propagation remains NumPy-vectorized.
- optimizer and Monte Carlo use bounded process-pool evaluation.
- RF waveform and matrix calculations remain NumPy/FFT based.

## Second optimization review
The remaining largest architectural debt is the size of `core/engine.py`.
It is intentionally retained as a compatibility engine in V0.6 while high-cost kernels already live in dedicated numerical modules.
The next safe extraction targets are:
1. semiconductor / propagation models,
2. satcom + beamforming services,
3. radiation service,
4. payload orchestration,
5. integrated mission service.

This staged approach avoids a high-risk all-at-once rewrite while leaving `app.py` clean now.
