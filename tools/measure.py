#!/usr/bin/env python3
"""ACE-100 corpus measurement (Issue 3 draft).

Reports the size of the governed corpus: the bytes of each document, the
corpus total, and the front-matter share. Bytes are the exact unit, and
`wc -c` reproduces them anywhere. A token count is an estimate (bytes / 4),
and the output labels it so. The tool is a diagnostic, not a checker: it
settles no rule, and a run never fails. The self-compliance rule in
docs/standard/about.md stands on this tool: the standard makes no
quantitative claim without a committed measurement.

  tools/measure.py <path>...   # measure the given files
  tools/measure.py             # measure every .md file under the current tree

The full sweep honors .ace-ignore, like tools/lint.py. Each issue commits
one snapshot of the sweep to tools/measurements/.
"""
import re, sys, pathlib

ROOT = pathlib.Path.cwd()

def fm_bytes(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return len(text[:m.end()].encode()) if m else 0

def sweep_files():
    files = sorted(ROOT.rglob('*.md'))
    ign = ROOT / '.ace-ignore'
    if ign.exists():
        pats = [l.strip() for l in ign.read_text().splitlines()
                if l.strip() and not l.strip().startswith('#')]
        rx = [re.compile(p) for p in pats]
        files = [f for f in files
                 if not any(r.search(str(f.relative_to(ROOT))) for r in rx)]
    return files

def main(argv):
    files = [pathlib.Path(a) for a in argv] if argv else sweep_files()
    if not files:
        print('the sweep matched no files — check .ace-ignore')
        return 2
    rows = []
    for f in files:
        rel = f.relative_to(ROOT) if f.is_absolute() else f
        text = f.read_text()
        rows.append((len(text.encode()), fm_bytes(text), str(rel)))
    total = sum(r[0] for r in rows)
    fm = sum(r[1] for r in rows)
    print('ACE-100 corpus measurement')
    print('bytes are exact; a token count is an estimate (bytes / 4)')
    print()
    print(f'documents:    {len(rows)}')
    print(f'corpus:       {total:,} bytes ({total // 4:,} tokens, estimate)')
    print(f'front matter: {fm:,} bytes, {100 * fm / total:.1f}% of the corpus')
    print()
    print(f'{"bytes":>8}  {"front matter":>12}  document')
    for b, fb, path in sorted(rows, key=lambda r: (-r[0], r[2])):
        print(f'{b:>8,}  {fb:>12,}  {path}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
