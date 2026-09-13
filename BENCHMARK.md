# Space Deep Tech Center V0.6 Performance Audit

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
