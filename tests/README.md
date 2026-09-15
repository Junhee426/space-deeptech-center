# Regression checks

Install the Python requirements and start the app from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

In another terminal:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
npm.cmd install --prefix .test-tools playwright@1.63.0 --ignore-scripts --no-audit --no-fund
node .test-tools/node_modules/playwright/cli.js install chromium
$env:PLAYWRIGHT_MODULE = (Resolve-Path .test-tools/node_modules/playwright).Path
node tests/ui-regression.cjs
```

Optional environment variables: `APP_URL` selects the local app URL; `CHROMIUM_PATH` selects an existing Chromium executable; `REVIEW_OUTPUT` saves viewport screenshots. The browser test uses an isolated browser context, real local APIs, and a single injected 422 response to verify failure handling.

Coverage: 10 views at 1440/1024/390px; visible run buttons; shared mission geometry; PHY and beamforming architecture labels; ISL visibility; calculated SVG dimensions; invalid input; stale responses; error messages; warning stability; saved scenario restoration; Optimizer execution; Optimizer stale-response discard (a response for inputs that changed mid-flight, or that arrives after a newer run, must never be rendered). The Python regression checks both integrated evaluation paths with a non-default Walker geometry.
