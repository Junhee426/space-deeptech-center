import numpy as np
from concurrent.futures import ProcessPoolExecutor
import contextlib
import os
import threading

# Hard cap on worker processes for any single parallel_map call, regardless of
# how many CPUs the host reports -- an unbounded pool sized off a large
# container's CPU count can itself become a resource problem under concurrent
# requests.
MAX_WORKER_PROCESSES = 8

# Service-wide cap on how many heavy jobs (optimizer/Monte Carlo/coverage
# batches) may run at once. This is a simple in-process semaphore: it bounds
# concurrent load on this worker, not a distributed limit across replicas.
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "4"))
_job_semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)

class TooManyConcurrentJobsError(RuntimeError):
    """Raised when MAX_CONCURRENT_JOBS heavy jobs are already running service-wide."""

@contextlib.contextmanager
def job_slot():
    """
    Acquire one of MAX_CONCURRENT_JOBS service-wide slots for a heavy
    computation (optimizer/Monte Carlo/coverage). Raises TooManyConcurrentJobsError
    immediately (non-blocking) rather than queuing requests indefinitely behind
    an already-saturated worker pool.
    """
    acquired=_job_semaphore.acquire(blocking=False)
    if not acquired:
        raise TooManyConcurrentJobsError(
            f"Too many concurrent heavy computation jobs are already running "
            f"(limit={MAX_CONCURRENT_JOBS}). Please retry shortly."
        )
    try:
        yield
    finally:
        _job_semaphore.release()

def batched_design_grid(materials,processors,altitudes,beams,rf,elems,bw):
    mesh=np.array(np.meshgrid(
        np.arange(len(materials)),np.arange(len(processors)),altitudes,beams,rf,elems,bw,indexing="ij"
    ),dtype=object)
    rows=mesh.reshape(7,-1).T
    return [{
      "material":materials[int(r[0])],"processor":processors[int(r[1])],
      "altitude_km":float(r[2]),"beams":int(r[3]),"rf_output_w":float(r[4]),
      "elements":int(r[5]),"bandwidth_mhz":float(r[6])
    } for r in rows]

def parallel_map(func,items,max_workers=None,chunksize=16):
    if not items:return []
    workers=max_workers or max(1,min(MAX_WORKER_PROCESSES,(os.cpu_count() or 2)-1))
    if workers<=1 or len(items)<32:
        return [func(x) for x in items]
    try:
        ex=ProcessPoolExecutor(max_workers=workers)
    except Exception:
        # Process creation itself is unavailable in this deployment environment
        # (e.g. a sandboxed container with no permission to fork/spawn) -- serial
        # evaluation is the correct, intentional fallback here (see README/
        # BENCHMARK.md: "automatically fall back to serial evaluation if process
        # creation is unavailable"). This is the ONLY case that falls back.
        return [func(x) for x in items]
    try:
        with ex:
            return list(ex.map(func,items,chunksize=chunksize))
    except Exception:
        # A failure *raised by func() for one of the items* (or a worker crashing
        # mid-batch) must NOT silently re-run the entire job serially from
        # scratch: that doubles the compute cost, and if the failure is
        # deterministic (bad input) it fails again anyway while hiding the
        # original error behind a second, confusing traceback. Propagate the
        # real error instead so the caller can see what actually went wrong.
        raise

def monte_carlo_draws(rng,runs,means,sigmas):
    """Vectorized independent normal draws keyed by variable name."""
    return {k:np.maximum(0,rng.normal(means[k],sigmas[k],runs)) for k in means}
