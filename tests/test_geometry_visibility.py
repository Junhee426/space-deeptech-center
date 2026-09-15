import unittest
import numpy as np
from core import engine


class ElevationDirectionTests(unittest.TestCase):
    """Item 1: elevation must be measured user->satellite, not satellite->user."""

    def test_user_directly_below_satellite_is_plus_90(self):
        user_xyz = np.array([[engine.R_EARTH, 0.0, 0.0]])
        sat_xyz = np.array([engine.R_EARTH + 1280.0, 0.0, 0.0])
        elev, rng = engine._user_elevation_deg_np(sat_xyz, user_xyz)
        self.assertAlmostEqual(float(elev[0]), 90.0, places=6)
        self.assertAlmostEqual(float(rng[0]), 1280.0, places=6)

    def test_satellite_on_opposite_side_of_earth_is_minus_90(self):
        user_xyz = np.array([[-engine.R_EARTH, 0.0, 0.0]])
        sat_xyz = np.array([engine.R_EARTH + 1280.0, 0.0, 0.0])
        elev, _ = engine._user_elevation_deg_np(sat_xyz, user_xyz)
        self.assertAlmostEqual(float(elev[0]), -90.0, places=6)


class PerUserVisibilityMaskingTests(unittest.TestCase):
    """Item 1: users below the min-elevation threshold must not get channel/SINR/
    throughput derived from a satellite they cannot see, even when the region
    anchor point itself still has a visible serving satellite."""

    def test_masked_users_get_exactly_zero_throughput(self):
        # This threshold (with the default Walker geometry at t=0) is confirmed to
        # sit strictly between some users' elevations and others', so the region
        # anchor still finds a serving satellite while some individual users do not.
        p = engine.PayloadInput(
            geometry_channel_enabled=True,
            geometry_min_elevation_deg=41,
            users=8,
            geometry_user_radius_km=1500,
        )
        r = engine.payload(p)
        geo = r["geometry"]
        self.assertTrue(geo["visible"], "test fixture must keep the region anchor visible")

        elevs = geo["user_elevation_deg"]
        visible_mask = geo["user_visible"]
        throughput = r["traffic"]["user_throughput_mbps"]

        self.assertEqual(len(visible_mask), len(elevs))
        # The mask must be a direct, per-user reflection of elevation vs threshold.
        for elev, vis in zip(elevs, visible_mask):
            self.assertEqual(vis, elev >= p.geometry_min_elevation_deg)

        # Sanity: this fixture must actually exercise both branches of the mask,
        # otherwise the assertions below would pass vacuously.
        self.assertTrue(any(visible_mask), "fixture produced no visible users")
        self.assertTrue(any(not v for v in visible_mask), "fixture produced no masked users")

        for vis, mbps in zip(visible_mask, throughput):
            if not vis:
                self.assertEqual(mbps, 0.0)

    def test_no_satellite_visible_anywhere_gives_all_zero_throughput_and_elevations(self):
        p = engine.PayloadInput(
            geometry_channel_enabled=True,
            geometry_min_elevation_deg=89.9,
            users=6,
        )
        r = engine.payload(p)
        geo = r["geometry"]
        self.assertFalse(geo["visible"])
        self.assertTrue(all(v == -90.0 for v in geo["user_elevation_deg"]))
        self.assertTrue(all(v is False for v in geo["user_visible"]))


if __name__ == "__main__":
    unittest.main()
