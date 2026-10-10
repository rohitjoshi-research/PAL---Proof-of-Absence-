# Proof of Absence From Vehicle Radar

**Claim-driven, image-free evidence against delayed no-contact injury claims**

Rohit Joshi · personal research project · manuscript in preparation (2026)

> **PRIVATE draft.** Do not share or make this repository public before the patent decision and employer IP clearance.
> All results are from a ray-traced **simulation**; this is a research concept, not a product.

[![reproduce](../../actions/workflows/reproduce.yml/badge.svg)](../../actions/workflows/reproduce.yml)

---

## In one minute

| | |
|---|---|
| **Problem** | A driver crosses a solid line. Weeks later, someone files an injury claim: *"I was right behind you and braked hard."* There was no crash, so crash-triggered recorders stored nothing, and dashcam loops have long been overwritten. The driver has to prove a negative. |
| **Idea** | The car's own rear radars already watch that area. Keep a compact, signed record of **where the radar saw free space**, turn the later claim into a **zone and time window**, disclose **only that zone**, and refute the claim only when a vehicle there could not plausibly have been missed. |
| **Verdict** | SUPPORTED · REFUTED (standard) · REFUTED (weak) · INCONCLUSIVE · INVALID. INCONCLUSIVE is never evidence against the driver. |
| **Key results (simulated)** | No wrong verdict on 5,302 nominal claims; 68% (rule tier) and 54% (formal tier) of fabricated claims refuted; 0.020% wrong refutations when both tiers agree in a pre-registered test of 40,000 claims; 2.45 MB per driving hour and about 49 kB per disclosed claim. |
| **Main caveat** | Simulation only. The miss bound is too optimistic for weakly reflecting cars once the radar model is about 9 dB too optimistic, and the detection log used by the rule tier is not yet sealed. |

---

## 1. The problem

In early 2026, Hong Kong police reported a new pattern of traffic fraud. Claimants filmed drivers crossing a solid line, reported the violation, and later demanded compensation for neck injuries, alleging that they had braked suddenly behind the driver. By October 2026, police were investigating hundreds of suspicious cases. Related staged-collision schemes are prosecuted in the UK, Australia and the US.

The accused vehicle is poorly equipped to answer:

- **Event data recorders** and automated-driving data recorders save data around a trigger such as a crash. Without contact, there is no trigger.
- **Dashcams** overwrite their loop long before a delayed claim arrives, rarely see the area behind the car, and raise privacy concerns if kept longer.
- The driver must show that a vehicle was **not** in a specific place, yet modern cars already carry rear-corner radars that observe exactly that place.

**Research questions**

1. Can a vehicle refute delayed, no-contact position claims from its own radar data, without images, at practical storage and disclosure cost?
2. Which system components keep wrong refutations and wrong supports near zero?
3. Does an explicit bound on the probability of missing the claimed vehicle make fewer wrong refutations than detection rules under conditions neither was designed for?
4. Does the system resist a dishonest vehicle owner who manipulates sensors or the record?

---

## 2. How it works

![System architecture](docs/figures/fig_architecture.png)

**In the vehicle (continuous, no images)**

1. **Attestation and liveness.** A radar whose blockage flag is set or whose calibration residual exceeds 2° is excluded. So is a radar that reports nothing while its neighbor sees traffic in its field of view. An excluded sensor's space is *unknown*, never *free*.
2. **Enrichment.** When the car detects its own solid-line crossing (the trigger of the scam), the record switches from 2.5° sectors at 2 Hz to 1° sectors at 10 Hz for ±10 s.
3. **Free-space record.** For each sample and angular sector the car stores two bytes: how far the radar saw free space, whether that range ended in a return, a bearing bin, and how many healthy sensors covered the sector.
4. **Ledger.** Every 60 s the sector leaves are salted, hashed into a Merkle tree, chained to the previous block and signed (Ed25519). The latest block hash leaves the car once per hour as an anchor.

**After a claim (offline verifier)**

5. **Disclosure.** The owner discloses only the sectors of the claimed zone in the claimed window.
6. **Zone and window.** The verifier converts the claim (lane, gap range, class, time ± tolerance) into a road-frame zone and a clock-bounded window.
7. **Integrity and completeness.** It checks signatures, the hash chain to the anchor and the Merkle roots. It rejects the disclosure as INVALID if any sample, sector or block of the window is missing or repeated.
8. **Support, then two refutation tiers**, combined into a graded verdict:

![Verdict logic](docs/figures/fig_verdict.png)

- **Rule tier:** refute if healthy sensors covered the zone at every sample, no detection at all fell inside it, and the claimed vehicle is not a weak reflector. Motorcycle claims are never refuted.
- **Formal tier:** refute only if every sample saw the whole zone as free *and* a bound on the probability that a genuine claimant would have been missed is at most ε = 10⁻³. The bound uses the farthest zone range, the fewest covering sensors and the worst modeled weather, and it accounts for a fade that persists over the whole event.
- **Graded verdict:** both tiers refute → REFUTED (standard); one → REFUTED (weak), naming the tier; none → INCONCLUSIVE. A SUPPORTED from either tier overrides refutation.

---

## 3. What is new, and what is not

**Not new on its own:**
- continuous recording as evidence;
- free / occupied / unknown space and occlusion reasoning;
- the search-theory update after an unsuccessful search;
- checking a reported object against observed free space (V2X misbehavior detection);
- radar blockage detection by overlapping visibility;
- Merkle trees, signatures, anchoring and salted selective disclosure.

**The contribution** is the system that ties these to a **delayed, offline and adversarial third-party claim**:
- a road-frame zone derived from the claim;
- sensor health as a precondition for refutation;
- two refutation tiers in a graded verdict;
- sector-level selective disclosure whose **completeness** the verifier checks, so a negative claim can rest on proof that nothing was withheld.

It also contributes evidence, including a null result, on which parts actually carry the safety.

> The novelty statements are provisional. The patent search did not include a professional database or full-text Chinese, Japanese and Korean sources.

---

## 4. Results (all simulated)

A purpose-built 2-D simulator ray-traces three radars at 0.5° and 10 Hz around a lane change across a solid line. It covers traffic, an occluding van, weather, ghosts, blockage, misalignment, clock and pose errors. Only the simulator holds ground truth.

| Experiment | Outcome |
|---|---|
| Main benchmark, 6,000 scenes | Rule tier, formal tier and graded verdict: **0 wrong refutations, 0 wrong supports** on 3,461 genuine and 1,841 fabricated claims. Coverage of fabricated claims: rule tier **68.4%**, formal tier **53.7%**, both agree 50.5%. |
| Ablations | Removing the claim-derived zone, persistence or attestation produced wrong verdicts (Holm-adjusted p ≤ 9.9 × 10⁻⁵). |
| 13 degradation conditions | Rule and formal tiers: 0 wrong refutations. Coverage falls most with ghosts and misalignment. |
| **Pre-registered test**, 40,000 new scenes under 4 unseen degradations | Wrong refutations: rule tier 6, formal tier 5 of 24,993 genuine claims. The test could not separate the tiers (p = 1.0). When both agree: 5 wrong (**0.020%**, pooled 95% upper limit 0.047%); the 0.1% target was missed within 2 of the 4 conditions. Coverage: rule 71.2%, formal 43.8%. |
| Owner attacks | A silently covered radar caused 14–15 wrong refutations without liveness and **none with it**. A radar rotated just below the 2° limit still causes 4–6 wrong supports. |
| Ledger | Verdict identical after disclosure in 60/60 scenes; **8 of 8** edit, withholding and replay attacks detected. |
| Cost | Free-space record **2.45 MB per driving hour**; median **48.6 kB** per disclosed enriched claim with hourly anchoring. |

<p>
<img src="docs/figures/fig_errcov.png" width="49%" alt="Error versus coverage in the pre-registered test">
<img src="docs/figures/fig_degr.png" width="49%" alt="Coverage under 13 degradation conditions">
</p>

**Calibration of the miss bound against the simulator.** The bound held under the matched model. For cars, it was optimistic by more than an order of magnitude once returns were about 9 dB weaker than modeled: 3 misses against 0.08 expected.

![Calibration of the miss bound](docs/figures/fig_calib.png)

**Stress tests of the assumptions** (exploratory, run after all other results):

| Test | Formal tier | Rule tier |
|---|---|---|
| A truck outside the zone hides the claimed area | refuted none (abstains) | refuted 85.6% of hidden fabricated claims, 1 genuine |
| Claimant brakes and leaves the zone | 0 wrong refutations | 0 wrong refutations |
| Rear radar attenuated by 10 dB, no flag | 0 wrong refutations | 0 wrong refutations |
| Fades correlated over time (AR(1), ρ = 0.5, 0.9) | no miss (low power) | not tested |

**What carries the safety.** The two simple rules of the rule tier remove most wrong refutations: let any in-zone detection block refutation, and never refute a weak reflector. The formal tier abstains far more often. Its value is **auditability** (each refutation states the assumptions under which it could be wrong, plus a number) and **occlusion-awareness**: it refutes only space it actually observed.

---

## 5. Limitations

- **Simulation only:** 2-D, radar parameters assumed, no real sensor data, no baseline from the literature.
- **Bound optimism:** the bound is optimistic for weakly reflecting cars under about 9 dB of model error.
- **Detection log unsealed:** the rule tier's detection log is not yet integrity-protected. Its storage is only estimated, at 1.5–19 MB/h.
- **Development data:** the rule tier's two rules and one free-space clause were designed on development data. Only the pre-registered test is out-of-sample for both tiers.
- **Untested settings:** short claimed gaps (< 24 m), zones seen by one radar only, and real occluders and fading have not been tested.
- **Private pre-registration:** the pre-registration was recorded privately, not with an external registry.

The next steps are fitting the radar model to public radar datasets, a proving-ground campaign with soft targets, and a new pre-registered test with an external time stamp.

---

## 6. Repository

| Path | What it is |
|---|---|
| `sim.py`, `method.py`, `ledger_v2.py` | Simulator (ground truth), formal and rule tiers, integrity ledger |
| `run_v23.py`, `run_v23_bench.py`, `run_phase7.py` | Benchmark runners and conditions (`sim.py`, `method.py`, `run_v23.py`, `run_phase7.py` frozen for the pre-registered test) |
| `results73/`, `batch3/`, `round2/`, `round3/`, `validation/` | Per-scene results, calibration, attacks, ledger test, review analyses, stress tests, sanity checks |
| `analyze_prereg.py`, `make_numbers.py` | Regenerate every number in the paper |
| `notebooks/PAL_reproduce.ipynb` | One-click reproduction (Jupyter or Colab), about 4 minutes |
| `paper/` | IEEEtran LaTeX source, figures, compiled PDF |
| `video/` | Source of the explainer video, subtitles, voice-over script |
| `REPRODUCE.md` | Full reproduction guide: file-by-file table, re-run commands, seeds, GitHub and Colab instructions |

**Quick start**
```
pip install -r requirements.txt -r requirements-notebook.txt       # Python >= 3.12
jupyter nbconvert --to notebook --execute notebooks/PAL_reproduce.ipynb --output executed.ipynb
```
In Colab, open `notebooks/PAL_reproduce.ipynb` from this repository and follow the first cell. See `REPRODUCE.md`.

---

## 7. Citation, licence, disclosures

```
R. Joshi, "Proof of Absence From Vehicle Radar: Claim-Driven Evidence Against Delayed No-Contact Injury Claims,"
manuscript in preparation, 2026.
```

- **Licence:** code under MIT (`LICENSE`); data, figures and text under CC BY 4.0 (`LICENSE-DATA.md`).
- **Disclosures:** personal research, no funding. Views are the author's own. One component (the liveness test) overlaps an existing patent held by the author's employer, so employer IP clearance is required before publication.
- **AI use:** literature and patent search, code, analysis, reviews and drafting were assisted by an AI system (Claude, Anthropic). The author designed the study and is responsible for the content.
