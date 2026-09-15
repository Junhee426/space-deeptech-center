# Regression checks

Install into an isolated environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Python checks cover shared mission geometry, zenith elevation, horizon masking, zero-service states, agreement between integrated paths, bounded Coverage chunks, outage duration, Monte Carlo efficiency uncertainty and reproducibility, actual pool reuse, serial fallback, worker-error propagation, retryable overload, API validation and default endpoint smoke tests.

For the browser suite, start the app from the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765
```

In another terminal:

```powershell
npm.cmd install --prefix .test-tools playwright@1.63.0 --ignore-scripts --no-audit --no-fund
node .test-tools/node_modules/playwright/cli.js install chromium
$env:PLAYWRIGHT_MODULE = (Resolve-Path .test-tools/node_modules/playwright).Path
node tests/ui-regression.cjs
```

Optional environment variables: `APP_URL` selects the local app URL; `CHROMIUM_PATH` selects an existing Chromium executable; `REVIEW_OUTPUT` saves viewport screenshots. The browser test uses an isolated browser context, real local APIs, and a single injected 422 response to verify failure handling.

Browser coverage: 10 views at 1440/1024/390px; visible run buttons; shared mission geometry; PHY and beamforming architecture labels; ISL visibility; calculated SVG dimensions; invalid input; stale responses; error messages; warning stability; saved scenario restoration; Optimizer execution.

Batch control is per API process. Use the deployment's single Uvicorn worker for one global batch limit, or size process/worker counts together. Clients should retry a 503 after the returned delay; the browser displays the error and supports rerunning the action.

The detailed CONOPS suite uses the same server and browser environment:

```powershell
node tests/conops-regression.cjs
```

It checks all three diagram views at 1440/1024/390px, beam rendering limits, altitude/elevation geometry, Walker phasing, ISL visibility, architecture-dependent signal paths, antenna sizing, layer controls, animation/reduced-motion behavior, and invalid-input recovery. `REVIEW_OUTPUT` additionally captures the overall, payload, coverage and mobile illustrations.
