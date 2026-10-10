# Proof of Absence — reproducibility package (v2.3.1)

> **PRIVATE.** Do not publish or share before the patent decision and employer IP clearance. Keep the GitHub
> repository **private** until then (a public repository, even briefly, is a public disclosure).
> The Zenodo and CITATION metadata are deliberately non-descriptive; keep any Zenodo deposit as an unpublished draft.

[![reproduce](../../actions/workflows/reproduce.yml/badge.svg)](../../actions/workflows/reproduce.yml)

## Put it on GitHub

```
cd PAL-proof-of-absence
gh repo create PAL-proof-of-absence --private --source . --push      # or: git remote add origin <url> && git push -u origin main
```

The workflow `.github/workflows/reproduce.yml` then checks the SHA-256 list and executes the notebook on every push
(about 5 minutes); a failing assertion fails the run.

## Run it in Colab

1. Open `https://colab.research.google.com/github/<user>/PAL-proof-of-absence/blob/main/notebooks/PAL_reproduce.ipynb`
   (replace `<user>`; Colab asks for GitHub access to open a private repository), or upload the notebook to Colab.
2. In the first cell, set `REPO_URL` to the repository (for a private repository:
   `https://<token>@github.com/<user>/PAL-proof-of-absence.git`, with a fine-grained read-only token), or leave it empty
   and upload this folder as a zip when asked.
3. Run all cells. If the first cell installs the pinned packages, it stops and asks you to restart the runtime
   (Runtime > Restart session); then run all cells again.

Code, simulated data and paper source for *Proof of Absence From Vehicle Radar: Claim-Driven Evidence Against Delayed
No-Contact Injury Claims* (R. Joshi, manuscript, round-4 revision). A vehicle answers a later claim ("a vehicle of class k
was in lane ℓ, g_min–g_max behind you, at time t") from its own radar data, without images: a zone and window derived from
the claim, attested sensors with a liveness test, a signed and selectively disclosable free-space record, and a graded
verdict from a rule tier and a formal tier with a miss-probability bound.

## Start here

Open `notebooks/PAL_reproduce.ipynb` in Jupyter (or in Colab, as above). In about 4 minutes it:

1. checks that the code matches the SHA-256 hashes frozen for the pre-registered test;
2. recomputes the numbers of the paper from the result files in a scratch copy and compares them byte for byte
   (`analyze_prereg.py`, `make_numbers.py`, `round2/analyses.py`, `round2/analyses_r3.py`; the stress tests and
   the timing are shown as shipped);
3. shows the pre-registered analysis (H1, H2), the paired interval, the calibration by class and the matched-coverage comparison;
4. regenerates 180 scenes from their seeds and compares the verdicts with the stored ones;
5. runs the integrity ledger with its eight attacks (3 scenes) and the simulator sanity checks V1–V5;
6. redraws the four data figures and compares them with the shipped PDFs;
7. deletes its scratch folder. **It does not modify any shipped file.**

Local: Python ≥ 3.12, `pip install -r requirements.txt` (and `requirements-notebook.txt` for Jupyter).
Tested with Python 3.13.16, numpy 2.5.3, cryptography 50.0.1, matplotlib 3.11.2; Python 3.11 with numpy 2.4 gave
bit-identical verdicts.

## Paper terms and code names

| Paper | Code / CSV column |
|---|---|
| formal tier | `method.PAL_V23`, column `PAL v2.3` (bound in `PAL v2.3 bound`); `formal` in `round3/` |
| rule tier (called a "stricter detection-log baseline" in the frozen `method.py` docstring) | `method.objlist_strict(..., no_moto=True)`, column `Rule k3` (`Rule k2`…`Rule k6`: persistence count swept); `rule` in `round3/` |
| rule tier without the motorcycle rule | column `Rule k3 no-moto-rule` |
| persistence-only baseline (reads the detection log) | `method.objlist_verdict(k_support=3, liveness=True, gate=1.0)`, column `ObjList-best v2.1`; `persistence_only` in `round3/` |
| graded verdict, standard (both tiers refute) | `Combined (formal and rule)` in `numbers_rev2.json` |
| conservative-model tier (exploratory, not proposed) | column `PAL v2.3 conservative bound (exploratory)` |
| early prototype | column `PAL-v1 (Phase 3)` |
| ablations | columns `v2.3 no …` |
| free-space record, ledger | `method.build_record`, `ledger_v2.py` |

## Contents

| Path | Content |
|---|---|
| `README.md`, `CHECKSUMS.sha256` | This file; SHA-256 of every shipped file (`sha256sum -c CHECKSUMS.sha256`) |
| `LICENSE`, `LICENSE-DATA.md`, `CITATION.cff`, `.zenodo.json` | MIT for code; CC BY 4.0 for data, figures and text; citation and (non-descriptive) archive metadata |
| `requirements.txt`, `requirements-notebook.txt` | Pinned Python packages; Jupyter for the notebook |
| `sim.py` | 2-D ray-traced radar simulator; **the only file holding ground truth** (frozen) |
| `method.py` | Formal tier, rule tier, baselines, ablations, miss bound (frozen) |
| `run_phase7.py` | Nominal parameters and the 13 degradation conditions (frozen; importing it creates an empty `results7/`) |
| `run_v23.py` | Runner: `prereg [N]`, `boundary [N]`, `main`, `sweeps`, `clockcheck [N]` (frozen; `main`/`sweeps` ignore N; writes `results73/DONE-<mode>`) |
| `run_v23_bench.py` | Runner for the two stress sets (`confirm [N]`); the shipped `confirm-*.meta.json` were written at packaging time, before this runner wrote them |
| `ledger_v2.py` | Integrity layer: HMAC-derived per-leaf salts, Merkle multiproofs, signed time ranges, hash chain, Ed25519, verifier with completeness and duplicate checks |
| `analyze_prereg.py` | Pre-registered analysis → `results73/prereg_analysis.json` |
| `make_numbers.py` | Main, ablation, degradation, stress-set, far-edge, calibration, attack and ledger numbers → `numbers_rev2.json` |
| `results73/` | Per-scene verdicts (CSV) with run metadata; `PREREGISTRATION.json` (frozen hashes, amendment); `prereg_analysis.json`; `clockcheck-clock0.3.*` is the 400-scene check behind the pre-freeze clock fix (`run_v23.py clockcheck 400`) |
| `batch3/r6_bound_vs_sim.*` | Calibration of the bound against the simulator |
| `batch3/r9_attacks.*` | Owner attacks (sub-threshold rotation, silent blockage) |
| `batch3/r20_integrity.py`, `r20_result.txt` | Ledger test: verdict equality after disclosure, eight attacks (asserted), storage and disclosure sizes |
| `batch3/r19_curves.py`, `r19_result.json` | Curved-road diagnosis of the ideal-sensor check (scene IDs from `validation/`) |
| `batch3/boundary_v21.json`, `review11/boundary_v21.py` | Earlier free test on the far-edge scenes |
| `validation/run_validation_v21.py`, `validation_v21.json` | Sanity checks V1–V5: known answers, ideal sensors vs geometric visibility, bound check, baseline independence, geometry round trip (v2.1 configuration) |
| `round2/analyses.py`, `analyses.json`, `timing.json` | Review statistics: paired interval, calibration bins, strategic claims, occlusion flags; verifier timing (wall clock, varies) |
| `round2/analyses_r3.py`, `analyses_r3.json` | Calibration by class, matched-coverage comparison, missed enrichment, claim lengths, chain cost |
| `round2/sens_eq6.py`, `method_sens.py`, `sens_eq6.json` | Sensitivity: no-return clause of eq. (6) tightened (copy of `method.py` with one line changed) |
| `round3/sim_x.py`, `stress_x.py`, `stress_x.csv`, `calib_x.csv`, `stress_x.json` | Exploratory stress tests: occluder outside the zone, braking claimant, 10 dB attenuation, time-correlated fades (copy of `sim.py` with four knobs, off by default; checked against `main.csv`) |
| `round3/log_cost.py`, `log_cost.json` | Storage estimate of the (unsealed) detection log |
| `compare_results.py` | Compares a re-run folder with the shipped result files (exit code 1 on any difference) |
| `paper/` | IEEEtran LaTeX source (`main.tex` is the master; `paper/README.md`), TikZ figures, `figs.py` (draws the four data figures), compiled `main.pdf` |
| `notebooks/PAL_reproduce.ipynb` | Reproduction notebook (asserts every reproduced number; the figure comparison is a soft check) |
| `.github/workflows/reproduce.yml`, `.gitignore` | Continuous check on GitHub (checksums + notebook); ignored build files |
| `video/` | Source of the explainer video (deterministic HTML animation, renderer, soundtrack), subtitles and voice-over script; see `video/README.md` |

## Re-running

Every script, including `paper/figs.py` and the LaTeX build, **overwrites** its shipped output without asking. Re-run in a copy and compare:

```
cp -r PAL-proof-of-absence rerun && cd rerun
python3 run_v23.py prereg            # or any command from the table in the notebook
python3 compare_results.py ../PAL-proof-of-absence .
```

Seeds: main 7,000,000 + i; degradation 8,000,000 + i; stress sets 10,000,000 + i; pre-registered 11,000,000 + i;
far edge 12,000,000 + i; attacks 13,000,000 + i; calibration 14,000,000 + i (also the correlated-fade calibration);
round-3 stress tests 15,000,000 + i. Ledger keys are seeded, so
`r20_result.txt` is byte-reproducible.

Paper: `cd paper && python3 figs.py && latexmk -pdf main.tex` (TeX Live 2023 or later, with IEEEtran, TikZ, algorithmicx,
booktabs, cite, xurl, needspace, flushend, newunicodechar). The build leaves `main.aux`, `.log`, `.fls` and `.fdb_latexmk` behind.

## Shown in code, simulated, assumed

- **Shown in code (on simulated records):** known-answer scenes and geometry round trip (`validation/`); verdict equality
  after selective disclosure; detection of eight edit, withholding and replay attacks on the free-space record.
- **Simulated:** every rate, count, interval and p-value.
- **Assumed:** all sensor parameters in `sim.PARAMS` (radar cross-sections about 10 dB below preliminary published values),
  fault rates, flag recall, log noise; the detection model of the bound (assumptions A1–A6 in the paper).
- **Not shown:** anything about real radar. No real sensor data, personal data or images are included.

## Known limitations (paper, Section VIII)

The detection log read by the rule tier is not integrity-protected (its storage is only estimated), and the rule tier
refuted unobserved zones in the occlusion stress test; the bound is optimistic for cars beyond
about 9 dB of model error; a radar rotated just below the 2° limit causes wrong supports; liveness uses the whole event
window; the rule tier and the far-edge clause were designed on development data; claimed gaps were 24–48 m long;
the pre-registration was recorded privately, not with an external registry.

## Licences and citation

Code: MIT (`LICENSE`). Data, figures and text: CC BY 4.0 (`LICENSE-DATA.md`). Cite via `CITATION.cff`.
ORCID, affiliation, DOI and release date are placeholders to fill at release.

*AI-use disclosure:* code, analysis and documentation were developed with the assistance of an AI system (Claude, Anthropic).
