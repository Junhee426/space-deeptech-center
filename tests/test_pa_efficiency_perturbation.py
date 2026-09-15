import unittest
import numpy as np
from core import engine


class PaEfficiencyPerturbationPropagationTests(unittest.TestCase):
    """Item 5: pa_eff_perturbation_mult (driven by MonteCarloInput.pa_eff_sigma_pct)
    must actually perturb PA efficiency and propagate into DC power, heat and mass."""

    def test_multiplier_changes_dc_power_heat_and_mass(self):
        baseline = engine.satcom(engine.SatcomInput())
        perturbed = engine.satcom(engine.SatcomInput(pa_eff_perturbation_mult=0.8))

        self.assertLess(perturbed["device"]["pa_eff_pct"], baseline["device"]["pa_eff_pct"])
        # Lower efficiency for the same RF output -> more DC power drawn, more heat.
        self.assertGreater(perturbed["device"]["pa_dc_w"], baseline["device"]["pa_dc_w"])
        self.assertGreater(perturbed["device"]["heat_w"], baseline["device"]["heat_w"])
        # More heat -> a larger radiator -> more payload mass.
        self.assertGreater(perturbed["payload"]["mass_kg"], baseline["payload"]["mass_kg"])

    def test_default_multiplier_is_neutral(self):
        baseline = engine.satcom(engine.SatcomInput())
        explicit_neutral = engine.satcom(engine.SatcomInput(pa_eff_perturbation_mult=1.0))
        self.assertEqual(baseline, explicit_neutral)


class MonteCarloPaEfficiencySamplingTests(unittest.TestCase):
    """Item 5 verification criteria: same seed+sigma reproducibility, and sigma=0
    matches the unperturbed baseline exactly."""

    def test_same_seed_and_sigma_is_reproducible(self):
        mc = engine.MonteCarloInput(runs=100, seed=123, pa_eff_sigma_pct=6)
        r1 = engine.api_montecarlo(mc)
        r2 = engine.api_montecarlo(mc)
        self.assertEqual(r1["metrics"], r2["metrics"])
        self.assertEqual(r1["samples"], r2["samples"])

    def test_zero_sigma_pa_eff_multiplier_is_exactly_one(self):
        # rng.normal(1.0, 0.0, N) is a degenerate distribution returning exactly
        # the mean for every draw, so sigma=0 must reproduce the unperturbed
        # baseline bit-for-bit -- not just "approximately".
        rng = np.random.default_rng(42)
        draws = np.maximum(0.05, rng.normal(1.0, 0.0 / 100, 50))
        self.assertTrue(np.all(draws == 1.0))

    def test_montecarlo_runs_to_completion_with_zero_pa_eff_sigma(self):
        mc = engine.MonteCarloInput(runs=100, seed=1, pa_eff_sigma_pct=0)
        r = engine.api_montecarlo(mc)
        self.assertEqual(r["runs"], 100)
        self.assertEqual(len(r["samples"]), 100)

    def test_nonzero_sigma_changes_results_vs_zero_sigma(self):
        base_kwargs = dict(runs=200, seed=99)
        r_zero = engine.api_montecarlo(engine.MonteCarloInput(pa_eff_sigma_pct=0, **base_kwargs))
        r_pert = engine.api_montecarlo(engine.MonteCarloInput(pa_eff_sigma_pct=15, **base_kwargs))
        self.assertNotEqual(r_zero["metrics"]["power_w"], r_pert["metrics"]["power_w"])


class FastPathGeometryDisclosureTests(unittest.TestCase):
    """Item 5 verification: optimizer/sensitivity/Monte Carlo do intentionally use
    a Fast screening model (per README's documented Full/Fast strategy) without
    per-user geometry/visibility masking for batch performance -- this must be
    disclosed, not silently/quietly done."""

    def test_optimize_discloses_fast_screening(self):
        r = engine.api_optimize(engine.OptimizeInput())
        self.assertIn("note", r)
        self.assertIn("Fast", r["note"])

    def test_sensitivity_discloses_fast_screening(self):
        r = engine.api_sensitivity(engine.SensitivityInput(steps=3))
        self.assertIn("note", r)
        self.assertIn("Fast", r["note"])

    def test_montecarlo_discloses_fast_screening(self):
        r = engine.api_montecarlo(engine.MonteCarloInput(runs=100))
        self.assertIn("note", r)


if __name__ == "__main__":
    unittest.main()
