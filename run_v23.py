"""Phase 11 batch 2. v2.3 = v2.2 + window-end check tolerant of the clock bound.
Modes: prereg (generalisation test G1-G4, frozen), main, confirm, sweeps, boundary. Output: results73/.
Each row stores verdicts plus the formal tier's bound value (for the epsilon sweep) and rule-tier variants (k sweep)."""
import csv, json, os, sys, time
from multiprocessing import Pool
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sim, method, run_phase7 as p7
OUT = os.path.join(HERE, "results73"); os.makedirs(OUT, exist_ok=True)
FULL = [method.PAL_V23, method.PAL_V23_CONS, *method.ABLATIONS_V23, method.PAL_V1]
G = [("G1-rcs-12", {"rcs_offset_db": -12.0}),
     ("G2-rcs-3-fade8", {"rcs_offset_db": -3.0, "fade_persist_sigma_db": 8.0}),
     ("G3-highspeed", {"ego_speed_range": [27.8, 36.1]}),
     ("G4-rain-dense", {"weather_probs": [0.0, 1.0, 0.0], "traffic_max": 12})]
CONFIRM = [("confirm-rcs-9", {"rcs_offset_db": -9.0}),
           ("confirm-degraded", {"rcs_offset_db": -6.0, "fade_persist_sigma_db": 6.0, "p_blocked": 0.3, "blocked_recall": 0.5})]

def job(args):
    i, seed0, ov, full = args
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM))); sim.PARAMS.update(ov)
    rng = np.random.default_rng(seed0 + i); sc = sim.make_scene(rng); meas = sim.simulate(sc, rng)
    row = {"scene": i, "genuine": sc.truth["genuine"], "empty": sc.truth["empty"], "claim_cls": str(sc.claim["cls"]),
           "curved": sc.road.kappa != 0.0, "weather": sc.weather, "n_actors": len(sc.actors),
           "gap_max": round(sc.claim["gap_max"], 2), "violation_detected": bool(meas["diag"]["violation_detected"])}
    v, b = method.pal_verdict(meas, sc.claim, sc.weather, method.PAL_V23)
    row["PAL v2.3"] = v; row["PAL v2.3 bound"] = "" if b is None else f"{b:.3e}"
    for c in (FULL[1:] if full else []):
        row[c.name] = method.pal_verdict(meas, sc.claim, sc.weather, c)[0]
    for k in (2, 3, 4, 5, 6):
        row[f"Rule k{k}"] = method.objlist_strict(meas, sc.claim, no_moto=True, k_support=k)
    row["Rule k3 no-moto-rule"] = method.objlist_strict(meas, sc.claim, no_moto=False, k_support=3)
    row["ObjList-best v2.1"] = method.objlist_verdict(meas, sc.claim, k_support=3, liveness=True, gate=1.0)
    return row

def run(tag, ov, n, seed0, full):
    t = time.time()
    with Pool(2) as p: rows = p.map(job, [(i, seed0, ov, full) for i in range(n)], chunksize=10)
    with open(os.path.join(OUT, f"{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump({"tag": tag, "N": n, "seed0": seed0, "override": ov}, open(os.path.join(OUT, f"{tag}.meta.json"), "w"), indent=2)
    print(tag, n, round(time.time() - t, 1), "s", flush=True)

if __name__ == "__main__":
    what = sys.argv[1]; n_override = int(sys.argv[2]) if len(sys.argv) > 2 else None
    if what == "prereg":
        for tag, ov in G: run(tag, ov, n_override or 10000, 11_000_000, False)
    if what == "boundary": run("boundary-far-edge", {"genuine_gap_mode": "far_edge"}, n_override or 2000, 12_000_000, True)
    if what == "main": run("main", {}, 6000, 7_000_000, True)
    if what == "confirm":
        for tag, ov in CONFIRM: run(tag, ov, 10000, 10_000_000, True)
    if what == "sweeps":
        run("nominal-1000", {}, 1000, 8_000_000, True)
        for tag, ov in p7.SWEEPS: run(tag, ov, 1000, 8_000_000, True)
    if what == "clockcheck": run("clockcheck-clock0.3", {"clock_sigma_s": 0.3}, n_override or 300, 8_000_000, False)
    open(os.path.join(OUT, f"DONE-{what}"), "w").write("ok")
