from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from core import engine
from simulation import services

router=APIRouter()

@router.post("/satcom")
def satcom(x: engine.SatcomInput): return engine.satcom(x)

@router.post("/beamforming")
def beamforming(x: engine.BeamInput): return engine.beamforming(x)

@router.post("/radiation")
def radiation(x: engine.RadInput): return engine.radiation(x)

@router.post("/payload")
def payload(x: engine.PayloadInput): return engine.payload(x)

@router.get("/parts")
def parts(): return engine.api_parts()

@router.post("/satcom/orbit-sweep")
def orbit_sweep(x: engine.SatcomInput): return engine.orbit_sweep(x)

@router.post("/satcom/material-sweep")
def material_sweep(x: engine.SatcomInput): return engine.mat_sweep(x)

@router.post("/integrated")
def integrated(x: engine.IntegratedInput): return engine.api_integrated(x)

@router.post("/optimize")
def optimize(x: engine.OptimizeInput): return services.optimize(x)

@router.post("/sensitivity")
def sensitivity(x: engine.SensitivityInput): return services.sensitivity(x)

@router.post("/report-summary")
def report_summary(x: engine.IntegratedInput): return engine.api_report_summary(x)

@router.post("/coverage")
def coverage(x: engine.CoverageInput): return engine.api_coverage(x)

@router.post("/montecarlo")
def montecarlo(x: engine.MonteCarloInput): return services.monte_carlo(x)

@router.post("/coverage-sweep")
def coverage_sweep(x: engine.CoverageInput): return engine.api_coverage_sweep(x)

@router.get("/theory")
def theory(): return engine.api_theory()

@router.post("/propagation")
def propagation(x: engine.PropagationInput): return engine.api_propagation(x)

@router.post("/poisson-device")
def poisson_device(x: engine.PoissonDeviceInput): return engine.api_poisson_device(x)

@router.post("/pass-timeline")
def pass_timeline(x: engine.PassTimelineInput): return engine.api_pass_timeline(x)

@router.get("/physics-registry")
def physics_registry(): return engine.api_physics_registry()

@router.get("/performance")
def performance(): return engine.api_performance()

@router.get("/architecture")
def architecture():
    return {
      "version":"0.6.0",
      "bootstrap":"app.py",
      "engine":"core/engine.py",
      "api":"api/routes.py",
      "simulation":"simulation/services.py + workers.py + batch.py",
      "numerics":["physics/core.py","orbit/walker.py"],
      "design":"thin FastAPI bootstrap with domain numerical modules"
    }

@router.get("/health")
def health():
    return {"status":"ok","version":"0.6.0","labs":9,"physics_models":len(engine.PHYSICS_REGISTRY)}
