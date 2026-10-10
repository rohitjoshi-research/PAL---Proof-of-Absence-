"""
Phase 7 experiments. One seed per scene; every sweep condition uses the SAME seeds, so
conditions are paired as well as methods. Output: results7/<condition>.csv + params.
Usage: python3 run_phase7.py [main|sweeps|params|all] [workers]
"""
import csv
import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim
import method

OUT = os.path.join(HERE, "results7")
os.makedirs(OUT, exist_ok=True)
NOMINAL_SIM = json.loads(json.dumps(sim.PARAMS))

MAIN = ("main", {}, 6000, 7_000_000)
SWEEPS = [
    ("rcs-3", {"rcs_offset_db": -3.0}),
    ("rcs-6", {"rcs_offset_db": -6.0}),
    ("rcs-9", {"rcs_offset_db": -9.0}),
    ("fade6", {"fade_persist_sigma_db": 6.0}),
    ("fade8", {"fade_persist_sigma_db": 8.0}),
    ("ghost0.1", {"ghost_rate": 0.1}),
    ("ghost0.3", {"ghost_rate": 0.3}),
    ("blockage", {"p_blocked": 0.3, "blocked_recall": 0.5}),
    ("misalign", {"p_misalign": 0.3, "calib_noise_deg": 2.0}),
    ("clock0.3", {"clock_sigma_s": 0.3}),
    ("pose-noise", {"pose_noise_l_m": 0.3, "pose_noise_psi_deg": 1.0}),
    ("dense", {"traffic_max": 12}),
    ("degraded", {"rcs_offset_db": -6.0, "fade_persist_sigma_db": 6.0, "p_blocked": 0.3,
                  "blocked_recall": 0.5}),
]
SWEEP_N, SWEEP_SEED = 1000, 8_000_000
PARAM_CONFIGS = [
    method.Config("eps 1e-2", eps=1e-2), method.Config("eps 1e-4", eps=1e-4),
    method.Config("inset 0.15", inset=0.15), method.Config("inset 0.5", inset=0.5),
    method.Config("gate 1.0", gate=1.0), method.Config("gate 3.0", gate=3.0),
]
METHODS = [method.PAL_FULL, *method.ABLATIONS, method.PAL_V1]


def job(args):
    i, seed0, override, extra = args
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(NOMINAL_SIM))); sim.PARAMS.update(override)
    rng = np.random.default_rng(seed0 + i)
    sc = sim.make_scene(rng)
    meas = sim.simulate(sc, rng)
    row = {"scene": i, "genuine": sc.truth["genuine"], "empty": sc.truth["empty"],
           "claim_cls": str(sc.claim["cls"]), "curved": sc.road.kappa != 0.0,
           "weather": sc.weather, "time_of_day": sc.time_of_day, "n_actors": len(sc.actors),
           "blocked": sc.blocked or "", "blocked_flagged": any(meas["diag"]["blocked_flag"].values()),
           "misaligned": bool(sc.misalign), "violation_detected": meas["diag"]["violation_detected"]}
    for cfg in METHODS + (PARAM_CONFIGS if extra else []):
        v, b = method.pal_verdict(meas, sc.claim, sc.weather, cfg)
        row[cfg.name] = v
        if cfg is method.PAL_FULL:
            row["PAL-full bound"] = "" if b is None else f"{b:.3e}"
    row["ObjList-best"] = method.objlist_verdict(meas, sc.claim)
    return row


def run(tag, override, n, seed0, workers, extra=False):
    t = time.time()
    with Pool(workers) as p:
        rows = p.map(job, [(i, seed0, override, extra) for i in range(n)], chunksize=10)
    with open(os.path.join(OUT, f"{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    meta = {"tag": tag, "N": n, "seed0": seed0, "override": override,
            "sim_params": {**NOMINAL_SIM, **override}, "runtime_s": round(time.time() - t, 1),
            "method_params": {"nominal": method.NOMINAL, "eps": method.EPS, "inset": method.SUPPORT_INSET,
                              "inset_long": method.SUPPORT_INSET_LONG, "gate": method.TRACK_GATE,
                              "calib_limit_deg": method.CALIB_LIMIT_DEG, "clock_bound_s": method.CLOCK_BOUND}}
    with open(os.path.join(OUT, f"{tag}.meta.json"), "w") as f:
        json.dump(meta, f, indent=2, default=float)
    print(tag, n, "scenes", meta["runtime_s"], "s", flush=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if what in ("params", "all"):
        run("params", {}, 1000, 9_000_000, W, extra=True)
    if what in ("main", "all"):
        run(MAIN[0], MAIN[1], MAIN[2], MAIN[3], W)
    if what in ("sweeps", "all"):
        run("nominal-1000", {}, SWEEP_N, SWEEP_SEED, W)
        for tag, ov in SWEEPS:
            run(tag, ov, SWEEP_N, SWEEP_SEED, W)
    open(os.path.join(OUT, f"DONE-{what}"), "w").write("ok")
