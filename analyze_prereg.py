"""Analysis exactly as pre-registered (results73/PREREGISTRATION.json)."""
import csv, json, math, os
from math import comb
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "results73")
TAGS = ["G1-rcs-12", "G2-rcs-3-fade8", "G3-highspeed", "G4-rain-dense"]
def mcnemar(a, b):
    n01 = sum(x and not y for x, y in zip(a, b)); n10 = sum(y and not x for x, y in zip(a, b)); n = n01 + n10
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, j) for j in range(min(n01, n10) + 1)) / 2 ** n)
    return n01, n10, p
def wilson_upper(k, n, z=1.959964):
    p = k / n; d = 1 + z * z / n
    return (p + z * z / (2 * n) + z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
rows = {t: list(csv.DictReader(open(os.path.join(D, f"{t}.csv")))) for t in TAGS}
G = [r for t in TAGS for r in rows[t] if r["genuine"] == "True"]; E = [r for t in TAGS for r in rows[t] if r["empty"] == "True"]
F = lambda r: r["PAL v2.3"] == "REFUTED"; Rl = lambda r: r["Rule k3"] == "REFUTED"
out = {"n_genuine": len(G), "n_empty": len(E)}
a = [F(r) for r in G]; b = [Rl(r) for r in G]
n01, n10, p = mcnemar(a, b)
out["H1"] = {"formal_WR": sum(a), "rule_WR": sum(b), "only_formal": n01, "only_rule": n10, "p_exact_mcnemar": p}
std = sum(F(r) and Rl(r) for r in G)
out["H2"] = {"standard_WR": std, "wilson95_upper": wilson_upper(std, len(G)), "pass": wilson_upper(std, len(G)) < 1e-3}
def cov(f, S): return sum(f(r) for r in S) / len(S)
out["coverage"] = {"formal": cov(F, E), "rule": cov(Rl, E), "standard": cov(lambda r: F(r) and Rl(r), E), "weak_or_better": cov(lambda r: Rl(r) or F(r), E)}
out["wrong_supports"] = {"formal": sum(r["PAL v2.3"] == "SUPPORTED" for r in E), "rule": sum(r["Rule k3"] == "SUPPORTED" for r in E)}
out["per_condition"] = {}
for t in TAGS:
    g = [r for r in rows[t] if r["genuine"] == "True"]; e = [r for r in rows[t] if r["empty"] == "True"]
    out["per_condition"][t] = {"n_genuine": len(g), "n_empty": len(e),
        "formal_WR": sum(F(r) for r in g), "rule_WR": sum(Rl(r) for r in g),
        "formal_WR_by_class": {c: sum(F(r) for r in g if r["claim_cls"] == c) for c in ("car", "motorcycle")},
        "rule_WR_by_class": {c: sum(Rl(r) for r in g if r["claim_cls"] == c) for c in ("car", "motorcycle")},
        "formal_cov": cov(F, e), "rule_cov": cov(Rl, e), "objlist_best_WR": sum(r["ObjList-best v2.1"] == "REFUTED" for r in g)}
# secondary: error-coverage curves
def pal_eps(r, eps):
    if r["PAL v2.3"] == "SUPPORTED" or r["PAL v2.3 bound"] == "": return False
    return float(r["PAL v2.3 bound"]) <= eps
curve_f = []
for e_ in [1e-1, 3e-2, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 1e-5, 1e-6]:
    curve_f.append({"eps": e_, "WR": sum(pal_eps(r, e_) for r in G), "coverage": sum(pal_eps(r, e_) for r in E) / len(E)})
curve_r = []
for col in ["Rule k2", "Rule k3", "Rule k4", "Rule k5", "Rule k6", "Rule k3 no-moto-rule", "ObjList-best v2.1"]:
    curve_r.append({"rule": col, "WR": sum(r[col] == "REFUTED" for r in G), "coverage": sum(r[col] == "REFUTED" for r in E) / len(E)})
out["curve_formal"] = curve_f; out["curve_rule"] = curve_r
json.dump(out, open(os.path.join(D, "prereg_analysis.json"), "w"), indent=2)
print(json.dumps(out, indent=1))
