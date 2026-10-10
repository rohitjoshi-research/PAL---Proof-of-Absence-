Proof of Absence From Vehicle Radar
Image-free vehicle evidence against delayed no-contact injury claims
Rohit Joshi · personal research project · manuscript in preparation (2026)
Private draft. Do not share or make public before the patent decision and employer IP clearance. All results come from simulation. This is a research concept, not a product.
Show Image
The problem
A driver crosses a solid line. Weeks later, an injury claim arrives: "I was right behind you and braked hard." There was no crash, so event recorders saved nothing, and dashcam loops are long overwritten. The driver must prove a negative: that no vehicle was there. In 2026, Hong Kong police investigated hundreds of such cases.
The idea
The car's rear radars already watch that area. So the car keeps evidence of empty space instead of video:
Record free space. For each angular sector, the car stores how far its radar saw clear road. That is two bytes, no images.
Trust only healthy sensors. A blocked, misaligned or silent radar is excluded. Its area counts as unknown, never free.
Seal the record. Every minute the data is salted, hashed into a Merkle tree, chained and signed. A fingerprint leaves the car every hour.
Turn the claim into a zone. The claimed lane, distance and time become a zone on the road and a time window.
Disclose only that zone. The verifier checks the signatures and that nothing was withheld or repeated.
Decide. Two independent tiers judge the zone:
Rule tier: the zone was fully covered, there was no detection inside it, and the claim is not about a motorcycle.
Formal tier: the zone was seen as free in every sample, and the chance of missing a real vehicle is at most 1 in 1,000.
Verdict	Meaning
SUPPORTED	A vehicle was seen in the zone
REFUTED (standard)	Both tiers refute
REFUTED (weak)	One tier refutes (named)
INCONCLUSIVE	The car could not decide; never evidence against the driver
INVALID	The disclosed record failed its integrity or completeness checks
Results (simulated)
Wrong verdicts on 5,302 nominal claims	0
Fabricated claims refuted	68% rule tier · 54% formal tier
Pre-registered test, 40,000 new claims	wrong refutations: rule 6, formal 5; when both agree 0.020%
Covered or silent radar (owner attack)	14–15 wrong refutations without the liveness check, 0 with it
Tampering attacks on the sealed record	8 of 8 detected
Storage · disclosure	2.45 MB per driving hour · about 49 kB per claim
Truck hiding the zone (stress test)	formal tier refuted 0% (correctly abstains); rule tier 85.6%
Takeaway. Two simple rules give most of the safety. The miss bound adds what rules lack: an auditable risk statement and refutation only of space the car actually observed.
Limitations
Simulation only: radar parameters are assumed and no real data was used.
The bound is too optimistic for weakly reflecting cars once the radar model is about 9 dB too optimistic.
The detection log used by the rule tier is not yet sealed.
Only the pre-registered test is fully out-of-sample.
Novelty is provisional until a professional patent search is done.
Repository
Path	Content
sim.py · method.py · ledger_v2.py	Simulator · verdict tiers · sealed ledger
results73/ · batch3/ · round2/ · round3/	Results, attacks, calibration, stress tests
notebooks/PAL_reproduce.ipynb	One-click reproduction, about 4 minutes (Jupyter or Colab)
paper/	LaTeX source and PDF
video/	Explainer video source
REPRODUCE.md	Full reproduction guide
pip install -r requirements.txt -r requirements-notebook.txt   # Python >= 3.12
jupyter nbconvert --to notebook --execute notebooks/PAL_reproduce.ipynb --output executed.ipynb
Citation · licence
R. Joshi, "Proof of Absence From Vehicle Radar: Claim-Driven Evidence Against Delayed No-Contact Injury Claims," manuscript in preparation, 2026.
Licence: code under MIT; data, figures and text under CC BY 4.0.
Views: personal views; no funding.
AI use: AI-assisted (Claude, Anthropic); the author is responsible for the content.
