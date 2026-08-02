#!/usr/bin/env python3
"""ACE-100 corpus measurement (Issue 4).

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

Issue 4 governs comments too (ACE 10.1), so the sweep reports the comment
prose of the source files beside the documents. The two are separate totals.
A document is prose from the first byte, and a source file holds prose in its
comments alone.
"""
import re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lint import COMMENT_SYNTAX, extract_comments, DIRECTIVE

ROOT = pathlib.Path.cwd()

def fm_bytes(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return len(text[:m.end()].encode()) if m else 0

def ignored():
    ign = ROOT / '.ace-ignore'
    if not ign.exists():
        return []
    return [re.compile(l.strip()) for l in ign.read_text().splitlines()
            if l.strip() and not l.strip().startswith('#')]

def sweep_files(suffixes=('.md',)):
    files = sorted(f for f in ROOT.rglob('*')
                   if f.suffix in suffixes and f.is_file())
    rx = ignored()
    return [f for f in files
            if not any(r.search(str(f.relative_to(ROOT))) for r in rx)]

def comment_bytes(path):
    """The bytes of the comment prose of a source file (ACE 10.1)."""
    family = COMMENT_SYNTAX.get(path.suffix)
    if not family:
        return 0
    try:
        pieces = extract_comments(path.read_text(), family)
    except (UnicodeDecodeError, OSError):
        return 0
    prose = [t for _, t in pieces if t.strip() and not DIRECTIVE.search(t)]
    return len('\n'.join(prose).encode())

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

    # The comment corpus (ACE 10.1). A source file is measured by its comment
    # prose, and never by its code. A directive is structured data (ACE 10.6),
    # and it stays out of the total.
    if argv:
        return 0
    src = sweep_files(tuple(COMMENT_SYNTAX))
    crows = [(comment_bytes(f), str(f.relative_to(ROOT))) for f in src]
    crows = [r for r in crows if r[0]]
    if not crows:
        return 0
    ctotal = sum(r[0] for r in crows)
    print()
    print('comment prose')
    print(f'source files: {len(crows)}')
    print(f'comments:     {ctotal:,} bytes ({ctotal // 4:,} tokens, estimate)')
    print(f'share:        {100 * ctotal / (total + ctotal):.1f}% of all governed prose')
    print()
    print(f'{"bytes":>8}  source file')
    for b, path in sorted(crows, key=lambda r: (-r[0], r[1])):
        print(f'{b:>8,}  {path}')
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
