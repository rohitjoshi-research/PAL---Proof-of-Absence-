# PAL manuscript — IEEEtran LaTeX source (round-4 revision)

PRIVATE. Do not share before a patent decision and employer IP clearance.

The LaTeX files are the master copy (hand-maintained; the earlier Markdown converter is retired).

Build:

```
PAL_ROOT=<package folder> python3 figs.py     # draws fig_pie, fig_degr, fig_errcov, fig_calib from the result files
latexmk -pdf main.tex                          # pdflatex; IEEEtran, cite, algorithmicx, booktabs, tikz, xurl, needspace, flushend
```

| File | Content |
|---|---|
| main.tex | Preamble (palette colors, `\ifprivate` switch for the draft header), title, author, inputs |
| abstract.tex, keywords.tex | Abstract (≤ 250 words), index terms |
| (in body.tex) | Table II notation; Table VIII exploratory stress tests; Data and Code Availability; Acknowledgment (AI use). Funding and conflict of interest are in the first-page footnote (main.tex) |
| body.tex | Sections I–IX, Data and Code Availability, Acknowledgment |
| alg1.tex | Algorithm 1, verification of a claim |
| fig1.tex | Fig. 1, system architecture (TikZ) |
| fig_block.tex | Fig. 2, verdict logic (TikZ) |
| fig_pie.tex / .pdf | Fig. 3, composition of the main benchmark |
| fig_errcov.tex / .pdf | Fig. 4, error–coverage curves of the pre-registered test |
| fig_degr.tex / .pdf | Fig. 5, coverage under the 13 degradation conditions |
| fig_calib.tex / .pdf | Fig. 6, calibration of the miss bound by claimed class |
| refs.tex | 58 references in order of first citation, IEEE style, with access dates for online sources |

Color meaning (same in every figure): blue rule tier, orange formal tier, aqua detection log and ledger,
gray shared steps and neutral categories, violet standard refutation, yellow weak refutation,
magenta genuine claims and observed misses, red invalid, green supported.

Before submission
- Affiliation, ORCID (placeholders in main.tex).
- All references were checked online on Oct. 9, 2026. Still to confirm by hand: the author of [OR/MS Today 2017] (cited without author), the end pages of UN R155/R156 and of the GDPR (start pages cited).
- Length: 16 pages; check the current T-ITS page limit and overlength charges.
- Set `\privatefalse` in main.tex to remove the draft running head and footnote.
- Employer IP clearance and the patent decision (first-page footnote).
