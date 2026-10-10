"""Owner attacks: dishonest-owner attacks on genuine claims (seeds 13,000,000 + i, same seeds per attack).
A0 no attack; A1 sub-threshold misalignment (1.0-1.9 deg, every scene); A2 silent blockage of a rear radar
(flag never set) on an empty road; A3 silent blockage in normal traffic."""
import sys, os, json, csv
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, sim, method, run_phase7 as p7
from multiprocessing import Pool
NOLIVE = [c for c in method.ABLATIONS_V23 if c.name == "v2.3 no liveness"][0]
ATT = {"A0-none": {}, "A1-misalign-subthreshold": {"p_misalign": 1.0, "misalign_range_deg": [1.0, 1.9]},
       "A2-silent-block-empty-road": {"p_blocked": 1.0, "blocked_recall": 0.0, "traffic_max": 0},
       "A3-silent-block-traffic": {"p_blocked": 1.0, "blocked_recall": 0.0}}
def job(a):
    tag, i = a
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM))); sim.PARAMS.update(ATT[tag])
    rng = np.random.default_rng(13_000_000 + i); sc = sim.make_scene(rng); m = sim.simulate(sc, rng)
    row = {"attack": tag, "scene": i, "genuine": sc.truth["genuine"], "empty": sc.truth["empty"], "cls": str(sc.claim["cls"]),
           "blocked_same_side": bool(sc.blocked) and ((sc.blocked == "rear_left") == (sc.lc_dir > 0)),
           "misalign_deg": json.dumps(sc.misalign)}
    row["PAL v2.3"] = method.pal_verdict(m, sc.claim, sc.weather, method.PAL_V23)[0]
    row["PAL v2.3 no liveness"] = method.pal_verdict(m, sc.claim, sc.weather, NOLIVE)[0]
    row["Rule k3"] = method.objlist_strict(m, sc.claim, no_moto=True)
    row["ObjList-best v2.1 no liveness"] = method.objlist_verdict(m, sc.claim, k_support=3, liveness=False, gate=1.0)   # persistence-only baseline without liveness
    row["ObjList-best v2.1"] = method.objlist_verdict(m, sc.claim, k_support=3, liveness=True, gate=1.0)
    return row
if __name__ == "__main__":
    N = int(sys.argv[1]); out = []
    with Pool(2) as p:
        for tag in ATT: out += p.map(job, [(tag, i) for i in range(N)], chunksize=20)
    with open(os.path.join(HERE, "r9_attacks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print("done", len(out))
