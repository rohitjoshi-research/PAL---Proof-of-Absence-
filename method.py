"""
PAL v2 methods (Phase 6). Consume ONLY the measured sensor table, the noisy ego log,
the vehicle's self-diagnostics and the claim. Never the scene ground truth.

Methods:
  PAL-full     claim-derived road-frame zone + observability attestation + bounded
               false refutation + persistence rule for support + self-violation enrichment
  ablations    PAL-full with exactly one component switched off
  PAL-v1       the Phase-3 method on the new simulator (ego-frame box, confidence
               threshold only, no attestation, k = 1, base stream)
  ObjList-best strongest object-list baseline: detections only, but given the
               claim-derived zone, attestation-based sensor exclusion, the 10 Hz stream
               and the persistence rule
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from sim import EGO_L, LANE_W, CLASS_RCS, SENSORS, Road, wrap

BASE = {"res_deg": 2.5, "rate_hz": 2.0}
ENRICHED = {"res_deg": 1.0, "rate_hz": 10.0}
EPS = 1e-3                 # maximum accepted probability of false refutation
CALIB_LIMIT_DEG = 2.0      # residual above which a sensor's sectors become unknown
CLOCK_BOUND = 0.3          # declared clock uncertainty (s)
SUPPORT_INSET = 0.3        # m; returns must lie this far inside the claimed lane to support
SUPPORT_INSET_LONG = 0.5   # m; ... and this far inside the claimed gap range (range quantisation)
TRACK_GATE = 2.0           # m; returns in different samples count as one object if this close

# The method's OWN nominal detection model (a copy; the simulator may deviate from it)
NOMINAL = {"snr0_db": -7.0, "pd_slope_db": 1.5, "fade_persist_sigma_db": 4.0,
           "fade_sample_sigma_db": 3.0,
           "weather_loss_db": {"clear": 0.0, "rain": 2.5, "fog": 1.0}}
V1_CONF = {"clear": 0.97, "rain": 0.93, "fog": 0.60}       # Phase-3 rule

GH_X, GH_W = np.polynomial.hermite.hermgauss(24)


@dataclass
class Config:
    name: str
    zone: str = "road"        # road | egobox
    attest: bool = True
    bound: bool = True
    k_support: int = 2
    enrich: bool = True
    v1_conf: bool = False
    eps: float = EPS
    inset: float = SUPPORT_INSET
    gate: float = TRACK_GATE
    liveness: bool = False
    model: dict | None = None      # sensor model used by the miss bound (None = NOMINAL)
    # v2.2 (Phase 11 review fixes); defaults keep v2.1 behaviour bit-identical
    weather_worst: bool = False    # bound uses worst-case weather loss (record stores no weather)
    strict_free: bool = False      # a hit counts as free only if it lies >= delta BEYOND the zone
    window_cover: bool = False     # samples must cover the whole window W (no gaps / missing ends)


PAL_FULL = Config("PAL-full")
ABLATIONS = [Config("no claim-derived zone", zone="egobox"),
             Config("no attestation", attest=False),
             Config("no bound", bound=False),
             Config("no persistence", k_support=1),
             Config("no enrichment", enrich=False)]
PAL_LIVE = Config("PAL-full + liveness", liveness=True)
# v2.1 = v2.0 + the two Phase-7 fixes (liveness cross-check, persistence k=3 within 1 m)
PAL_V21 = Config("PAL v2.1", liveness=True, k_support=3, gate=1.0)
PAL_V21_CONS = Config("PAL v2.1 conservative bound", liveness=True, k_support=3, gate=1.0,
                      model={"rcs_offset_db": -6.0, "fade_persist_sigma_db": 6.0})
PAL_V23 = Config("PAL v2.3", liveness=True, k_support=3, gate=1.0,
                 weather_worst=True, strict_free=True, window_cover=True)
PAL_V23_CONS = Config("PAL v2.3 conservative bound (exploratory)", liveness=True, k_support=3, gate=1.0,
                      weather_worst=True, strict_free=True, window_cover=True,
                      model={"rcs_offset_db": -6.0, "fade_persist_sigma_db": 6.0})
_V23 = dict(weather_worst=True, strict_free=True, window_cover=True)
ABLATIONS_V23 = [Config("v2.3 no claim-derived zone", zone="egobox", liveness=True, k_support=3, gate=1.0, **_V23),
                 Config("v2.3 no attestation", attest=False, liveness=True, k_support=3, gate=1.0, **_V23),
                 Config("v2.3 no liveness", liveness=False, k_support=3, gate=1.0, **_V23),
                 Config("v2.3 no bound", bound=False, liveness=True, k_support=3, gate=1.0, **_V23),
                 Config("v2.3 no persistence", liveness=True, k_support=1, gate=1.0, **_V23),
                 Config("v2.3 no enrichment", enrich=False, liveness=True, k_support=3, gate=1.0, **_V23)]
ABLATIONS_V21 = [Config("v2.1 no claim-derived zone", zone="egobox", liveness=True, k_support=3, gate=1.0),
                 Config("v2.1 no attestation", attest=False, liveness=True, k_support=3, gate=1.0),
                 Config("v2.1 no liveness", liveness=False, k_support=3, gate=1.0),
                 Config("v2.1 no bound", bound=False, liveness=True, k_support=3, gate=1.0),
                 Config("v2.1 no persistence", liveness=True, k_support=1, gate=1.0),
                 Config("v2.1 no enrichment", enrich=False, liveness=True, k_support=3, gate=1.0)]
PAL_V1 = Config("PAL-v1 (Phase 3)", zone="egobox", attest=False, bound=False, k_support=1,
                enrich=False, v1_conf=True)


# ---------------------------------------------------------------------------
# geometry helpers (road frame <-> ego frame) using LOGGED ego pose and curvature
# ---------------------------------------------------------------------------
def road_inverse(px, py, kappa):
    px, py = np.asarray(px, float), np.asarray(py, float)
    if abs(kappa) < 1e-9:
        return px, py
    k = 1.0 / kappa
    sg = np.sign(k)
    th = np.arctan2(sg * px, -sg * (py - k))
    l = k - sg * np.hypot(px, py - k)
    return th * k, l


def ego_world(log):
    road = Road(log["kappa"])
    x, y, th = road.to_world(log["s"], log["l"])
    return float(x), float(y), float(th) + log["psi_rel"], road


def ego_to_world(xe, ye, pose):
    ex, ey, epsi = pose
    c, s = math.cos(epsi), math.sin(epsi)
    return ex + c * xe - s * ye, ey + s * xe + c * ye


def world_to_ego(xw, yw, pose):
    ex, ey, epsi = pose
    c, s = math.cos(-epsi), math.sin(-epsi)
    dx, dy = xw - ex, yw - ey
    return c * dx - s * dy, s * dx + c * dy


class Zone:
    """Claimed zone for one sample. 'road' = rectangle in road frame relative to the ego's
    logged s (claim-derived); 'egobox' = the same distances as a box in the ego frame."""

    def __init__(self, claim, log, mode):
        self.mode = mode
        self.claim = claim
        self.log = log
        ex, ey, epsi, road = ego_world(log)
        self.pose = (ex, ey, epsi)
        self.road = road
        rear = log["s"] - EGO_L / 2
        self.s0, self.s1 = rear - claim["gap_max"], rear - claim["gap_min"]
        self.l0, self.l1 = claim["lane_offset"] - LANE_W / 2, claim["lane_offset"] + LANE_W / 2
        # ego-box version
        self.x0, self.x1 = -EGO_L / 2 - claim["gap_max"], -EGO_L / 2 - claim["gap_min"]
        yc = claim["lane_offset"] - log["l"]
        self.y0, self.y1 = yc - LANE_W / 2, yc + LANE_W / 2

    def points_ego(self, step=0.5):
        if self.mode == "egobox":
            xs, ys = np.meshgrid(np.arange(self.x0, self.x1 + 1e-9, step),
                                 np.arange(self.y0, self.y1 + 1e-9, step))
            return xs.ravel(), ys.ravel()
        ss, ll = np.meshgrid(np.arange(self.s0, self.s1 + 1e-9, step),
                             np.arange(self.l0, self.l1 + 1e-9, step))
        wx, wy, _ = self.road.to_world(ss.ravel(), ll.ravel())
        return world_to_ego(wx, wy, self.pose)

    def road_coords(self, xe, ye):
        """(along-road offset behind the ego rear, lateral) of an ego-frame point."""
        xe, ye = np.asarray(xe, float), np.asarray(ye, float)
        if self.mode == "egobox":
            return -EGO_L / 2 - xe, ye + self.log["l"]
        wx, wy = ego_to_world(xe, ye, self.pose)
        s, l = road_inverse(wx, wy, self.road.kappa)
        return (self.log["s"] - EGO_L / 2) - s, l

    def contains_ego(self, xe, ye, margin=-SUPPORT_INSET_LONG, inset=SUPPORT_INSET):
        """Is a sensor return inside the claimed zone (used for SUPPORT only)?
        Along the road: `margin` (negative = inset). Across lanes: the return must lie
        `inset` metres INSIDE the lane (~1.5 sigma of logged pose error), so a vehicle
        hugging the lane line in the next lane cannot support a claim."""
        xe, ye = np.asarray(xe, float), np.asarray(ye, float)
        if self.mode == "egobox":
            return (xe >= self.x0 - margin) & (xe <= self.x1 + margin) & \
                   (ye >= self.y0 + inset) & (ye <= self.y1 - inset)
        wx, wy = ego_to_world(xe, ye, self.pose)
        s, l = road_inverse(wx, wy, self.road.kappa)
        return (s >= self.s0 - margin) & (s <= self.s1 + margin) & \
               (l >= self.l0 + inset) & (l <= self.l1 - inset)


# ---------------------------------------------------------------------------
# evidence record (what the vehicle stores)
# ---------------------------------------------------------------------------
def silent_sensors(meas):
    """Liveness cross-check: a sensor with NO returns in the whole window while any other
    sensor (even one excluded for calibration) reports returns inside its field of view
    and range is treated as blocked."""
    hits = {n: sum(int(r["hit"].sum()) for r in S["rows"]) for n, S in meas["sensors"].items()}
    out = set()
    for n, S in meas["sensors"].items():
        if hits[n] > 0:
            continue
        bore, half, rmax = SENSORS[n]
        for o, So in meas["sensors"].items():
            if o == n:
                continue
            for row in So["rows"]:
                a = So["ang_measured"][row["hit"]]
                r = row["range"][row["hit"]]
                if np.any((np.abs(wrap(a - bore)) <= half) & (r <= rmax)):
                    out.add(n)
                    break
    return out


def healthy_sensors(meas, attest, liveness=False):
    silent = silent_sensors(meas) if liveness else set()
    out = []
    for n in meas["sensors"]:
        if attest and (meas["diag"]["blocked_flag"][n] or
                       meas["diag"]["calib_residual_deg"][n] > CALIB_LIMIT_DEG):
            continue
        if n in silent:
            continue
        out.append(n)
    return out


def build_record(meas, stream, attest, liveness=False):
    """Per sample: sector free range, hit flag, bearing bin, number of healthy radars."""
    res = stream["res_deg"]
    n_sec = int(round(360 / res))
    step = int(round(1.0 / (stream["rate_hz"] * 0.1)))
    idx = [k for k, t in enumerate(meas["t_true"]) if (round(t * 10) % step == 0)]
    sensors = healthy_sensors(meas, attest, liveness)
    samples = []
    for k in idx:
        d_free = np.zeros(n_sec)
        hit = np.zeros(n_sec, bool)
        bbin = np.zeros(n_sec, int)
        ncov = np.zeros(n_sec, int)
        angs, rngs, hits = [], [], []
        for n in sensors:
            S = meas["sensors"][n]
            row = S["rows"][k]
            sec_n = ((S["ang_measured"] + 180.0) // res).astype(int) % n_sec
            ncov[np.unique(sec_n)] += 1
            angs.append(S["ang_measured"]); rngs.append(row["range"]); hits.append(row["hit"])
        if angs:
            a = np.concatenate(angs); r = np.concatenate(rngs); hh = np.concatenate(hits)
            sec = ((a + 180.0) // res).astype(int) % n_sec
            order = np.lexsort((r, sec))
            first = np.unique(sec[order], return_index=True)
            for s_i, j in zip(first[0], first[1]):
                o = order[j]
                d_free[s_i] = min(127.5, math.floor(r[o] / 0.5) * 0.5)   # quantised down
                hit[s_i] = hh[o]
                frac = ((a[o] + 180.0) % res) / res
                bbin[s_i] = min(7, int(frac * 8))
        samples.append({"t": float(meas["t_logged"][k]), "log": meas["ego_log"][k],
                        "d_free": d_free, "hit": hit, "bin": bbin, "ncov": ncov})
    return {"res": res, "n_sec": n_sec, "samples": samples}


def record_bytes_per_sample(stream):
    return 4 + int(round(360 / stream["res_deg"])) * 2 + 16


# ---------------------------------------------------------------------------
# bounded false refutation (method's internal model)
# ---------------------------------------------------------------------------
def _pd(snr):
    return 1.0 / (1.0 + np.exp(-snr / NOMINAL["pd_slope_db"]))


def miss_bound(cls, ranges, ncovs, weather, model=None):
    """P(a target of class `cls` at the given worst-case ranges is missed in EVERY sample),
    with a persistent fade shared across samples and independent per-sample fluctuation."""
    M = {**NOMINAL, **(model or {})}
    su, sv = M["fade_persist_sigma_db"], M["fade_sample_sigma_db"]
    u = math.sqrt(2) * su * GH_X
    v = math.sqrt(2) * sv * GH_X
    wu = GH_W / math.sqrt(math.pi)
    total = np.ones_like(u)
    for r, m in zip(ranges, ncovs):
        base = M["snr0_db"] + CLASS_RCS[cls] + M.get("rcs_offset_db", 0.0) - \
            40 * math.log10(max(r, 0.5) / 80.0) - M["weather_loss_db"][weather]
        snr = base + u[:, None] + v[None, :]
        q = (wu[None, :] * (1 - 1.0 / (1.0 + np.exp(-snr / M["pd_slope_db"])))).sum(axis=1)
        total *= q ** max(1, m)
    return float((wu * total).sum())


# ---------------------------------------------------------------------------
# verdicts
# ---------------------------------------------------------------------------
def persistent(points, k, gate=TRACK_GATE):
    """points: list of (sample_index, gap, lateral) for returns inside the zone.
    True if some return is matched, within TRACK_GATE metres, by returns from at least
    k - 1 OTHER samples (a consistent object, not scattered ghosts)."""
    if k <= 1:
        return len(points) > 0
    for i, (si, g, l) in enumerate(points):
        others = {sj for sj, g2, l2 in points if sj != si and math.hypot(g - g2, l - l2) <= gate}
        if len(others) >= k - 1:
            return True
    return False

def pal_verdict(meas, claim, weather, cfg: Config):
    stream = ENRICHED if (cfg.enrich and meas["diag"]["violation_detected"]) else BASE
    rec = build_record(meas, stream, cfg.attest, cfg.liveness)
    res, n_sec = rec["res"], rec["n_sec"]
    t0 = claim["t_event"] - claim["t_tol"] - CLOCK_BOUND
    t1 = claim["t_event"] + claim["t_tol"] + CLOCK_BOUND
    per, ranges, ncovs, n_occ, pts = [], [], [], 0, []
    for smp in rec["samples"]:
        if not (t0 <= smp["t"] <= t1):
            continue
        z = Zone(claim, smp["log"], cfg.zone)
        px, py = z.points_ego()
        rr = np.hypot(px, py)
        sec = ((np.degrees(np.arctan2(py, px)) + 180.0) // res).astype(int) % n_sec
        # occupied: a return whose position falls inside the zone
        occ = False
        for s_i in np.unique(sec):
            if smp["hit"][s_i]:
                ang = math.radians(-180.0 + s_i * res + (smp["bin"][s_i] + 0.5) * res / 8)
                hx, hy = smp["d_free"][s_i] * math.cos(ang), smp["d_free"][s_i] * math.sin(ang)
                if z.contains_ego(hx, hy, inset=cfg.inset):
                    occ = True
                    g, l = z.road_coords(hx, hy)
                    pts.append((len(per), float(g), float(l)))
        free = not occ
        worst, mincov = 0.0, 9
        for s_i in np.unique(sec):
            rmax = float(rr[sec == s_i].max())
            if smp["ncov"][s_i] == 0 or smp["d_free"][s_i] + 0.5 < rmax:
                free = False
            elif cfg.strict_free and smp["hit"][s_i] and smp["d_free"][s_i] < rmax + 0.5:
                free = False   # a return at or near the far zone edge is never read as free space
            worst = max(worst, rmax)
            mincov = min(mincov, int(smp["ncov"][s_i]))
        if cfg.v1_conf and V1_CONF[weather] < 0.90:
            free = False
        n_occ += occ
        per.append("occupied" if occ else ("free" if free else "unknown"))
        ranges.append(worst); ncovs.append(max(mincov, 1))
    if not per:
        return "INCONCLUSIVE", None
    if cfg.window_cover:
        ts = [smp["t"] for smp in rec["samples"] if t0 <= smp["t"] <= t1]
        dt = 1.0 / stream["rate_hz"]
        # ends: W is padded by the clock bound, so the first/last sample may sit up to that bound inside
        ends_ok = (ts[0] - t0 <= 1.5 * dt + CLOCK_BOUND) and (t1 - ts[-1] <= 1.5 * dt + CLOCK_BOUND)
        gaps_ok = all(b - a <= 1.5 * dt for a, b in zip(ts, ts[1:]))
        if not (ends_ok and gaps_ok):
            per.append("unknown")       # part of W was not sampled -> cannot be free throughout
    if persistent(pts, cfg.k_support, cfg.gate):
        return "SUPPORTED", None
    if all(p == "free" for p in per):
        if cfg.bound:
            w_used = max(NOMINAL["weather_loss_db"], key=NOMINAL["weather_loss_db"].get) if cfg.weather_worst else weather
            b = miss_bound(claim["cls"], ranges, ncovs, w_used, cfg.model)
            return ("REFUTED" if b <= cfg.eps else "INCONCLUSIVE"), b
        return "REFUTED", None
    return "INCONCLUSIVE", None


def objlist_verdict(meas, claim, k_support=2, liveness=False, gate=TRACK_GATE):
    """Strongest object-list baseline: 10 Hz detections, healthy sensors only, claim-derived
    zone, persistence rule. It cannot represent 'not observed', so absence of detections
    inside a covered zone is read as absence of the claimant."""
    sensors = healthy_sensors(meas, attest=True, liveness=liveness)
    t0 = claim["t_event"] - claim["t_tol"] - CLOCK_BOUND
    t1 = claim["t_event"] + claim["t_tol"] + CLOCK_BOUND
    covered, pts, n_s = True, [], 0
    for k, t in enumerate(meas["t_logged"]):
        if not (t0 <= t <= t1):
            continue
        z = Zone(claim, meas["ego_log"][k], "road")
        px, py = z.points_ego()
        bear = np.degrees(np.arctan2(py, px))
        cov = np.zeros(len(px), bool)
        for n in sensors:
            S = meas["sensors"][n]
            bore, half, rmax = SENSORS[n]
            cov |= (np.abs(wrap(bear - bore)) <= half) & (np.hypot(px, py) <= rmax)
            row = S["rows"][k]
            if row["hit"].any():
                a = np.radians(S["ang_measured"][row["hit"]])
                r = row["range"][row["hit"]]
                hx, hy = r * np.cos(a), r * np.sin(a)
                inside = z.contains_ego(hx, hy)
                if inside.any():
                    g, l = z.road_coords(hx[inside], hy[inside])
                    pts.extend((n_s, float(gg), float(ll)) for gg, ll in zip(g, l))
        covered &= bool(cov.all())
        n_s += 1
    if persistent(pts, k_support, gate):
        return "SUPPORTED"
    if not covered:
        return "INCONCLUSIVE"
    return "REFUTED"


def objlist_strict(meas, claim, no_moto=False, k_support=3):
    """Phase 11 stricter detection-log baselines (review finding 1).
    ObjList-strict: ObjList-best v2.1, but ANY in-zone detection, even a single non-persistent one,
    blocks refutation. ObjList-strict-moto: additionally never refutes a motorcycle claim."""
    v = objlist_verdict(meas, claim, k_support=k_support, liveness=True, gate=1.0)
    if v != "REFUTED":
        return v
    if no_moto and claim["cls"] == "motorcycle":
        return "INCONCLUSIVE"
    sensors = healthy_sensors(meas, attest=True, liveness=True)
    t0 = claim["t_event"] - claim["t_tol"] - CLOCK_BOUND
    t1 = claim["t_event"] + claim["t_tol"] + CLOCK_BOUND
    for k, t in enumerate(meas["t_logged"]):
        if not (t0 <= t <= t1):
            continue
        z = Zone(claim, meas["ego_log"][k], "road")
        for n in sensors:
            S = meas["sensors"][n]; row = S["rows"][k]
            if row["hit"].any():
                a = np.radians(S["ang_measured"][row["hit"]]); r = row["range"][row["hit"]]
                if z.contains_ego(r * np.cos(a), r * np.sin(a), margin=0.0, inset=0.0).any():
                    return "INCONCLUSIVE"
    return "REFUTED"
