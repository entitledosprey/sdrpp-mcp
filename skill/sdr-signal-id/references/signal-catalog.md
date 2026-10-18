# Signal catalog: how common signals look and sound

Measurements refer to `analyze_signal` output fields. "Width" = occupied bandwidth.
Good external reference for anything not here: the Signal Identification Wiki
(sigidwiki.com), which has waterfall images and audio samples. Point the user there for confirmation.

## Analog voice

| Signal | Where | Width | Waterfall look | Features | Sound |
|---|---|---|---|---|---|
| Broadcast FM | 88–108 MHz | ~200 kHz (+ HD Radio OFDM blocks ±130–200 kHz) | Wide solid band, steady | constant envelope, `wfm.stereo_pilot_19k`, `rds_57k` | music/talk; SDR++ WFM shows RDS name |
| NFM voice (public safety, ham, GMRS, business) | 136–174, 220, 420–470 MHz | 8–16 kHz (12.5 kHz channel ≈ 11 kHz occupied, 25 kHz ≈ 16 kHz) | Bursts of activity, push-to-talk | constant envelope, deviation rms 1–3 kHz, often `ctcss_hz` | voice, squelch tail, courtesy beeps on repeaters |
| Airband AM | 118–137 MHz | 6–8 kHz | Short transmissions, carrier line in the middle | strong `carrier_fraction`, symmetric | pilots/ATC, clipped speech; ATIS loops continuously |
| SSB voice | HF, 50.1+, 144.2, 432.1 | ~2.7 kHz one-sided | Lumpy, sloped one side, no carrier | `spectral_skew` large, no carrier, varying envelope | "Donald Duck" unless mode/tuning exact |
| CB AM | 26.965–27.405 | 6–8 kHz | like airband | | truckers ch19, skip during solar max |
| NOAA Weather Radio | 162.400–162.550 | ~10 kHz | continuous | constant, continuous | synthetic voice forecast loop; SAME bursts (AFSK 520.83 baud, 2083.3/1562.5 Hz) before alerts |

## Digital voice (identifiable, mostly not decodable here)

| Signal | Width | Signature |
|---|---|---|
| DMR (Tier II/III) | 12.5 kHz | 4FSK 4800 sym/s (±648/±1944 Hz). Single active slot → power pulses every 60 ms (`power_periodicity_s` ≈ 0.06). Repeaters with both slots look continuous. Harsh "buzzing" sound in FM. |
| P25 Phase 1 | 12.5 kHz | C4FM 4FSK 4800 sym/s (±600/±1800 Hz), continuous during a call, no TDMA. Control channels continuous 24/7. |
| P25 Phase 2 | 12.5 kHz | H-DQPSK (varying envelope) 6000 sym/s, TDMA 2 slots. |
| NXDN | 6.25 or 12.5 kHz | 4FSK 2400 (NXDN48) or 4800 (NXDN96) sym/s. |
| D-STAR | ~6 kHz | GMSK 4800 bps (2 levels, smooth), ham 2 m/70 cm. |
| System Fusion (C4FM) | 12.5 kHz | 4FSK 4800 sym/s on ham repeaters, looks like P25. |
| M17 | 9 kHz | 4FSK 4800 sym/s, ham; SDR++ has an M17 decoder module. |
| TETRA | 25 kHz | π/4-DQPSK 18 ksym/s, TDMA (not used in US public safety). |

Identification tip: the band and the user licensee (via RadioReference.com or FCC ULS lookup
by frequency) tell you more than the modulation alone.

## Data signals

| Signal | Where | Signature | Decoder |
|---|---|---|---|
| POCSAG pager | 929–932, 152/157/158 MHz | 2FSK ±4.5 kHz, 512/1200/2400 baud, bursts of a few seconds; distinct "brrrap" | `decode … pocsag` |
| FLEX pager | 929–932 | 2/4FSK 1600/3200 sym/s, transmissions on 1.875 s frame boundaries | `decode … flex` |
| APRS / AX.25 | 144.390 (NA), 145.825 (ISS) | NFM with AFSK 1200/2200 Hz tones, ~0.5–1 s bursts | `decode … aprs` |
| ACARS | 129–131.55 | AM carrier with MSK 2400 bps, ~0.5–2 s bursts, buzzy | acarsdec |
| VDL Mode 2 | 136.65–136.975 | D8PSK 10.5 ksym/s ~25 kHz bursts | dumpvdl2 |
| AIS | 161.975/162.025 | GMSK 9600, 26.7 ms bursts | AIS-catcher / rtl_ais |
| ADS-B / Mode S | 1090 | 1 Mbps PPM pulses, 120 µs; looks like vertical speckle across ~2 MHz | dump1090/readsb (needs dongle) |
| UAT | 978 | 1 Mbps CPFSK bursts | dump978 |
| Railroad EOT/HOT | 457.9375 / 452.9375 | FSK 1200 short bursts | softEOT, pyEOT |
| ISM sensors / remotes | 315, 345, 433.92, 915 | OOK (on/off pulses) or FSK, ms-long bursts, often repeated 3–10× | `decode … ism` (rtl_433) |
| Smart meters (ERT) | 912–928 | FHSS, OOK/FSK bursts | rtlamr |
| LoRa | 902–928 | chirp (diagonal lines on waterfall), 125/250/500 kHz | gr-lora |
| Radiosondes | 400–406, 1676–1682 | GFSK 4800 (RS41), 1–2 s cycles, launched 00Z/12Z (6–7 am/pm CT) | radiosonde_auto_rx |
| EPIRB/ELT | 406.0–406.1, 121.5 | 406: 0.5 s BPSK burst ~every 50 s; 121.5: swept AM tone (real emergencies are rare; tests on the hour's first 5 min) | |
| Meteor-M LRPT | 137.1 / 137.9 | QPSK 72 ksym/s ~120 kHz, only during passes, Doppler-shifting | SDR++ Meteor Demodulator → SatDump |
| Trunked control channel (P25/Motorola) | 806–869, 450–470 | continuous 24/7 digital carrier, never stops | identifies a trunked system; follow with SDRTrunk/OP25 (separate dongle) |
| LTE / 5G | 600–894+ | 1.4–20 MHz flat-topped OFDM block, continuous (downlink) | identify only; content is off-limits |
| ATSC TV | 54–608 MHz | 6 MHz flat block with small pilot at lower edge (+310 kHz) | identify the station via its channel |
| DME / TACAN | 962–1213 | paired pulses (~12 µs spacing), speckle | |

## Interference and artefacts

| Looks like | Usually is |
|---|---|
| Steady narrow carrier at exact MHz multiples / constant position when retuning in small steps | RTL-SDR or USB spur (birdie). Test: retune by 100 kHz; a real signal moves on the waterfall, a spur doesn't. |
| Spike exactly at centre frequency | DC offset of zero-IF tuner; masked by tools. |
| Mirror image of a strong signal on the opposite side of centre | IQ imbalance image; enable IQ correction in SDR++. |
| Many copies of a strong station everywhere / raised floor | Overload: lower gain. FM broadcast and pager towers are common culprits; an FM band-stop filter helps. |
| Broad hash every few kHz drifting slowly | Switching power supplies, LED drivers, PCs nearby. |
| Comb of lines every 15.734 kHz or so | Old monitor / video. |
| Wideband noise that rises and falls | Power line arcing, motors, plasma. |

## Good first targets (US listeners)

Reliable, legal, interesting:
1. **NOAA Weather Radio** 162.400–162.550 (NFM) — always on. Find which of the 7 channels the local transmitter uses.
2. **FM broadcast** with RDS (WFM) — see station names in SDR++.
3. **Airband** 118–137 AM — tower/approach for the nearest airport; ATIS loops.
4. **APRS** 144.390 — decode positions with `decode 144.39 aprs`.
5. **ISM 433.92 / 315 / 345** — neighbours' weather stations, TPMS, door sensors via `decode … ism`.
6. **Pagers** 929–932 — very common bursts; summarise, don't repeat personal content.
7. **ADS-B** 1090 — aircraft positions (needs dump1090 with SDR++ stopped).
8. **Radiosondes** ~400–406 MHz around 6–7 am/pm CT twice daily from the nearest NWS site.
9. **Railroad** 160.2–161.6 MHz AAR channels, plus EOT 457.9375.
10. **Meteor-M** weather satellite images during passes (137.1/137.9, needs a V-dipole or QFH).
