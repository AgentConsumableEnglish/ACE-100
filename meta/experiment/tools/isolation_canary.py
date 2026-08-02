#!/usr/bin/env python3
"""Assert that a run workspace cannot reach the task's solution.

Experiment 1 asserted isolation in prose and never tested it. Its network-off
claim was false (Bash had unrestricted egress) and, more seriously, every
workspace shared a git object store with a full clone, so each task's
reference merge commit was reachable from inside the workspace. The sweep in
audit/network-sweep.json found 28 of 96 runs reaching solution content
through one channel or the other.

This canary converts "isolated" from an assumption into a precondition. It is
designed to FAIL against the Experiment 1 workspace scheme and PASS against
the hardened one, so running it both ways demonstrates the fix rather than
asserting it.

Local checks (meaningful anywhere):
  L1  the reference merge commit is not a known object
  L2  the base commit's descendants are unreachable
  L3  history contains exactly the synthetic baseline commit
  L4  no remote is configured (so `git fetch` has nowhere to go)
  L5  cherry-picking the reference solution fails

Network checks (--network; meaningful only inside the sandboxed container):
  N1  github.com unreachable
  N2  api.github.com unreachable
  N3  raw.githubusercontent.com unreachable
  N4  the Go module proxy IS reachable (dependency work must still be possible)

Exit code 0 only when every selected check passes.

Usage:
  isolation_canary.py --workspace WS --merge-sha SHA [--base-sha SHA] [--network]
  isolation_canary.py --self-test --manifest manifest.json   # both schemes
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def sh(cmd: list, cwd=None, timeout=60) -> tuple:
    """Run a command; return (rc, stdout+stderr). Never raises."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except (OSError, ValueError) as exc:
        return 127, str(exc)


class Canary:
    def __init__(self):
        self.results = []

    def check(self, cid: str, desc: str, ok: bool, detail: str = "") -> None:
        self.results.append({"id": cid, "description": desc, "pass": bool(ok),
                             "detail": detail[:300]})

    @property
    def failed(self):
        return [r for r in self.results if not r["pass"]]

    def report(self, label: str) -> bool:
        print(f"\n=== isolation canary: {label} ===")
        for r in self.results:
            mark = "PASS" if r["pass"] else "FAIL"
            print(f"  [{mark}] {r['id']}  {r['description']}")
            if not r["pass"] and r["detail"]:
                print(f"         {r['detail'].splitlines()[0][:160]}")
        n_bad = len(self.failed)
        print(f"  -> {len(self.results) - n_bad}/{len(self.results)} passed")
        return n_bad == 0


def local_checks(c: Canary, ws: Path, merge_sha: str, base_sha: str = "") -> None:
    # L1 the solution commit must not be a knowable object
    rc, out = sh(["git", "-C", str(ws), "cat-file", "-t", merge_sha])
    c.check("L1", f"reference merge {merge_sha[:12]} is not a known object",
            rc != 0, out)

    # L2 nothing after the base commit is reachable
    rc, out = sh(["git", "-C", str(ws), "rev-list", "--all", "--count"])
    n_commits = out.strip() if rc == 0 else "?"
    c.check("L3", f"history is a single synthetic baseline commit (found {n_commits})",
            rc == 0 and out.strip() == "1", out)

    if base_sha:
        rc, out = sh(["git", "-C", str(ws), "cat-file", "-t", base_sha])
        c.check("L2", f"upstream base commit {base_sha[:12]} is not a known object "
                      "(workspace history is synthetic)", rc != 0, out)

    # L4 no remote: `git fetch` must have nowhere to go
    rc, out = sh(["git", "-C", str(ws), "remote", "-v"])
    c.check("L4", "no git remote is configured", rc == 0 and not out.strip(), out)

    # L5 the direct exploit found in Experiment 1
    rc, out = sh(["git", "-C", str(ws), "cherry-pick", "-n", merge_sha])
    if rc == 0:
        sh(["git", "-C", str(ws), "cherry-pick", "--abort"])
        sh(["git", "-C", str(ws), "reset", "--hard"])
    c.check("L5", "cherry-picking the reference solution fails", rc != 0, out)


def network_checks(c: Canary) -> None:
    blocked = [("N1", "https://github.com"),
               ("N2", "https://api.github.com"),
               ("N3", "https://raw.githubusercontent.com")]
    for cid, url in blocked:
        rc, out = sh(["curl", "-sS", "--max-time", "12", "-o", "/dev/null", url])
        c.check(cid, f"{url} is unreachable", rc != 0, out)

    rc, out = sh(["curl", "-sS", "--max-time", "25", "-o", "/dev/null",
                  "https://proxy.golang.org/github.com/pkg/errors/@v/list"])
    c.check("N4", "Go module proxy IS reachable (dependency work still possible)",
            rc == 0, out)


def self_test(manifest_path: Path) -> int:
    """Demonstrate the fix: run the canary against both workspace schemes.

    Requires the Experiment 1 clone and arm snapshots to be present. Produces
    no subject-model runs and writes nothing into the data layout.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import run_cell  # noqa: E402

    manifest = json.load(open(manifest_path))
    task = manifest["tasks"][0]
    base = task["base_commit"]
    merge = REFERENCE_MERGES.get(task["task_id"])
    if not merge:
        print(f"no reference merge recorded for {task['task_id']}", file=sys.stderr)
        return 2
    corpus = json.load(open(run_cell.EXPERIMENT_DIR / "arms" /
                            "corpus-manifest.json"))["files"]

    print(f"self-test on {task['task_id']} (base {base[:12]}, "
          f"reference merge {merge[:12]})")
    overall = []
    for mode in ("worktree", "isolated"):
        ws = run_cell.materialize_workspace(base, "original", corpus, mode=mode)
        c = Canary()
        local_checks(c, Path(ws), merge, base)
        ok = c.report(f"{mode} scheme")
        overall.append((mode, ok))
        run_cell.cleanup_workspace(Path(ws))

    print("\n=== summary ===")
    for mode, ok in overall:
        print(f"  {mode:10} {'isolated' if ok else 'LEAKS'}")
    expected = dict(overall).get("worktree") is False and \
        dict(overall).get("isolated") is True
    print("\nexpected outcome (worktree LEAKS, isolated passes): "
          f"{'CONFIRMED' if expected else 'NOT CONFIRMED'}")
    return 0 if expected else 1


# Reference merge commits per task, resolved from the evaluation metadata.
REFERENCE_MERGES = {
    "pr-14461": "85daf49c69632452af6dad67c4f529e4ccf17d9a",
    "pr-14690": "41f564ce376cb837123b17b9145cd14537ba74c2",
    "pr-14985": "efde8a253d80453156e4de80308576bd3876c7d3",
    "pr-15108": "2854c982703e3832ff2866e3a8fd3ed9c904fca4",
    "pr-15307": "dbd5c55bf7ce728eae7d9d98146037d1aa795674",
    "pr-15495": "3e8f5a9f6f25e7d068fd834a5ce5756369c78a5c",
}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace")
    ap.add_argument("--merge-sha")
    ap.add_argument("--base-sha", default="")
    ap.add_argument("--task", help="look the merge sha up by task id")
    ap.add_argument("--network", action="store_true",
                    help="also run egress checks (use inside the container)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--manifest",
                    default=str(Path(__file__).resolve().parent.parent / "manifest.json"))
    ap.add_argument("--json-out")
    args = ap.parse_args()

    if args.self_test:
        return self_test(Path(args.manifest))

    merge = args.merge_sha or REFERENCE_MERGES.get(args.task or "")
    c = Canary()
    if args.workspace:
        if not merge:
            print("need --merge-sha or a --task with a known reference merge",
                  file=sys.stderr)
            return 2
        local_checks(c, Path(args.workspace), merge, args.base_sha)
    if args.network:
        network_checks(c)
    if not c.results:
        print("nothing to check: pass --workspace and/or --network", file=sys.stderr)
        return 2

    ok = c.report(args.workspace or "network only")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"checks": c.results, "all_passed": ok}, indent=2) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
