import numpy as np
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import os

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
    workers=max_workers or max(1,min(8,(os.cpu_count() or 2)-1))
    if workers<=1 or len(items)<32:
        return [func(x) for x in items]
    # Fall back to serial only when the process pool itself is unusable (can't spawn
    # processes in this deployment, or a worker crashed outright). A genuine exception
    # raised by func() on a specific item is a real bug and should propagate immediately
    # instead of silently re-running the whole batch serially just to hit it again.
    try:
        ex=ProcessPoolExecutor(max_workers=workers)
    except OSError:
        return [func(x) for x in items]
    try:
        with ex:
            return list(ex.map(func,items,chunksize=chunksize))
    except BrokenProcessPool:
        return [func(x) for x in items]

def monte_carlo_draws(rng,runs,means,sigmas):
    """Vectorized independent normal draws keyed by variable name."""
    return {k:np.maximum(0,rng.normal(means[k],sigmas[k],runs)) for k in means}
