"""cmfctl — control a CMF Headphone Pro from Linux.

The package holds the protocol (`proto`), the command table lifted from
Nothing X (`constants`), and the command line itself (`cli`). Nothing here
touches the network at import time, so the pure parts can be tested with the
headphones switched off.

Reached through `bin/cmfctl`, which is what `install.sh` puts on PATH.
"""
