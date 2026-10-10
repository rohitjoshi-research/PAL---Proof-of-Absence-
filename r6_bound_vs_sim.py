"""R6: validate the miss bound against the RAY-TRACED simulator (not its own formula).
Genuine claims only, no traffic, no occluder, no faults; per scene: did every sample in W look free
(the event the bound bounds), and what bound did the method compute for that scene (worst-case weather, v2.3)."""
import sys, os, json, csv
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, sim, method, run_phase7 as p7
from multiprocessing import Pool
CONDS = {"matched": {}, "rcs-6": {"rcs_offset_db": -6.0}, "rcs-9": {"rcs_offset_db": -9.0},
         "fade6": {"fade_persist_sigma_db": 6.0}, "rcs-6-fade6": {"rcs_offset_db": -6.0, "fade_persist_sigma_db": 6.0}}
BASE = {"traffic_max": 0, "p_blocked": 0.0, "p_misalign": 0.0, "ghost_rate": 0.0}
CFG = method.Config("probe", liveness=True, k_support=3, gate=1.0, weather_worst=True, strict_free=True,
                    window_cover=True, eps=1.0)   # eps=1: returns the bound whenever all samples are free

def bound_any(meas, claim):
    """Bound value for the scene's geometry regardless of whether samples were free (same ranges/ncovs as pal_verdict)."""
    stream = method.ENRICHED if meas["diag"]["violation_detected"] else method.BASE
    rec = method.build_record(meas, stream, True, True)
    res, n_sec = rec["res"], rec["n_sec"]
    t0 = claim["t_event"] - claim["t_tol"] - method.CLOCK_BOUND; t1 = claim["t_event"] + claim["t_tol"] + method.CLOCK_BOUND
    ranges, ncovs = [], []
    for smp in rec["samples"]:
        if not (t0 <= smp["t"] <= t1): continue
        z = method.Zone(claim, smp["log"], "road"); px, py = z.points_ego(); rr = np.hypot(px, py)
        sec = ((np.degrees(np.arctan2(py, px)) + 180.0) // res).astype(int) % n_sec
        ranges.append(float(rr.max())); ncovs.append(max(1, int(min(smp["ncov"][s] for s in np.unique(sec)))))
    w = max(method.NOMINAL["weather_loss_db"], key=method.NOMINAL["weather_loss_db"].get)
    return method.miss_bound(claim["cls"], ranges, ncovs, w)

def job(a):
    tag, i = a
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM))); sim.PARAMS.update(BASE); sim.PARAMS.update(CONDS[tag])
    rng = np.random.default_rng(14_000_000 + i)
    sc = sim.make_scene(rng, {"genuine": True, "occluder": False, "n_traffic": 0, "weather": "rain"})
    m = sim.simulate(sc, rng)
    v, _ = method.pal_verdict(m, sc.claim, sc.weather, CFG)
    return {"cond": tag, "scene": i, "cls": sc.claim["cls"], "genuine": sc.truth["genuine"],
            "all_free": v == "REFUTED", "bound": bound_any(m, sc.claim)}

if __name__ == "__main__":
    N = int(sys.argv[1]); out = []
    with Pool(2) as p:
        for tag in CONDS:
            out += p.map(job, [(tag, i) for i in range(N)], chunksize=20)
    with open(os.path.join(HERE, "r6_bound_vs_sim.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print("done", len(out))
