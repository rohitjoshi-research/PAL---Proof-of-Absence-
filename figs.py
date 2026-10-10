"""All data figures of the paper, drawn from the result files (no typed numbers).
Outputs (vector PDF): fig_pie.pdf, fig_degr.pdf, fig_errcov.pdf, fig_calib.pdf.
Palette: reference categorical slots (blue, orange, aqua, yellow) in fixed order; ink and grid tokens."""
import csv, json, os, sys
import matplotlib
import matplotlib.ticker
matplotlib.use("pdf")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("PAL_ROOT", os.path.join(HERE, ".."))          # package root (results73/, batch3/)
R73, B3 = os.path.join(ROOT, "results73"), os.path.join(ROOT, "batch3")
OUT = os.environ.get("PAL_FIGDIR", HERE)                                   # where the PDFs are written
META = {"CreationDate": None}                                               # deterministic PDF bytes
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"         # categorical slots 1-4
S5, S7 = "#e87ba4", "#4a3aa7"                                       # slot 5 magenta = genuine claims / misses; slot 7 violet reserved for "standard refutation"
GRAY_D, GRAY_L = "#898781", "#c3c2b7"
sys.path.insert(0, ROOT)
from method import EPS                                                # operating point of the formal tier
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({"font.family": "serif", "font.serif": ["TeX Gyre Termes", "Times New Roman", "DejaVu Serif"],
                     "mathtext.fontset": "stix", "font.size": 8, "pdf.fonttype": 42, "axes.edgecolor": AXIS,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False})
rows = lambda p: list(csv.DictReader(open(p)))
G = lambda R: [r for r in R if r["genuine"] == "True"]
E = lambda R: [r for r in R if r["empty"] == "True"]


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, lw=0.5); ax.set_axisbelow(True)


# ---------------------------------------------------------------- Fig. pie: composition of the main benchmark
def fig_pie():
    sys.path.insert(0, ROOT)
    import numpy as np, sim, run_phase7 as p7
    M = rows(os.path.join(R73, "main.csv"))
    nb = [r for r in M if r["genuine"] != "True" and r["empty"] != "True"]
    smaller = 0
    for r in nb:                                  # re-derive the cause of "neither" from the scene itself
        i = int(r["scene"]); sim.PARAMS.clear(); sim.PARAMS.update(json.loads(json.dumps(p7.NOMINAL_SIM)))
        sc = sim.make_scene(np.random.default_rng(7_000_000 + i)); c = sc.claim; rear = -sim.EGO_L / 2
        for a in sc.actors:
            gap = rear - (a.s(0) + a.dims[0] / 2)
            if c["gap_min"] <= gap <= c["gap_max"] and abs(a.l - c["lane_offset"]) <= 1.0 and sim.CLASS_RCS[a.cls] < sim.CLASS_RCS[c["cls"]]:
                smaller += 1; break
    parts = [("Genuine", len(G(M)), S5), ("Empty zone (fabricated)", len(E(M)), INK2),
             ("Neither: partial/off-time overlap", len(nb) - smaller, GRAY_D), ("Neither: smaller vehicle", smaller, GRAY_L)]
    fig = plt.figure(figsize=(3.45, 1.1)); ax = fig.add_axes([0.0, 0.02, 0.28, 0.96])
    vals = [p[1] for p in parts]
    wedges, _ = ax.pie(vals, colors=[p[2] for p in parts], startangle=90, counterclock=False,
                       wedgeprops=dict(edgecolor="white", linewidth=1.2))
    ax.axis("equal")
    from decimal import Decimal, ROUND_HALF_UP
    pct = lambda n: Decimal(100 * n) / Decimal(len(M))
    labels = [f"{p[0]}: {p[1]:,} ({pct(p[1]).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}%)" for p in parts]
    fig.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.29, 0.5), frameon=False, fontsize=8, handlelength=1.0, handletextpad=0.5)
    fig.savefig(os.path.join(OUT, "fig_pie.pdf"), metadata=META)
    return dict(genuine=len(G(M)), empty=len(E(M)), partial=len(nb) - smaller, smaller=smaller)


# ---------------------------------------------------------------- Fig. degradation: coverage per condition
def fig_degr():
    sys.path.insert(0, ROOT)
    import run_phase7 as p7
    conds = [("nominal-1000", "Nominal")] + [(t, t) for t, _ in p7.SWEEPS]
    names = {"rcs-3": "Returns −3 dB", "rcs-6": "Returns −6 dB", "rcs-9": "Returns −9 dB", "fade6": "Fade σ 6 dB",
             "fade8": "Fade σ 8 dB", "ghost0.1": "Ghost rate 0.1", "ghost0.3": "Ghost rate 0.3", "blockage": "Blockage",
             "misalign": "Misalignment", "clock0.3": "Clock σ 0.3 s", "pose-noise": "Pose noise", "dense": "Dense traffic",
             "degraded": "Combined"}
    meth = [("Rule k3", "Rule tier", S1), ("PAL v2.3", "Formal tier", S2), ("ObjList-best v2.1", "Persistence-only baseline", GRAY_D)]
    data = []
    for tag, lab in conds:
        R = rows(os.path.join(R73, f"{tag}.csv")); e, g = E(R), G(R)
        data.append((names.get(tag, lab), [(100 * sum(r[m] == "REFUTED" for r in e) / len(e), sum(r[m] == "REFUTED" for r in g)) for m, _, _ in meth]))
    fig, ax = plt.subplots(figsize=(3.45, 3.95))
    h = 0.26
    for j, (m, lab, col) in enumerate(meth):
        ys = [i + (j - 1) * h for i in range(len(data))]
        ax.barh(ys, [d[1][j][0] for d in data], height=h - 0.03, color=col, label=lab)
        for y, d in zip(ys, data):
            wr = d[1][j][1]
            if wr:
                ax.text(d[1][j][0] + 1, y, f"{wr} WR", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(data))); ax.set_yticklabels([d[0] for d in data]); ax.invert_yaxis()
    ax.set_xlim(0, 112); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xlabel("Coverage of fabricated claims (%)")
    grid(ax, "x")
    ax.legend(loc="upper center", bbox_to_anchor=(0.38, -0.09), ncol=2, frameon=False, fontsize=8, handlelength=1.0, columnspacing=0.8)
    fig.tight_layout(pad=0.2); fig.savefig(os.path.join(OUT, "fig_degr.pdf"), metadata=META)
    return data


# ---------------------------------------------------------------- Fig. error-coverage (pre-registered test)
def fig_errcov():
    d = json.load(open(os.path.join(R73, "prereg_analysis.json")))
    f = d["curve_formal"]; r = {x["rule"]: x for x in d["curve_rule"]}
    fig, ax = plt.subplots(figsize=(3.45, 2.6))
    ax.plot([100 * p["coverage"] for p in f], [p["WR"] for p in f], "-o", color=S2, ms=3.8, lw=1.5, label=r"Formal tier, $\varepsilon$ swept")
    used = [p for p in f if p["eps"] == EPS][0]
    ax.plot(100 * used["coverage"], used["WR"], "D", mfc=S2, mec=INK, mew=0.9, ms=6.5, zorder=5)
    ax.annotate(r"$\varepsilon=10^{-3}$ (used)", (100 * used["coverage"], used["WR"]), textcoords="offset points", xytext=(8, -15),
                ha="left", va="center", fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6, shrinkA=0, shrinkB=3))
    for p in f:
        lab = {1e-1: r"$10^{-1}$", 1e-6: r"$10^{-6}$"}.get(p["eps"])   # eps values of the sweep in prereg_analysis.json
        if lab:
            off = {1e-1: (-4, 3), 1e-6: (3, 5)}[p["eps"]]
            ax.annotate(lab, (100 * p["coverage"], p["WR"]), textcoords="offset points", xytext=off,
                        ha="right" if off[0] < 0 else "left", fontsize=8, color=INK2)
    pts = [("Rule k3", "Rule tier", "o", S1, (7, 0), "left"),
           ("Rule k3 no-moto-rule", "Rule tier without\nmotorcycle rule: ", "o", "white", (0, -17), "center"),
           ("ObjList-best v2.1", "Persistence-only baseline", "o", GRAY_D, (-7, 0), "right")]
    for key, lab, mk, face, off, ha in pts:
        x = r[key]; edge = GRAY_D if key.startswith("ObjList") else S1
        ax.plot(100 * x["coverage"], x["WR"], mk, mfc=face, mec=edge, mew=1.4, ms=6)
        txt = f"{lab}{x['WR']}" if lab.endswith(": ") else f"{lab}: {x['WR']}"
        ax.annotate(txt, (100 * x["coverage"], x["WR"]), textcoords="offset points", xytext=off, ha=ha, va="center", fontsize=8)
    ax.set_yscale("symlog", linthresh=1); ax.set_ylim(-0.3, 150)
    ax.set_yticks([0, 1, 5, 10, 30, 100]); ax.set_yticklabels(["0", "1", "5", "10", "30", "100"])
    ax.set_xlim(20, 100)
    ax.set_xlabel("Coverage of fabricated claims (%)"); ax.set_ylabel(f"Wrong refutations (of {d['n_genuine']:,})")
    grid(ax, "both"); ax.legend(loc="lower right", frameon=False, fontsize=8)
    fig.tight_layout(pad=0.3); fig.savefig(os.path.join(OUT, "fig_errcov.pdf"), metadata=META)


# ---------------------------------------------------------------- Fig. bound calibration (three panels)
def fig_calib():
    R = rows(os.path.join(B3, "r6_bound_vs_sim.csv"))
    order = [("matched", "Matched"), ("fade6", "Fade σ\n4→6 dB"), ("rcs-6", "Returns\n−6 dB"),
             ("rcs-9", "Returns\n−9 dB"), ("rcs-6-fade6", "−6 dB,\nσ 6 dB")]
    panels = [("motorcycle claims", lambda r: r["cls"] == "motorcycle"),
              ("car claims", lambda r: r["cls"] == "car"),
              (r"bound $\leq\varepsilon$ (refutable)", lambda r: float(r["bound"]) <= EPS)]
    out = []
    fig, axs = plt.subplots(1, 3, figsize=(7.1, 2.4))
    for k, (ax, (title, sel)) in enumerate(zip(axs, panels)):
        exp_, obs, n = [], [], 0
        for c, _ in order:
            x = [r for r in R if r["cond"] == c and r["genuine"] == "True" and sel(r)]
            n = len(x); exp_.append(sum(float(r["bound"]) for r in x)); obs.append(sum(r["all_free"] == "True" for r in x))
        out.append((title, n, list(zip([o[0] for o in order], exp_, obs))))
        xs = range(len(order)); w = 0.38
        ax.bar([i - w / 2 for i in xs], exp_, width=w - 0.04, color=GRAY_D, label="Expected (sum of bounds)")
        ax.bar([i + w / 2 for i in xs], obs, width=w - 0.04, color=S5, label="Observed misses")
        top = max(max(exp_), max(obs), 1.0)
        small = max(exp_) < 1
        for i, e, o in zip(xs, exp_, obs):
            if not small:
                ax.text(i - w / 2, e + top * 0.02, f"{e:.1f}", ha="center", fontsize=7, color=INK2, va="bottom")
            ax.text(i + w / 2, o + top * 0.02, f"{o}", ha="center", fontsize=7.5, color=INK, va="bottom")
        if small:
            ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
            ax.text(0.03, 0.96, f"expected {max(exp_):.2f} per condition", transform=ax.transAxes,
                    ha="left", va="top", fontsize=7.5, color=INK2)
        ax.set_xticks(list(xs)); ax.set_xticklabels([o[1] for o in order], fontsize=7)
        ax.set_title(f"({'abc'[k]}) {title}, n = {n:,}", fontsize=8, color=INK2); ax.set_ylim(0, top * 1.3); grid(ax)
        ax.set_ylabel("Misses (count)")
    axs[0].legend(loc="upper left", frameon=False, fontsize=7.5)
    fig.tight_layout(pad=0.3, w_pad=0.5); fig.savefig(os.path.join(OUT, "fig_calib.pdf"), metadata=META)
    return out


if __name__ == "__main__":
    print("pie", fig_pie())
    d = fig_degr(); print("degr", [(n, [(round(c, 1), w) for c, w in v]) for n, v in d])
    fig_errcov()
    print("calib", fig_calib())
