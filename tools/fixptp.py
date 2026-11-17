#!/usr/bin/env python3
"""Repair a PTP tape image written by z88dk-appmake.

appmake numbers the blocks correctly only up to 99 and writes a wrong checksum
into the block that sets the end-of-program pointer.  The PRIMO's own SAVE
counts blocks in BCD (..., 98, 99, 00, 01, ...) and sums every block.

    tools/fixptp.py in.ptp out.ptp
"""
import struct
import sys


def bcd(n):
    n %= 100
    return (n // 10) << 4 | n % 10


def fix(data):
    assert data[0] == 0xFF
    pos, out, i = 3, bytearray(), 0
    while pos < len(data):
        marker = data[pos]
        ln = struct.unpack_from("<H", data, pos + 1)[0]
        body = bytearray(data[pos + 3:pos + 3 + ln])
        body[1] = bcd(i)
        body[-1] = sum(body[1:-1]) & 0xFF
        out += bytes([marker]) + struct.pack("<H", ln) + body
        pos += 3 + ln
        i += 1
        if marker == 0xAA:
            break
    return b"\xff" + struct.pack("<H", len(out) + 3) + bytes(out)


if __name__ == "__main__":
    src, dst = sys.argv[1:3]
    open(dst, "wb").write(fix(open(src, "rb").read()))
