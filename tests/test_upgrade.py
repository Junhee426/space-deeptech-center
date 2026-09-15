import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from fastapi.testclient import TestClient
from core import engine
from core.version import VERSION
from orbit import walker
from simulation import batch
from app import app


class GeometryRegressionTests(unittest.TestCase):
    def test_overhead_elevation_and_below_horizon_channel(self):
        sat = np.array([[engine.R_EARTH + 1280, 0., 0.]])
        with patch.object(engine, '_region_user_grid', return_value=[[0., 0.], [0., 180.]]), \
             patch.object(engine, '_visible_satellites_np', return_value=(sat, np.array([0]), np.array([90.]), np.array([1280.]))):
            result = engine._geometry_channel_matrix(engine.PayloadInput(users=2, beams=1))
        self.assertAlmostEqual(result['user_elevation_deg'][0], 90.)
        self.assertAlmostEqual(result['user_elevation_deg'][1], -90.)
        self.assertTrue(np.any(result['H'][0]))
        self.assertTrue(np.all(result['H'][1] == 0))

    def test_no_visible_satellite_has_zero_capacity_in_both_integrated_paths(self):
        scenario = engine.IntegratedInput()
        scenario.payload.geometry_inclination_deg = 0
        scenario.payload.geometry_planes = 1
        scenario.payload.geometry_sats_per_plane = 1
        scenario.payload.geometry_min_elevation_deg = 90
        scenario.payload.analysis_mode = 'Fast'
        for calculate in (engine.api_integrated, engine.integrated_calc):
            with self.subTest(path=calculate.__name__):
                result = calculate(scenario)
                self.assertFalse(result['payload']['geometry']['visible'])
                self.assertEqual(result['payload']['traffic']['aggregate_scheduled_gbps'], 0)
                self.assertEqual(result['integrated']['effective_capacity_gbps'], 0)
                self.assertGreater(result['satcom']['link']['aggregate_gbps'], 0)
                self.assertIn('Walker', result['payload']['geometry']['channel_source'])

    def test_zero_effective_beams_has_no_synthetic_service(self):
        scenario = engine.IntegratedInput()
        scenario.beam.available_power_w = 0
        scenario.payload.geometry_channel_enabled = False
        scenario.payload.analysis_mode = 'Fast'
        result = engine.integrated_calc(scenario)
        self.assertEqual(result['integrated']['effective_beams'], 0)
        self.assertEqual(result['integrated']['effective_capacity_gbps'], 0)

    def test_integrated_paths_share_metrics(self):
        scenario = engine.IntegratedInput()
        detailed = engine.api_integrated(scenario)
        compact = engine.integrated_calc(scenario)
        for key in compact['integrated'].keys() & detailed['integrated'].keys():
            self.assertEqual(detailed['integrated'][key], compact['integrated'][key], key)

    def test_chunked_visibility_matches_full_and_bounds_arrays(self):
        times = np.arange(721) * 120.
        args = (1280, 42, 16, 8, 1, times, 20, 'Korea')
        expected = walker.regional_visibility_times(*args)['counts']
        with patch.object(walker, 'walker_positions_times', wraps=walker.walker_positions_times) as propagation:
            result = walker.regional_visibility_summary(*args)
        np.testing.assert_array_equal(result['counts'], expected)
        self.assertGreater(len(propagation.call_args_list), 1)
        for call in propagation.call_args_list:
            self.assertLessEqual(len(call.args[-1]) * 128, 65536)

    def test_outage_does_not_exceed_requested_duration(self):
        result = engine.api_coverage(engine.CoverageInput(duration_hours=1, inclination_deg=0, planes=1, sats_per_plane=1, min_elevation_deg=90))
        for row in result['regions']:
            self.assertEqual(row['longest_outage_min'], 60.)


class MonteCarloRegressionTests(unittest.TestCase):
    def test_pa_efficiency_uncertainty_changes_power_and_is_reproducible(self):
        fields = {name: 0 for name in engine.MonteCarloInput.model_fields if 'sigma' in name}
        fixed = engine.MonteCarloInput(runs=16, **fields)
        noisy = fixed.model_copy(update={'pa_eff_sigma_pct': 30})
        baseline = engine.api_montecarlo(fixed)
        varied = engine.api_montecarlo(noisy)
        repeated = engine.api_montecarlo(noisy)
        self.assertEqual(baseline['runs'], 16)
        self.assertFalse(baseline['parallel'])
        self.assertEqual(len({r['power_w'] for r in baseline['samples']}), 1)
        self.assertGreater(len({r['power_w'] for r in varied['samples']}), 1)
        self.assertNotEqual(baseline['metrics']['power_w'], varied['metrics']['power_w'])
        self.assertEqual(varied, repeated)

    def test_efficiency_reaches_link_and_payload_energy_models(self):
        high = engine.IntegratedInput()
        high.satcom.pa_efficiency_override = .8
        low = high.model_copy(deep=True)
        low.satcom.pa_efficiency_override = .02
        a, b = engine.integrated_calc(high), engine.integrated_calc(low)
        self.assertGreater(b['satcom']['device']['pa_dc_w'], a['satcom']['device']['pa_dc_w'])
        self.assertGreater(b['payload']['power']['pa_dc_w'], a['payload']['power']['pa_dc_w'])
        self.assertGreater(b['payload']['power']['heat_w'], a['payload']['power']['heat_w'])
        expected_dc = low.satcom.rf_output_w / 10 ** (low.payload.output_backoff_db / 10) / .02
        self.assertAlmostEqual(b['payload']['power']['pa_dc_w'], expected_dc, delta=.05)


class BatchRegressionTests(unittest.TestCase):
    def tearDown(self):
        batch.shutdown_pool()

    def test_real_pool_matches_serial_and_is_reused(self):
        values = list(range(-40, 0))
        serial = batch.evaluate_batch(abs, values, max_workers=1)
        parallel = batch.evaluate_batch(abs, values, max_workers=2)
        executor = batch._pool
        again = batch.evaluate_batch(abs, values, max_workers=2)
        self.assertEqual(serial.rows, parallel.rows)
        self.assertEqual(parallel.rows, again.rows)
        self.assertTrue(parallel.parallel)
        self.assertIs(executor, batch._pool)

    def test_worker_error_is_not_retried_as_serial(self):
        executor = MagicMock()
        executor.map.side_effect = ValueError('invalid calculation')
        worker = MagicMock()
        with patch.object(batch, 'ProcessPoolExecutor', return_value=executor):
            with self.assertRaisesRegex(ValueError, 'invalid calculation'):
                batch.evaluate_batch(worker, list(range(40)), max_workers=2)
        worker.assert_not_called()
        # Failure must release admission control for subsequent requests.
        self.assertEqual(batch.evaluate_batch(abs, [-1], max_workers=1).rows, [1])

    def test_pool_creation_failure_reports_serial_fallback(self):
        with patch.object(batch, 'ProcessPoolExecutor', side_effect=OSError('unavailable')), self.assertLogs('simulation.batch'):
            result = batch.evaluate_batch(abs, list(range(-40, 0)), max_workers=2)
        self.assertEqual(result.rows, list(range(40, 0, -1)))
        self.assertFalse(result.parallel)
        self.assertEqual(result.mode, 'serial-fallback')

    def test_busy_batch_returns_retryable_http_response(self):
        with TestClient(app) as client:
            batch._batch_gate.acquire()
            try:
                response = client.post('/api/montecarlo', json={'runs': 1})
            finally:
                batch._batch_gate.release()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['retry-after'], '2')


class ApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def test_home_health_and_schema(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('V' + VERSION, response.text)
        for path in ('/api/health', '/api/performance', '/api/architecture'):
            self.assertEqual(self.client.get(path).json()['version'], VERSION)
        self.assertEqual(self.client.get('/openapi.json').status_code, 200)

    def test_bad_inputs_are_422_not_server_errors(self):
        cases = [
            ('satcom', {'frequency_ghz': 0}),
            ('satcom', {'frequency_ghz': 'Infinity'}),
            ('satcom', {'altitude_km': -6371}),
            ('satcom', {'bandwidth_mhz': -1}),
            ('payload', {'geometry_planes': 0}),
            ('payload', {'users': 1000000}),
            ('payload', {'timeslots': 1000000}),
            ('payload', {'hpa_samples': 10000000}),
            ('payload', {'modulation_order': 3}),
            ('radiation', {'mission_years': 0}),
            ('radiation', {'tid_tolerance_krad': 0}),
            ('montecarlo', {'rf_output_sigma_pct': -1}),
            ('montecarlo', {'runs': 0}),
            ('montecarlo', {'runs': 5000, 'base': {'payload': {'users': 128, 'timeslots': 128}}}),
            ('optimize', {'base': {'payload': {'users': 128, 'timeslots': 128}}}),
            ('sensitivity', {'parameter': 'unknown'}),
            ('sensitivity', {'low': 0, 'parameter': 'bandwidth_mhz'}),
            ('sensitivity', {'low': 40, 'high': 10}),
            ('coverage', {'planes': 60, 'sats_per_plane': 60, 'duration_hours': 168, 'time_step_sec': 5}),
            ('pass-timeline', {'planes': 60, 'sats_per_plane': 60, 'duration_hours': 72, 'time_step_sec': 5}),
        ]
        for endpoint, data in cases:
            with self.subTest(endpoint=endpoint, data=data):
                response = self.client.post('/api/' + endpoint, json=data)
                self.assertEqual(response.status_code, 422, response.text)

    def test_default_science_endpoints(self):
        for endpoint in ('satcom', 'beamforming', 'radiation', 'payload', 'integrated', 'coverage', 'propagation', 'poisson-device', 'sensitivity', 'report-summary'):
            with self.subTest(endpoint=endpoint):
                response = self.client.post('/api/' + endpoint, json={})
                self.assertEqual(response.status_code, 200, response.text)


if __name__ == '__main__':
    unittest.main()
