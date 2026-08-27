#!/bin/bash
# The version string, and everything that has to agree with it.
#
# src/cmfctl/__init__.py is canonical. This file's job is to stop every other
# copy drifting from it, so the expected value is *derived* rather than typed
# here -- a release bump then touches the files the procedure names and never
# a test.
#
# cli.py imports __version__ instead of repeating it, so --version cannot drift
# by construction. That is the difference from pip-plugin, whose bash CLI cannot
# import and therefore needs a genuine two-file cross-check. What remains able
# to drift here is the changelog and the git tag, which is what this covers.
set -uo pipefail

TEST_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(dirname "$TEST_DIR")
# shellcheck source-path=SCRIPTDIR source=lib/assert.sh
source "$TEST_DIR/lib/assert.sh"

INIT="$ROOT/src/cmfctl/__init__.py"
CLI="$ROOT/bin/cmfctl"
CHANGELOG="$ROOT/CHANGELOG.md"

assert_file "$INIT" "the package declares a version somewhere"
if [[ ! -f $INIT ]]; then
  report
  exit $?
fi

VERSION=$(grep -m1 '^__version__' "$INIT" | cut -d'"' -f2)

if [[ -n $VERSION ]]; then
  pass "__init__.py declares __version__ ($VERSION)"
else
  fail "__init__.py declares __version__" "no __version__ assignment found"
  report
  exit $?
fi

if [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  pass "the version is semver"
else
  fail "the version is semver" "got: $VERSION"
fi

# --- the CLI ---------------------------------------------------------------
runtime=$(python3 "$CLI" --version 2>&1 | tr -d '[:space:]')
status=$?
assert_eq 0 "$status" "--version exits 0"
assert_eq "$VERSION" "$runtime" "--version reports the declared version"

help_text=$(python3 "$CLI" --help 2>&1)
assert_contains "$help_text" "--version" "--version is listed in --help"

# --- one copy, not several -------------------------------------------------
# Docs are excluded deliberately: a changelog is *supposed* to name versions,
# and the spec and task list discuss them. What must not happen is a second
# copy in code, which is the kind that goes stale silently.
copies=$(grep -rF "$VERSION" \
  "$ROOT/src" "$ROOT/bin" "$ROOT/tools" "$ROOT/install.sh" 2>/dev/null | wc -l)
assert_eq 1 "$copies" "the version literal appears exactly once in the code"

# --- the changelog ---------------------------------------------------------
# The only copy that can drift, since cli.py imports the canonical one.
if [[ -f $CHANGELOG ]]; then
  # The newest heading that is not [Unreleased] -- the last released version.
  latest=$(grep -m1 -E '^## \[[0-9]' "$CHANGELOG" | sed -E 's/^## \[([^]]+)\].*/\1/')
  assert_eq "$VERSION" "$latest" "the newest released CHANGELOG entry matches"
else
  skip "T5" "CHANGELOG.md does not exist yet; changelog cross-check deferred"
fi

# --- the git tag -----------------------------------------------------------
# Only meaningful once a release is cut. Named so the debt is visible.
head_tag=$(git -C "$ROOT" tag --points-at HEAD 2>/dev/null | head -1)
if [[ -n $head_tag ]]; then
  assert_eq "v$VERSION" "$head_tag" "the tag on HEAD matches the declared version"
else
  skip "T12" "HEAD is not tagged; tag/version cross-check deferred to release"
fi

report
