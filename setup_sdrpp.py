#!/usr/bin/env python3
"""Configure SDR++ for the sdrpp MCP server. Run with SDR++ CLOSED.

- adds an "IQ Exporter" module instance (Baseband, TCP server, float32, localhost:4533)
- adds a "Center Probe" baseband recorder the Rigctl Server can trigger
- makes the Rigctl Server listen on startup (localhost:4532)
Backups of every changed file are written next to it.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CONF = Path.home() / ".config/sdrpp"
IQ_PORT = 4533
PROBE_NAME = "Center Probe"
PROBE_DIR = Path(os.environ.get("SDRPP_MCP_DATA", Path.home() / ".local/share/sdrpp-mcp")) / "center-probe"


def load(name):
    p = CONF / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save(name, data):
    p = CONF / f"{name}.json"
    if p.exists():
        p.with_suffix(f".json.bak-{int(time.time())}").write_text(p.read_text())
    p.write_text(json.dumps(data, indent=4))
    print(f"  wrote {p}")


def main():
    if subprocess.run(["pgrep", "-x", "sdrpp"], capture_output=True).returncode == 0:
        sys.exit("SDR++ is running. Close it first (it overwrites its config on exit).")

    cfg = load("config")
    inst = cfg.setdefault("moduleInstances", {})
    if "IQ Exporter" not in inst:
        inst["IQ Exporter"] = {"enabled": True, "module": "iq_exporter"}
        save("config", cfg)
        print("Added IQ Exporter module instance.")

    # A dedicated baseband recorder whose filenames reveal the true centre frequency
    # (rigctl alone only reports the VFO). The MCP server records ~0.15 s and deletes it.
    if PROBE_NAME not in inst:
        inst[PROBE_NAME] = {"enabled": True, "module": "recorder"}
        save("config", cfg)
        print(f"Added {PROBE_NAME} recorder instance.")
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    rec = load("recorder_config")
    p = rec.setdefault(PROBE_NAME, {})
    want_p = {"mode": 0, "recPath": str(PROBE_DIR), "nameTemplate": "probe_$t_$f_$h$m$s",  # mode 0 = baseband
              "ignoreSilence": False}
    if any(p.get(k) != v for k, v in want_p.items()):
        p.update(want_p)
        save("recorder_config", rec)

    rig = load("rigctl_server_config")
    r = rig.setdefault("Rigctl Server", {})
    want_r = {"autoStart": True, "host": "localhost", "port": r.get("port", 4532), "tuning": True,
              "recording": True, "recorder": PROBE_NAME}
    if any(r.get(k) != v for k, v in want_r.items()):
        r.update(want_r)
        save("rigctl_server_config", rig)
        print("Rigctl Server will listen on startup (localhost:4532) and drive the centre probe.")

    iq = load("iq_exporter_config")
    e = iq.setdefault("IQ Exporter", {})
    # SDR++ stores these options by their display names.
    want = {"mode": "Baseband", "protocol": "TCP (Server)", "sampleType": "Float32",
            "packetSize": e.get("packetSize", 4096), "host": "localhost", "port": IQ_PORT,
            "running": True}
    if any(e.get(k) != v for k, v in want.items()):
        e.update(want)
        save("iq_exporter_config", iq)
    print(f"IQ Exporter: {json.dumps(e)}")
    print("\nDone. Start SDR++ and press play.")


if __name__ == "__main__":
    main()
