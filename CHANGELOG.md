# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While on `0.x`, the CLI surface may change between minor versions; see
[`tasks/plan.md`](tasks/plan.md) for the versioning policy.

## [Unreleased]

## [0.1.0] - 2026-08-28

Control of a CMF Headphone Pro from Linux, over the protocol its phone app
speaks. Battery, all six noise-cancellation modes, LDAC and the negotiated
codec, plus raw access to every command id lifted from Nothing X.

### Added

- **The protocol, reverse-engineered from live capture.** Bluetooth Classic
  RFCOMM on **channel 28** — no existing Nothing/CMF tool reaches this device,
  because they all hardcode channel 15. Frames are
  `55 <flags> <target> | cmd | len | fsn | payload | [crc]`, the flags byte
  deciding whether a CRC-16/MODBUS trailer is present. Every asynchronous
  notification the device pushes uses the CRC-less variant. Written up in
  [`docs/FINDINGS.md`](docs/FINDINGS.md).
- `battery`, and `status` — which gathers everything over a **single** RFCOMM
  link. That is what makes polling from a bar widget cheap: opening the link
  dominates the cost, so one call per value would be both slow and prone to
  `EBUSY`. `--json` for consumers.
- `anc`, reading and setting **all six modes** — `high`, `mid`, `low`,
  `adaptive`, `off`, `transparency`. The device supports six, not the three
  first assumed; `COMFORTABLE` and `SMART_2` exist in the app but this model
  rejects them, acking the write and sending no notification.
- **Resuming ANC returns to the level you left**, not to `high`. The
  headphones already store the remembered level in the `0xE003` payload's
  second field, which is what the phone app reads. Setting `low`, switching to
  `transparency` to talk, then switching back now lands on `low`.
- `codec`, and the codec in `status`. The LDAC **flag** and the **negotiated**
  codec are different facts — the flag says the headphones will offer LDAC,
  the codec is what host and device actually agreed on. Anything inferring one
  from the other misreports whenever they disagree. Read from PipeWire, so it
  costs no Bluetooth.
- `features`, decoding the supported-feature mask, and `dump`, which queries
  every known command to see what answers.
- `get` and `set` for any of the 128 command ids, so a command that has no
  wrapper is still reachable.
- `listen`, streaming decoded notifications, and `probe`, scanning RFCOMM
  channels — useful for porting to another model.
- `install.sh`, which symlinks `bin/cmfctl` onto `PATH`. It refuses to
  overwrite a file it did not create, and reports every missing prerequisite
  in one pass.

### Known behaviour

- **Writing the LDAC flag power-cycles the headphones.** They announce
  power-off, restart and re-pair on their own — roughly 6–9 seconds — and
  because A2DP capabilities are exchanged when the link is established, that
  restart *is* the renegotiation. No host action is needed, and forcing a
  reconnect on top of it strands the card on a dead profile.
- Bass boost is acked and ignored by this model, which has the physical Energy
  Slider instead. The Energy Slider and volume are not readable over this
  channel.
- Key and gesture configuration, and the custom EQ curve, are not yet decoded.
- `ldac`, `spatial` and `eq` have no dedicated subcommand yet. Their command
  ids and payload formats are in [`docs/FINDINGS.md`](docs/FINDINGS.md) and
  reachable through `set`.

[Unreleased]: https://github.com/SoftARV/cmfctl/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SoftARV/cmfctl/releases/tag/v0.1.0
