# Paper source

`paper.md` is the preprint source (one paper covering both experiments;
Experiment 2 sections are marked pending). Render with pandoc, e.g.:

    pandoc paper.md -o paper.pdf --pdf-engine=xelatex -V geometry:margin=1.1in

Status: Experiment 1 sections complete except the blinded-judge results
(marked *pending*; land after `evaluate.py judge` runs) and the Experiment 2
slots. Numbers trace to `../analysis/summary.json` and `../audit/`; figures
for the camera-ready regenerate from `../analysis/figures/`.
