"""Decode LoRa frames from a complex64 IQ file with gr-lora_sdr.

Runs under the system python3 (where GNU Radio lives), not the server's venv:

    python3 lora_gr.py FILE RATE BW SF CENTER_HZ [SYNC_WORD] [PREAMBLE_LEN]

RATE must be an integer multiple of BW. Prints one JSON object per frame:
{"payload": hex, "crc_ok": bool, "cr": int, "len": int}.
"""

import json
import sys

import pmt
from gnuradio import blocks, gr
import gnuradio.lora_sdr as lora_sdr


def main():
    path = sys.argv[1]
    rate, bw, sf, center = (int(float(a)) for a in sys.argv[2:6])
    sync = int(sys.argv[6], 0) if len(sys.argv) > 6 else 0x12
    preamble = int(sys.argv[7]) if len(sys.argv) > 7 else 8
    if rate % bw:
        sys.exit("RATE must be an integer multiple of BW")

    tb = gr.top_block()
    src = blocks.file_source(gr.sizeof_gr_complex, path, False)
    sync_blk = lora_sdr.frame_sync(center, bw, sf, False, [sync], rate // bw, preamble)
    chain = [
        sync_blk,
        lora_sdr.fft_demod(False, True),
        lora_sdr.gray_mapping(False),
        lora_sdr.deinterleaver(False),
        lora_sdr.hamming_dec(False),
        hdr := lora_sdr.header_decoder(False, 1, 255, True, 2, False),
        lora_sdr.dewhitening(),
        crc := lora_sdr.crc_verif(0, True),
    ]
    data, flags = blocks.vector_sink_b(), blocks.vector_sink_b()
    tb.msg_connect((hdr, "frame_info"), (sync_blk, "frame_info"))
    tb.connect(src, *chain)
    tb.connect((crc, 0), data)
    tb.connect((crc, 1), flags)
    tb.run()

    payload = bytes(data.data())
    tags = sorted(data.tags(), key=lambda t: t.offset)
    starts = [t.offset for t in tags] + [len(payload)]
    for i, tag in enumerate(tags):
        info = pmt.to_python(tag.value)
        frame = payload[starts[i]:starts[i + 1]]
        print(json.dumps({"payload": frame.hex(), "len": len(frame),
                          "crc_ok": bool(info.get("crc_valid", False)),
                          "cr": info.get("cr")}), flush=True)


if __name__ == "__main__":
    main()
