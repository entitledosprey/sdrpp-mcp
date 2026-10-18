#!/usr/bin/env python3
"""Convert an SDRTrunk playlist's channel frequencies into SDR++ Frequency Manager import files.

SDR++ can't follow trunking or decode P25 voice, so talkgroup aliases have no equivalent; this
keeps the part that's useful in SDR++: each site's control-channel frequencies as bookmarks
(NFM, 12.5 kHz), so they're easy to find on the waterfall.

    python3 tools/sdrtrunk_to_sdrpp.py playlist.xml OUT_DIR

Writes one JSON per channel/site plus ALL_control_channels.json. Import them in SDR++ under
Frequency Manager -> Import (into the selected list).
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root = ET.parse(sys.argv[1]).getroot()
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    every = {}
    for ch in root.iter("channel"):
        system = ch.get("system") or "System"
        site = re.sub(r"\s*\(.*\)", "", ch.get("site") or ch.get("name") or "Site")
        freqs = [int(f.text) for f in ch.iter("frequency") if f.text]
        if not freqs:
            continue
        marks = {f"{system} {site} CC{i} ({hz / 1e6:.5f})":
                 {"frequency": float(hz), "bandwidth": 12500.0, "mode": 0}
                 for i, hz in enumerate(freqs, 1)}
        every.update(marks)
        name = re.sub(r"[^A-Za-z0-9]+", "_", f"{system} {site}").strip("_")
        (out / f"{name}.json").write_text(json.dumps({"bookmarks": marks}, indent=4))
        print(f"{name}.json: {len(freqs)} frequencies")
    (out / "ALL_control_channels.json").write_text(json.dumps({"bookmarks": every}, indent=4))
    print(f"ALL_control_channels.json: {len(every)} frequencies")


if __name__ == "__main__":
    main()
