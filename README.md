# Proof of Absence (PAL)

Claim-driven, image-free vehicle evidence against delayed no-contact injury claims.


## Status: read this first

This repository holds a method, a ray-traced simulation study, and a reproduction package. It does not hold a working product.

- No vehicle implementation, real radar recording, or real-world dataset exists yet.
- Every rate, count and interval comes from a 2-D ray-traced simulator. Its radar parameters are assumed.
- The video in `video/` is a concept explainer. Its news headlines are real and dated, but paraphrased, and the sources are shown on screen.
- The paper states its limits (Section VIII-H) and what real radar data must show next (Section VIII-I).
- Keep this repository **private** until the patent decision and employer IP clearance.

## The idea in four lines

A driver crosses a solid line; weeks later someone claims, "I was right behind you and braked hard". There was no crash, so no recorder kept anything.
PAL keeps a signed, image-free record of where the car's own radars saw **free space**, sector by sector.
From the claim, a verifier builds a road zone and time window, checks that nothing was withheld, and reads only that zone.
It refutes only when the zone was observed empty and a missed vehicle is unlikely (≤ 10⁻³). Otherwise it says INCONCLUSIVE, which is never evidence against the driver.

## What is in this repository

```
paper/
  main.pdf                       the paper (IEEE two-column format, 16 pages)
  *.tex, figs.py, fig_*.pdf      LaTeX source, TikZ figures, and the script that draws the data figures
notebooks/
  PAL_reproduce.ipynb            one-click reproduction: checks hashes, recomputes every number,
                                 regenerates scenes, runs the ledger attacks (Jupyter or Colab, ~4 min)
sim.py                           2-D ray-traced radar simulator (the only file holding ground truth)
method.py                        formal tier (miss bound), rule tier, baselines, ablations
ledger_v2.py                     sealed record: salted Merkle leaves, hash chain, Ed25519, completeness check
run_v23.py, run_v23_bench.py     benchmark runners (frozen for the pre-registered test)
analyze_prereg.py, make_numbers.py   regenerate the paper's numbers from the result files
results73/                       per-scene verdicts, pre-registration record with frozen code hashes
batch3/                          bound calibration, owner attacks, ledger test
round2/, round3/                 review analyses, sensitivity check, exploratory stress tests
validation/                      simulator sanity checks (known answers, geometry round trip)
video/                           explainer-video source, subtitles, voice-over script
docs/figures/                    the paper's figures as images
REPRODUCE.md                     full reproduction guide (every file, every command, every seed)
```

## Quick start

**Read the paper:** open `paper/main.pdf`.

**Run the notebook:** open `notebooks/PAL_reproduce.ipynb` in Google Colab and choose Runtime → Run all. In the first cell, set `REPO_URL`, or upload the repository zip when asked. No GPU is needed.

**Run it locally:**

```
pip install -r requirements.txt -r requirements-notebook.txt      # Python >= 3.12
jupyter nbconvert --to notebook --execute notebooks/PAL_reproduce.ipynb --output executed.ipynb
```

**Rebuild the paper:**

```
cd paper
python3 figs.py               # data figures from the result files
latexmk -pdf main.tex
```

This needs a LaTeX installation with the IEEEtran class, TikZ, algorithmicx, booktabs, xurl and flushend.

## Main contributions of the paper

1. A formulation of delayed, offline, adversarial position claims as a proof-of-absence problem, with a dishonest-owner threat model.
2. An evidence system:
   - a claim-derived road-frame zone;
   - sensor attestation and liveness;
   - a per-sector free-space record, densified around the car's own solid-line crossing;
   - a signed ledger that discloses only the zone and checks that nothing was withheld.
3. Two refutation tiers, detection rules and a miss-probability bound with three soundness propositions, combined into a graded verdict.
4. A simulation study:
   - ablations, 13 degradation conditions and owner attacks;
   - a ledger attack test and a calibration of the bound;
   - a pre-registered test on 40,000 claims;
   - exploratory stress tests of the assumptions.

## Findings worth knowing (all simulated, assumed radar parameters)

- **No wrong verdict on 5,302 nominal claims.** Of the fabricated claims, the rule tier refuted 68% and the formal tier 54%.
- **Pre-registered test (40,000 claims, unseen conditions):** wrong refutations were 6 (rule tier) and 5 (formal tier), and the test could not separate the tiers.
  - When both tiers agree, the wrong-refutation rate is 0.020%.
  - The 0.1% target was missed within 2 of the 4 conditions.
- **Two simple rules carry most of the safety:** any detection inside the zone blocks refutation, and motorcycle claims are never refuted.
- **Liveness matters under attack.** A silently covered radar caused 14–15 wrong refutations without the liveness check and none with it.
- **The formal tier's value is auditability and occlusion-awareness.** When a truck hid the zone, it refuted none of the hidden claims; the rule tier refuted 85.6%.
- **The miss bound is too optimistic for weakly reflecting cars** once the radar model is about 9 dB too optimistic: 3 misses against 0.08 expected.
- **The sealed record is cheap.** It costs 2.45 MB per driving hour and about 49 kB per disclosed claim, and all 8 tampering attacks were detected.
- **One part is not yet covered.** The detection log used by the rule tier is not sealed; it would add an estimated 1.5–19 MB per hour.

## How to cite

```
Joshi, R. (2026). Proof of Absence From Vehicle Radar: Claim-Driven Evidence Against
Delayed No-Contact Injury Claims. Manuscript in preparation.
```

GitHub also reads `CITATION.cff` to offer a "Cite this repository" button. A DOI will be added at release.

## Third-party content

The explainer video in `video/` shows paraphrased headlines from news outlets and official sources, for illustration. The sources and dates are listed on the video's sources card and in `video/src/data.js`. All rights remain with the publishers. The video and this repository use no logos or brand marks.

## Disclosures

**Funding:** none. This is independent research.

**Conflict of interest:**
- The author works in the automotive domain at a Tier 1 supplier.
- This is a personal research concept, carried out outside employment duties and without employer resources. It does not represent the position, product roadmap or intellectual property of that employer or of any company named in the patent review.
- One component, the sensor liveness test, overlaps a patent held by the author's employer, so clearance is required before publication.

## License

Code is licensed under MIT (`LICENSE`). Data, figures and text are licensed under CC BY 4.0 (`LICENSE-DATA.md`).
