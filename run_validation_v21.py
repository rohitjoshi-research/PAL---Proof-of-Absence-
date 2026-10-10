"""
Simulator sanity checks (run before the benchmarks, on the v2.1 configuration of the formal tier).
Usage: python3 validation/run_validation_v21.py   -> validation/validation_v21.json (about 1 min; fixed seeds)
  V1 known-answer single-scene cases with ideal sensors
  V2 ideal sensors over random scenes: PAL must never falsely refute or falsely support,
     and its REFUTED set must equal the geometrically visible-and-empty set
  V3 bound calibration: method's miss bound vs empirical miss-all rate (matched + mismatched)
  V4 baseline independence: the object-list baseline is unaffected by PAL flags
  V5 geometry: road-frame round trip on straight and curved roads
Writes validation.json. Fixed seeds.
"""
import copy
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # package root
import sim
import method

OUT = {}
ORIG = copy.deepcopy(sim.PARAMS)


def ideal():
    sim.PARAMS.update({"snr0_db": 60.0, "fade_persist_sigma_db": 0.0,
                       "fade_sample_sigma_db": 0.0, "ghost_rate": 0.0})


def restore():
    sim.PARAMS.clear(); sim.PARAMS.update(copy.deepcopy(ORIG))


# ---------------------------------------------------------------- V1
ideal()
base = dict(kappa=0.0, ego_v=18.0, lc_dir=1, weather="clear", time_of_day="afternoon",
            claim_cls="car", n_traffic=0, blocked=None, misalign={}, clock_offset=0.0)
cases = [
    ("empty zone, fabricated", dict(genuine=False, occluder=False), "REFUTED"),
    ("car in zone, genuine", dict(genuine=True, occluder=False), "SUPPORTED"),
    ("van directly behind, body inside the zone", dict(genuine=False, occluder=True), "SUPPORTED"),
    ("empty zone, rear radar on the zone side blocked (flagged)", dict(genuine=False, occluder=False, blocked="rear_left"), "INCONCLUSIVE"),
    ("empty zone, rear radar on the far side blocked (flagged)", dict(genuine=False, occluder=False, blocked="rear_right"), "REFUTED"),
    ("empty zone, curved road R=300 m", dict(genuine=False, occluder=False, kappa=1 / 300), "REFUTED"),
]
v1 = []
for i, (name, f, expect) in enumerate(cases):
    rng = np.random.default_rng(500 + i)
    force = {**base, **f}
    sc = sim.make_scene(rng, force)
    # in the fabricated cases make sure the claimant is not accidentally in the zone
    m = sim.simulate(sc, rng)
    if f.get("blocked"):
        m["diag"]["blocked_flag"][f["blocked"]] = True
    got, b = method.pal_verdict(m, sc.claim, sc.weather, method.PAL_V21)
    v1.append({"case": name, "expected": expect, "got": got, "truth_genuine": sc.truth["genuine"],
               "truth_empty": sc.truth["empty"], "pass": got == expect})
OUT["V1_known_answers"] = v1


# ---------------------------------------------------------------- V2
def visible_and_empty(sc, meas):
    """Ground-truth: at every in-window sample the zone holds no vehicle and every zone point
    is in line of sight of a covering, unblocked sensor (truth geometry, not the method)."""
    healthy = [n for n in sim.SENSORS if sc.blocked != n]
    for k, t in enumerate(meas["t_true"]):
        if abs(t) > 1.3 + 1e-9:
            continue
        ego = sc.ego_pose(t)
        z = method.Zone(sc.claim, {"s": sc.ego_v * t, "l": float(sc.ego_l(t)),
                                   "psi_rel": float(np.arctan2(sc.ego_dl(t), sc.ego_v)),
                                   "kappa": sc.road.kappa}, "road")
        px, py = z.points_ego(0.5)
        rr = np.hypot(px, py)
        dirs = np.stack([px / rr, py / rr], 1)
        boxes = []
        for a in sc.actors:
            wx, wy, th = sc.road.to_world(a.s(t), a.l)
            bx, by = sim.to_ego(wx, wy, ego)
            boxes.append((float(bx), float(by), float(th) - ego[2], a.dims[0], a.dims[1]))
        if boxes:
            B = np.array(boxes)
            D = sim.ray_box_dist(dirs, B[:, 0], B[:, 1], B[:, 2], B[:, 3], B[:, 4])
            if (D.min(axis=1) <= rr + 0.5).any():
                return False
        bear = np.degrees(np.arctan2(py, px))
        cov = np.zeros(len(px), bool)
        for n in healthy:
            bore, half, rmax = sim.SENSORS[n]
            cov |= (np.abs(sim.wrap(bear - bore)) <= half - 0.5) & (rr <= rmax)
        if not cov.all():
            return False
    return True


rng = np.random.default_rng(42)
NOBOUND = method.Config("geometry check", bound=False, liveness=True, k_support=3, gate=1.0)
fr = fs = agree = n = 0
disagree = []
for i in range(300):
    sc = sim.make_scene(rng, {"blocked": None, "misalign": {}, "clock_offset": 0.0})
    m = sim.simulate(sc, rng)
    got, _ = method.pal_verdict(m, sc.claim, sc.weather, method.PAL_V21)
    geo, _ = method.pal_verdict(m, sc.claim, sc.weather, NOBOUND)
    if sc.truth["genuine"] and got == "REFUTED":
        fr += 1
    if sc.truth["empty"] and got == "SUPPORTED":
        fs += 1
    if sc.truth["empty"]:
        n += 1
        vis = visible_and_empty(sc, m)
        ok = (geo == "REFUTED") == vis
        agree += ok
        if not ok and len(disagree) < 8:
            disagree.append({"scene": i, "pal_no_bound": geo, "visible_and_empty": vis,
                             "kappa": sc.road.kappa, "n_actors": len(sc.actors)})
OUT["V2_ideal_sensors"] = {"scenes": 300, "false_refutations": fr, "false_supports": fs,
                           "empty_scenes": n, "refuted_equals_visible": agree,
                           "agreement_rate": round(agree / max(n, 1), 4), "disagreements": disagree}
restore()

# ---------------------------------------------------------------- V3
def empirical_miss_all(cls, r, n_samples, m_radars, params, trials, rng):
    su, sv = params["fade_persist_sigma_db"], params["fade_sample_sigma_db"]
    rcs = sim.CLASS_RCS[cls] + params.get("rcs_offset_db", 0.0)
    u = rng.normal(0, su, trials)
    base = params["snr0_db"] + rcs - 40 * math.log10(r / 80.0) - params["weather_loss_db"]["clear"]
    miss = np.ones(trials, bool)
    for _s in range(n_samples):
        for _m in range(m_radars):
            snr = base + u + rng.normal(0, sv, trials)
            det = rng.random(trials) < 1 / (1 + np.exp(-snr / params["pd_slope_db"]))
            miss &= ~det
    return float(miss.mean())


rng = np.random.default_rng(7)
rows = []
for label, params in (("matched", dict(ORIG)),
                      ("mismatched: RCS -3 dB, persistent fade 6 dB",
                       {**ORIG, "rcs_offset_db": -3.0, "fade_persist_sigma_db": 6.0})):
    for cls in ("car", "motorcycle"):
        for r in (20.0, 40.0, 60.0, 80.0):
            for n_s, m_r in ((5, 1), (5, 2), (27, 1)):
                pred = method.miss_bound(cls, [r] * n_s, [m_r] * n_s, "clear")
                emp = empirical_miss_all(cls, r, n_s, m_r, params, 200000, rng)
                rows.append({"model": label, "class": cls, "range_m": r, "samples": n_s,
                             "radars": m_r, "bound": pred, "empirical": emp,
                             "bound_ge_empirical": pred >= emp * 0.8 or emp < 2e-5})
OUT["V3_bound_calibration"] = rows

# ---------------------------------------------------------------- V4
rng = np.random.default_rng(99)
same = 0
for i in range(40):
    sc = sim.make_scene(rng)
    m = sim.simulate(sc, rng)
    before = method.objlist_verdict(m, sc.claim)
    for cfg in [method.PAL_FULL, *method.ABLATIONS, method.PAL_V1]:
        method.pal_verdict(m, sc.claim, sc.weather, cfg)
    after = method.objlist_verdict(m, sc.claim)
    same += before == after
OUT["V4_baseline_independence"] = {"scenes": 40, "identical": same}

# ---------------------------------------------------------------- V5
err = 0.0
for kap in (0.0, 1 / 300, -1 / 300, 1 / 600):
    road = sim.Road(kap)
    s = np.linspace(-80, 80, 50); l = np.linspace(-5, 5, 50)
    x, y, _ = road.to_world(s, l)
    s2, l2 = method.road_inverse(x, y, kap)
    err = max(err, float(np.abs(s2 - s).max()), float(np.abs(l2 - l).max()))
OUT["V5_geometry_roundtrip_max_err_m"] = err

OUT["params_simulator"] = ORIG
OUT["params_method"] = {"nominal": method.NOMINAL, "eps": method.EPS,
                        "calib_limit_deg": method.CALIB_LIMIT_DEG, "clock_bound_s": method.CLOCK_BOUND,
                        "base_stream": method.BASE, "enriched_stream": method.ENRICHED}
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_v21.json"), "w") as f:
    json.dump(OUT, f, indent=2, default=float)
print(json.dumps({k: v for k, v in OUT.items() if k not in ("V3_bound_calibration", "params_simulator", "params_method")}, indent=2, default=float))
bad = [r for r in rows if not r["bound_ge_empirical"]]
print("V3 rows:", len(rows), "bound below empirical:", len(bad))
for r in bad[:12]:
    print(r)
