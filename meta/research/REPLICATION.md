# Replicating these experiments

This tree holds pre-registered experiments evaluating the ACE-100 kit. Each
experiment owns its registration, config, and data; the tooling is shared and
versioned so a result can be traced to the exact code that produced it.

```
meta/research/
  lib/                     shared pipeline, used by every experiment
  experiments/<id>/        one directory per experiment
    PREREGISTRATION.md     binding; amendments appended, never rewritten
    experiment.json        target repo, seed, arms, caps, thresholds
    manifest.json          the sampled tasks
    audit/  analysis/      committed artifacts
    data/  arms/  repo/    gitignored; published as release assets
  paper/                   one paper covering all experiments
```

## Every artifact names the tooling that made it

Generated artifacts carry a `provenance` block:

```json
"provenance": {
  "tool": "analyze.py",
  "tooling_commit": "0e199e20cd332e78fd31c667db3f0525c7b00ed5",
  "repo_head_at_run": "0e199e20cd332e78fd31c667db3f0525c7b00ed5",
  "tooling_dirty": false,
  "generated_at": "2026-08-02T13:04:54+00:00"
}
```

`tooling_commit` is **the commit that last modified `meta/research/lib`** — the
revision to check out to reproduce that artifact. It is deliberately not the
repository HEAD: HEAD moves every time anything is committed (including the
artifact itself), whereas the lib commit is stable until the tools actually
change. `repo_head_at_run` is kept for forensics.

`tooling_dirty: true` means the artifact was produced from uncommitted tool
changes and **cannot** be reproduced from a commit hash alone. Treat any such
artifact as provisional.

Markdown artifacts carry the same information in a one-line header.

## Reproducing a published number

```sh
# 1. the tooling revision named by the artifact you want to reproduce
git checkout <tooling_commit>

# 2. point at the experiment
export ACE_EXPERIMENT_DIR="$PWD/meta/research/experiments/exp1"

# 3. fetch the raw run data (gitignored; see the release assets)
#    into $ACE_EXPERIMENT_DIR/data/

# 4. re-run. Analysis is deterministic: seeded bootstrap, sorted keys,
#    no timestamps in the numbers.
python3 meta/research/lib/analyze.py
python3 meta/research/lib/classify_turns.py
```

`summary.json` and `turn-decomposition.json` should match byte for byte once
the `provenance` block is removed (it records a fresh timestamp each run).

## Re-running collection

Collection is expensive and, for Experiment 1, **complete** — do not re-run it.
Its cells are recorded in `experiments/exp1/data/runs.jsonl`; the tools skip
completed cells.

```sh
export ACE_EXPERIMENT_DIR=.../experiments/exp1
export ACE_REPO_CLONE=$ACE_EXPERIMENT_DIR/repo/repo      # run_cell
export ACE_EXPERIMENT_REPO=$ACE_EXPERIMENT_DIR/repo/repo # evaluate
```

Note the two variables name the same clone but are read by different tools.

Costs are computed at **standard published prices**, not the introductory or
billed rates, so figures stay stable over time. The Batches API halves both
sides; judging cost is reported separately from subject-run cost and never
folded into a cost hypothesis.

## Isolation

Experiment 1's registered "network off" claim was false in two ways, both
documented in `experiments/exp1/audit/network-sweep.json` and the paper's
protocol-deviation section. Anyone re-running collection should use the
hardened path and verify it rather than assume it:

```sh
python3 meta/research/lib/isolation_canary.py --self-test
```

The canary is written to **fail** against the Experiment 1 workspace scheme
and pass against the hardened one, so running it demonstrates the fix instead
of asserting it.

## Adding an experiment

1. `mkdir experiments/<id>` with `PREREGISTRATION.md` and `experiment.json`.
2. Register **before** collecting. Amendments append; they never rewrite.
3. Run tools with `ACE_EXPERIMENT_DIR` pointing at the new directory. There is
   no default — a tool that guessed could write one experiment's numbers into
   another's tree.
4. Keep repo-specific settings in `experiment.json`, not in `lib/`. If a change
   to `lib/` is unavoidable, remember every prior artifact's `tooling_commit`
   still pins the old behaviour, so past results stay reproducible.
