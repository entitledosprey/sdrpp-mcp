"""Parse MeshCore packets (firmware v1.x packet format).

Only cleartext structure is decoded: routing, path, and node adverts (name, type,
position). Message bodies are encrypted end to end or per channel and are left alone.
"""

import struct
from datetime import datetime, timezone

ROUTES = ["transport-flood", "flood", "direct", "transport-direct"]
PAYLOADS = {0: "request", 1: "response", 2: "text message", 3: "ack", 4: "advert",
            5: "group text", 6: "group data", 7: "anonymous request", 8: "returned path",
            9: "trace", 10: "multipart", 11: "control", 15: "custom"}
NODE_TYPES = {1: "chat node", 2: "repeater", 3: "room server", 4: "sensor"}


def _advert(p: bytes) -> dict:
    if len(p) < 100:
        return {"error": "advert too short"}
    out = {"node_id": p[:32].hex()[:16], "node_hash": f"{p[0]:02x}"}
    ts = struct.unpack_from("<I", p, 32)[0]
    out["advert_time"] = datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")
    app = p[100:]
    if not app:
        return out
    flags, i = app[0], 1
    out["node_type"] = NODE_TYPES.get(flags & 0x0F, f"type {flags & 0x0F}")
    if flags & 0x10 and len(app) >= i + 8:
        lat, lon = struct.unpack_from("<ii", app, i)
        out["lat"], out["lon"] = lat / 1e6, lon / 1e6
        i += 8
    i += 2 * bool(flags & 0x20) + 2 * bool(flags & 0x40)
    if flags & 0x80:
        out["name"] = app[i:].split(b"\0")[0].decode("utf-8", "replace")
    return out


def parse(raw: bytes) -> dict:
    """Decode the cleartext parts of one MeshCore packet."""
    if len(raw) < 2:
        return {"error": "too short"}
    h = raw[0]
    route, ptype, ver = h & 0x03, (h >> 2) & 0x0F, h >> 6
    out = {"route": ROUTES[route], "type": PAYLOADS.get(ptype, f"reserved {ptype}"),
           "version": ver + 1}
    i = 1
    if route in (0, 3):
        if len(raw) < 5:
            return {**out, "error": "truncated transport codes"}
        out["transport_codes"] = list(struct.unpack_from("<HH", raw, 1))
        i = 5
    if i >= len(raw):
        return {**out, "error": "missing path length"}
    plen = raw[i]
    hops, hsize = plen & 0x3F, (plen >> 6) + 1
    i += 1
    path = raw[i:i + hops * hsize]
    out["hops"] = hops
    if hops:
        out["path"] = [path[k:k + hsize].hex() for k in range(0, len(path), hsize)]
    i += hops * hsize
    payload = raw[i:]
    out["payload_len"] = len(payload)
    if ptype == 4:
        out["advert"] = _advert(payload)
    elif ptype in (0, 1, 2, 8) and len(payload) >= 4:
        out.update(dest_hash=f"{payload[0]:02x}", src_hash=f"{payload[1]:02x}", encrypted=True)
    elif ptype in (5, 6) and payload:
        out.update(channel_hash=f"{payload[0]:02x}", encrypted=True)
    elif ptype == 7 and len(payload) >= 33:
        out.update(dest_hash=f"{payload[0]:02x}", sender_id=payload[1:33].hex()[:16], encrypted=True)
    elif ptype == 3 and len(payload) >= 4:
        out["ack_checksum"] = payload[:4].hex()
    elif ptype == 11 and payload:
        out["control_subtype"] = payload[0] >> 4
    return out
