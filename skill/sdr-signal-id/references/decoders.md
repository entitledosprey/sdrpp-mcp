# Decoders and tools

## Via the sdrpp MCP `decode` tool (works alongside SDR++)

| decoder arg | Tool | Decodes | Install |
|---|---|---|---|
| pager, pocsag, flex | multimon-ng | POCSAG 512/1200/2400, FLEX | `sudo apt install multimon-ng` |
| aprs / afsk1200 | multimon-ng | AX.25 APRS packets | same |
| eas / same | multimon-ng | NOAA SAME / EAS headers (event, area FIPS codes, duration) | same |
| dtmf, zvei, morse | multimon-ng | DTMF digits, selcall tones, CW | same |
| ism | rtl_433 (offline on IQ) | ~250 protocols: weather stations, TPMS, remotes, sensors, meters | `sudo apt install rtl-433` |

The tool captures from SDR++'s IQ stream, so SDR++ keeps running. `record_iq` writes `.cu8`
files rtl_433 and most other tools can replay (`rtl_433 -r file.cu8 -s 250000`).

## SDR++ built-in modules (installed here)

- **Radio**: NFM/WFM (with RDS)/AM/DSB/USB/LSB/CW/RAW demod.
- **Meteor Demodulator**: Meteor-M LRPT QPSK → soft symbols for SatDump.
- **Pager decoder**: FLEX/POCSAG inside SDR++ (experimental).
- **M17 decoder**: M17 digital voice (ham).
- **ATV decoder**: analog TV.
- **Scanner**: steps through a range and stops on signals above a level.
- **Frequency Manager**: bookmarks (`export_bookmarks` writes the logbook here).
- **Recorder**: audio/baseband WAV recording.
- **IQ Exporter / Network sink / Rigctl server**: used by the MCP server.

## External tools worth installing (may need exclusive dongle access)

| Tool | For | Notes |
|---|---|---|
| dump1090-fa / readsb | ADS-B 1090 | Needs the dongle: stop SDR++ (`sdr_power off` doesn't release it; quit SDR++). apt: `dump1090-mutability`. |
| dump978-fa | UAT 978 | US general aviation. |
| acarsdec | ACARS | Can decode several channels at once from the dongle. |
| dumpvdl2 | VDL Mode 2 | 136.x MHz. |
| AIS-catcher | AIS ships | Coastal, Great Lakes and river traffic. |
| SatDump | Meteor LRPT, many satellites | Can work from SDR++ baseband recordings. |
| radiosonde_auto_rx | Weather balloons | Tracks and uploads to SondeHub. |
| rtlamr | Utility meters (ERT) | Needs rtl_tcp: SDR++ can't share, run it from the dongle directly. |
| SDRTrunk / OP25 | P25/DMR trunking (unencrypted only) | Java GUI / GNU Radio; ideally a second dongle. |
| direwolf | APRS / AX.25 (better than multimon) | Reads audio from a pipe or ALSA loopback. |
| WSJT-X | FT8 etc. on HF/6 m | Needs SSB audio routed via a virtual audio cable (PulseAudio null sink). |
| gpredict | Satellite pass predictions | Doppler-tunes SDR++ through its rigctl server. |

Exclusive-access tools: tell the user to quit SDR++ first, then run the tool with `!`.
