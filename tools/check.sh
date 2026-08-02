#!/usr/bin/env bash
# ACE-100 canonical checker (Issue 4). It settles the mechanical rules that a
# shell can settle:
#
#   front matter and its mandatory properties (ACE 13.2)
#   the parent index that `isPartOf` names (ACE 13.2, ACE 11.3)
#   the H1 (ACE 13.6)
#   the 120-line size limit (ACE 15.1)
#   American spelling in prose (ACE 1.12)
#   link resolution (ACE 14.5)
#   backticked repository paths (ACE 14.9)
#   one README.md index in each directory (ACE 11.3)
#
# It does not check vocabulary layers, voice, tense, modality, or meaning.
# It does not check sentence limits or topic division. A clean run is
# necessary and not sufficient. A reader covers the rest.
#
# This checker reads markdown alone. `tools/lint.py` covers the pattern rules,
# and it covers the comments of source files (ACE 10.1).
#
# Adapted from the checker of the first field migration, with thanks.
#
#   tools/check.sh <path>...   # check the given files
#   tools/check.sh             # check every governed file
#
# A .ace-ignore file at the repository root excludes paths from the full
# sweep. It holds one grep pattern for each line.
#
# The exit is non-zero when a check fails. A failure names the file and the
# ACE rule.

set -uo pipefail
# The repository root is the git toplevel. Without git, it is the current
# directory. The adopt command resolves the root the same way, and the linter
# reads the current directory.
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 2

files=()
sweep=0
if [ "$#" -gt 0 ]; then
  files=("$@")
else
  sweep=1
  # The find fallback strips its "./" prefix. A .ace-ignore pattern anchored
  # with "^" then matches the same path in the two modes.
  list=$(git ls-files --cached --others --exclude-standard '*.md' 2>/dev/null || find . -name '*.md' | sed 's|^\./||')
  if [ -f .ace-ignore ]; then
    # Strip blank lines and `#` comments first. An empty pattern matches every
    # line. A single blank line here excludes the whole corpus. The sweep then
    # reports a clean run over nothing, and ACE 17.3 warns about that failure.
    patterns=$(grep -v -e '^[[:space:]]*$' -e '^[[:space:]]*#' .ace-ignore)
    if [ -n "$patterns" ]; then
      list=$(printf '%s\n' "$list" | grep -v -f <(printf '%s\n' "$patterns"))
    fi
  fi
  while IFS= read -r line; do
    [ -n "$line" ] && files+=("$line")
  done <<EOF
$list
EOF
fi

if [ "${#files[@]}" -eq 0 ]; then
  # A sweep that matches nothing is a broken sweep, not a clean one.
  [ "$sweep" -eq 1 ] && { echo 'the sweep matched no files — check .ace-ignore'; exit 2; }
  echo 'no files to check'
  exit 0
fi

fail=0
# A finding names its rule, for example "ACE 13.6". The `exempt` property of
# the document can carry that identifier (ACE 13.7). The finding is then not
# an error. The filter sits here, in one place, for every check alike.
note() {
  id=$(printf '%s' "$1" | sed -n 's/.*ACE \([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -1)
  if [ -n "$id" ]; then
    case "$exempt" in *"$id"*) return 0 ;; esac
  fi
  printf '%s\n' "$1"; fail=1
}
exempt=''

for f in "${files[@]}"; do
  exempt=''
  [ -f "$f" ] || { note "$f — missing"; continue; }

  # --- front matter (ACE 13.2) -------------------------------------------------
  if [ "$(head -1 "$f")" != "---" ]; then
    note "$f:1 — ACE 13.2: no front matter; the document must open with '---'"
    continue
  fi
  close=$(awk 'NR>1 && $0=="---" {print NR; exit}' "$f")
  if [ -z "$close" ]; then
    note "$f:1 — ACE 13.2: front matter never closes"
    continue
  fi

  # Exemptions (ACE 13.7): rule identifiers named in `exempt:` are skipped.
  exempt=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"exempt:")==1 {print; exit}' "$f")

  props='"@type" name description isPartOf'
  # ACE 13.3: the root index of the repository is the one document with no parent.
  [ "$f" = "README.md" ] && props='"@type" name description'
  for prop in $props; do
    awk -v c="$close" -v p="$prop" 'NR>1 && NR<c && index($0, p": ")==1 {found=1} END {exit !found}' "$f" \
      || note "$f — ACE 13.2: front matter has no '$prop' property"
  done

  # --- the parent index resolves, and is a file (ACE 13.2, 11.3, 15.2) ---------
  # `isPartOf` names the parent index, from the repository root. A division
  # replaces one document with an index and its parts. Each part then names a
  # parent that is gone. Nothing else reads the property, so the break is
  # silent. A `<placeholder>` belongs to a template, and it names no real file.
  parent=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"isPartOf: ")==1 {sub(/^isPartOf: */,""); print; exit}' "$f")
  parent=${parent%\"}; parent=${parent#\"}; parent=${parent%\'}; parent=${parent#\'}
  case "$parent" in
    ''|'<'*) : ;;
    *)
      if [ ! -e "$parent" ]; then
        note "$f — ACE 13.2: the 'isPartOf' index does not resolve: $parent"
      elif [ -d "$parent" ]; then
        note "$f — ACE 11.3: the 'isPartOf' index is a directory: $parent"
      fi ;;
  esac

  # --- the H1 is the first line of the body, and equals `name` (ACE 13.6) ------
  h1=$(awk -v c="$close" 'NR>c && NF {print; exit}' "$f")
  case "$h1" in
    '# '*)
      name=$(awk -v c="$close" 'NR>1 && NR<c && index($0,"name: ")==1 {sub(/^name: */,""); print; exit}' "$f")
      name=${name%\"}; name=${name#\"}; name=${name%\'}; name=${name#\'}
      [ "${h1#\# }" = "$name" ] \
        || note "$f — ACE 13.6: the H1 and the 'name' property differ
    H1:   ${h1#\# }
    name: $name" ;;
    *) note "$f — ACE 13.6: the first line of the body must be the H1, found: ${h1:0:40}" ;;
  esac

  # --- size (ACE 15.1: 120 body lines, everything counts) ----------------------
  case "$exempt" in *"15.1"*) : ;; *)
    body=$(awk -v c="$close" 'NR>c' "$f" | wc -l | tr -d ' ')
    [ "$body" -le 120 ] || note "$f — ACE 15.1: $body body lines, the limit is 120"
  ;; esac

  # --- American English in prose (ACE 1.12) ------------------------------------
  # Backticked text, code blocks, link targets, and path-shaped tokens are
  # identifiers or quoted text. The rule does not reach inside them.
  # A dictionary table names words to ban them, and a mention is not a use.
  indict=0
  case "$f" in docs/dictionary/*) indict=1 ;; esac
  case "$exempt" in *"1.12"*) : ;; *)
    british=$(awk -v c="$close" -v indict="$indict" '
      NR<=c {next}
      /^```/ {code = !code; next}
      code {next}
      /^[[:space:]]*>/ {next}  # a blockquote is quoted text (ACE 1.5)
      indict && /^[[:space:]]*\|/ {next}
      {
        gsub(/`[^`]*`/, "")
        gsub(/\]\([^)]*\)/, "]")
        gsub(/[^ \t]*\.(md|ts|tsx|js|json|sh|py|css|sql)\b/, "")
        gsub(/[^ \t]*\/[^ \t]*/, "")
        print
      }' "$f" \
      | grep -oiE '\b(colour|behaviour|centre|licence|catalogue|organis(e|ed|ing|ation)|normalis(e|ed|ing|ation)|initialis(e|ed|ing|ation)|analys(e|ed|ing)|recognis(e|ed|ing))[a-z]*' \
      | sort -u | paste -sd' ' - | tr -d '\n')
    [ -z "$british" ] || note "$f — ACE 1.12: British spelling in prose: $british"
  ;; esac

  # --- links resolve, and point at files (ACE 14.5) -----------------------------
  dir=$(dirname "$f")
  while IFS= read -r target; do
    [ -n "$target" ] || continue
    case "$target" in http*|'#'*|mailto:*|'<'*) continue ;; esac
    path="${target%%#*}"
    [ -n "$path" ] || continue
    if [ ! -e "$dir/$path" ]; then
      note "$f — ACE 14.5: link does not resolve: $target"
    elif [ -d "$dir/$path" ]; then
      note "$f — ACE 14.5: link points at a directory: $target"
    fi
  done < <(grep -o '](\([^)]*\))' "$f" 2>/dev/null | sed 's/^](//; s/)$//')

  # --- backticked repository paths resolve (ACE 14.9) ---------------------------
  # A backticked span with a slash is an identifier and a pointer at the same
  # time. ACE 1.5 exempts it from the word rules. No other check reads it, and
  # a division strands it silently.
  #
  # Placeholders in angle brackets, globs, spans with spaces, and URLs are not
  # paths. The path resolves from the repository root or from the document.
  # An anchor or a final slash drops.
  while IFS= read -r span; do
    [ -n "$span" ] || continue
    case "$span" in
      *'<'*|*'*'*|*' '*|*'://'*) continue ;;
      */*) : ;;
      *) continue ;;
    esac
    p=${span%%#*}; p=${p%/}
    [ -e "$p" ] || [ -e "$dir/$p" ] \
      || note "$f — ACE 14.9: backticked path does not resolve: $span"
  done < <(awk -v c="$close" 'NR<=c {next} /^```/ {code=!code; next} code {next} {print}' "$f" \
    | grep -o '`[^`]*`' | sed 's/^`//; s/`$//' | sort -u)
done

# --- every governed directory has an index (ACE 11.3) --------------------------
# A directory declares no exemption, so the filter must not read the last file's.
exempt=''
if [ "$sweep" -eq 1 ]; then
  for dir in $(printf '%s\n' "${files[@]}" | sed -e '/\//!s:.*:.:' -e 's:/[^/]*$::' | sort -u); do
    [ "$dir" = "." ] && continue
    [ -f "$dir/README.md" ] || note "$dir — ACE 11.3: the directory has no README.md index"
  done
fi

if [ "$fail" -eq 0 ]; then
  printf 'ok — %d file(s) pass the mechanical checks\n' "${#files[@]}"
fi
exit "$fail"
