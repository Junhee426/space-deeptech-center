import math
import unittest

from pydantic import ValidationError

from core import engine


class FiniteNumberValidationTests(unittest.TestCase):
    def test_nan_frequency_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(frequency_ghz=float("nan"))

    def test_infinite_altitude_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(altitude_km=float("inf"))

    def test_negative_infinite_value_rejected(self):
        with self.assertRaises(ValidationError):
            engine.PayloadInput(input_power_dbw=float("-inf"))


class PhysicalRangeValidationTests(unittest.TestCase):
    def test_zero_frequency_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(frequency_ghz=0)

    def test_frequency_far_outside_rf_bands_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(frequency_ghz=1e6)

    def test_altitude_below_karman_line_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(altitude_km=50)

    def test_negative_altitude_rejected(self):
        with self.assertRaises(ValidationError):
            engine.CoverageInput(altitude_km=-100)

    def test_valid_defaults_still_construct(self):
        engine.SatcomInput()
        engine.PayloadInput()
        engine.CoverageInput()
        engine.PassTimelineInput()
        engine.MonteCarloInput()
        engine.PropagationInput()
        engine.PoissonDeviceInput()


class EnumValidationTests(unittest.TestCase):
    def test_unknown_material_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(material="Unobtainium")

    def test_unknown_processor_rejected(self):
        with self.assertRaises(ValidationError):
            engine.SatcomInput(processor="Quantum")

    def test_unknown_polarization_rejected(self):
        with self.assertRaises(ValidationError):
            engine.PropagationInput(polarization="Diagonal")

    def test_unknown_traffic_pattern_rejected(self):
        with self.assertRaises(ValidationError):
            engine.PayloadInput(traffic_pattern="Chaotic")

    def test_known_enum_values_accepted(self):
        engine.SatcomInput(material="SiC", processor="ASIC")
        engine.PayloadInput(traffic_pattern="Edge-heavy", scheduler="Max C/I")


class WalkerConstellationCrossFieldValidationTests(unittest.TestCase):
    """Item 4: infeasible Walker constellation phasing (F >= planes) must be
    rejected rather than silently wrapped (the old `f % planes` behavior)."""

    def test_coverage_input_rejects_phasing_out_of_range(self):
        with self.assertRaises(ValidationError):
            engine.CoverageInput(planes=4, walker_f=4)
        with self.assertRaises(ValidationError):
            engine.CoverageInput(planes=4, walker_f=10)

    def test_pass_timeline_input_rejects_phasing_out_of_range(self):
        with self.assertRaises(ValidationError):
            engine.PassTimelineInput(planes=4, walker_f=5)

    def test_payload_input_rejects_phasing_out_of_range(self):
        with self.assertRaises(ValidationError):
            engine.PayloadInput(geometry_planes=4, geometry_walker_f=10)

    def test_valid_phasing_accepted(self):
        engine.CoverageInput(planes=4, walker_f=3)
        engine.CoverageInput(planes=4, walker_f=0)


class ModelCopyRevalidationTests(unittest.TestCase):
    """Item 4: validators must also fire on model_copy(update=...), not only at
    initial construction, since the codebase updates these models almost
    exclusively through model_copy when propagating shared mission parameters."""

    def test_model_copy_rejects_invalid_walker_phasing(self):
        base = engine.CoverageInput()
        with self.assertRaises(ValidationError):
            base.model_copy(update={"walker_f": 999})

    def test_model_copy_rejects_non_finite_value(self):
        base = engine.CoverageInput()
        with self.assertRaises(ValidationError):
            base.model_copy(update={"altitude_km": float("nan")})

    def test_model_copy_rejects_unknown_enum(self):
        base = engine.SatcomInput()
        with self.assertRaises(ValidationError):
            base.model_copy(update={"material": "Unobtainium"})

    def test_model_copy_with_valid_update_still_works(self):
        base = engine.SatcomInput()
        updated = base.model_copy(update={"altitude_km": 900})
        self.assertEqual(updated.altitude_km, 900.0)

    def test_assignment_is_also_validated(self):
        base = engine.CoverageInput()
        with self.assertRaises(ValidationError):
            base.walker_f = 999


class EndToEndApiValidationTests(unittest.TestCase):
    """Sanity: the full pipeline still runs with defaults after adding validation."""

    def test_full_pipeline_smoke(self):
        self.assertTrue(engine.satcom(engine.SatcomInput()))
        self.assertTrue(engine.beamforming(engine.BeamInput()))
        self.assertTrue(engine.radiation(engine.RadInput()))
        self.assertTrue(engine.payload(engine.PayloadInput()))
        self.assertTrue(engine.api_integrated(engine.IntegratedInput()))
        self.assertTrue(engine.integrated_calc(engine.IntegratedInput()))
        self.assertTrue(engine.api_coverage(engine.CoverageInput(duration_hours=1)))
        self.assertTrue(engine.api_pass_timeline(engine.PassTimelineInput(duration_hours=1)))
        self.assertTrue(engine.api_propagation(engine.PropagationInput()))
        self.assertTrue(engine.api_poisson_device(engine.PoissonDeviceInput()))
        self.assertTrue(engine.orbit_sweep(engine.SatcomInput()))
        self.assertTrue(engine.mat_sweep(engine.SatcomInput()))


if __name__ == "__main__":
    unittest.main()
