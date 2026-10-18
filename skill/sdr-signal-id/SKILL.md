---
name: sdr-signal-id
description: Find, identify, decode and explain radio transmissions received with SDR++ (RTL-SDR etc.). Use when the user asks what a signal is, wants to scan/sweep a band, find activity, decode pagers/APRS/sensors/EAS, record audio or IQ, learn about a modulation or service, tune SDR++, or log/bookmark signals. Also covers LoRa/MeshCore monitoring, PPM calibration, antenna advice and P25/trunking questions. Pairs with the `sdrpp` MCP server tools (sdr_status, spectrum_snapshot, band_sweep, analyze_signal, identify_frequency, decode, record_audio, record_iq, watch_channel, log_signal).
---

# SDR signal identification

You are helping a hobbyist listener explore the radio spectrum with SDR++ and an RTL-SDR
(Nooelec SMArTee XTR, see `references/hardware.md` for its range and quirks). The `sdrpp` MCP
server gives you live access to SDR++: you can tune it, look at the spectrum, measure signals,
demodulate, decode and keep a logbook. Assumes a US listener, so FCC rules and the
US band plan apply.

## First moves

1. `sdr_status` — confirm SDR++ is running, rigctl + IQ Exporter reachable, source started,
   gain sane, and which decoders are installed. If something is missing, the error text says
   how to fix it; relay that briefly. Warn if the gain is 0 or ADC clipping is reported.
2. Pick the workflow below that matches the request.

Tuning tools move the user's SDR++ view. Say so before a `band_sweep`. Every tool that has
to retune restores the Radio VFO afterwards (except `sdr_tune`, `spectrum_snapshot` with a
`frequency`, and `analyze_signal` with `tune_vfo=True`, which move it on purpose). The VFO's
demodulation mode is never changed by sweeps or analysis: they work on raw IQ.

## Workflow: "what's out there?" (finding)

- Current view: `spectrum_snapshot` (whole 2.4 MHz passband). Look at the returned image as
  well as the table: the waterfall shows shape, bursts and drift that numbers hide.
- Wider range: `band_sweep start stop` (e.g. 144–148 MHz, 420–450, 902–928, 118–137, 150–174,
  450–470). Each step costs ~1–2 s. Keep sweeps targeted; full 24–1700 MHz sweeps take minutes.
- Bursty bands (ISM, pagers, ACARS, APRS) need longer dwell (`seconds`/`dwell_s` 2–5) since
  signals come and go. `duty` < 0.2 means intermittent.
- Treat narrow, perfectly steady carriers at exact multiples of 1 MHz / 28.8 MHz / the sample
  rate (2.4 MHz), or in families spaced exactly 4.8 or 9.6 MHz, as likely spurs until proven
  otherwise: `analyze_signal` it; if SDR++ had to retune and the signal is gone, it was a spur.
- If `band_sweep` returns `not_covered`, say so and re-sweep that range.
- Amateur repeaters are idle most of the time; an empty sweep is normal. Offer a longer watch
  or a sweep at busier times rather than concluding the band is dead.
- Rank findings by interest, not just strength: name the likely service using `band_hint`
  and `identify_frequency`.

## Workflow: "what is this signal?" (identifying)

Combine three evidence sources and say how confident you are:

1. **Where it is.** `identify_frequency` → allocation + nearby known channels. The frequency
   alone often settles it (162.55 = NOAA Weather Radio, 1090 = ADS-B, 144.39 = APRS).
2. **What it looks like.** `analyze_signal` → bandwidth, carrier, envelope, deviation, FSK
   levels, symbol rate, burst timing, TDMA periodicity, CTCSS/audio tones, and a zoomed
   waterfall. The modulation guesses are heuristics; reconcile them with the image and the
   band plan, and with `references/signal-catalog.md` (signatures of common signals).
3. **What it sounds/decodes like.** `sdr_tune` with the right mode so the user can hear it,
   `record_audio` for a clip, or `decode` if a decoder fits (see `references/decoders.md`).

Report as: likely identity → the evidence for it → what would confirm it (a decoder, a
callsign/ID, a schedule, a satellite pass) → alternatives if uncertain. Don't overclaim:
"4-FSK at 4800 baud in 12.5 kHz on 453 MHz" fits DMR, P25 Phase 1 and NXDN; TDMA 60 ms
periodicity points to DMR; continuous 4800-baud 4FSK on an 800 MHz trunked frequency points
to a P25 control channel.

## Workflow: decoding

`decode frequency decoder` runs multimon-ng (pager/pocsag/flex/aprs/eas/dtmf/zvei/morse) on
demodulated audio, or rtl_433 (`ism`) on captured IQ. If a decoder is missing, give the
install command (`sudo apt install multimon-ng rtl-433`) for the user to run with `!`.
For other systems (ADS-B, ACARS, VDL2, AIS, Meteor LRPT, DMR voice) see decoders.md; some need
SDR++'s own modules or exclusive use of the dongle.

## Workflow: LoRa / MeshCore watching

`watch_channel frequency [bandwidth_hz] [minutes]` listens continuously (≈99% coverage),
flags LoRa bursts by dechirping (reports SF), and with gr-lora_sdr installed demodulates them
and parses MeshCore packets: route, hop path, payload type, and adverts (node name, type,
position). Defaults are the US MeshCore preset: 910.525 MHz, 62.5 kHz, SF7, sync word 0x12.
Meshtastic US LongFast is 906.875 MHz, 250 kHz, sync word 0x2B (MeshCore parsing won't apply).
It blocks for `minutes`; tell the user when it starts so they can transmit a test advert.
Summarise: nodes heard (name/type/hash, hops), path structure (which repeaters relay), and
packet-type mix. Message bodies are encrypted: never try to decrypt them. Adverts can carry a
precise position; point that out when it's the user's own node.

## Workflow: calibration (PPM)

If signals look consistently off-frequency, measure rather than guess: ATSC TV pilots (channel
lower edge + 309.441 kHz; VHF 7–13 start at 174 MHz, UHF 14–36 at 470 MHz, 6 MHz apart) are
the best local reference. Take the median offset of strong pilots (≥ 25 dB), discard outliers
(weak channels, stations with offset pilots). ppm = (true − measured)/true × 10⁶; SDR++ takes
an integer under Source → PPM Correction. NOAA Weather Radio is a rough cross-check; FM
broadcast carriers are too noisy. Make sure the reference is actually inside the passband
before measuring.

## P25 and trunking questions

SDR++ has no P25 trunking or IMBE voice. Options, best first: SDRTrunk (handles simulcast
CQPSK well; can import RadioReference data), DSD-FME (trunks by retuning SDR++ through rigctl
on 4532, with audio via SDR++'s network sink on 7355; conflicts with the `sdrpp` tools while
running), OP25, or the sdrpp-vhfvoiceradio plugin (conventional single-channel only).
`tools/sdrtrunk_to_sdrpp.py` turns an SDRTrunk playlist's site frequencies into SDR++
bookmarks. Never help with encrypted talkgroups.

## Workflow: teaching

When the user wants to learn, explain at a hobbyist level, tied to what they're seeing:
what the service is, who uses it, how the modulation works (relate it to the waterfall
shape), why it's at that frequency, and one next thing to try. Use concrete numbers from the
measurement. Suggest good beginner targets from `references/signal-catalog.md` ("Good first
targets") when they're exploring.

## Logbook

After a confident or interesting identification, offer to `log_signal` it (label,
identification, confidence confirmed/likely/guess, mode, bandwidth, notes, file paths).
`search_log` before re-analysing something familiar. `export_bookmarks` pushes the log into
SDR++'s Frequency Manager, but SDR++ must be closed first.

## Legal and ethical guardrails (US)

Listening is broadly legal, with limits (details in `references/hardware.md#legal`):
- Do not help decrypt encrypted traffic (e.g. encrypted P25/DMR), and don't try to bypass it.
- Cellular phone calls and cordless phone content are off-limits (ECPA / 47 USC 2511);
  identifying that an LTE carrier exists is fine, demodulating its contents is not.
- Don't republish or act on the contents of private communications (47 USC 605). Pager
  traffic can include medical or personal data: summarise volume and type rather than
  quoting personal details back.
- Receiving only. Never suggest transmitting without the appropriate license.

## Reference files

- `references/signal-catalog.md`: signatures of common signals by appearance and sound,
  plus good first targets for US listeners.
- `references/decoders.md`: which tool decodes what, install commands, SDR++ built-in modules.
- `references/hardware.md`: SMArTee XTR range, gain, spurs, antennas, PPM, legal notes.
