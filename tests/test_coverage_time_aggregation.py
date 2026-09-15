import unittest
import numpy as np
from core import engine


class LongestOutageDurationTests(unittest.TestCase):
    """Item 3: outage duration must be the actual elapsed interval between the
    first and last bad sample, not (sample count) * step, which credits the
    terminal sample an extra full step-width it shouldn't get."""

    def test_outage_ending_60_minutes_before_window_end_is_exactly_60_minutes(self):
        step_s = 60.0  # 1-minute samples
        n = 200
        times = np.arange(n) * step_s  # window end at index n-1 = 199 min

        window_end_min = (n - 1) * step_s / 60.0
        gap_after_outage_min = 60
        outage_duration_min = 60

        end_idx = int(round((window_end_min - gap_after_outage_min) * 60.0 / step_s))
        start_idx = end_idx - outage_duration_min

        ok = np.ones(n, dtype=bool)
        ok[start_idx:end_idx + 1] = False  # inclusive run of outage_duration_min+1 samples

        duration_s = engine._longest_outage_duration_s(times, ok)
        self.assertEqual(duration_s / 60.0, 60.0)
        self.assertNotEqual(duration_s / 60.0, 61.0)  # the old (sample_count * step) bug

    def test_no_outage_is_zero(self):
        times = np.linspace(0, 3600, 61)
        ok = np.ones(61, dtype=bool)
        self.assertEqual(engine._longest_outage_duration_s(times, ok), 0.0)

    def test_single_sample_outage_is_zero_elapsed(self):
        # A single bad sample has no elapsed interval between "first" and "last"
        # bad instant -- it is a single point in time, not a step-width outage.
        times = np.linspace(0, 600, 11)  # step = 60s
        ok = np.ones(11, dtype=bool)
        ok[5] = False
        self.assertEqual(engine._longest_outage_duration_s(times, ok), 0.0)

    def test_picks_the_longest_of_multiple_runs(self):
        times = np.arange(20) * 10.0
        ok = np.ones(20, dtype=bool)
        ok[2:4] = False    # 2 samples -> 10s elapsed
        ok[10:17] = False  # 7 samples -> 60s elapsed
        self.assertEqual(engine._longest_outage_duration_s(times, ok), 60.0)


class RespectRequestedWindowTests(unittest.TestCase):
    """Item 3: when the time step is larger than the requested analysis duration,
    the analyzed window must not be silently extended past what was requested."""

    def test_pass_timeline_never_samples_past_requested_duration(self):
        p = engine.PassTimelineInput(duration_hours=0.01, time_step_sec=900)
        r = engine.api_pass_timeline(p)
        requested_end_min = p.duration_hours * 60.0
        last_time_min = max(row["time_min"] for row in r["rows"])
        self.assertLessEqual(last_time_min, requested_end_min + 1e-9)

    def test_pass_timeline_last_sample_hits_requested_end_exactly(self):
        p = engine.PassTimelineInput(duration_hours=0.01, time_step_sec=900)
        r = engine.api_pass_timeline(p)
        requested_end_min = round(p.duration_hours * 60.0, 3)
        last_time_min = max(row["time_min"] for row in r["rows"])
        self.assertAlmostEqual(last_time_min, requested_end_min, places=3)

    def test_coverage_proxy_does_not_crash_when_step_exceeds_duration(self):
        c = engine.CoverageInput(duration_hours=0.01, time_step_sec=1800)
        r = engine._coverage_proxy(c)
        self.assertEqual(len(r["regions"]), 3)
        for row in r["regions"]:
            self.assertGreaterEqual(row["availability_pct"], 0.0)
            self.assertLessEqual(row["availability_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
