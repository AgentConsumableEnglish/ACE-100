# Paper source — Experiment 1

`paper.md` is the preprint source for Experiment 1. Its YAML front matter names
the experiment it draws on, its status, and the tag that pins it for citation.
Render with pandoc, e.g.:

    pandoc paper.md -o paper.pdf --pdf-engine=xelatex -V geometry:margin=1.1in

Status: complete, tagged `paper-exp1-v1`. Numbers trace to
`../../experiments/exp1/analysis/summary.json` and
`../../experiments/exp1/audit/`; figures for the camera-ready regenerate from
`../../experiments/exp1/analysis/figures/`.

A later paper citing this one cites the tag for arguments and the experiment's
`analysis/summary.json` for any number it restates, so a correction to the data
follows through.
