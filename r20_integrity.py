"""Ledger test: integrity layer end to end on benchmark scenes, verdict equality after disclosure, attack tests,
storage and disclosure sizes. Each scene's 2.6 s window is embedded in a realistic stream:
50 s of base samples (2 Hz, 2.5 deg) before, the enriched or base event stream, and 60 min of base
driving afterwards (chain to the next hourly anchor).
Usage: python3 batch3/r20_integrity.py N   (N scenes; the shipped result uses N = 60)"""
import sys, os, json, copy, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, sim, method, run_phase7 as p7, ledger_v2 as L
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def regen(i, seed0=7_000_000):
    sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM)))
    rng = np.random.default_rng(seed0 + i); sc = sim.make_scene(rng); return sc, sim.simulate(sc, rng)

def zone_sectors(claim):
    def f(t, log, n_sec):
        res = 360.0 / n_sec
        z = method.Zone(claim, log, "road"); px, py = z.points_ego()
        return sorted({int(s) for s in (((np.degrees(np.arctan2(py, px)) + 180.0) // res).astype(int) % n_sec)})
    return f

def filler(t, n_sec):
    return {"d_free": np.full(n_sec, 30.0), "hit": np.zeros(n_sec, bool), "bin": np.zeros(n_sec, int), "ncov": np.full(n_sec, 2)}

def build_ledger(sc, meas, after_min=60, block_s=60.0, offset=0.0, key_seed=0):
    enriched = meas["diag"]["violation_detected"]
    stream = method.ENRICHED if enriched else method.BASE
    rec = method.build_record(meas, stream, True, True)
    key = Ed25519PrivateKey.from_private_bytes(np.random.default_rng(key_seed).bytes(32))   # seeded: byte-reproducible
    led = L.LedgerV2(key, np.random.default_rng(1), block_s)
    log0 = rec["samples"][0]["log"]; t_first = rec["samples"][0]["t"]
    w0, w1 = window(sc.claim)   # filler samples (synthetic driving) never fall inside the claim window
    t = t_first - 50.0 - offset
    while t < t_first - 10.0:                     # base driving before the event
        led.append(t, log0, filler(t, 144), 144); t += 0.5
    dt = 1.0 / stream["rate_hz"]; n = rec["n_sec"]
    t = t_first - 10.0 + 1e-6 if enriched else t_first - 10.0
    while t < t_first - 1e-9:                     # event stream before the simulated window
        if not (w0 <= t <= w1): led.append(t, log0, filler(t, n), n)
        t += dt
    for smp in rec["samples"]:
        led.append(smp["t"], smp["log"], smp, n)
    t = rec["samples"][-1]["t"] + dt
    while t < t_first + 10.0:
        if not (w0 <= t <= w1): led.append(t, log0, filler(t, n), n)
        t += dt
    while t < t_first + 10.0 + after_min * 60:    # base driving until the hourly anchor
        led.append(t, log0, filler(t, 144), 144); t += 0.5
    anchor = led.anchor()
    return led, key, anchor, rec, stream

def verdict_from(samples, sc, meas):
    """Formal-tier verdict on the verified partial record (the record builder is swapped for the disclosed samples)."""
    n = samples[0][0]
    fake = {"res": 360.0 / n, "n_sec": n, "samples": [s for _, s in samples]}
    orig = method.build_record
    method.build_record = lambda *a, **k: fake
    try:
        return method.pal_verdict(meas, sc.claim, sc.weather, method.PAL_V23)[0]
    finally:
        method.build_record = orig

def window(claim):
    return claim["t_event"] - claim["t_tol"] - method.CLOCK_BOUND, claim["t_event"] + claim["t_tol"] + method.CLOCK_BOUND

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    N = int(sys.argv[1]); eq, sizes = 0, []
    for i in range(N):
        sc, meas = regen(i)
        led, key, anchor, rec, stream = build_ledger(sc, meas)
        t0, t1 = window(sc.claim); zf = zone_sectors(sc.claim)
        d = led.disclose(t0, t1, zf)
        samples = L.verify(d, key.public_key(), anchor, t0, t1, zf)
        v_full = method.pal_verdict(meas, sc.claim, sc.weather, method.PAL_V23)[0]
        v_disc = verdict_from(samples, sc, meas)
        eq += v_full == v_disc
        sizes.append((stream["rate_hz"], L.LedgerV2.disclosure_bytes(d), sum(len(b["leaves"]) for b in d["blocks"]),
                      sum(len(b["proof"]) for b in d["blocks"]), len(d["headers"])))
    print(f"verdict identical after disclosure+verification: {eq}/{N}")
    for rate in (2.0, 10.0):
        s = [x for x in sizes if x[0] == rate]
        if s:
            print(f"rate {rate} Hz: n={len(s)} disclosure bytes median {statistics.median(x[1] for x in s):.0f} "
                  f"max {max(x[1] for x in s)}; leaves median {statistics.median(x[2] for x in s):.0f}; "
                  f"proof hashes median {statistics.median(x[3] for x in s):.0f}; headers {statistics.median(x[4] for x in s):.0f}")
    # storage measured on ledgers: one hour of base-resolution driving, and one 20 s enriched event
    sc0, meas0 = regen(0)
    log0 = method.build_record(meas0, method.BASE, True, True)["samples"][0]["log"]
    hb = L.LedgerV2(Ed25519PrivateKey.from_private_bytes(bytes(32)), np.random.default_rng(2), 60.0)
    for k in range(7200): hb.append(k * 0.5, log0, filler(k * 0.5, 144), 144)
    hb.anchor()
    print("storage per hour, base:", hb.storage_bytes(), "B")
    he = L.LedgerV2(Ed25519PrivateKey.from_private_bytes(bytes(32)), np.random.default_rng(3), 60.0)
    for k in range(200): he.append(k * 0.1, log0, filler(k * 0.1, 360), 360)
    he.anchor()
    print("enriched 20 s event:", sum(len(p) for b in he.blocks for p in b.payloads), "B leaves;", he.storage_bytes(), "B with header and seed")
    # ---------------- attacks on one scene with a hit in the zone (genuine claim)
    for i in range(N, N + 400):
        sc, meas = regen(i)
        if sc.truth["genuine"] and method.pal_verdict(meas, sc.claim, sc.weather, method.PAL_V23)[0] == "SUPPORTED":
            break
    else:
        raise SystemExit("no SUPPORTED genuine scene found for the attack tests")
    print("attack scene:", i)
    led, key, anchor, rec, stream = build_ledger(sc, meas, offset=0.0)
    t0, t1 = window(sc.claim); zf = zone_sectors(sc.claim); pub = key.public_key()
    base = led.disclose(t0, t1, zf)
    results = {}
    def attempt(name, d, anc=anchor, pk=pub):
        try:
            L.verify(d, pk, anc, t0, t1, zf); results[name] = "NOT DETECTED"
        except L.VerifyError as e:
            results[name] = f"detected: {e}"
    # E1 edit a disclosed zone sector with a hit so it reads free
    d = copy.deepcopy(base); blk = d["blocks"][0]; idx = None
    for j, (k_, p, salt) in enumerate(blk["leaves"]):
        if len(p) == 2 and (p[1] >> 7):
            idx = k_; blk["leaves"][j] = (idx, L.enc_sector(127.5, False, 0, 2), salt); break
    assert idx is not None, "attack scene has no disclosed hit sector"
    attempt("E1 edit hit sector to free", d)
    # E2 edit, rebuild the block and re-sign with an attacker key
    forged = copy.deepcopy(led); fk = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    bidx = d["blocks"][0]["index"]; b = forged.blocks[bidx]
    b.payloads[idx] = L.enc_sector(127.5, False, 0, 2)
    leaves = [L.leaf_hash(L.salt_for(b.seed, k), k, p) for k, p in enumerate(b.payloads)]
    b.levels = L.levels_of(leaves); b.header.root = b.levels[-1][0]; b.header.signature = fk.sign(b.header.body())
    attempt("E2 edit + rebuild + re-sign (attacker key)", forged.disclose(t0, t1, zf))
    # E3 key compromise: rebuild and re-sign the whole chain with the real key; anchor already published
    for k2 in range(bidx, len(forged.blocks)):
        hb = forged.blocks[k2].header
        if k2 > bidx: hb.prev = forged.blocks[k2 - 1].header.hash()
        hb.signature = key.sign(hb.body())
    attempt("E3 key compromise, chain re-signed", forged.disclose(t0, t1, zf))
    # W1 withhold one zone sector with a hit
    d = copy.deepcopy(base); blk = d["blocks"][0]
    keep = [x for x in blk["leaves"] if x[0] != idx]; blk["leaves"] = keep
    blk["proof"] = L.multiproof(led.blocks[blk["index"]].levels, [x[0] for x in keep])   # valid proof for the reduced set
    attempt("W1 withhold a zone sector (valid proof)", d)
    # W2 withhold a whole sample (ego leaf + its sectors)
    d = copy.deepcopy(base); blk = d["blocks"][0]
    ego_idx = [x[0] for x in blk["leaves"] if len(x[1]) == 40][1]
    k0, n_of = 0, None                                   # sector count of that sample, from the block layout
    for t_, n_ in led.blocks[blk["index"]].header.layout:
        if k0 == ego_idx: n_of = n_; break
        k0 += 1 + n_
    red = [x for x in blk["leaves"] if not (ego_idx <= x[0] < ego_idx + 1 + n_of)]
    attempt_d = copy.deepcopy(d); attempt_d["blocks"][0]["leaves"] = red
    attempt_d["blocks"][0]["proof"] = L.multiproof(led.blocks[blk["index"]].levels, [x[0] for x in red])
    attempt("W2 withhold a whole sample (valid proof)", attempt_d)
    # W3 withhold a block: place a block boundary inside the window and drop the second block
    led2, key2, anchor2, *_ = build_ledger(sc, meas, offset=9.0)
    d2 = led2.disclose(t0, t1, zf)
    nb = len(d2["blocks"])
    if nb >= 2:
        d2["blocks"] = d2["blocks"][:1]
        try:
            L.verify(d2, key2.public_key(), anchor2, t0, t1, zf); results["W3 withhold a block"] = "NOT DETECTED"
        except L.VerifyError as e:
            results["W3 withhold a block"] = f"detected: {e}"
    else:
        results["W3 withhold a block"] = f"not constructed (window in {nb} block)"
    # W4 withhold the FIRST block of the window, with its header and all earlier headers
    d4 = led2.disclose(t0, t1, zf)
    if len(d4["blocks"]) >= 2:
        keep = d4["blocks"][1]["index"]
        d4["blocks"] = d4["blocks"][1:]; d4["headers"] = [h for h in d4["headers"] if h.index >= keep]
        try:
            L.verify(d4, key2.public_key(), anchor2, t0, t1, zf); results["W4 withhold the first block"] = "NOT DETECTED"
        except L.VerifyError as e:
            results["W4 withhold the first block"] = f"detected: {e}"
    else:
        results["W4 withhold the first block"] = f"not constructed (window in {len(d4['blocks'])} block)"
    # W5 replay: list a disclosed block twice so that its samples count twice in the bound
    d5 = copy.deepcopy(base); d5["blocks"] = d5["blocks"] + [copy.deepcopy(d5["blocks"][0])]
    try:
        L.verify(d5, pub, anchor, t0, t1, zf); results["W5 replay a block (duplicate samples)"] = "NOT DETECTED"
    except L.VerifyError as e:
        results["W5 replay a block (duplicate samples)"] = f"detected: {e}"
    assert all(v.startswith("detected") for v in results.values()), results
    print(json.dumps(results, indent=1))
