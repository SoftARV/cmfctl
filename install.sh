#!/bin/bash

# Installs cmfctl: puts the CLI on PATH. That is the whole job.
#
# There is nothing to compile and nothing to download -- cmfctl is stdlib
# Python talking RFCOMM through AF_BLUETOOTH -- so "installing" is one symlink
# and a handful of checks that fail here, where the message can be read,
# rather than later inside a bar widget that can only say "not connected".
#
# Safe to re-run. It never overwrites a file it did not create.

set -euo pipefail

REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
BIN_DIR="$HOME/.local/bin"
TARGET="$REPO/bin/cmfctl"
LINK="$BIN_DIR/cmfctl"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  cat <<USAGE
Usage: ./install.sh

Installs cmfctl from this checkout:

  * checks python3 and the kernel's Bluetooth support
  * symlinks bin/cmfctl into ~/.local/bin

Re-running is safe: an existing link to this checkout is left alone, and a
file that is not our symlink is never touched.
USAGE
  exit 0
fi

say() { printf '  %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*" >&2; }

printf '\ncmfctl installer\n\n'

problems=0

# --- dependencies ----------------------------------------------------------
# Everything missing is reported in one pass. Discovering prerequisites one
# run at a time is the kind of small rudeness that makes people give up.
missing=()

if ! command -v python3 >/dev/null 2>&1; then
  missing+=("python3 (3.9 or newer)")
else
  if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
    missing+=("python3 3.9 or newer (found $(python3 -V 2>&1 | cut -d' ' -f2))")
  fi
  # The one dependency that is neither a package nor a Python module: the
  # kernel has to expose Bluetooth sockets at all. Without it every command
  # would fail at connect time with an error nobody can act on.
  if ! python3 -c 'import socket; socket.AF_BLUETOOTH' >/dev/null 2>&1; then
    missing+=("a kernel with AF_BLUETOOTH support (BlueZ)")
  fi
fi

if (( ${#missing[@]} )); then
  warn "missing prerequisites:"
  for item in "${missing[@]}"; do
    warn "  - $item"
  done
  warn "install them and re-run; nothing has been changed"
  exit 1
fi
say "dependencies: python3 $(python3 -V 2>&1 | cut -d' ' -f2), AF_BLUETOOTH present"

# --- the CLI ---------------------------------------------------------------
mkdir -p "$BIN_DIR"

if [[ -L $LINK ]]; then
  if [[ $(readlink -f "$LINK") == "$(readlink -f "$TARGET")" ]]; then
    say "cmfctl: already linked at $LINK"
  else
    # A link pointing at another checkout is stale, not sacred -- this repo
    # moving is exactly how one appears.
    ln -sfn "$TARGET" "$LINK"
    say "cmfctl: re-pointed $LINK at this checkout"
  fi
elif [[ -e $LINK ]]; then
  # Not ours. A hand-written wrapper, or a copy someone made. Replacing it
  # would destroy work that we cannot recover, so refuse -- and do not claim
  # success, because cmfctl is not on PATH when this branch runs.
  warn "cmfctl: $LINK exists and is not a symlink; leaving it alone"
  warn "        remove it and re-run to link this checkout instead"
  problems=1
else
  ln -s "$TARGET" "$LINK"
  say "cmfctl: linked $LINK -> $TARGET"
fi

# --- reachability ----------------------------------------------------------
# The link can be perfect and the command still not found. Say so here; the
# alternative is the user meeting "command not found" with no idea why.
case ":$PATH:" in
*":$BIN_DIR:"*) : ;;
*)
  warn "$BIN_DIR is not on your PATH, so cmfctl will not be found"
  warn "        add it to your shell profile, e.g."
  warn "        export PATH=\"\$HOME/.local/bin:\$PATH\""
  ;;
esac

printf '\n'
if (( problems )); then
  warn "finished with problems; cmfctl is not installed"
  exit 1
fi

say "check it with:  cmfctl status --json"
printf '\n'
