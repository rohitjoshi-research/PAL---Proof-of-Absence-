"""Curved-road diagnosis: why the formal tier without the bound is INCONCLUSIVE in the 8 scenes of the ideal-sensor
check (seed 42, 300 scenes) where the zone is visible and empty. Writes batch3/r19_result.json (about 1 min).
Usage: python3 batch3/r19_curves.py"""
import sys, os, copy, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, sim, method
ORIG = copy.deepcopy(sim.PARAMS)
sim.PARAMS.update({"snr0_db": 60.0, "fade_persist_sigma_db": 0.0, "fade_sample_sigma_db": 0.0, "ghost_rate": 0.0})
TARGET = {121, 144, 145, 158, 228, 232, 244, 253}   # disagreements of the ideal-sensor check with geometric visibility
NOB = method.Config("geometry check", bound=False, liveness=True, k_support=3, gate=1.0)
rng = np.random.default_rng(42); causes = {}   # seed 42 = the ideal-sensor check (V2); TARGET = its 8 disagreement scenes
for i in range(300):
    sc = sim.make_scene(rng, {"blocked": None, "misalign": {}, "clock_offset": 0.0}); m = sim.simulate(sc, rng)
    if i not in TARGET: continue
    stream = method.ENRICHED if m["diag"]["violation_detected"] else method.BASE
    rec = method.build_record(m, stream, True, True); res, n_sec = rec["res"], rec["n_sec"]
    why = []
    for smp in rec["samples"]:
        if abs(smp["t"]) > 1.3: continue
        z = method.Zone(sc.claim, smp["log"], "road"); px, py = z.points_ego(); rr = np.hypot(px, py)
        sec = ((np.degrees(np.arctan2(py, px)) + 180.0) // res).astype(int) % n_sec
        for s in np.unique(sec):
            rmax = float(rr[sec == s].max())
            if smp["ncov"][s] == 0: why.append("no coverage")
            elif smp["d_free"][s] + 0.5 < rmax:
                why.append("hit outside zone shortens the sector (hit %s)" % ("yes" if smp["hit"][s] else "no-FOV-edge"))
    v, _ = method.pal_verdict(m, sc.claim, sc.weather, NOB)
    causes[i] = {"verdict": v, "kappa": sc.road.kappa, "reasons": dict(Counter(why))}
sim.PARAMS.clear(); sim.PARAMS.update(ORIG)   # restore the nominal parameters
json.dump(causes, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "r19_result.json"), "w"), indent=1, default=float)
print(json.dumps(causes, indent=1, default=float))
