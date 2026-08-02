# ACE-100 evaluation experiment

Empirical evaluation of the ACE-100 kit against its stated goals: does adopting the
kit reduce LLM-agent cost without degrading work quality? Governed by
[PREREGISTRATION.md](PREREGISTRATION.md) — read that first; it fixes the hypotheses,
thresholds, and procedures, and any deviation requires a logged amendment there.

This tree is development material: excluded from kit governance (`.ace-ignore`) and
from the release (`meta/publish.sh`).

## Layout

| Path | Purpose |
|---|---|
| `PREREGISTRATION.md` | The registered plan. Committed before repo selection or any run. |
| `tools/select_tasks.py` | Mechanical task selection from merged-PR history (§4 of the plan). Needs an authenticated `gh`. |
| `tools/` (planned) | `build_arms`, `run_cell` + scheduler, `evaluate`, `analyze` — see §9 of the plan. |
| `manifest.json` (generated) | Task manifest with per-task base commits, prompts, and audit log. |
| `data/` (gitignored) | Raw run artifacts: transcripts, diffs, judge outputs. Published as a release asset; the repo keeps hashes only. |

## Order of operations

1. Choose the target repository against §3 criteria; record the choice as a
   pre-registration amendment.
2. `tools/select_tasks.py` — before any arm is built (temporal firewall, §4).
3. Build arms, run gates (§2), stamp commit hashes.
4. Runs (§5), evaluation (§6), analysis (§7).
