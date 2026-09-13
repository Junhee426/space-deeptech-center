from core.engine import OptimizeInput, MonteCarloInput, SensitivityInput, api_optimize, api_montecarlo, api_sensitivity

def optimize(inp: OptimizeInput):
    return api_optimize(inp)

def monte_carlo(inp: MonteCarloInput):
    return api_montecarlo(inp)

def sensitivity(inp: SensitivityInput):
    return api_sensitivity(inp)
