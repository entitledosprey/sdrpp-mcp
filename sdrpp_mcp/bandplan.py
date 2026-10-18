"""US (FCC / ITU Region 2) band plan and notable-frequency reference.

Frequencies are in MHz here for readability; lookup() takes Hz.
This is a practical listener's guide, not a regulatory document.
"""

# (start_mhz, stop_mhz, name, typical modes / notes)
ALLOCATIONS = [
    (0.53, 1.71, "AM broadcast (MW)", "AM, 10 kHz channels"),
    (1.8, 2.0, "160 m amateur", "CW, LSB, digital"),
    (2.3, 26.1, "Shortwave (HF) broadcast/utility/amateur mix", "AM broadcast, SSB utility, CW, RTTY, FT8; needs direct sampling or upconverter on RTL-SDR"),
    (26.965, 27.405, "CB radio (40 ch)", "AM (and SSB on ch 36-40); ch 9 emergency 27.065, ch 19 highway 27.185"),
    (28.0, 29.7, "10 m amateur", "CW, USB, FM repeaters 29.6+, FT8 28.074"),
    (30.0, 50.0, "VHF low band", "Public safety/business/military FM, mostly legacy; 46-49 MHz old cordless phones"),
    (50.0, 54.0, "6 m amateur", "USB/CW (50.125 calling), FT8 50.313, FM 52.525"),
    (54.0, 72.0, "TV VHF-low ch 2-4 (mostly vacant)", "ATSC 8VSB 6 MHz wide if present"),
    (72.0, 76.0, "72-76 MHz fixed/RC/aux", "R/C models, paging, hearing assist"),
    (76.0, 88.0, "TV VHF-low ch 5-6 (mostly vacant)", "ATSC 8VSB 6 MHz"),
    (88.0, 108.0, "FM broadcast", "WFM ~200 kHz, 19 kHz stereo pilot, RDS at 57 kHz, HD Radio OFDM sidebands"),
    (108.0, 118.0, "Aviation navigation (VOR/ILS)", "AM with 30 Hz/9960 Hz nav tones, Morse ident; 108-112 ILS localizer"),
    (118.0, 137.0, "Aviation voice (airband)", "AM, 25 kHz/8.33 kHz channels; 121.5 emergency; ACARS 129-131.55; VDL2 136.65-136.975"),
    (137.0, 138.0, "Weather/LEO satellite downlinks", "Meteor-M LRPT 137.1/137.9 (QPSK 72k), Orbcomm ~137.2-137.8, legacy NOAA APT"),
    (138.0, 144.0, "Federal/military VHF", "FM, often encrypted; 143-144 CAP"),
    (144.0, 148.0, "2 m amateur", "FM repeaters 145.1-147.4, 146.52 simplex calling, APRS 144.39, SSB 144.2, ISS 145.800/145.825"),
    (148.0, 150.8, "Federal / military / satellites", "Various"),
    (150.8, 162.0, "VHF high-band land mobile", "Public safety, fire, EMS, business, railroad (160.215-161.565), marine 156-162, MURS 151.82-154.60"),
    (156.0, 162.05, "VHF marine", "FM 25 kHz; ch16 156.800 distress/calling; AIS 161.975/162.025 (GMSK 9600)"),
    (162.4, 162.55, "NOAA Weather Radio", "WFM-ish narrow FM continuous voice + SAME/EAS AFSK bursts"),
    (162.0, 174.0, "Federal land mobile", "FM/P25, often encrypted"),
    (174.0, 216.0, "TV VHF-high ch 7-13", "ATSC 8VSB 6 MHz with pilot near lower edge"),
    (216.0, 222.0, "216-222 MHz misc / AMTS / telemetry", "Various"),
    (222.0, 225.0, "1.25 m amateur", "FM repeaters"),
    (225.0, 400.0, "Military aviation UHF / satellite", "AM voice 225-400; satcom 240-270; often encrypted"),
    (400.0, 406.0, "Meteorological aids / satellites", "Radiosondes (RS41 GFSK 4800 ~400-406), EPIRB/COSPAS-SARSAT 406.0-406.1"),
    (406.1, 420.0, "Federal land mobile", "P25, often encrypted"),
    (420.0, 450.0, "70 cm amateur", "FM repeaters 442-450, 446.0 simplex, satellites 435-438, ATV; 433.92 ISM overlap"),
    (433.05, 434.79, "433 MHz ISM / SRD", "OOK/FSK sensors, weather stations, remotes (rtl_433)"),
    (450.0, 470.0, "UHF land mobile", "Business, public safety, GMRS/FRS 462/467, railroad EOT 457.9375/HOT 452.9375, DMR/NXDN/P25"),
    (470.0, 608.0, "TV UHF ch 14-36", "ATSC 8VSB 6 MHz; also T-band land mobile in some metros"),
    (608.0, 698.0, "600 MHz cellular (T-Mobile n71) + ch 37 radio astronomy", "LTE/5G OFDM"),
    (698.0, 806.0, "700 MHz cellular + public safety", "LTE (OFDM 5-20 MHz), FirstNet; 769-775/799-805 public-safety narrowband P25"),
    (806.0, 824.0, "800 MHz trunked land mobile (mobile tx)", "P25/EDACS/Motorola trunking"),
    (824.0, 849.0, "Cellular 850 uplink", "LTE uplink bursts"),
    (851.0, 869.0, "800 MHz trunked land mobile (base tx)", "Trunked control channels (continuous digital), P25 phase 1/2"),
    (869.0, 894.0, "Cellular 850 downlink", "LTE/5G OFDM continuous"),
    (896.0, 902.0, "900 MHz land mobile / broadband", "Utility private LTE"),
    (902.0, 928.0, "33 cm amateur / 915 MHz ISM", "LoRa (CSS), smart meters (ERT/ rtlamr), Z-Wave 908.42, FHSS sensors, rtl_433"),
    (928.0, 929.0, "928 MHz fixed / paging links", "Various"),
    (929.0, 932.0, "Paging (one-way)", "POCSAG 512/1200/2400 and FLEX 1600/3200/6400, FSK"),
    (932.0, 941.0, "Fixed / paging / MAS", "Various"),
    (941.0, 960.0, "Studio-transmitter links / fixed", "Various"),
    (960.0, 1215.0, "Aeronautical radionavigation", "DME/TACAN pulses 962-1213, UAT ADS-B 978, Mode S / ADS-B 1090 (PPM pulses), SSR interrogations 1030"),
    (1215.0, 1240.0, "GNSS L2 / radar", "GPS L2 1227.6 (below noise floor)"),
    (1240.0, 1300.0, "23 cm amateur", "ATV, FM, satellites; radars"),
    (1300.0, 1390.0, "Long-range radar", "Pulsed radar"),
    (1420.0, 1421.0, "Hydrogen line (radio astronomy)", "1420.405 MHz; needs dish/horn + LNA + long integration"),
    (1525.0, 1559.0, "Inmarsat / L-band satcom downlinks", "Inmarsat-C 1537-1545 (BPSK 1200), STD-C EGC, AERO; needs L-band patch + LNA"),
    (1559.0, 1610.0, "GNSS L1", "GPS L1 1575.42, Galileo E1, GLONASS ~1602 (below noise floor)"),
    (1610.0, 1626.5, "Iridium / Globalstar", "Iridium 1616-1626.5 TDMA bursts (gr-iridium)"),
    (1670.0, 1710.0, "Meteorological satellites / radiosondes", "US NWS radiosondes 1676-1682, GOES HRIT 1694.1, HRPT ~1698-1707 (dish required)"),
]

# Named channels / well-known frequencies: (mhz, name, notes)
NOTABLE = [
    (27.065, "CB channel 9", "Emergency"),
    (27.185, "CB channel 19", "Highway / truckers"),
    (28.074, "10 m FT8", "USB digital"),
    (50.313, "6 m FT8", "USB digital"),
    (121.5, "Aviation emergency (guard)", "AM; ELT beacons have swept-tone audio"),
    (123.45, "Air-to-air chat (unofficial)", "AM"),
    (122.75, "Air-to-air / private fixed wing", "AM"),
    (129.125, "ACARS", "AM-MSK 2400 bps bursts (acarsdec)"),
    (130.025, "ACARS", "AM-MSK 2400 bps bursts"),
    (130.425, "ACARS", "AM-MSK 2400 bps bursts"),
    (130.45, "ACARS", "AM-MSK 2400 bps bursts"),
    (131.125, "ACARS", "AM-MSK 2400 bps bursts"),
    (131.55, "ACARS (US primary)", "AM-MSK 2400 bps bursts"),
    (136.65, "VDL Mode 2", "D8PSK 10.5 ksym/s bursts (dumpvdl2)"),
    (136.7, "VDL Mode 2", "D8PSK bursts"),
    (136.725, "VDL Mode 2", "D8PSK bursts"),
    (136.775, "VDL Mode 2", "D8PSK bursts"),
    (136.8, "VDL Mode 2", "D8PSK bursts"),
    (136.975, "VDL Mode 2 (common signalling)", "D8PSK bursts"),
    (137.1, "Meteor-M LRPT (alt)", "QPSK 72 ksym/s during passes; SDR++ Meteor demodulator / SatDump"),
    (137.9, "Meteor-M LRPT", "QPSK 72 ksym/s during passes"),
    (144.39, "APRS (North America)", "AFSK 1200 Bell 202 in NFM; multimon-ng AFSK1200 / direwolf"),
    (145.8, "ISS voice downlink", "NFM during passes / ARISS contacts"),
    (145.825, "ISS / satellite APRS digipeater", "AFSK 1200"),
    (146.52, "2 m national simplex calling", "NFM"),
    (151.82, "MURS 1", "NFM 11.25 kHz"),
    (151.88, "MURS 2", "NFM"),
    (151.94, "MURS 3", "NFM"),
    (154.57, "MURS 4 (blue dot)", "FM 20 kHz"),
    (154.6, "MURS 5 (green dot)", "FM 20 kHz"),
    (156.8, "Marine channel 16", "Distress, safety and calling, NFM"),
    (156.45, "Marine channel 9", "Boater calling"),
    (156.65, "Marine channel 13", "Bridge-to-bridge"),
    (161.975, "AIS 1", "GMSK 9600 bursts (ship positions)"),
    (162.025, "AIS 2", "GMSK 9600 bursts"),
    (162.4, "NOAA Weather Radio WX2", "NFM voice + SAME"),
    (162.425, "NOAA Weather Radio WX4", "NFM voice + SAME"),
    (162.45, "NOAA Weather Radio WX5", "NFM voice + SAME"),
    (162.475, "NOAA Weather Radio WX3", "NFM voice + SAME"),
    (162.5, "NOAA Weather Radio WX6", "NFM voice + SAME"),
    (162.525, "NOAA Weather Radio WX7", "NFM voice + SAME"),
    (162.55, "NOAA Weather Radio WX1", "NFM voice + SAME"),
    (243.0, "Military aviation emergency (UHF guard)", "AM"),
    (403.0, "Radiosonde (typical)", "GFSK; 400-406 band"),
    (406.025, "COSPAS-SARSAT EPIRB/PLB", "BPSK 400 bps 0.5 s bursts every ~50 s (illegal to transmit test)"),
    (433.92, "433 MHz ISM centre", "OOK/FSK remotes and sensors (rtl_433)"),
    (446.0, "70 cm national simplex calling", "NFM"),
    (452.9375, "Railroad HOT (head-of-train)", "FSK 1200 (EOT/HOT telemetry)"),
    (457.9375, "Railroad EOT (end-of-train)", "FSK 1200 telemetry bursts"),
    (462.5625, "FRS/GMRS 1", "NFM"),
    (462.5875, "FRS/GMRS 2", "NFM"),
    (462.6125, "FRS/GMRS 3", "NFM"),
    (462.6375, "FRS/GMRS 4", "NFM"),
    (462.6625, "FRS/GMRS 5", "NFM"),
    (462.6875, "FRS/GMRS 6", "NFM"),
    (462.7125, "FRS/GMRS 7", "NFM"),
    (462.55, "GMRS 15 / repeater output", "NFM"),
    (462.575, "GMRS 16 / repeater output", "NFM"),
    (462.6, "GMRS 17 / repeater output", "NFM"),
    (462.625, "GMRS 18 / repeater output", "NFM"),
    (462.65, "GMRS 19 / repeater output", "NFM"),
    (462.675, "GMRS 20 / repeater output (travel/emergency)", "NFM"),
    (462.7, "GMRS 21 / repeater output", "NFM"),
    (462.725, "GMRS 22 / repeater output", "NFM"),
    (467.5625, "FRS 8", "NFM 0.5 W"),
    (467.5875, "FRS 9", "NFM"),
    (467.6125, "FRS 10", "NFM"),
    (467.6375, "FRS 11", "NFM"),
    (467.6625, "FRS 12", "NFM"),
    (467.6875, "FRS 13", "NFM"),
    (467.7125, "FRS 14", "NFM"),
    (315.0, "315 MHz SRD (US car keyfobs, TPMS, garage)", "OOK/FSK (rtl_433)"),
    (345.0, "Honeywell/2GIG security sensors", "OOK/FSK (rtl_433)"),
    (319.5, "Interlogix/GE security sensors", "OOK (rtl_433)"),
    (908.42, "Z-Wave (US)", "FSK 9.6/40/100 kbps"),
    (915.0, "915 MHz ISM centre", "LoRa, meters, sensors"),
    (978.0, "UAT ADS-B", "CPFSK 1.04 Mbps bursts (dump978)"),
    (1030.0, "SSR interrogation", "Pulses from ground radar/TCAS"),
    (1090.0, "Mode S / ADS-B", "PPM 1 Mbps pulses; needs exclusive dongle for dump1090/readsb"),
    (1420.405, "Hydrogen line", "Radio astronomy"),
    (1575.42, "GPS L1", "Below noise floor; visible only as a slight floor rise with a good antenna"),
    (1694.1, "GOES HRIT/EMWIN", "BPSK 927 ksym/s, dish required"),
]

def lookup(freq_hz: float, window_khz: float = 50.0) -> dict:
    """Return allocations containing freq and notable channels near it."""
    mhz = freq_hz / 1e6
    allocs = [
        {"band": n, "range_mhz": f"{a:g}-{b:g}", "notes": notes}
        for a, b, n, notes in ALLOCATIONS
        if a <= mhz <= b
    ]
    near = []
    for f, n, notes in NOTABLE:
        d_khz = (f - mhz) * 1000
        if abs(d_khz) <= window_khz:
            near.append({"freq_mhz": f, "name": n, "notes": notes, "offset_khz": round(d_khz, 2)})
    near.sort(key=lambda r: abs(r["offset_khz"]))
    return {"freq_mhz": round(mhz, 6), "allocations": allocs, "nearby_known": near}


def short_label(freq_hz: float) -> str:
    """One-line label for annotating detections."""
    r = lookup(freq_hz, window_khz=7.5)
    if r["nearby_known"]:
        return r["nearby_known"][0]["name"]
    if r["allocations"]:
        # The narrowest containing allocation is the most specific.
        best = min(
            (a for a in ALLOCATIONS if a[0] <= freq_hz / 1e6 <= a[1]),
            key=lambda a: a[1] - a[0],
        )
        return best[2]
    return ""
