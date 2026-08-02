# ACE-100 evaluation research

Empirical evaluation of the ACE-100 kit against its stated goals: does adopting
the kit reduce LLM-agent cost without degrading work quality? Each experiment is
pre-registered and owns its plan; each reports in its own paper.

This tree is development material: excluded from kit governance (`.ace-ignore`)
and from the release (`meta/publish.sh`).

## Layout

| Path | Purpose |
|---|---|
| `lib/` | The shared pipeline, used by every experiment. Tools take `--experiment-dir` (or `$ACE_EXPERIMENT_DIR`) and have no default. |
| `experiments/<id>/` | One directory per experiment: `PREREGISTRATION.md`, `experiment.json`, `manifest.json`, committed `audit/` and `analysis/`, gitignored `data/`, `arms/`, `repo/`. |
| `papers/<id>/` | One paper per experiment. Front matter names the experiments it draws on, its status, and its citation tag. |
| `REPLICATION.md` | Step-by-step reproduction, and how artifact provenance works. |
| `OPEN-QUESTIONS.md` | The register of unsettled claims, `OQ-N`. A preregistration cites the question it answers. |

Experiments and papers are separate trees on purpose. An experiment's artifacts
are provenance-stamped outputs a replicator re-derives; a paper is argued prose
that gets revised, tagged, and cited after the numbers are frozen.

## Current state

| Experiment | State | Paper |
|---|---|---|
| `exp1` | Complete. Realistic tasks sampled from merged-PR history. | `papers/exp1/`, tagged `paper-exp1-v1` |
| `exp2` | Registered; not yet run. Tasks where documentation is load-bearing. | none yet |

## Order of operations for a new experiment

1. Write `experiments/<id>/PREREGISTRATION.md` and commit it before any run.
   Record the target repository as an amendment there.
2. `lib/select_tasks.py` — before any arm is built (temporal firewall).
3. Build arms, run gates, stamp commit hashes.
4. Runs, evaluation, analysis.
5. Write `papers/<id>/paper.md`; tag it when it is final.
