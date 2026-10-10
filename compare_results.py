"""Compare the result files of a re-run folder with the shipped package: python3 compare_results.py SHIPPED RERUN
Prints same / DIFFERENT / MISSING (not re-run) for every .csv, .json and .txt result file; exits 1 on any difference.
round2/timing.json holds wall-clock times and always differs."""
import filecmp, os, sys
a, b = sys.argv[1], sys.argv[2]; bad = False
for d in ["results73", "batch3", "round2", "round3", "validation", "."]:
    for f in sorted(os.listdir(os.path.join(a, d))):
        if not f.endswith((".csv", ".json", ".txt")) or f.startswith(("requirements", ".zenodo", "CHECKSUMS")):
            continue
        pa, pb = os.path.join(a, d, f), os.path.join(b, d, f)
        state = "MISSING  " if not os.path.exists(pb) else ("same     " if filecmp.cmp(pa, pb, shallow=False) else "DIFFERENT")
        print(state, os.path.join(d, f)); bad = bad or state != "same     "
sys.exit(1 if bad else 0)
