import unittest
from unittest.mock import patch
from core import engine


class MissionGeometryTests(unittest.TestCase):
    def test_integrated_paths_preserve_selected_walker_geometry(self):
        scenario = engine.IntegratedInput()
        scenario.satcom.altitude_km = 888
        scenario.payload.geometry_inclination_deg = 55
        scenario.payload.geometry_planes = 4
        scenario.payload.geometry_sats_per_plane = 6
        scenario.payload.geometry_walker_f = 2
        scenario.payload.geometry_min_elevation_deg = 15
        scenario.payload.hpa_samples = 256
        real_payload = engine.payload
        for calculate in (engine.api_integrated, engine.integrated_calc):
            with self.subTest(path=calculate.__name__):
                observed = []
                def capture(payload_input):
                    observed.append(payload_input)
                    return real_payload(payload_input)
                with patch.object(engine, 'payload', side_effect=capture):
                    calculate(scenario)
                effective = observed[0]
                self.assertEqual(effective.geometry_inclination_deg, 55)
                self.assertEqual(effective.geometry_altitude_km, 888)
                self.assertEqual(effective.geometry_planes, 4)
                self.assertEqual(effective.geometry_sats_per_plane, 6)
                self.assertEqual(effective.geometry_walker_f, 2)
                self.assertEqual(effective.geometry_min_elevation_deg, 15)
                self.assertEqual(scenario.payload.geometry_inclination_deg, 55)


if __name__ == '__main__':
    unittest.main()
