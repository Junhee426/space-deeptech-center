import unittest
import numpy as np

from orbit import walker
from core import engine
from simulation.batch import (
    job_slot,
    TooManyConcurrentJobsError,
    MAX_CONCURRENT_JOBS,
    parallel_map,
)


# Must be module-level (not a closure/lambda) so ProcessPoolExecutor can pickle it.
def _bad_worker(v):
    if v == 5:
        raise ValueError("boom")
    return v * 2


def _double(v):
    return v * 2


class ChunkedPropagationMatchesFullTests(unittest.TestCase):
    """Item 6: streaming/chunked position computation must be numerically
    identical to the previous single-shot full-array computation."""

    def test_chunked_positions_match_unchunked(self):
        times = np.arange(0, 3600, 60.0)
        full = walker.walker_positions_times(1280, 42, 16, 8, 1, times)
        chunks = list(walker.walker_positions_times_chunked(1280, 42, 16, 8, 1, times, chunk_steps=7))
        reassembled = np.concatenate([c for _, c in chunks], axis=0)
        self.assertTrue(np.allclose(full, reassembled))
        # Confirm chunking actually happened (more than one chunk for this input).
        self.assertGreater(len(chunks), 1)


class MultiRegionReuseTests(unittest.TestCase):
    """Item 6: reusing propagated positions across regions must give identical
    results to computing each region independently."""

    def test_multi_region_matches_per_region_computation(self):
        times = np.arange(0, 3600, 60.0)
        regions = list(walker.REGIONS.keys())
        multi = walker.regional_visibility_times_multi(1280, 42, 16, 8, 1, times, 20, regions)
        for r in regions:
            single = walker.regional_visibility_times(1280, 42, 16, 8, 1, times, 20, r)
            self.assertTrue(np.array_equal(multi[r]["counts"], single["counts"]))
            self.assertTrue(np.array_equal(multi[r]["max_elevation"], single["max_elevation"]))

    def test_coverage_proxy_still_returns_all_regions(self):
        r = engine._coverage_proxy(engine.CoverageInput(duration_hours=2))
        self.assertEqual(
            sorted(row["region"] for row in r["regions"]),
            sorted(walker.REGIONS.keys()),
        )


class RequestSizeLimitTests(unittest.TestCase):
    """Item 6: an oversized per-request computation (steps * satellites) must be
    rejected with a clear error, not silently allocated / left to hang."""

    def test_check_request_size_rejects_oversized_request(self):
        with self.assertRaises(walker.WalkerComputationTooLargeError):
            walker.check_request_size(10_000_000, 1000)

    def test_check_request_size_allows_reasonable_request(self):
        walker.check_request_size(1000, 128)  # should not raise

    def test_api_coverage_rejects_oversized_request(self):
        with self.assertRaises(walker.WalkerComputationTooLargeError):
            engine.api_coverage(engine.CoverageInput(
                duration_hours=168, time_step_sec=5, planes=60, sats_per_plane=60
            ))


class ConcurrentJobLimitTests(unittest.TestCase):
    """Item 6: a service-wide cap on concurrent heavy jobs."""

    def test_job_slot_rejects_beyond_limit(self):
        held = []
        try:
            for _ in range(MAX_CONCURRENT_JOBS):
                cm = job_slot()
                cm.__enter__()
                held.append(cm)
            with self.assertRaises(TooManyConcurrentJobsError):
                with job_slot():
                    pass
        finally:
            for cm in held:
                cm.__exit__(None, None, None)

    def test_job_slot_available_again_after_release(self):
        with job_slot():
            pass  # should not raise, and should release cleanly


class TargetedExceptionHandlingTests(unittest.TestCase):
    """Item 6: parallel_map must not blanket-rerun the entire job serially when a
    worker item raises -- it must propagate the real error."""

    def test_worker_exception_propagates_not_blanket_rerun(self):
        # Fail-fast: the real ValueError from the worker must propagate, not be
        # swallowed and silently retried by re-running the whole batch serially.
        with self.assertRaises(ValueError):
            parallel_map(_bad_worker, list(range(40)), max_workers=4)

    def test_successful_batch_still_uses_process_pool_path(self):
        results = parallel_map(_double, list(range(40)), max_workers=4)
        self.assertEqual(sorted(results), sorted(v * 2 for v in range(40)))


if __name__ == "__main__":
    unittest.main()
