# Space Deep Tech Center V0.6

This release renumbers the project to **V0.5** and focuses on computational architecture.

## Major optimization work

### 1. Monte Carlo
Random parameter generation is vectorized with NumPy.
The simulation package also provides `ProcessPoolExecutor` based `parallel_map()` for CPU-bound batch workloads.

### 2. Optimizer batch grid
Design-space combinations are generated as one NumPy mesh rather than constructed ad hoc.
The existing evaluator is preserved for numerical compatibility while the batch layer is ready for parallel case evaluation.

### 3. Walker time propagation
`orbit/walker.py` propagates the full `time × satellite × xyz` array in NumPy:
- Walker phase
- circular Kepler mean motion
- inclination / RAAN
- Earth rotation
- ECI → ECEF
- topocentric regional visibility

This removes the previous Python loop over every time sample.

### 4. Modular architecture
```text
app.py
physics/
  core.py
orbit/
  walker.py
payload/
  vectorized.py
simulation/
  batch.py
api/
  routes.py
```

The legacy API surface remains available from `app.py` to avoid breaking the Render frontend while physics and high-cost numerical kernels are progressively moved into dedicated modules.

### 5. Full / Fast strategy
- Interactive RF Payload: Full
- Optimizer: Fast screening
- Monte Carlo: Fast screening
- Sensitivity: Fast screening

## KASA visual identity
The UI retains the previous KASA-inspired palette:
- Navy `#012B49`
- Red `#F94239`

## New diagnostic API
`GET /api/architecture`
`GET /api/performance`

## Recommended next refactor
V0.6 should move the remaining legacy endpoint functions out of `app.py`, leaving it as a thin FastAPI bootstrap file only.


## Actual parallel endpoints
- `/api/optimize` now evaluates the batched candidate grid with a bounded `ProcessPoolExecutor`.
- `/api/montecarlo` vectorizes all random draws first, then distributes independent system cases to the process pool.
- Both automatically fall back to serial evaluation if process creation is unavailable in the deployment environment.


See `BENCHMARK.md` for the fresh-process V0.6 performance audit.
