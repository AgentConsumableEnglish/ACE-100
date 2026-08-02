#!/usr/bin/env python3
"""Uniform, all-channel recount of documentation consumption per run.

Registered by Experiment 1 Amendment 4 and revised by Amendment 5 (instrument
revision 2): the collection-time per-run counters (Read-tool-only) are
superseded by this analysis-time recount, applied identically to every run.

Revision 2 changes, each mandated by Amendment 5 and traceable to the per-run
doc-read audit archived at audit/doc-read-audit.json:

  * Arm-relative matching. A read counts when its path resolves to a file in
    that arm's own docs snapshot (arms/<arm>-docs), enumerated by the corpus
    rule (all *.md/*.mdx except CHANGELOG*, testdata/, .github/, node_modules/,
    LICENSE*). The original manifest matched only the original arm's 103 files
    and structurally undercounted the ace arm (205 files). The nodocs arm is
    matched against the union of all arms' paths with every event flagged
    absent_at_start (its workspace shipped no docs; content under such a path
    was created during the run, or the event is a false match).
  * Relative-path resolution: exact membership, or unambiguous >=2-component
    suffix match (reads issued below a `cd` defeat literal matching).
  * Attribution corrections: harness empty-output placeholder and error-only
    outputs count 0 chars; grep output is attributed per doc-path line prefix
    whenever more than one file could have produced it; compound-command
    output is split at echoed separator literals where present, else the
    mixed-command no-attribution rule stands; a doc named only as a find/ls
    -name pattern is not a read; in-place edits (sed -i) are not reads.
  * Channel additions: git show/diff/log, diff, and od invocations naming arm
    doc files; sidechain Bash commands (previously sidechain Read only).
  * Audited supplement: events hand-verified by the audit that path-based
    extraction cannot see (content laundered through temp copies, xargs
    sub-shells, python heredocs) are merged from audit/doc-read-audit.json
    with source="agent_audit" and tabulated separately; a supplement event
    supersedes the unattributed automatic event it re-measures. Web-channel
    audit events are excluded here: they belong to the Amendment-5 network
    sweep (audit/network-sweep.json), not to in-arm docs consumption.

Channels: read, bash, grep, sidechain (subagent Read or Bash), ambient
(CLAUDE.md import closure, constant per arm), supplement (audited events).

Output: data/docs-consumption.jsonl (one record per run) and a per-arm summary
plus a reconciliation report (audit event -> captured/supplemented) on stdout.
Token estimates are chars/4. Idempotent; safe to re-run.

Usage: docs_recount.py [--data-dir meta/experiment/data]
                       [--arms-dir meta/experiment/arms]
                       [--audit-file meta/experiment/audit/doc-read-audit.json]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import defaultdict
from pathlib import Path

DOC_EXTS = {".md", ".mdx"}
READER_WORDS = {"cat", "grep", "rg", "head", "tail", "less", "more", "sed",
                "awk", "diff", "od"}
GIT_READER = re.compile(r"\bgit(?:\s+-C\s+\S+)?\s+(show|diff|log)\b")
PLACEHOLDER = "(Bash completed with no output)"
ERROR_LINE = re.compile(
    r"No such file or directory|command not found|no matches found|"
    r"^\s*(grep|cat|sed|head|tail|ls|find|diff|od|zsh|bash|sh):|^usage:",
    re.IGNORECASE)
SHA_TOKEN = re.compile(r"^[0-9a-f]{7,40}$")
FIND_PATTERN = re.compile(
    r"-i?name\s+([\"']?)([^\s\"']+)\1|-path\s+([\"']?)([^\s\"']+)\3")
# Flags whose value is a separate following token.
VALUED_FLAGS = {"-e", "-f", "-m", "-A", "-B", "-C", "--max-count", "--include",
                "--exclude", "--glob", "--iglob", "-g", "-c"}
# Commands whose output is operational noise (path lists, status lines), not
# document-sized content: they do not block attributing a compound command's
# doc segment, at the cost of including their few lines in the segment chars.
SMALL_CMDS = {"find", "ls", "pwd", "wc", "which", "cd", "true", "mkdir",
              "cp", "mv", "rm", "touch", "basename", "dirname", "test", "["}
SMALL_GIT = {"checkout", "status", "add", "restore", "stash"}

# Audit channels that are network access, not in-arm consumption; they are
# covered by audit/network-sweep.json per Amendment 5.
WEB_CHANNEL = re.compile(r"web|curl", re.IGNORECASE)

PATHISH = re.compile(r"[\w./-]+\.mdx?\b")


# ---------------------------------------------------------------------------
# Arm doc enumeration and matching
# ---------------------------------------------------------------------------

def enumerate_arm_docs(arms_dir: Path, arm: str) -> set:
    """All doc paths in one arm snapshot, by the corpus-manifest rule."""
    root = arms_dir / f"{arm}-docs"
    out = set()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in DOC_EXTS:
            continue
        rel = str(p.relative_to(root))
        parts = rel.split("/")
        name = parts[-1].lower()
        if name.startswith("changelog") or name.startswith("license"):
            continue
        if {"testdata", ".github", "node_modules"} & set(parts):
            continue
        out.add(rel)
    return out


class ArmMatcher:
    """Resolve path-like tokens against one arm's doc set.

    Exact membership after normalization, then unambiguous suffix matching
    with at least two path components (Amendment 5: reads issued below a
    `cd` name paths relative to the subdirectory).
    """

    def __init__(self, paths: set, absent_at_start: bool = False):
        self.paths = set(paths)
        self.absent_at_start = absent_at_start
        self._suffixes = defaultdict(set)
        for p in self.paths:
            parts = p.split("/")
            for k in range(2, len(parts) + 1):
                self._suffixes["/".join(parts[-k:])].add(p)

    def _normalize(self, token: str) -> str:
        token = token.strip("\"'`")
        if "/ws/" in token:
            token = token.split("/ws/", 1)[1]
        while token.startswith("./") or token.startswith("../"):
            token = token[2:] if token.startswith("./") else token[3:]
        return token

    def resolve(self, token: str):
        """Return the arm doc path this token denotes, or None."""
        t = self._normalize(token)
        if t in self.paths:
            return t
        if "/" in t:
            hits = self._suffixes.get(t, ())
            if len(hits) == 1:
                return next(iter(hits))
        return None

    def search(self, text: str) -> bool:
        return any(self.resolve(t) for t in PATHISH.findall(text))

    def paths_in(self, text: str, exclude=()) -> list:
        out = []
        for t in PATHISH.findall(text):
            if t in exclude:
                continue
            p = self.resolve(t)
            if p and p not in out:
                out.append(p)
        return out


def build_matchers(arms_dir: Path) -> dict:
    """Per-arm matchers; nodocs gets the union of all arms, flagged."""
    per_arm = {arm: enumerate_arm_docs(arms_dir, arm)
               for arm in ("original", "ace", "naive")}
    union = set().union(*per_arm.values())
    matchers = {arm: ArmMatcher(paths) for arm, paths in per_arm.items()}
    matchers["nodocs"] = ArmMatcher(union, absent_at_start=True)
    return matchers


# Ambient (auto-loaded) tokens per arm: chars/4 of the CLAUDE.md import
# closure, measured from the arm snapshots. The nodocs arm has no corpus and
# therefore no ambient docs.
def ambient_tokens(arms_dir: Path) -> dict:
    out = {"nodocs": 0}
    for arm in ("original", "ace", "naive"):
        total = 0
        seen = set()
        def walk(rel: str, depth: int = 0):
            nonlocal total
            if rel in seen or depth > 5:
                return
            seen.add(rel)
            p = arms_dir / f"{arm}-docs" / rel
            if not p.is_file():
                return
            text = p.read_text(errors="replace")
            total += len(text)
            for m in re.finditer(r"(?m)(?:^|\s)@([\w./-]+\.(?:md|txt))", text):
                walk(m.group(1), depth + 1)
        walk("CLAUDE.md")
        out[arm] = total // 4
    return out


# ---------------------------------------------------------------------------
# Bash command analysis
# ---------------------------------------------------------------------------

def _split_quote_aware(text: str, seps: tuple, two_char: tuple = ()) -> list:
    """Split text at separators, respecting single/double quotes."""
    parts, buf, i, n = [], [], 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c); buf.append(text[i + 1]); i += 2; continue
        if text[i:i + 2] in two_char:
            parts.append("".join(buf)); buf = []; i += 2; continue
        if c in seps:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def split_units(cmd: str) -> list:
    """Split a compound command into pipeline units at ; && || and newlines.

    Quote-aware; a pipeline (cmds joined by |) stays one unit because it has
    one output.
    """
    return _split_quote_aware(cmd, ("\n", ";"), ("&&", "||"))


def _argv(text: str) -> list:
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _strip_redirects(tokens: list) -> tuple:
    """Remove redirection tokens; report whether stdout goes to a file."""
    out, silent, skip = [], False, False
    for t in tokens:
        if skip:
            skip = False
            continue
        if t == "2>&1":
            continue
        m = re.fullmatch(r"(\d?)(>>?|<<?)(.*)", t)
        if m:
            fd, op, target = m.groups()
            if op in (">", ">>") and fd in ("", "1") and target != "&2":
                silent = True
            if not target:
                skip = True  # target is the next token
            continue
        out.append(t)
    return out, silent


def _file_operands(tokens: list) -> list:
    """Reader arguments that denote files: non-flag, non-numeric, non-SHA."""
    ops = []
    for t in tokens:
        if not t or t.startswith("-") or SHA_TOKEN.match(t):
            continue
        if t in ("/dev/null", ".", ".."):
            continue
        if re.fullmatch(r"\d+([,.]\d+)?", t):
            continue
        ops.append(t)
    return ops


def _drop_flags(tokens: list) -> list:
    body, skip = [], False
    for t in tokens:
        if skip:
            skip = False
            continue
        if t.startswith("-") and t != "-":
            if t in VALUED_FLAGS:
                skip = True
            continue
        body.append(t)
    return body


def analyze_unit(unit: str, matcher: ArmMatcher, find_excluded: set) -> dict:
    """Classify one pipeline unit.

    verdict: doc | mixed | nondoc | echo | silent-other | other
    docs: arm doc paths named as file operands; is_grep / multi_file drive the
    grep line-prefix attribution rule.
    """
    segments = _split_quote_aware(unit, ("|",))
    head_tokens = _argv(segments[0]) if segments else []
    first = head_tokens[0] if head_tokens else ""

    if first in ("echo", "printf") and len(segments) == 1:
        rest, silent = _strip_redirects(head_tokens[1:])
        if silent:
            return {"verdict": "silent-other", "docs": [], "is_grep": False,
                    "multi_file": False}
        # Separator literals routinely start with '-' ("---"); drop only the
        # actual echo flags.
        literal = " ".join(t.strip("\"'") for t in rest
                           if t not in ("-n", "-e", "-E")).strip()
        return {"verdict": "echo", "literal": literal, "docs": [],
                "is_grep": False, "multi_file": False}

    docs, nondocs = [], []
    is_reader = False
    is_grep = False
    n_ops = 0
    silent = False
    for si, seg in enumerate(segments):
        toks = _argv(seg)
        if not toks:
            continue
        toks, seg_silent = _strip_redirects(toks)
        if not toks:
            continue
        word = toks[0]
        git_m = GIT_READER.match(" ".join(toks))
        if word == "find":
            continue  # not a reader; patterns excluded via find_excluded
        if word not in READER_WORDS and not git_m:
            if si == 0:
                silent = seg_silent
            continue
        args = toks[1:]
        if word == "sed" and any(a == "-i" or a.startswith("-i'")
                                 or a.startswith('-i"') for a in args):
            continue  # in-place edit: a write, not a read
        is_reader = True
        silent = silent or seg_silent
        if git_m:
            if "--" in args:
                args = args[args.index("--") + 1:]
            ops = [t for t in _file_operands(_drop_flags(args))
                   if "/" in t or re.search(r"\.\w{1,5}$", t)]
        elif word in ("grep", "rg"):
            is_grep = True
            body = _drop_flags(args)
            ops = _file_operands(body[1:]) if body else []
        elif word in ("sed", "awk"):
            body = _drop_flags(args)
            ops = _file_operands(body[1:]) if body else []
        else:  # cat head tail less more diff od
            ops = _file_operands(_drop_flags(args))
        for op in ops:
            if matcher._normalize(op) in find_excluded or op in find_excluded:
                continue
            n_ops += 1
            p = matcher.resolve(op)
            if p:
                if p not in docs:
                    docs.append(p)
            else:
                nondocs.append(op)

    if not is_reader:
        verdict = "silent-other" if silent else "other"
        if first in SMALL_CMDS or (
                first == "git" and len(head_tokens) > 1
                and head_tokens[1] in SMALL_GIT):
            verdict = "small"
        return {"verdict": verdict, "docs": [],
                "is_grep": False, "multi_file": False}
    multi = n_ops > 1
    if docs and not nondocs:
        return {"verdict": "doc", "docs": docs, "is_grep": is_grep,
                "multi_file": multi}
    if docs and nondocs:
        # grep mixing docs and non-docs is recoverable via line prefixes.
        verdict = "doc" if is_grep else "mixed"
        return {"verdict": verdict, "docs": docs, "is_grep": is_grep,
                "multi_file": True}
    return {"verdict": "nondoc", "docs": [], "is_grep": is_grep,
            "multi_file": multi}


def grep_prefix_chars(out: str, matcher: ArmMatcher) -> tuple:
    """Chars of grep-style output lines whose file prefix resolves to a doc.

    grep prints 'path:...' (or 'path-...' for context lines) only when
    reading multiple files; unprefixed output proves a single file was read.
    Returns (chars, resolved_paths).
    """
    total = 0
    paths = []
    for line in out.splitlines(keepends=True):
        m = re.match(r"([^\s:][^:\n]*?)[:\-](?:\d+[:\-])?", line)
        if not m:
            continue
        p = matcher.resolve(m.group(1))
        if p:
            total += len(line)
            if p not in paths:
                paths.append(p)
    return total, paths


def attribute_bash(cmd: str, out: str, matcher: ArmMatcher) -> dict:
    """Amendment-5 attribution for one Bash tool call.

    Returns {} when the command touches no arm doc; otherwise
    {paths, attributed_chars, attributed (bool), notes}.
    """
    find_excluded = set()
    for m in FIND_PATTERN.finditer(cmd):
        find_excluded.add(m.group(2) or m.group(4))

    units = [analyze_unit(u, matcher, find_excluded)
             for u in split_units(cmd)]
    doc_units = [u for u in units if u["docs"]]

    if not doc_units:
        # Recursive/dir-target greps name no doc operand but can still emit
        # doc content, always with 'path:' prefixes. Detect via the output.
        if any(u["is_grep"] for u in units) and out and out != PLACEHOLDER:
            chars, paths = grep_prefix_chars(out, matcher)
            if chars > 0:
                return {"paths": paths, "attributed_chars": chars,
                        "attributed": True, "notes": "grep prefix lines"}
        return {}

    paths = []
    for u in doc_units:
        for p in u["docs"]:
            if p not in paths:
                paths.append(p)

    # Whole-output corrections first.
    if out == PLACEHOLDER:
        return {"paths": paths, "attributed_chars": 0, "attributed": True,
                "notes": "empty-output placeholder"}
    stripped = out.strip()
    if stripped and len(stripped) < 300 and all(
            ERROR_LINE.search(l) for l in stripped.splitlines() if l.strip()):
        return {"paths": paths, "attributed_chars": 0, "attributed": True,
                "notes": "error-only output"}

    groups = _group_by_echo(units, out)

    attributed = 0
    lost_segments = False
    for group_units, segment in groups:
        g_doc = [u for u in group_units if u["verdict"] == "doc"]
        g_bad = [u for u in group_units
                 if u["verdict"] in ("mixed", "nondoc", "other")]
        if not g_doc:
            continue
        if g_bad:
            lost_segments = True
            continue
        if len(g_doc) == 1 and g_doc[0]["is_grep"] and g_doc[0]["multi_file"]:
            chars, _ = grep_prefix_chars(segment, matcher)
            attributed += chars
        else:
            attributed += len(segment)
    if attributed == 0 and lost_segments:
        return {"paths": paths, "attributed_chars": 0, "attributed": False,
                "notes": "mixed command; no clean doc segment"}
    return {"paths": paths, "attributed_chars": attributed, "attributed": True,
            "notes": "partial: doc segments only" if lost_segments else ""}


def _group_by_echo(units: list, out: str) -> list:
    """Pair unit groups with output segments using echoed separator literals.

    Falls back to one group holding everything when a literal cannot be
    located in the output in order.
    """
    marker_units = [u for u in units
                    if u["verdict"] == "echo" and u.get("literal")]
    if not marker_units:
        return [(units, out)]
    positions = []
    cursor = 0
    for mu in marker_units:
        idx = out.find(mu["literal"], cursor)
        if idx < 0:
            return [(units, out)]
        positions.append((idx, idx + len(mu["literal"])))
        cursor = idx + len(mu["literal"])
    unit_groups = []
    current = []
    for u in units:
        if u["verdict"] == "echo" and u.get("literal"):
            unit_groups.append(current)
            current = []
        else:
            current.append(u)
    unit_groups.append(current)
    seg_starts = [0] + [end for (_s, end) in positions]
    seg_ends = [s for (s, _e) in positions] + [len(out)]
    return [(g, out[s:e])
            for g, s, e in zip(unit_groups, seg_starts, seg_ends)]


# ---------------------------------------------------------------------------
# Transcript extraction (shared core; extract_doc_reads.py imports this)
# ---------------------------------------------------------------------------

def result_text(block) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def extract_run_events(transcript: Path, matcher: ArmMatcher) -> list:
    """Every doc-read event in one transcript, with attributed chars."""
    results = {}
    uses = []
    for line in open(transcript, errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        side = bool(e.get("isSidechain"))
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses.append((b.get("name"), b.get("input") or {},
                             b.get("id"), side))
            elif b.get("type") == "tool_result":
                results[b.get("tool_use_id")] = result_text(b)

    events = []
    for name, inp, uid, side in uses:
        out = results.get(uid, "")
        if name == "Read":
            fp = str(inp.get("file_path", ""))
            p = matcher.resolve(fp)
            if p:
                chars = 0 if out == PLACEHOLDER else len(out)
                events.append({
                    "channel": "sidechain" if side else "read",
                    "paths": [p], "output_chars": len(out),
                    "attributed_chars": chars, "attributed": True,
                    "excerpt": out[:200],
                })
        elif name == "Bash":
            cmd = str(inp.get("command", ""))
            att = attribute_bash(cmd, out, matcher)
            if att:
                events.append({
                    "channel": "sidechain" if side else "bash",
                    "paths": att["paths"], "command": cmd[:300],
                    "output_chars": len(out),
                    "attributed_chars": att["attributed_chars"],
                    "attributed": att["attributed"],
                    "notes": att["notes"], "excerpt": out[:200],
                })
        elif name == "Grep" and not side:
            blob = " ".join(str(inp.get(k, ""))
                            for k in ("path", "glob", "pattern"))
            paths = matcher.paths_in(blob)
            if paths:
                chars = 0 if out == PLACEHOLDER else len(out)
                events.append({
                    "channel": "grep", "paths": paths,
                    "output_chars": len(out), "attributed_chars": chars,
                    "attributed": True, "excerpt": out[:200],
                })
    if matcher.absent_at_start:
        for ev in events:
            ev["absent_at_start"] = True
    return events


# ---------------------------------------------------------------------------
# Audited supplement
# ---------------------------------------------------------------------------

def load_audit_supplement(audit_path: Path):
    """Audit missed events eligible for the supplement, keyed by run.

    Web-channel events are excluded (network sweep territory). Returns
    {(task, arm, trial): [event, ...]} with normalized fields.
    """
    if not audit_path.is_file():
        return {}
    audit = json.load(open(audit_path))
    out = defaultdict(list)
    for t in audit.get("per_task", []):
        task = t.get("task_id")
        for me in t.get("missed_events", []):
            chan = me.get("channel", "")
            paths = [p for p in me.get("paths", [])
                     if not p.startswith("http") and not p.startswith("/")]
            if WEB_CHANNEL.search(chan) or not paths:
                continue
            out[(task, me.get("arm"), me.get("trial"))].append({
                "channel": "supplement", "paths": paths,
                "audit_channel": chan,
                "output_chars": me.get("approx_chars", 0),
                "attributed_chars": me.get("approx_chars", 0),
                "attributed": True, "source": "agent_audit",
                "evidence": (me.get("evidence") or "")[:300],
            })
    return out


def reconcile_supplement(auto_events: list, candidates: list) -> tuple:
    """Reconcile audit candidates against one run's automatic events.

    A candidate is CAPTURED when an automatic event shares a path and carries
    attributed chars of at least half the audit estimate (the extractor now
    sees it). Otherwise the candidate is SUPPLEMENTED; if an automatic event
    shares a path but attributed ~nothing (the extractor sees the command but
    cannot attribute its content), that event is superseded so calls are not
    double-counted. Each automatic event is consumed at most once.

    Returns (captured, supplemental, superseded_ids) where superseded_ids are
    indices into auto_events.
    """
    available = set(range(len(auto_events)))
    captured, supplemental, superseded = [], [], set()
    for cand in sorted(candidates,
                       key=lambda c: -c["attributed_chars"]):
        want = max(cand["attributed_chars"], 1)
        # Best capture: attributed chars within [0.5x, 2x] of the audit
        # estimate, closest ratio wins (first-fit mispairs when one run has
        # several events on the same path).
        best, best_dist = None, None
        for i in available:
            ev = auto_events[i]
            if not set(ev["paths"]) & set(cand["paths"]):
                continue
            r = ev["attributed_chars"] / want
            if 0.5 <= r <= 2.0:
                dist = abs(r - 1.0)
                if best is None or dist < best_dist:
                    best, best_dist = i, dist
        if best is not None:
            available.remove(best)
            captured.append(cand)
            continue
        # No capture: supersede one zero-attribution automatic event on the
        # same path (the extractor saw the command but could not attribute
        # its content) so calls are not double-counted. Events with real
        # attributed chars are never superseded.
        for i in sorted(available):
            ev = auto_events[i]
            if set(ev["paths"]) & set(cand["paths"]) and \
                    ev["attributed_chars"] == 0:
                superseded.add(i)
                available.remove(i)
                break
        supplemental.append(cand)
    return captured, supplemental, superseded


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("--data-dir", default=str(base / "data"))
    ap.add_argument("--arms-dir", default=str(base / "arms"))
    ap.add_argument("--audit-file",
                    default=str(base / "audit" / "doc-read-audit.json"))
    args = ap.parse_args()
    data = Path(args.data_dir)
    arms_dir = Path(args.arms_dir)

    matchers = build_matchers(arms_dir)
    ambient = ambient_tokens(arms_dir)
    supplement = load_audit_supplement(Path(args.audit_file))
    if not supplement:
        print(f"note: no audit supplement loaded from {args.audit_file}",
              file=sys.stderr)

    out_path = data / "docs-consumption.jsonl"
    records = []
    recon = {"captured": 0, "supplemented": 0, "superseded": 0}
    for transcript in sorted(data.glob("runs/*/*/trial-*/transcript.jsonl")):
        parts = transcript.parts
        task_id, arm, trial = parts[-4], parts[-3], parts[-2]
        matcher = matchers[arm]
        events = extract_run_events(transcript, matcher)
        captured, extra, superseded = reconcile_supplement(
            events, supplement.get((task_id, arm, trial), []))
        recon["captured"] += len(captured)
        recon["supplemented"] += len(extra)
        recon["superseded"] += len(superseded)
        events = [ev for i, ev in enumerate(events)
                  if i not in superseded] + extra

        rec = defaultdict(int)
        for ev in events:
            ch = ev["channel"]
            rec[f"{ch}_calls"] += 1
            rec[f"{ch}_chars"] += ev["attributed_chars"]
            if not ev.get("attributed", True):
                rec["unattributed_calls"] += 1
            if ev.get("absent_at_start"):
                rec["absent_at_start_calls"] += 1
                rec["absent_at_start_chars"] += ev["attributed_chars"]
        explicit_tokens = sum(
            rec.get(f"{c}_chars", 0)
            for c in ("read", "bash", "grep", "sidechain", "supplement")) // 4
        records.append({
            "task_id": task_id, "arm": arm, "trial": trial,
            "instrument": "revision-2",
            **{k: rec[k] for k in sorted(rec)},
            "explicit_doc_tokens": explicit_tokens,
            "ambient_doc_tokens": ambient.get(arm, 0),
            "total_doc_tokens": explicit_tokens + ambient.get(arm, 0),
        })
    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    by_arm = defaultdict(list)
    for r in records:
        by_arm[r["arm"]].append(r)
    print(f"recounted {len(records)} runs -> {out_path} (instrument revision 2)")
    print(f"audit reconciliation: {recon['captured']} captured by the "
          f"extractor, {recon['supplemented']} supplemented, "
          f"{recon['superseded']} automatic events superseded")
    print(f"{'arm':10} {'runs':>4} {'mean explicit tok':>17} {'median':>7} "
          f"{'runs w/ contact':>15} {'ambient':>8}")
    for arm in ("original", "ace", "naive", "nodocs"):
        rs = by_arm.get(arm)
        if not rs:
            continue
        toks = sorted(r["explicit_doc_tokens"] for r in rs)
        contact = sum(1 for t in toks if t > 0)
        print(f"{arm:10} {len(rs):>4} {sum(toks)//len(toks):>17} "
              f"{toks[len(toks)//2]:>7} {contact:>10}/{len(rs):<4} "
              f"{ambient.get(arm, 0):>8}")


if __name__ == "__main__":
    main()
