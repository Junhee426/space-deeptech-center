# Space Deep Tech Center V0.7.0

A FastAPI engineering workbench for satellite links, digital beamforming, RF payloads, radiation, constellation coverage and mission trade studies.

## V0.7 upgrade

- **Geometry and service:** user elevation uses the ground-to-satellite direction. Users below the elevation mask have zero channel gain. A geometry-enabled scenario with no visible serving satellite produces zero throughput; zero effective beams also produce zero service. Synthetic channels are used only when geometry is explicitly disabled, including Fast batch screening.
- **Shared calculations:** interactive mission results and batch evaluation use the same integrated calculation. Request models live in `core/models.py` and remain available through `core.engine` for compatibility.
- **Uncertainty:** Monte Carlo samples PA efficiency and applies the same efficiency to the link and payload power/thermal calculations. The requested run count (1–5,000) is respected. A fixed seed reproduces V0.7 results; outputs differ from V0.6 because efficiency uncertainty is now included.
- **Bounded workloads:** Coverage reduces visibility in chunks of at most 65,536 satellite-time cells. API models reject invalid physical inputs and excessive orbit/batch workloads with HTTP 422.
- **Batch execution:** Optimizer and Monte Carlo reuse a process pool with two workers by default. `SDTC_MAX_WORKERS=1` selects serial execution; values are capped at eight and the host CPU count. One batch is admitted per API process; concurrent requests receive HTTP 503 with `Retry-After: 2`. Calculation errors propagate; pool unavailability is logged and reported as `serial-fallback`. Responses report the actual `parallel` and `execution` values.
- **Dependencies:** FastAPI 0.141.1, Starlette 1.6.0, Uvicorn 0.53.0 and Jinja2 3.1.6. Windows uses Uvicorn's portable HTTP implementation; other platforms retain its standard extras.

## Run

Python 3.11 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. The existing Render service configuration is in `render.yaml`.

## Structure

```text
app.py                FastAPI bootstrap, lifespan and overload response
api/routes.py         API routes
core/models.py        Validated request models and workload limits
core/engine.py        Domain models and shared mission calculation
core/version.py       Application version
physics/core.py       Scalar physical utilities
orbit/walker.py       Vectorized propagation and chunked visibility
payload/vectorized.py Signal-processing kernels
simulation/           Batch services, shared process pool and workers
static/, templates/   Interactive workbench
```

Diagnostics: `GET /api/health`, `/api/architecture`, `/api/performance`.

## Validation

See [tests/README.md](tests/README.md) for Python and browser regressions, and [BENCHMARK.md](BENCHMARK.md) for recorded performance context.

The UI retains the KASA-inspired navy `#012B49` and red `#F94239`. Orbit models remain circular two-body approximations; J2, drag, eccentricity and refraction are outside their scope. Fast screening results require confirmation with the intended geometry. Mass, cost and thermal layout indicators are engineering proxies.
