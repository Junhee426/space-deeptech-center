import unittest
from core import engine


class NoVisibilityNoSyntheticFallbackTests(unittest.TestCase):
    """Item 2: geometry_channel_enabled=True with no visible satellite must yield
    real zero throughput/capacity, never a synthetic/idealized channel fallback."""

    def _no_visibility_payload_input(self):
        # min_elevation_deg=89.9 makes it effectively impossible for any Walker
        # satellite to be visible from the region anchor at t=0 with the default
        # constellation, so geometry["visible"] is False (no serving satellite at all).
        return engine.PayloadInput(
            geometry_channel_enabled=True,
            geometry_min_elevation_deg=89.9,
            users=8,
        )

    def test_payload_throughput_is_all_zero_not_synthetic(self):
        p = self._no_visibility_payload_input()
        r = engine.payload(p)
        self.assertFalse(r["geometry"]["visible"])
        self.assertEqual(r["traffic"]["user_throughput_mbps"], [0.0] * p.users)
        self.assertEqual(r["traffic"]["aggregate_scheduled_gbps"], 0.0)
        self.assertNotIn("synthetic fallback", r["geometry"]["channel_source"])
        self.assertTrue(
            any("no synthetic fallback" in w or "0 Mbps" in w for w in r["warnings"])
        )

    def test_api_integrated_capacity_is_zero_not_fallback_to_link_estimate(self):
        scenario = engine.IntegratedInput()
        scenario.payload.geometry_channel_enabled = True
        scenario.payload.geometry_min_elevation_deg = 89.9
        result = engine.api_integrated(scenario)
        self.assertEqual(result["integrated"]["effective_capacity_gbps"], 0.0)
        # Sanity: the satcom link-level estimate this used to fall back to is
        # genuinely non-zero, so a 0.0 result here is a real fix, not a vacuous check.
        self.assertGreater(result["satcom"]["link"]["aggregate_gbps"], 0.0)

    def test_integrated_calc_capacity_is_zero_not_fallback_to_link_estimate(self):
        scenario = engine.IntegratedInput()
        scenario.payload.geometry_channel_enabled = True
        scenario.payload.geometry_min_elevation_deg = 89.9
        result = engine.integrated_calc(scenario)
        self.assertEqual(result["integrated"]["effective_capacity_gbps"], 0.0)
        self.assertGreater(result["satcom"]["link"]["aggregate_gbps"], 0.0)

    def test_geometry_disabled_still_uses_synthetic_architecture_model(self):
        # When geometry_channel_enabled is False outright, the synthetic
        # architecture-level channel model is the intended, documented behavior
        # (not related to satellite visibility at all) and must be unaffected.
        p = engine.PayloadInput(geometry_channel_enabled=False, users=8)
        r = engine.payload(p)
        self.assertEqual(r["geometry"]["channel_source"], "synthetic architecture-level channel model")


if __name__ == "__main__":
    unittest.main()
