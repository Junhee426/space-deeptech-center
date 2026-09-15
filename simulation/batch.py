import numpy as np
from concurrent.futures import ProcessPoolExecutor
import os
import atexit
import logging
import multiprocessing
import threading
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

logger = logging.getLogger(__name__)
_batch_gate = threading.Lock()
_pool = None
_pool_workers = None


class BatchBusyError(RuntimeError):
    """Another batch is already consuming this server's compute budget."""


@dataclass
class BatchResult:
    rows: list
    parallel: bool
    mode: str


def shutdown_pool():
    global _pool, _pool_workers
    if _pool is not None:
        _pool.shutdown(wait=True, cancel_futures=True)
        _pool = None
        _pool_workers = None


atexit.register(shutdown_pool)

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

def evaluate_batch(func, items, max_workers=None, chunksize=16):
    """Reuse a bounded pool; reject concurrent batches and propagate calculation errors."""
    global _pool, _pool_workers
    if not items:
        return BatchResult([], False, "serial")
    workers = max_workers if max_workers is not None else int(os.environ.get("SDTC_MAX_WORKERS", "2"))
    workers = max(1, min(8, workers, os.cpu_count() or 1))
    if not _batch_gate.acquire(blocking=False):
        raise BatchBusyError("A simulation is already running. Retry shortly.")
    try:
        if workers == 1 or len(items) < 32:
            return BatchResult([func(x) for x in items], False, "serial")
        if _pool is None or _pool_workers != workers:
            shutdown_pool()
            try:
                # Spawn avoids forking the threaded API server and works on Windows.
                _pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"))
                _pool_workers = workers
            except (OSError, NotImplementedError):
                logger.warning("Process pool unavailable; using serial evaluation", exc_info=True)
                return BatchResult([func(x) for x in items], False, "serial-fallback")
        try:
            return BatchResult(list(_pool.map(func, items, chunksize=chunksize)), True, "process-pool")
        except BrokenProcessPool:
            logger.warning("Process pool failed; using serial evaluation", exc_info=True)
            shutdown_pool()
            return BatchResult([func(x) for x in items], False, "serial-fallback")
    finally:
        _batch_gate.release()


def parallel_map(func, items, max_workers=None, chunksize=16):
    """Compatibility wrapper for callers that only need result rows."""
    return evaluate_batch(func, items, max_workers, chunksize).rows


def monte_carlo_draws(rng,runs,means,sigmas):
    """Vectorized independent normal draws keyed by variable name."""
    return {k:np.maximum(0,rng.normal(means[k],sigmas[k],runs)) for k in means}
