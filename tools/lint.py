#!/usr/bin/env python3
"""ACE-100 extended linter (Issue 3 draft).

Settles the pattern rules beyond tools/check.sh: sentence word limits with the
canonical count over logical sentences (ACE 5.1, 6.1, 8.5-8.8), paragraph
sentence counts (ACE 6.6), modality (ACE 3.7), contractions (ACE 4.2), Latin
abbreviations (ACE 8.4), replacements-table words (ACE 1.3), the progressive
form (ACE 3.3), heading depth (ACE 14.3), kebab-case names (ACE 14.1),
document types and genres (ACE 12.1, 12.5), and exemption declarations
(ACE 13.7, 17.7).

It does NOT check: the function-word layer (needs part-of-speech reading),
voice, the perfect tenses, "-ing" verb forms beyond the progressive (ACE 3.4
is a rule about grammar, and grammar needs a reader), meaning,
one-name-per-item, or topic division. A clean run is necessary and not
sufficient.

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
# Predicate adjectives that follow "be" without a progressive reading
# ("the file is missing"). ING_NOT_VERB holds exact words whose letters end
# in "ing" with no verb suffix — exact membership, not a suffix test, so
# "using" and "processing" stay caught. Compounds of "thing" pass by suffix.
ING_ADJECTIVES = {'missing', 'existing', 'remaining', 'outstanding', 'pending', 'recurring', 'load-bearing'}
ING_NOT_VERB = {'thing', 'string', 'sing', 'king', 'ring', 'wing', 'spring', 'bring', 'during', 'sting', 'swing'}

def split_fm(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    return (m.group(1), text[m.end():]) if m else (None, text)

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
    # A blockquote is the markdown spelling of a quotation (ACE 1.5).
    t = re.sub(r'^[ \t]*>.*$', ' QUOTE. ', t, flags=re.M)
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
    banned = load_banned()
    files = [pathlib.Path(a) for a in argv] if argv else sweep_files()
    if not argv and not files:
        # A sweep that matches nothing is a broken sweep, not a clean one.
        print('the sweep matched no files — check .ace-ignore')
        return 2
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
        # The progressive form is the machine-settleable slice of the "-ing"
        # rules (ACE 3.3). The rest of ACE 3.4 is grammar, and needs a reader.
        for mm in re.finditer(r'\b(am|is|are|was|were|be|been|being)\s+([A-Za-z-]*[a-z]ing)\b', scope, re.I):
            w = mm.group(2).lower()
            if w in ING_ADJECTIVES or w in ING_NOT_VERB or w.endswith('thing'):
                continue
            note(rel, f'ACE 3.3: the progressive form: "{mm.group(1)} {mm.group(2)}"')

        limit = 15 if fmd.get('@type') == 'HowTo' else 20
        if in_tmpl:
            continue
        # Every count runs over the logical sentence (ACE 8.8): the wrapped
        # lines of one paragraph join before any split, so a hard-wrapped
        # document counts the same as an unwrapped one.
        blocks, cur = [], []
        for l in plines:
            if l.strip():
                cur.append(l.strip())
            elif cur:
                blocks.append(cur); cur = []
        if cur:
            blocks.append(cur)
        for b in blocks:
            paras, items = [], []
            for l in b:
                if l.startswith('|') or l.startswith('#'):
                    continue
                m = re.match(r'^([-*]|\d+\.)\s+', l)
                if m:
                    items.append(l[m.end():])
                else:
                    paras.append(l)
            para = ' '.join(paras)
            for src in ([para] if para else []) + items:
                for s in re.split(r'[.!?]+', src.replace(':', '.')):
                    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9'@-]*", s)
                    if len(toks) > limit:
                        note(rel, f'ACE {"5.1" if limit==15 else "6.1"}: {len(toks)} words: {s.strip()[:70]}')
            # ACE 6.6: five sentences maximum in a paragraph. A vertical list
            # is its own structure (ACE 8.6), so the items stay outside the
            # count. The split here is deliberate: a period ends a sentence
            # only before a new start, so "ACE 8.5" and "changes.md" do not
            # divide, and a rule reference never inflates the count.
            if para:
                sents = [s for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9`"(*\[])', para)
                         if re.search(r'[A-Za-z0-9]', s)]
                if len(sents) > 5:
                    note(rel, f'ACE 6.6: {len(sents)} sentences in one paragraph, the limit is five')

    for i in issues:
        print(i)
    if not issues:
        print(f'ok — {len(files)} file(s) pass the extended checks')
    return 1 if issues else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
