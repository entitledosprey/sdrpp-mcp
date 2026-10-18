# Hardware, reception quality and legal notes

## The receiver: Nooelec NESDR SMArTee XTR

- Tuner: Elonics E4000 (that's what "XTR" means), RTL2832U ADC, 8-bit, TCXO (≈0.5 ppm, so PPM
  correction usually 0).
- Range roughly **65–2300 MHz** with a **gap around 1100–1250 MHz** (E4000 PLL gap).
  Below ~65 MHz (CB, 10 m, 6 m, HF) it is weak or deaf; HF needs an upconverter (e.g. Ham It Up)
  plus an SDR++ frequency offset. E4000 does not support direct sampling.
- Has a bias tee ("biasT" in config) to power an LNA. Only enable it when an LNA/active antenna
  that needs power is connected.
- Max stable sample rate 2.4 MS/s (2.56 may drop samples).

If unsure of the tuner, SDR++'s log on source start prints the tuner type.

## Gain

- Gain 0 means minimum gain: weak signals will be missing. Typical good starting point is
  ~30–40 dB on the E4000 slider, then adjust: raise until the noise floor rises a few dB with no
  signal present, stop before strong signals sprout copies (overload). `sdr_status` warns about
  ADC clipping.
- Tuner AGC on is fine for casual listening; manual gain is better for measuring.
- Near FM/pager/TV towers, an FM band-stop filter dramatically reduces overload.

## Antennas (biggest factor in what you can hear)

- The stock telescopic/mag-mount whip works for strong local signals (FM, NOAA, local repeaters,
  pagers, ISM nearby). For a quarter-wave whip, element length (cm) ≈ 7125 / f(MHz):
  162 MHz → 44 cm, 433 MHz → 16.5 cm, 1090 MHz → 6.5 cm.
- Dipole length per side ≈ 7125 / f(MHz) cm; V-dipole at 120° with 53 cm legs for 137 MHz satellites.
- Height and getting outside/near a window beat everything else. Metal-coated (low-E) windows
  block a lot.
- Use good coax; RG-174 thin cable loses several dB per metre at UHF.

## Spurs and artefacts

- RTL dongles produce birdies at multiples of 28.8 MHz (the crystal) and others from USB noise.
  Spurs stay put on screen when you retune by a small amount; real signals move.
- Use a USB extension cable to get the dongle away from the PC.

## Legal (US) {#legal}

- Receiving radio is generally legal. Exceptions and limits:
  - **ECPA (18 USC 2510–2511):** intercepting cellular, cordless phone, and other private
    electronic communications not "readily accessible to the general public" is illegal;
    encrypted or scrambled transmissions are not readily accessible.
  - **47 USC 605:** don't divulge or use the contents of non-public communications you overhear
    (e.g. pager messages, business dispatch) for your or others' benefit.
  - Scanner use in a vehicle is restricted in some states (e.g. Indiana, Kentucky, Minnesota,
    Florida, New York) unless licensed. Illinois has no general mobile-scanner ban, but check.
- Public broadcast, amateur, NOAA weather, aviation, marine, APRS, ADS-B, weather satellites and
  ISM telemetry are commonly monitored by hobbyists.
- Transmitting needs a license (amateur, GMRS) or certified equipment: receive-only here.
