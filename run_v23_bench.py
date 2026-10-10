"""Stress sets (exploratory): returns -9 dB and the combined condition, 10,000 scenes each (seeds 10,000,000 + i).
Writes results73/confirm-rcs-9.csv and results73/confirm-degraded.csv (+ .meta.json) with a reduced method list
(formal tier, conservative-model tier, formal tier without the bound, early prototype, rule tiers, persistence-only
baseline). These are the shipped stress-set files; `run_v23.py confirm` would write the same files with the full
method list instead. Usage: python3 run_v23_bench.py confirm [N]   (OVERWRITES the two files; run in a copy)."""
import sys, os, json, csv, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, sim, method, run_phase7 as p7, run_v23 as r
from multiprocessing import Pool
NOB = [c for c in method.ABLATIONS_V23 if c.name == "v2.3 no bound"][0]


def light(a):
    i, seed0, ov = a
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM))); sim.PARAMS.update(ov)
    rng = np.random.default_rng(seed0 + i); sc = sim.make_scene(rng); m = sim.simulate(sc, rng)
    row = {"scene": i, "genuine": sc.truth["genuine"], "empty": sc.truth["empty"], "claim_cls": str(sc.claim["cls"]),
           "curved": sc.road.kappa != 0.0, "weather": sc.weather, "n_actors": len(sc.actors),
           "gap_max": round(sc.claim["gap_max"], 2), "violation_detected": bool(m["diag"]["violation_detected"])}
    v, b = method.pal_verdict(m, sc.claim, sc.weather, method.PAL_V23)
    row["PAL v2.3"] = v; row["PAL v2.3 bound"] = "" if b is None else f"{b:.3e}"
    for c in (method.PAL_V23_CONS, NOB, method.PAL_V1):
        row[c.name] = method.pal_verdict(m, sc.claim, sc.weather, c)[0]
    row["Rule k3"] = method.objlist_strict(m, sc.claim, no_moto=True)
    row["Rule k3 no-moto-rule"] = method.objlist_strict(m, sc.claim, no_moto=False)
    row["ObjList-best v2.1"] = method.objlist_verdict(m, sc.claim, k_support=3, liveness=True, gate=1.0)
    return row


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "confirm":
        raise SystemExit(__doc__)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    for tag, ov in r.CONFIRM:
        t = time.time()
        with Pool(2) as p:
            rows = p.map(light, [(i, 10_000_000, ov) for i in range(n)], chunksize=10)
        path = os.path.join(r.OUT, f"{tag}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        with open(os.path.join(r.OUT, f"{tag}.meta.json"), "w") as f:
            json.dump({"tag": tag, "N": n, "seed0": 10_000_000, "override": ov, "runner": "run_v23_bench.py confirm"}, f, indent=2)
        print("wrote", path, round(time.time() - t), "s", flush=True)
