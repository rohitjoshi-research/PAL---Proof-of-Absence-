"""
PAL v2 - physically grounded scene + sensor simulator (Phase 6).

Ground truth lives here and ONLY here. Methods never read it; they only see the
sensor output (per-ray range / hit / measured bearing) and the ego log (with noise).

Model summary (all parameter values ASSUMED unless stated; see PARAMS):
  * Road: 3 lanes, straight or constant-curvature, frame (s = along road, l = lateral).
  * Ego performs a lane change across the solid line centred on t = 0 (the violation
    the Hong Kong fraud pattern films). The claim refers to t = 0.
  * Vehicles are oriented boxes aligned with the road tangent; ray tracing is exact
    for oriented rectangles (slab test in each box frame).
  * Sensors: two rear-corner radars (boresight +/-135 deg, FOV +/-75 deg, 80 m) and
    one front radar (0 deg, +/-50 deg, 160 m). Rays are cast from the ego origin
    (simplification: mounting offsets ignored).
  * Detection: radar-equation SNR with per-class RCS, R^-4 range loss, weather loss,
    a PERSISTENT per-object fade (aspect, correlated over the whole window) and a
    per-sample per-radar fluctuation. Pd = logistic(SNR / 1.5 dB).
    A missed first object is invisible: the ray reports free space to max range.
    This is the physical root of false refutation.
  * Faults: radar blockage (no returns at all), radar yaw misalignment (measured
    bearing = true + error), ghost targets (multipath), clock offset.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

LANE_W = 3.5
LANES = (-LANE_W, 0.0, LANE_W)
EGO_L, EGO_W = 4.6, 1.85
DT = 0.1                         # simulation step (10 Hz)
WIN = 1.3                        # samples simulated for t in [-WIN, +WIN]
RAY_STEP_DEG = 0.5

CLASS_DIMS = {"car": (4.5, 1.8), "van": (5.5, 2.0), "truck": (10.0, 2.5),
              "motorcycle": (2.2, 0.8)}
# Radar cross-section in dBsm (ASSUMED; typical literature orders of magnitude,
# REQUIRES SOURCE VERIFICATION before publication)
CLASS_RCS = {"car": 10.0, "van": 15.0, "truck": 20.0, "motorcycle": 0.0}

PARAMS = {
    "snr0_db": -7.0,            # SNR of a 0 dBsm target at 80 m (gives car Pd~0.88 at 80 m)
    "pd_slope_db": 1.5,
    "fade_persist_sigma_db": 4.0,
    "fade_sample_sigma_db": 3.0,
    "weather_loss_db": {"clear": 0.0, "rain": 2.5, "fog": 1.0},
    "ghost_rate": 0.03,          # ghosts per radar per sample
    "ghost_range": (5.0, 40.0),
    "rcs_offset_db": 0.0,        # robustness knob: true RCS minus nominal
    "p_blocked": 0.05,           # share of scenes with one rear radar blocked
    "blocked_recall": 0.95,      # probability the self-check flags a blockage
    "p_misalign": 0.05,          # share of scenes with one rear radar misaligned
    "misalign_range_deg": (4.0, 10.0),
    "calib_noise_deg": 0.5,      # noise on the self-calibration residual
    "clock_sigma_s": 0.1,
    "pose_noise_l_m": 0.10,
    "pose_noise_psi_deg": 0.3,
    "violation_recall": 0.95,
    "traffic_max": 6,
    # Phase 11 additions (defaults reproduce every earlier run bit-identically)
    "ego_speed_range": [13.9, 22.2],          # m/s (50-80 km/h)
    "weather_probs": [0.6, 0.3, 0.1],         # clear, rain, fog
    "genuine_gap_mode": "uniform",            # uniform | far_edge (claimant within 1 m of g_max)            # traffic vehicles per scene: uniform 0..traffic_max
}

SENSORS = {                      # name: (boresight deg, half FOV deg, max range m)
    "rear_left": (135.0, 75.0, 80.0),
    "rear_right": (-135.0, 75.0, 80.0),
    "front": (0.0, 50.0, 160.0),
}


def wrap(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------
# Road geometry
# ---------------------------------------------------------------------------
@dataclass
class Road:
    kappa: float = 0.0           # curvature 1/m (0 = straight)

    def heading(self, s):
        return self.kappa * np.asarray(s, dtype=float)

    def to_world(self, s, l):
        s = np.asarray(s, dtype=float)
        l = np.asarray(l, dtype=float)
        if abs(self.kappa) < 1e-12:
            cx, cy, th = s, np.zeros_like(s), np.zeros_like(s)
        else:
            th = self.kappa * s
            cx = np.sin(th) / self.kappa
            cy = (1 - np.cos(th)) / self.kappa
        return cx - l * np.sin(th), cy + l * np.cos(th), th


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
@dataclass
class Actor:
    s0: float                    # longitudinal position at t = 0 (centre)
    l: float                     # lateral position (lane centre + small offset)
    v: float                     # speed m/s
    cls: str
    role: str = "traffic"        # traffic | claimant | occluder
    fade_db: float = 0.0         # persistent aspect fade (ground truth only)

    @property
    def dims(self):
        return CLASS_DIMS[self.cls]

    def s(self, t):
        return self.s0 + self.v * t


@dataclass
class Scene:
    road: Road
    ego_v: float
    lc_dir: int                  # +1 left, -1 right lane change
    actors: list
    weather: str
    time_of_day: str
    blocked: str | None          # name of a blocked radar (ground truth)
    misalign: dict               # radar -> yaw error deg (ground truth)
    clock_offset: float          # s, logged time minus true time
    claim: dict                  # what the claimant says (input to methods)
    truth: dict = field(default_factory=dict)

    # ego trajectory: lane change from l=0 to lc_dir*LANE_W over t in [-2, 2]
    def ego_l(self, t):
        t = np.asarray(t, dtype=float)
        frac = np.clip((t + 2.0) / 4.0, 0, 1)
        return self.lc_dir * LANE_W * (1 - np.cos(np.pi * frac)) / 2

    def ego_dl(self, t):
        t = np.asarray(t, dtype=float)
        inside = (t > -2.0) & (t < 2.0)
        frac = np.clip((t + 2.0) / 4.0, 0, 1)
        return np.where(inside, self.lc_dir * LANE_W * np.pi / 8 * np.sin(np.pi * frac), 0.0)

    def ego_pose(self, t):
        s = self.ego_v * t
        x, y, th = self.road.to_world(s, self.ego_l(t))
        psi = th + np.arctan2(self.ego_dl(t), self.ego_v)
        return float(x), float(y), float(psi)


def to_ego(px, py, ego):
    ex, ey, epsi = ego
    dx, dy = np.asarray(px) - ex, np.asarray(py) - ey
    c, s = math.cos(-epsi), math.sin(-epsi)
    return c * dx - s * dy, s * dx + c * dy


def make_scene(rng: np.random.Generator, force: dict | None = None) -> Scene:
    """Random scene following the fraud pattern. `force` overrides fields (tests)."""
    f = force or {}
    kappa = f.get("kappa", rng.choice([0.0, 0.0, 1 / 300, -1 / 300, 1 / 600, -1 / 600]))
    road = Road(kappa)
    ego_v = f.get("ego_v", rng.uniform(*PARAMS["ego_speed_range"]))          # 50-80 km/h
    lc_dir = f.get("lc_dir", int(rng.choice([-1, 1])))
    weather = f.get("weather", rng.choice(["clear", "rain", "fog"], p=PARAMS["weather_probs"]))
    tod = f.get("time_of_day", rng.choice(["morning", "afternoon", "evening", "night"]))
    target_l = lc_dir * LANE_W                                # lane the ego moves into
    rear0 = -EGO_L / 2                                        # ego rear at t=0 (s, rel.)

    claim_cls = f.get("claim_cls", rng.choice(["car", "motorcycle"], p=[0.85, 0.15]))
    claim_v = ego_v + rng.uniform(-2.0, 2.0)
    d_min, d_max = 2.0, max(10.0, claim_v * 2.0)              # 2 s headway rule
    claim = {"lane_offset": target_l, "cls": claim_cls, "speed": claim_v,
             "gap_min": d_min, "gap_max": d_max, "t_event": 0.0, "t_tol": 1.0}

    actors: list[Actor] = []
    genuine = f.get("genuine", bool(rng.random() < 0.5))
    Lc, _ = CLASS_DIMS[claim_cls]
    if genuine:
        if PARAMS.get("genuine_gap_mode", "uniform") == "far_edge":
            gap = rng.uniform(d_max - 1.0, d_max)
        else:
            gap = rng.uniform(d_min + 1.0, d_max - 1.0)
        c_l = target_l + rng.uniform(-0.4, 0.4)
    else:                                                     # fraudster nearby, filming
        if rng.random() < 0.5:
            adj = [l for l in LANES if abs(l - target_l) > 1 and abs(l) <= LANE_W]
            c_l = float(rng.choice(adj)) + rng.uniform(-0.3, 0.3)
            gap = rng.uniform(3.0, 30.0)
        else:
            c_l = target_l + rng.uniform(-0.3, 0.3)
            gap = rng.uniform(d_max + 8.0, 60.0 if d_max + 8.0 < 60.0 else d_max + 20.0)  # Phase 11: high-speed fix
    claimant = Actor(s0=rear0 - gap - Lc / 2, l=c_l, v=ego_v + rng.uniform(-0.8, 0.8),
                     cls=claim_cls, role="claimant")
    actors.append(claimant)

    if f.get("occluder", rng.random() < 0.25):                # van right behind, outside zone
        g = rng.uniform(0.6, 1.4)
        actors.append(Actor(s0=rear0 - g - 5.5 / 2, l=target_l + rng.uniform(-0.2, 0.2),
                            v=ego_v, cls="van", role="occluder"))

    n_traffic = f.get("n_traffic", int(rng.integers(0, PARAMS["traffic_max"] + 1)))
    for _ in range(n_traffic):
        for _try in range(20):
            cls = rng.choice(["car", "van", "truck", "motorcycle"], p=[0.7, 0.1, 0.05, 0.15])
            L, _w = CLASS_DIMS[cls]
            a = Actor(s0=rng.uniform(-80, 80), l=float(rng.choice(LANES)) + rng.uniform(-0.3, 0.3),
                      v=ego_v + rng.uniform(-3, 3), cls=cls)
            if _clear_of(a, actors, ego_v, lc_dir):
                actors.append(a)
                break

    for a in actors:
        a.fade_db = rng.normal(0, PARAMS["fade_persist_sigma_db"])

    blocked = f.get("blocked", rng.choice(["rear_left", "rear_right"]) if rng.random() < PARAMS["p_blocked"] else None)
    misalign = f.get("misalign", {})
    if "misalign" not in f and rng.random() < PARAMS["p_misalign"]:
        misalign = {str(rng.choice(["rear_left", "rear_right"])):
                    float(rng.choice([-1, 1]) * rng.uniform(*PARAMS["misalign_range_deg"]))}
    clock = f.get("clock_offset", rng.normal(0, PARAMS["clock_sigma_s"]))

    sc = Scene(road, ego_v, lc_dir, actors, str(weather), str(tod), blocked, misalign, float(clock), claim)
    sc.truth = ground_truth(sc)
    return sc


def _clear_of(a, actors, ego_v, lc_dir):
    """No overlap with others or the ego path over the window (2 m spacing)."""
    for t in (-WIN, 0.0, WIN):
        sa = a.s(t)
        if abs(a.l) < LANE_W * 1.5 and abs(sa - ego_v * t) < (a.dims[0] + EGO_L) / 2 + 4 and \
                (abs(a.l) < 2.5 or abs(a.l - lc_dir * LANE_W) < 2.5):
            return False
        for b in actors:
            if abs(a.l - b.l) < 2.5 and abs(sa - b.s(t)) < (a.dims[0] + b.dims[0]) / 2 + 3:
                return False
    return True


def ground_truth(sc: Scene) -> dict:
    """Is the claim true? Computed from true geometry at t = 0, independent of methods.
    Genuine iff a vehicle of the claimed class has its front face in the claimed gap range
    and its centre within 1.0 m of the claimed lane centre."""
    c = sc.claim
    rear = -EGO_L / 2                       # ego rear in road s at t=0 (ego s=0)
    occ_claimed = False                     # strict: a vehicle at least as detectable as the
    occ_any = False                         #   claimed class, front face in the gap range,
    for a in sc.actors:                     #   centre within 1.0 m of the claimed lane
        L, W = a.dims
        front = a.s(0.0) + L / 2
        gap = rear - front
        strict = c["gap_min"] <= gap <= c["gap_max"] and abs(a.l - c["lane_offset"]) <= 1.0
        if strict and CLASS_RCS[a.cls] >= CLASS_RCS[c["cls"]]:
            occ_claimed = True
        # lenient: any part of the body overlaps the zone rectangle at ANY time in the claim
        # window (claim tolerance + declared clock bound), zone moving with the ego
        for t in np.arange(-1.3, 1.3 + 1e-9, 0.1):
            rear_t = sc.ego_v * t - EGO_L / 2
            z0, z1 = rear_t - c["gap_max"], rear_t - c["gap_min"]
            if (a.s(t) - L / 2 <= z1) and (a.s(t) + L / 2 >= z0) and \
                    abs(a.l - c["lane_offset"]) < LANE_W / 2 + W / 2:
                occ_any = True
    return {"genuine": occ_claimed,          # false refutation is judged on these
            "empty": not occ_any,            # false support is judged on these
            "occluded_setup": any(a.role == "occluder" for a in sc.actors)}


# ---------------------------------------------------------------------------
# Sensor simulation -> per-sample ray table (what the vehicle actually measures)
# ---------------------------------------------------------------------------
def pd_from_snr(snr_db):
    return 1.0 / (1.0 + np.exp(-np.asarray(snr_db) / PARAMS["pd_slope_db"]))


def snr_db(rcs_dbsm, rng_m, weather):
    return (PARAMS["snr0_db"] + rcs_dbsm - 40.0 * np.log10(np.maximum(rng_m, 0.5) / 80.0)
            - PARAMS["weather_loss_db"][weather])


def ray_box_dist(dirs, cx, cy, phi, L, W):
    """dirs: (R,2) unit vectors from origin. Boxes: arrays (B,). Returns (R,B) distances or inf."""
    c, s = np.cos(-phi), np.sin(-phi)                      # (B,)
    ox = c * (-cx) - s * (-cy)                             # origin in box frame (B,)
    oy = s * (-cx) + c * (-cy)
    dx = dirs[:, :1] * c - dirs[:, 1:] * s                 # (R,B)
    dy = dirs[:, :1] * s + dirs[:, 1:] * c
    hx, hy = L / 2, W / 2
    with np.errstate(divide="ignore", invalid="ignore"):
        tx1, tx2 = (-hx - ox) / dx, (hx - ox) / dx
        ty1, ty2 = (-hy - oy) / dy, (hy - oy) / dy
    tmin = np.maximum(np.minimum(tx1, tx2), np.minimum(ty1, ty2))
    tmax = np.minimum(np.maximum(tx1, tx2), np.maximum(ty1, ty2))
    ok = (tmax >= tmin) & (tmin > 0)
    out = np.where(ok, tmin, np.inf)
    return np.nan_to_num(out, nan=np.inf)


def simulate(sc: Scene, rng: np.random.Generator) -> dict:
    """Returns the measured ray table per sensor per sample plus the noisy ego log."""
    times = np.round(np.arange(-WIN, WIN + 1e-9, DT), 3)
    out = {"t_true": times, "t_logged": times + sc.clock_offset, "sensors": {}, "ego_log": []}
    for t in times:
        ex, ey, epsi = sc.ego_pose(t)
        out["ego_log"].append({"s": sc.ego_v * t + rng.normal(0, 0.05),
                               "l": float(sc.ego_l(t)) + rng.normal(0, PARAMS["pose_noise_l_m"]),
                               "psi_rel": float(np.arctan2(sc.ego_dl(t), sc.ego_v)) +
                               rng.normal(0, math.radians(PARAMS["pose_noise_psi_deg"])),
                               "kappa": sc.road.kappa + rng.normal(0, 1e-4)})
    for name, (bore, half, rmax) in SENSORS.items():
        ang_true = np.arange(bore - half, bore + half + 1e-9, RAY_STEP_DEG)
        dirs = np.stack([np.cos(np.radians(ang_true)), np.sin(np.radians(ang_true))], 1)
        err = sc.misalign.get(name, 0.0)
        rows = []
        for k, t in enumerate(times):
            ego = sc.ego_pose(t)
            cxs, cys, phis, Ls, Ws = [], [], [], [], []
            for a in sc.actors:
                wx, wy, th = sc.road.to_world(a.s(t), a.l)
                bx, by = to_ego(wx, wy, ego)
                cxs.append(float(bx)); cys.append(float(by)); phis.append(float(th) - ego[2])
                Ls.append(a.dims[0]); Ws.append(a.dims[1])
            if sc.actors:
                D = ray_box_dist(dirs, np.array(cxs), np.array(cys), np.array(phis),
                                 np.array(Ls), np.array(Ws))
                first = np.argmin(D, axis=1)
                dist = D[np.arange(len(dirs)), first]
            else:
                first = np.zeros(len(dirs), int)
                dist = np.full(len(dirs), np.inf)
            rng_out = np.full(len(dirs), rmax)
            hit = np.zeros(len(dirs), bool)
            if sc.blocked != name:
                # per-object detection draw for this sensor and sample
                det = {}
                for j, a in enumerate(sc.actors):
                    m = (first == j) & (dist <= rmax)
                    if not m.any():
                        continue
                    r = float(np.min(dist[m]))
                    snr = snr_db(CLASS_RCS[a.cls] + PARAMS["rcs_offset_db"], r, sc.weather) + \
                        a.fade_db + rng.normal(0, PARAMS["fade_sample_sigma_db"])
                    det[j] = rng.random() < pd_from_snr(snr)
                for j, ok in det.items():
                    m = (first == j) & (dist <= rmax)
                    if ok:
                        rng_out[m] = dist[m]
                        hit[m] = True
                # ghosts (multipath)
                for _g in range(rng.poisson(PARAMS["ghost_rate"])):
                    gr = rng.uniform(*PARAMS["ghost_range"])
                    ga = rng.uniform(bore - half, bore + half)
                    m = (np.abs(ang_true - ga) <= 0.75) & (rng_out > gr)
                    rng_out[m] = gr
                    hit[m] = True
            rows.append({"range": rng_out, "hit": hit})
        out["sensors"][name] = {"ang_measured": wrap(ang_true + err), "rows": rows,
                                "max_range": rmax}
    # self-diagnostics the vehicle can report (attestation inputs), with imperfect recall
    out["diag"] = {
        "blocked_flag": {n: (sc.blocked == n and rng.random() < PARAMS["blocked_recall"]) for n in SENSORS},
        "calib_residual_deg": {n: abs(sc.misalign.get(n, 0.0)) + abs(rng.normal(0, PARAMS["calib_noise_deg"]))
                               for n in SENSORS},
        "violation_detected": bool(rng.random() < PARAMS["violation_recall"]),
    }
    return out
