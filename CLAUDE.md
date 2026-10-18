# Development notes

## Layout

- `sdrpp_mcp/server.py`: FastMCP server and tool definitions; frequency parsing, tuning
  and passband helpers (`_in_band`, `_ensure_in_band`, `_tune_center`).
- `sdrpp_mcp/sdrpp.py`: SDR++ integration: config reading, `Rigctl` client, `live_center`
  (centre-probe trick), `capture_iq` (one-shot IQ Exporter read), `IQStream` (background
  thread, continuous chunks), `launch`.
- `sdrpp_mcp/dsp.py`: numpy/scipy DSP: spectrogram, noise floor, detection, channel
  extraction, demodulators, feature measurement, `classify`, audio/tone and stereo/RDS checks.
- `sdrpp_mcp/plots.py`: matplotlib (Agg) waterfall and sweep images.
- `sdrpp_mcp/bandplan.py`: US allocations (`ALLOCATIONS`) and named channels (`NOTABLE`).
- `sdrpp_mcp/meshcore.py`: MeshCore packet parser (cleartext fields only).
- `sdrpp_mcp/lora_gr.py`: standalone gr-lora_sdr flowgraph; runs under the **system**
  `/usr/bin/python3` (GNU Radio isn't in the venv), reads a cf32 file, prints JSON per frame.
- `sdrpp_mcp/logbook.py`: SQLite logbook and SDR++ Frequency Manager export.
- `setup_sdrpp.py`: one-off SDR++ configuration (run with SDR++ closed).
- `skill/sdr-signal-id/`: the companion skill (`SKILL.md` + `references/`).

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -e .   # install (editable)
.venv/bin/sdrpp-mcp                                   # run the stdio server
.venv/bin/python -c "import sdrpp_mcp.server"         # quick import check
```

There is no test suite. Test DSP changes against synthetic signals (NFM tone, WFM, AM, USB,
OOK, 2-FSK at known SNR) and, when hardware is available, against live references such as
broadcast FM, NOAA Weather Radio, or ATSC pilots for frequency accuracy. Restart the MCP
client connection after code changes; the server is a long-lived process.

## Constraints and gotchas

- **`mcp<2`**: the code uses `mcp.server.fastmcp.FastMCP`, which 2.x renamed.
- **SDR++ config value types**: IQ Exporter and recorder options are stored by *display name*
  (`"Baseband"`, `"TCP (Server)"`, `"Float32"`). The recorder `mode` must be an **int**
  (`0` = baseband); a string makes SDR++ crash at startup.
- **True centre frequency**: rigctl reports only the VFO, and SDR++ doesn't save `config.json`
  on rigctl retunes. `live_center()` triggers the "Center Probe" recorder and parses
  `_<hz>Hz_` from the filename. The result is cached for 30 s while the VFO is unchanged.
- **Tuning**: rigctl always uses SDR++'s normal tuning mode. A VFO jump outside the passband
  recentres, but not to a predictable offset. Always re-read the live centre and confirm
  `|target − centre|` is inside the usable band before measuring. `_tune_center` jumps away
  and back if the centre didn't follow.
- **DC spike**: mask ±`DC_MASK_HZ` (12 kHz) around centre, and ignore the outer
  `EDGE_FRACTION` (10%) of the band. `analyze_signal` retunes if a channel overlaps either.
- **Memory**: keep captures short. Multi-second complex64 captures at 2.4 MS/s plus
  spectrograms add up quickly.
- **Frequency Manager export** refuses while SDR++ is running, because SDR++ overwrites its config on exit.
  Mode ids: NFM 0, WFM 1, AM 2, DSB 3, USB 4, CW 5, LSB 6, RAW 7.
- **Decoders**: multimon-ng takes raw s16le audio at 22050 Hz. rtl_433 takes `cu8` IQ at 250 kS/s
  (`-r cu8:<file> -s <rate> -f <hz> -F json -M level`).
- **Tuning offset**: SDR++ recentres with the VFO about 885 kHz off centre after an
  out-of-view jump. `_tune_center` always approaches from below and learns that offset
  (`_approach_offset`), so later retunes land first try.
- **VFO restore**: tools that retune to reach a frequency wrap the work in `_keep_vfo()`.
- **watch_channel**: chunks are mixed with a continuous phase (`extract(..., n0=)`), and a burst
  still on air at a chunk end is carried into the next chunk, so packets aren't split. Output
  rate is 4x the channel bandwidth because gr-lora_sdr needs an integer oversampling factor.
  LoRa detection is `dsp.lora_check` (dechirp peak-to-mean; noise/FSK ≈ 8, LoRa ≫ 30).
  MeshCore: sync word 0x12, preamble 32 symbols at SF ≤ 8 (gr frame_sync is given 8 and
  still locks).

## Conventions

- Tools return plain dicts and strings. Errors raise `sdrpp.SdrppError` with a short fix hint.
- Frequencies are Hz internally. `parse_freq` accepts suffixes, and bare numbers below 1e4 are MHz.
- Tools that move the user's SDR++ view should restore the VFO, or report that they retuned.
- Keep the skill's legal guardrails: receive only, no decryption, no cellular or cordless-phone content.
  Summarise private traffic rather than repeating it.
