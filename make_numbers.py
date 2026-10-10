"""Regenerates the main-benchmark, ablation, degradation, stress-set, far-edge, calibration, attack and ledger numbers
of the manuscript from the result files. Output: numbers_rev2.json (name kept for continuity).
Inputs: results73/*.csv, results73/prereg_analysis.json, batch3/*.csv, batch3/boundary_v21.json, batch3/r20_result.txt.
The other numbers come from analyze_prereg.py, round2/analyses.py, round2/analyses_r3.py and round3/stress_x.py."""
import csv, json, math, os, re
from math import comb
H = os.path.dirname(os.path.abspath(__file__)); R73 = os.path.join(H, "results73"); B3 = os.path.join(H, "batch3")
def rows(p): return list(csv.DictReader(open(p)))
def mcn(a, b):
    n01 = sum(x and not y for x, y in zip(a, b)); n10 = sum(y and not x for x, y in zip(a, b)); n = n01 + n10
    return n01, n10, (1.0 if n == 0 else min(1.0, 2 * sum(comb(n, j) for j in range(min(n01, n10) + 1)) / 2 ** n))
def holm(ps):
    o = sorted(range(len(ps)), key=lambda i: ps[i]); adj = [0] * len(ps); run = 0
    for r, i in enumerate(o): run = max(run, min(1, (len(ps) - r) * ps[i])); adj[i] = run
    return adj
def wil(k, n, z=1.959964):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0, c - h), c + h]
def boot(flags, B=2000, seed=12345):
    import random; rnd = random.Random(seed); n = len(flags); s = []
    for _ in range(B): s.append(sum(flags[rnd.randrange(n)] for _ in range(n)) / n)
    s.sort(); return [s[int(0.025 * B)], s[int(0.975 * B) - 1]]
G = lambda R: [r for r in R if r["genuine"] == "True"]; E = lambda R: [r for r in R if r["empty"] == "True"]
REF = lambda m: (lambda r: r[m] == "REFUTED"); SUP = lambda m: (lambda r: r[m] == "SUPPORTED")
COMB = "Combined (formal and rule)"
def add_comb(R):
    for r in R:
        r[COMB] = "REFUTED" if (r["PAL v2.3"] == "REFUTED" and r["Rule k3"] == "REFUTED") else \
                  ("SUPPORTED" if "SUPPORTED" in (r["PAL v2.3"], r["Rule k3"]) else "INCONCLUSIVE")
    return R
def metrics(R, m, ci=False):
    g, e = G(R), E(R); wr = sum(map(REF(m), g)); ws = sum(map(SUP(m), e)); cov = sum(map(REF(m), e))
    d = {"WR": wr, "n_gen": len(g), "WS": ws, "n_emp": len(e), "cov": cov / len(e), "wr_wilson_up": wil(wr, len(g))[1], "ws_wilson_up": wil(ws, len(e))[1]}
    if ci: d["cov_boot95"] = boot([REF(m)(r) for r in e])
    return d
N = {}
# ---------------- main
M = add_comb(rows(os.path.join(R73, "main.csv")))
methods = ["PAL v2.3", "Rule k3", COMB, "Rule k3 no-moto-rule", "ObjList-best v2.1", "PAL-v1 (Phase 3)", "PAL v2.3 conservative bound (exploratory)"]
abl = [k for k in M[0] if k.startswith("v2.3 ")]
N["main"] = {"N": len(M), "genuine": len(G(M)), "empty": len(E(M)), "neither": len(M) - len(G(M)) - len(E(M)),
             "methods": {m: metrics(M, m, ci=True) for m in methods + abl}}
# ablation family: each ablation vs PAL v2.3 on WR, WS, coverage (exact McNemar, Holm over the family)
tests = []
for m in abl + ["PAL-v1 (Phase 3)"]:
    for met, S, f in (("WR", G(M), REF), ("WS", E(M), SUP), ("cov", E(M), REF)):
        a = [f(m)(r) for r in S]; b = [f("PAL v2.3")(r) for r in S]; n01, n10, p = mcn(a, b)
        tests.append({"method": m, "metric": met, "only_method": n01, "only_pal": n10, "p": p})
for t, a in zip(tests, holm([t["p"] for t in tests])): t["p_holm"] = a
N["main"]["ablation_tests"] = tests; N["main"]["ablation_family_size"] = len(tests)
a = [REF("Rule k3")(r) for r in E(M)]; b = [REF("PAL v2.3")(r) for r in E(M)]
N["main"]["cov_rule_vs_formal"] = dict(zip(["only_rule", "only_formal", "p"], mcn(a, b)))
# strata
bands = {"1-2": (1, 2), "3-4": (3, 4), "5+": (5, 99)}
N["main"]["density"] = {k: {m: metrics([r for r in M if lo <= int(r["n_actors"]) <= hi], m) for m in ["PAL v2.3", "Rule k3", "PAL-v1 (Phase 3)"]}
                        for k, (lo, hi) in bands.items()}
N["main"]["by_class_cov"] = {c: {m: metrics([r for r in M if r["claim_cls"] == c], m)["cov"] for m in ["PAL v2.3", "Rule k3"]} for c in ("car", "motorcycle")}
N["main"]["by_weather_cov"] = {w: {m: metrics([r for r in M if r["weather"] == w], m)["cov"] for m in ["PAL v2.3", "Rule k3"]} for w in ("clear", "rain", "fog")}
nb = [r for r in M if r["genuine"] != "True" and r["empty"] != "True"]
N["main"]["neither_verdicts"] = {m: {v: sum(r[m] == v for r in nb) for v in ("SUPPORTED", "INCONCLUSIVE", "REFUTED")} for m in ["PAL v2.3", "Rule k3", "ObjList-best v2.1"]}
N["main"]["enriched_share"] = sum(r["violation_detected"] == "True" for r in M) / len(M)
# ---------------- stress sets (exploratory: conditions chosen where the persistence-only baseline had failed)
N["confirm"] = {}
for tag in ("confirm-rcs-9", "confirm-degraded"):
    C = add_comb(rows(os.path.join(R73, f"{tag}.csv")))
    ms = ["PAL v2.3", "Rule k3", COMB, "Rule k3 no-moto-rule", "ObjList-best v2.1", "v2.3 no bound", "PAL v2.3 conservative bound (exploratory)", "PAL-v1 (Phase 3)"]
    d = {m: metrics(C, m) for m in ms}
    for other in ("Rule k3", "ObjList-best v2.1", "v2.3 no bound"):
        d[f"WR mcnemar PAL v2.3 vs {other}"] = dict(zip(["only_formal", "only_other", "p"], mcn([REF("PAL v2.3")(r) for r in G(C)], [REF(other)(r) for r in G(C)])))
    d["ObjList WR by class"] = {c: sum(REF("ObjList-best v2.1")(r) for r in G(C) if r["claim_cls"] == c) for c in ("car", "motorcycle")}
    N["confirm"][tag] = d
# ---------------- sweeps
import run_phase7 as p7
sw = {}; pool = {m: [0, 0, 0, 0] for m in ["PAL v2.3", "Rule k3", "ObjList-best v2.1", "v2.3 no bound", "PAL-v1 (Phase 3)"]}
for tag, _ in p7.SWEEPS:
    S = rows(os.path.join(R73, f"{tag}.csv")); sw[tag] = {m: metrics(S, m) for m in pool}
    for m in pool:
        x = sw[tag][m]; pool[m][0] += x["WR"]; pool[m][1] += x["n_gen"]; pool[m][2] += x["WS"]; pool[m][3] += x["n_emp"]
N["sweeps"] = {"per_condition": sw, "pooled": {m: dict(zip(["WR", "n_gen", "WS", "n_emp"], v)) for m, v in pool.items()},
               "nominal-1000": {m: metrics(rows(os.path.join(R73, "nominal-1000.csv")), m) for m in pool}}
# ---------------- pre-registered test, boundary
N["prereg"] = json.load(open(os.path.join(R73, "prereg_analysis.json")))
Bd = rows(os.path.join(R73, "boundary-far-edge.csv"))
N["boundary"] = {m: metrics(Bd, m) for m in ["PAL v2.3", "Rule k3", "ObjList-best v2.1", "v2.3 no bound"]}
N["boundary"]["PAL v2.1"] = json.load(open(os.path.join(B3, "boundary_v21.json")))
# ---------------- batch 3
R6 = rows(os.path.join(B3, "r6_bound_vs_sim.csv")); N["bound_vs_sim"] = {}
for cond in sorted({r["cond"] for r in R6}):
    x = [r for r in R6 if r["cond"] == cond and r["genuine"] == "True"]
    N["bound_vs_sim"][cond] = {"n": len(x), "expected": sum(float(r["bound"]) for r in x), "observed": sum(r["all_free"] == "True" for r in x),
                               "observed_moto": sum(r["all_free"] == "True" and r["cls"] == "motorcycle" for r in x)}
R9 = rows(os.path.join(B3, "r9_attacks.csv")); N["attacks"] = {}
for at in sorted({r["attack"] for r in R9}):
    x = [r for r in R9 if r["attack"] == at]
    N["attacks"][at] = {m: metrics(x, m) for m in ["PAL v2.3", "PAL v2.3 no liveness", "Rule k3", "ObjList-best v2.1 no liveness", "ObjList-best v2.1"]}
txt = open(os.path.join(B3, "r20_result.txt")).read()
N["integrity"] = {"verdict_identical": [int(x) for x in re.search(r"identical after disclosure\+verification: (\d+)/(\d+)", txt).groups()],
                  "attacks": json.loads(txt[txt.index("{"):]),
                  "disclosure_enriched_median_B": int(re.search(r"rate 10.0 Hz: .*?median (\d+)", txt).group(1)),
                  "disclosure_base_median_B": int(re.search(r"rate 2.0 Hz: .*?median (\d+)", txt).group(1)),
                  "storage_per_hour_base_B": int(re.search(r"storage per hour, base: (\d+)", txt).group(1)),
                  "enriched_event_B": int(re.search(r"enriched 20 s event: (\d+)", txt).group(1))}
json.dump(N, open(os.path.join(H, "numbers_rev2.json"), "w"), indent=1, default=float)
print("ok")
