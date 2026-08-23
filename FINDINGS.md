# CMF Headphone Pro — protocol notes

Device: `CMF Headphone Pro` (address redacted)
Host: Arch / BlueZ 5.87, connected over Bluetooth Classic.
All findings below are from live capture on real hardware, 2026-08-23.

## Transport

**RFCOMM channel 28.** Not channel 15, which is what every existing Nothing/CMF
tool hardcodes — that alone explains why none of them detect this device.

Channels open on the device: 12, 13, **28**, 30, and 17. Channel 28 is the one
speaking the Nothing protocol. Channel 17 answers with different framing
(`03 01 00 03 73 c9 eb`) and has not been identified. 12, 13 and 30 accept a
connection but stay silent.

The device advertises SPP (`00001101-0000-1000-8000-00805f9b34fb`) plus four
vendor-specific UUIDs:

    0000fdb3-3817-47d9-a10a-1f6656618f8e
    66666666-6666-6666-6666-666666666666
    aeac4a03-dff5-498f-843a-34487cf133eb
    df21fe2c-2515-4fdb-8886-f12c4d67927c

## Command ids come from the app

Nothing X 3.7.3 carries an unobfuscated command table at
`com.nothing.base.protocol.constant.ProtocolConstant` — 128 ids across `Query`,
`Set` and `Notification`. It is extracted verbatim into `constants.py`, so the
guessing stage is over. Everything captured empirically matches a named entry:

| wire bytes | id | name |
|-----|----|------|
| `0f f0` | `0xF00F` | `SET_CURRENT_NOISE_REDUCTION` |
| `01 e0` | `0xE001` | `EVENT_BATTERY_CHANGED` |
| `03 e0` | `0xE003` | `EVENT_NOISE_REDUCTION_LEVEL_CHANGED` |
| `14 e0` | `0xE014` | `EVENT_MAGIC_BUTTON` (the roller) |
| `41 40` | `0x4041` | response to `GET_HOST_LAG_MODE` |

**The command id is little-endian**, which the raw capture alone could not
settle — `0f f0` read big-endian looks like a plausible `0x0FF0`, but the app's
table proves it is `0xF00F`.

**Responses clear bit `0x8000`**: `0xF00F` -> `0x700F`, `0xC041` -> `0x4041`.

## Framing

    55 <flags> <target> | cmd_hi cmd_lo | len_lo len_hi | fsn | payload… | [crc_lo crc_hi]
    │                     │               │               │               └ present only when flags & 0x60
    │                     │               │               └ sequence number
    │                     │               └ u16 little-endian payload length
    │                     └ u16 big-endian command id
    └ sync byte, always 0x55

`flags` decides whether a CRC is appended:

| flags | CRC | seen on |
|-------|-----|---------|
| `0x60` | yes | frames the device sends at connect; all published Ear-line commands |
| `0x00` | no  | every asynchronous notification this device pushes |

`target` varies (`0x01`, `0x03`, `0x06`) and looks like a stream/target id, but
its meaning is not established.

CRC is **CRC-16/MODBUS** — init `0xFFFF`, poly `0xA001` (reflected), computed
over every byte from the sync through the end of the payload, appended
little-endian. Verified two ways: against published Nothing Ear (2) captures,
and against the CRC-bearing frames this device emits.

## Commands observed

| cmd | flags | payload | meaning |
|--------|-------|---------|---------|
| `0x4140` | `0x60` | `00` | hello, first frame after connect |
| `0x097C` | `0x60` | `00 04 00` | second connect frame, capability-ish |
| `0x01E0` | `0x00` | `01 06 <pct>` | **battery**, `<pct>` is percent |
| `0x03E0` | `0x00` | `01 <mode> 00 02 01 00` | **ANC state** |
| `0x14E0` | `0x00` | `0b` / `01` | playback or wear state, toggles in pairs |
| `0x19E0` | `0x00` | `00 01` / `00 00` | unidentified state toggle |

### Battery — confirmed

`0x01E0` arrives every 10 seconds with payload `01 06 37`. `0x37` = 55, and
BlueZ independently reported `Battery Percentage: 0x37 (55)` at the same moment.
Third payload byte is the battery percentage.

### ANC — confirmed by correlation

`0x03E0` fires each time the ANC mode changes. The mode byte matches the
published Ear-line values exactly:

| byte | mode |
|------|------|
| `0x01` | ANC on |
| `0x05` | off |
| `0x07` | transparency |

Capture correlates with cycling the button: `07` → `05` → `01` → `05`.

## Host -> device commands

### Set ANC — working

The Ear-line setter is accepted verbatim by this device:

    cmd 0x0FF0, flags 0x60, target 0x01, payload  01 <mode> 00

Example, switch to transparency:

    55 60 01 0f f0 03 00 01 01 07 00 fa 77

The device answers with an ack on `0x0F70`, then pushes the usual `0x03E0`
state notification carrying the new mode. Mode bytes are the same as above
(`0x01` anc, `0x05` off, `0x07` transparency).

### Set LDAC — working

`SET_LHDC_COMMANDS` is the hi-res toggle, used for LDAC on this device (the app
ships both `hight_quality_audio_lhdc` and `hight_quality_audio_ldac_copy`
strings against the same command):

    set:   cmd 0xF01C, payload 01 (on) / 00 (off)
    query: cmd 0xC029, no payload -> response 0x4029, last byte is the state

From `TWSDeviceExtKt.lhdc(TWSDevice, Boolean)` in the app, confirmed against
hardware in both directions.

**LDAC is off from the factory.**

**Writing this command power-cycles the headphones.** They announce power-off,
restart, and re-pair on their own — audible, and visible on the host as a
~6-9 second disconnect. Nothing needs to be done about it: A2DP capabilities
are exchanged when the link is established, so the restart *is* the
re-negotiation, and the new codec set is live as soon as the device is back.

Measured, touching nothing after the write:

    t=3s   connected=yes  codec=ldac
    t=6s   connected=no   codec=          <- device restarting
    t=9s   connected=yes  codec=aac       <- back, re-negotiated by itself

and symmetrically ~9s to come back on LDAC when enabling it.

Do **not** disconnect or cycle the A2DP profile to "apply" the change. That was
an early misreading: an A2DP teardown on its own (`pactl set-card-profile off`,
or switching to HFP) leaves the device connected and is harmless, and every
disconnect observed during testing was the write's own restart. Forcing a
reconnect on top only leaves the card stranded on a dead profile.

This also makes the flag a set-once affair rather than something to toggle
casually, which is why the bar widget only reports LDAC status.

### Command ranges

| range | meaning |
|-------|---------|
| `0xC000`+ | `Query` — read something |
| `0xF000`+ | `Set` — change something |
| `0xE000`+ | `Notification` — pushed by the device, unsolicited |

Responses to a `Query`/`Set` are the request id with bit `0x8000` cleared.

## What this model supports

`GET_SUPPORTED_FEATURE` is a little-endian bitmap (`DeviceSupportFeature`);
`GET_EXTRA_FEATURE_STATUS` is a count byte then `(feature_id, enabled)` pairs
(`DeviceExtraFeatureStatus`). On this unit:

    supported (0x0002AB43): wear-detect, game-mode, google-fast-pair,
      new-mobile, multi-split, auto-reconnect, denoise-anc,
      comfortable-mode, denoise-enc

    toggleable, all on: game-mode, google-fast-pair, new-mobile, multi-split,
      auto-reconnect, denoise-anc, denoise-enc, volume-adjust, song-switch

Of the 63 `Query` commands, **25 answer and 37 stay silent** — silence is how
the device says "not implemented on this model".

### Settings that work

| setting | set | get | payload |
|---------|-----|-----|---------|
| ANC | `0xF00F` | `0xC00E` | `01 <mode> 00`, mode `01`/`05`/`07` |
| LDAC | `0xF01C` | `0xC029` | `01` / `00` |
| Spatial audio | `0xF052` | `0xC04F` | `[on]` or `[on, head_tracking]` |
| EQ mode | `0xF010` | `0xC01F` | `[mode]` |

EQ modes (`EQModeEntity.Mode`): 0 balanced, 1 voice, 2 more-treble,
3 more-bass, 4 dirac, 5 custom, 6 new-voice, 7 new-instrument.

### Accepted but ignored

`SET_BASS_BOOST` (`0xF051`, payload `[on, level]`) is acked by the device, but
`GET_BASS_BOOST` keeps returning `00 00` afterwards. The Headphone Pro appears
not to implement a software bass boost — reasonable, since it has the physical
Energy Slider instead. An ack alone does **not** mean a command took effect;
always read the value back.

### Control customisation — structure known, vocabulary not

Nothing calls these "gestures": input events on the physical controls, each
bound to an action. On an over-ear the inputs are the roller and the button,
not touch gestures — the term is inherited from their earbuds.

The app's own resource strings give the vocabulary:

    inputs   single_press, double_press, triple_press,
             long_press / press_hold, double_press_hold,
             control_ic_rotate   (the roller)

    actions  control_play_pause, control_answer_call,
             control_answer_hang_up, control_decline_incoming_call,
             control_no_action

`GET_KEY_CONFIGURATION` (`0xC018`) returns, on this unit:

    04 | 06 0a 07 01 | 06 0a 01 0b | 06 05 01 23 | 06 01 07 0a

A leading count of 4 — matching four configurable inputs — followed by four
4-byte entries, one binding each. Every entry starts with `0x06`, which is
therefore not the input id; its meaning is unknown.

`0x0b` appears both here and as an `EVENT_MAGIC_BUTTON` payload, which is
suggestive but not proof.

**Deliberately not implemented.** Reading is harmless, but writing a wrong
mapping would silently rebind the controls with no way to reset them except a
phone. Finishing this needs the model's `IOTEar<Codename>GestureAction` enum,
and the codename is not yet pinned down — the over-ear candidates (packages
with no case references) are `elekid`, `forretress`, `heracross`, `hoothoot`.

`SET_KEY_CONFIGURATION` is `0xF003`.

## Notable negative result

**The Energy Slider emits nothing.** Moving it fully to bass and fully to treble
produced no frames at all, so it is handled internally rather than reported over
RFCOMM. Volume changes are likewise absent — those go over AVRCP, not this
channel.

## Not yet done

- No host→device write has been attempted. The set-ANC command id is unknown;
  the Ear line uses `0x0FF0`, this device notifies on `0x03E0`.
- `0x14E0` and `0x19E0` semantics unconfirmed.
- Channel 17's protocol unidentified.
- LDAC toggle, EQ, and spatial audio commands not located.

## Next steps

1. Pin the Headphone Pro's codename, pull its `IOTEar*GestureAction` enum, and
   implement `cmfctl controls` (read and set bindings by name). Cross-check
   against `EVENT_MAGIC_BUTTON` payloads captured while pressing each control.
2. Decode `GET_CUSTOM_EQ_VALUE` (109 zero bytes here) for per-band custom EQ.
3. Identify `0xE019`, pushed by the device but absent from the app's table.
4. Identify what RFCOMM channel 17 speaks.

## Files

| file | |
|------|--|
| `proto.py` | framing, CRC, build/parse, RFCOMM connect |
| `listen.py` | passive logger — sends nothing, records what the device pushes |
| `cmfctl.py` | the CLI: `battery`, `anc [mode]`, `listen`, `probe` |
| `try_anc.py` | the experiment that located the set-ANC command |
| `constants.py` | all 128 command ids, extracted from Nothing X 3.7.3 |
| `capture.log` | the raw capture these findings come from |
