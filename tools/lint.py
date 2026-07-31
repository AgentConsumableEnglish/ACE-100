#!/usr/bin/env python3
"""ACE-100 extended linter (Issue 2).

Settles the pattern rules beyond tools/check.sh: sentence word limits with the
canonical count (ACE 5.1, 6.1, 8.5-8.8), modality (ACE 3.7), contractions
(ACE 4.2), Latin abbreviations (ACE 8.4), replacements-table words (ACE 1.3),
"-ing" forms outside the allowlist (ACE 3.4), heading depth (ACE 14.3),
kebab-case names (ACE 14.1), document types and genres (ACE 12.1, 12.5), and
exemption declarations (ACE 13.7, 17.7).

It does NOT check: the function-word layer (needs part-of-speech reading),
voice, tense, meaning, one-name-per-item, or topic division. A clean run is
necessary and not sufficient.

  tools/lint.py <path>...   # lint the given files
  tools/lint.py             # lint every .md file under the current tree

The full sweep honors .ace-ignore (comments and blank lines permitted), and a
finding is not reported when its rule identifier is in the document's `exempt`
property (ACE 13.7).
"""
import re, sys, pathlib

ROOT = pathlib.Path.cwd()
TYPES = {'CollectionPage', 'TechArticle', 'HowTo', 'APIReference', 'DefinedTermSet'}
GENRES = {'decision-record', 'rules'}
ING_OK_SUFFIX = ('thing',)  # something, anything, nothing, everything
ING_NOT_SUFFIX = {'string', 'thing', 'sing', 'king', 'ring', 'wing', 'spring', 'during', 'bring'}

def split_fm(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return (m.group(1), text[m.end():]) if m else (None, text)

def load_allow():
    allow = set()
    p = ROOT / 'docs/dictionary/ing-allowlist.md'
    if p.exists():
        for l in p.read_text().splitlines():
            if l.startswith('|') and not re.match(r'\|\s*-', l):
                w = l.strip('|').split('|')[0].strip().lower()
                if w and w != 'word':
                    allow.add(w)
    return allow

def load_terms():
    """Declared technical terms, word by word.

    ACE 3.4 keeps a declared term with an "-ing" form permitted, so the linter
    reads the declarations before it reports one. The table divides into
    sibling parts once it passes the size limit, so every `technical-terms*.md`
    part is read, not the base one alone.
    """
    terms = set()
    for p in sorted((ROOT / 'docs/dictionary').glob('technical-terms*.md')):
        for l in p.read_text().splitlines():
            if l.startswith('|') and not re.match(r'\|\s*-', l):
                t = l.strip('|').split('|')[0].strip().lower()
                if t and t != 'term':
                    terms.update(t.split())
    return terms

def load_banned():
    banned = []
    p = ROOT / 'docs/dictionary/replacements.md'
    if p.exists():
        for l in p.read_text().splitlines():
            if l.startswith('|') and not re.match(r'\|\s*-', l):
                left = l.strip('|').split('|')[0].strip()
                if left.lower() in ('not permitted', ''):
                    continue
                if '(' in left:  # context-dependent rows need a reader
                    continue
                for w in left.split(','):
                    w = w.strip().lower()
                    if w:
                        banned.append(w)
    return banned

def clean(body):
    t = re.sub(r'```.*?```', ' CODEBLOCK. ', body, flags=re.S)
    t = re.sub(r'`[^`]*`', ' TICK ', t)
    t = re.sub(r'"[^"\n]*"', ' QUOTE ', t)
    t = re.sub(r'\([^)]*\)', ' PAREN ', t)   # ACE 8.7: counts once, as one word
    t = re.sub(r'<[^>\n]*>', ' PLACEHOLDER ', t)
    t = re.sub(r'\]\(([^)]*)\)', '] ', t)
    return t

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
    allow = load_allow()
    banned = load_banned()
    terms = load_terms()
    files = [pathlib.Path(a) for a in argv] if argv else sweep_files()
    issues = []
    exempt_map = {}
    def note(f, msg):
        m = re.match(r'ACE ([0-9]+\.[0-9]+)', msg)
        if m and m.group(1) in exempt_map.get(str(f), ''):
            return
        issues.append(f"{f} — {msg}")

    for f in files:
        rel = f.relative_to(ROOT) if f.is_absolute() else f
        srel = str(rel)
        in_dict = srel.startswith('docs/dictionary')
        in_tmpl = srel.startswith('docs/templates')
        text = f.read_text()
        fm, body = split_fm(text)
        if fm is None:
            note(rel, 'ACE 13.2: no front matter'); continue
        fmd = dict(re.findall(r'^"?(@?\w+)"?:\s*(.*)$', fm, re.M))
        exempt = fmd.get('exempt', '')
        exempt_map[str(rel)] = exempt
        def skipped(rule): return rule in exempt
        if exempt and not (ROOT / 'docs/standard/deviations.md').exists():
            note(rel, 'ACE 17.7: exempt declared but no deviations ledger exists')

        if fmd.get('@type') not in TYPES:
            note(rel, f"ACE 12.1: @type invalid: {fmd.get('@type')}")
        genre = fmd.get('genre', '')
        if genre and genre not in GENRES:
            note(rel, f"ACE 12.5: unknown genre: {genre}")
        if len(fmd.get('description', '').split()) > 20:
            note(rel, 'ACE 13.2: description over 20 words')

        if not re.fullmatch(r'(README|[a-z0-9]+(-[a-z0-9]+)*)\.md', f.name):
            note(rel, f'ACE 14.1: filename not kebab-case: {f.name}')
        for h in re.findall(r'^(#{4,6}) ', body, re.M):
            note(rel, f'ACE 14.3: heading depth {len(h)}')
        blines = body.strip('\n').split('\n')
        if len(blines) > 120 and not skipped('15.1'):
            note(rel, f'ACE 15.1: body {len(blines)} lines, the limit is 120')

        prose = clean(body)
        plines = prose.split('\n')
        prose_nt = '\n'.join(l for l in plines if not l.strip().startswith('|'))
        scope = prose_nt if in_dict else prose

        if ';' in scope:
            note(rel, 'ACE 8.1: semicolon in prose')
        for pat, rule, msg in [
            (r"\b\w+n't\b|\b\w+'re\b|\b\w+'ll\b|\b\w+'ve\b|\bit's\b", '4.2', 'contraction'),
            (r'\be\.g\.|\bi\.e\.|\betc\.', '8.4', 'Latin abbreviation'),
            (r'\b(may|might|could|shall|should)\b', '3.7', 'modality word that is not permitted'),
        ]:
            for mm in re.finditer(pat, scope, re.I):
                note(rel, f'ACE {rule}: {msg}: "{mm.group(0)}"')
        if genre not in ('decision-record',):
            for mm in re.finditer(r'\bwould\b', scope, re.I):
                note(rel, f'ACE 3.7: "would" outside a decision record — make sure that it is counterfactual (review, not error)')
                break
        if not in_dict:
            for w in banned:
                if re.search(r'\b' + re.escape(w) + r'\b', scope, re.I):
                    note(rel, f'ACE 1.3: replacements-table word: "{w}"')
        if not in_dict:
            for mm in re.finditer(r'\b([A-Za-z-]*[a-z]ing)\b', prose_nt):
                wl = mm.group(1).lower()
                head = wl.split('-')[-1]
                if wl in allow or wl in terms or wl.endswith(ING_OK_SUFFIX):
                    continue
                if head in allow or head in terms:
                    continue
                if wl in ING_NOT_SUFFIX or head in ING_NOT_SUFFIX:
                    continue
                if wl in ('codeblock',):
                    continue
                note(rel, f'ACE 3.4: "-ing" word outside the allowlist: {wl} (review: a noun or a technical use can be correct)')

        limit = 15 if fmd.get('@type') == 'HowTo' else 20
        if in_tmpl:
            continue
        for l in plines:
            l = l.strip()
            if not l or l.startswith('|') or l.startswith('#'):
                continue
            l = re.sub(r'^([-*]|\d+\.)\s+', '', l)
            l = l.replace(':', '.')
            for s in re.split(r'[.!?]+', l):
                toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9'@-]*", s)
                if len(toks) > limit:
                    note(rel, f'ACE {"5.1" if limit==15 else "6.1"}: {len(toks)} words: {s.strip()[:70]}')

    for i in issues:
        print(i)
    if not issues:
        print(f'ok — {len(files)} file(s) pass the extended checks')
    return 1 if issues else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
