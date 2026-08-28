#!/bin/bash
# The things that have to be true before this repo is worth pointing anyone at.
#
# A licence, a changelog, links that resolve, and no device address anywhere in
# the tree. The last one is the reason this file runs in CI: a MAC pushed to a
# public repo cannot be taken back by deleting it, so it is checked on every
# commit rather than remembered.
set -uo pipefail

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$TEST_DIR")
# shellcheck source-path=SCRIPTDIR source=lib/assert.sh
source "$TEST_DIR/lib/assert.sh"

# --- licence ---------------------------------------------------------------
# The repo is public. Without a licence nobody may legally use what it offers,
# however plainly the README invites them to.
assert_file "$ROOT/LICENSE" "LICENSE exists"
if [[ -f $ROOT/LICENSE ]]; then
  licence=$(cat "$ROOT/LICENSE")
  assert_contains "$licence" "MIT License" "LICENSE is MIT"
  assert_contains "$licence" "Miguel Rincon" "LICENSE names the author"
fi

# --- changelog -------------------------------------------------------------
assert_file "$ROOT/CHANGELOG.md" "CHANGELOG.md exists"
if [[ -f $ROOT/CHANGELOG.md ]]; then
  changelog=$(cat "$ROOT/CHANGELOG.md")
  assert_contains "$changelog" "## [Unreleased]" "keeps an Unreleased section"
  assert_contains "$changelog" "keepachangelog.com" "states the format it follows"
  assert_contains "$changelog" "semver.org" "states the versioning scheme"
  assert_contains "$changelog" "0.x" "carries the 0.x stability note"

  # A dated heading, not a bare one: "## [0.1.0]" with no date reads as
  # unreleased and is how a release silently loses its date.
  if grep -qE '^## \[[0-9]+\.[0-9]+\.[0-9]+\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$' \
      "$ROOT/CHANGELOG.md"; then
    pass "the released entry carries a date"
  else
    fail "the released entry carries a date" "expected: ## [x.y.z] - YYYY-MM-DD"
  fi
fi

# --- the README describes the current layout -------------------------------
# Every one of these was accurate before the move and is a lie after it.
readme=$(cat "$ROOT/README.md")
if [[ $readme == *"cmfctl.py"* ]]; then
  fail "README does not invoke cmfctl.py" \
       "the entry point is bin/cmfctl, installed as cmfctl"
else
  pass "README does not invoke cmfctl.py"
fi

if [[ $readme == *"constants.py"* && $readme != *"src/cmfctl/constants.py"* ]]; then
  fail "README points at constants.py by its real path"
else
  pass "README points at constants.py by its real path"
fi

assert_contains "$readme" "install.sh" "README tells you how to install it"

# --- relative links resolve ------------------------------------------------
# The move to docs/ broke three of these at once, and a broken link in a README
# is the first thing a stranger meets.
broken=()
while IFS= read -r doc; do
  dir=$(dirname "$doc")
  while IFS= read -r target; do
    [[ -z $target || $target == http* || $target == '#'* ]] && continue
    target=${target%%#*}
    [[ -z $target ]] && continue
    [[ -e $dir/$target ]] || broken+=("$doc -> $target")
  done < <(grep -oE '\]\([^)]+\)' "$doc" | sed -E 's/^\]\((.*)\)$/\1/')
done < <(find "$ROOT" -name '*.md' -not -path '*/.git/*')

if (( ${#broken[@]} == 0 )); then
  pass "every relative link in the docs resolves"
else
  fail "every relative link in the docs resolves" "${broken[@]}"
fi

# --- nothing identifying -------------------------------------------------
# capture.log is real traffic and was redacted by hand. Trusting that by
# memory is how the one that was missed gets published.
if leaked=$(git -C "$ROOT" grep -InE '([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}' -- . 2>/dev/null); then
  fail "no device address is committed anywhere" "$leaked"
else
  pass "no device address is committed anywhere"
fi

# --- the experiment is gone ------------------------------------------------
# try_anc.py proved the ANC write worked; that shipped as `cmfctl anc` and the
# method is written up in docs/FINDINGS.md. It has also been broken since the
# move, since it imported proto by bare name from the repo root.
if [[ -e $ROOT/try_anc.py ]]; then
  fail "the one-off ANC experiment is removed" "try_anc.py is still present"
else
  pass "the one-off ANC experiment is removed"
fi

report
