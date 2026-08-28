# Working on cmfctl

Rules this repo actually runs on. Most were learned the expensive way during
the 0.1.0 reorganisation; the reasoning is kept because a rule without its
reason gets dropped the first time it is inconvenient.

Design is in [`docs/SPEC.md`](docs/SPEC.md), protocol findings in
[`docs/FINDINGS.md`](docs/FINDINGS.md).

## The load-bearing things

**`bin/cmfctl` resolves its own path with `realpath`.** `install.sh` symlinks it
into `~/.local/bin`, so at run time `__file__` is the *symlink*. Only resolving
it finds `src/`. Break this and `cmfctl` keeps working in the repo while failing
for everyone who installed it — the least useful way for it to break. Any test
of it must run from **outside** the repo, or it passes regardless.

**Stdlib only.** No dependency is what lets `install.sh` be a single symlink.
Adding one changes the install story, so it is a decision, not a convenience.

**`decompiled/` is never committed.** It is derivative of Nothing's proprietary
app. The reason is written in `.gitignore`; leave it there.

**No device address, ever.** `docs/capture.log` is real traffic redacted by
hand. A MAC pushed to a public repo cannot be recalled by deleting it, so CI
greps the entire history, not just the diff.

**`proto.py` is reverse-engineered and expensive to re-derive.** Move it, format
it, test it — but changing what it puts on the wire needs hardware to confirm.

## Code

Comments explain **why**, never what. `constants.py` is resolved from the app's
own table "rather than transcribed by hand" because a hand-typed id silently
produces a command the device ignores — that is the kind of thing worth a line.

Match the surrounding voice. Prose comments run to the margin deliberately;
`ruff.toml` leaves `E501` out for that reason.

## Version

One canonical source: `__version__` in `src/cmfctl/__init__.py`. `cli.py`
**imports** it, so `--version` cannot drift. Never add a second literal —
`version_test.sh` fails if the string appears more than once in the code.

`CHANGELOG.md` follows Keep a Changelog with `## [Unreleased]` on top and dated
release headings. Write what the release *does*, not "initial release".

## Tests

`./test/run.sh` — needs no headphones and no network. Anything that does is a
manual checklist item, and must say so rather than being quietly skipped.

- **Derive expected values, never hardcode them.** A release bump should touch
  the files the procedure names and never a test.
- **Fixtures come from real captures.** A hand-typed frame only proves the code
  agrees with whoever typed it. `proto.build()` reproducing a captured device
  frame byte-for-byte is the strongest check in the suite.
- **A skip names the task that will remove it**, or reports `n/a` with the
  reason. An unexplained skip is how a test quietly stops testing anything.
- **A missing linter skips loudly and never fails.** `ruff` is a CI-only gate;
  a runner you cannot run locally stops being run.
- **Failures must carry their evidence.** An assertion reporting only
  `expected 0, actual 1` cost a push per guess when it failed on CI and passed
  locally. Include the output.
- Verify a new guard actually fires — break something on purpose and watch it
  fail — before trusting it.

## Lint

`ruff.toml` pins the rule set on purpose. Ruff's defaults widen between
releases, and an inherited selection means CI failing on someone else's release
schedule. Exclusions are listed there with reasons; add to them the same way.

## Releasing

Tag **after** merging and after CI is green, so `v<x.y.z>` names a commit that
is actually on `main`. `python3 -m compileall -q bin src tools`, `./test/run.sh`,
then tag, push with `--follow-tags`, then `gh release create`.
