"""cmfctl — control a CMF Headphone Pro from Linux.

The package holds the protocol (`proto`), the command table lifted from
Nothing X (`constants`), and the command line itself (`cli`). Nothing here
touches the network at import time, so the pure parts can be tested with the
headphones switched off.

Reached through `bin/cmfctl`, which is what `install.sh` puts on PATH.
"""

# The canonical version. cli.py imports this rather than repeating it, so
# `cmfctl --version` cannot drift from the package; test/version_test.sh
# derives what it expects from here and guards the copies that can --
# the changelog entry and the git tag.
__version__ = "0.1.0"
