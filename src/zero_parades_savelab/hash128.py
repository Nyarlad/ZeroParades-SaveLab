"""Scalar SpookyHash128 V2 used by Unity Hash128.

Reused from the locally verified interoperability implementation.
Algorithm: Bob Jenkins, public domain (see THIRD_PARTY_NOTICES.md).
No game binaries, resources, or decompiled source are distributed.
"""

import struct

MASK = (1 << 64) - 1
CONST = 0xDEADBEEFDEADBEEF


def rol(x, n):
    return (x << n | x >> 64 - n) & MASK


def short_mix(s):
    for n, rotation in enumerate([50, 52, 30, 41, 54, 48, 38, 37, 62, 34, 5, 36]):
        i = (n + 2) % 4
        j = (i + 1) % 4
        k = (i + 2) % 4
        s[i] = rol(s[i], rotation)
        s[i] = s[i] + s[j] & MASK
        s[k] ^= s[i]


def short_end(s):
    for n, rotation in enumerate([15, 52, 26, 51, 28, 9, 47, 54, 32, 25, 63]):
        i = (n + 2) % 4
        k = (i + 1) % 4
        s[k] ^= s[i]
        s[i] = rol(s[i], rotation)
        s[k] = s[k] + s[i] & MASK


def mix(data, s):
    for i, rotation in enumerate([11, 32, 43, 31, 17, 28, 39, 57, 55, 54, 22, 46]):
        s[i] = s[i] + data[i] & MASK
        s[(i + 2) % 12] ^= s[(i + 10) % 12]
        s[(i + 11) % 12] ^= s[i]
        s[i] = rol(s[i], rotation)
        s[(i + 11) % 12] = s[(i + 11) % 12] + s[(i + 1) % 12] & MASK


def end_partial(s):
    for i, rotation in enumerate([44, 15, 34, 21, 38, 33, 10, 13, 38, 53, 42, 54]):
        s[(i + 11) % 12] = s[(i + 11) % 12] + s[(i + 1) % 12] & MASK
        s[(i + 2) % 12] ^= s[(i + 11) % 12]
        s[(i + 1) % 12] = rol(s[(i + 1) % 12], rotation)


def spooky(data, seed=(0, 0)):
    length = len(data)
    if length < 192:
        s = [seed[0], seed[1], CONST, CONST]
        offset = 0
        while offset + 32 <= length:
            v = struct.unpack_from("<4Q", data, offset)
            s[2] = s[2] + v[0] & MASK
            s[3] = s[3] + v[1] & MASK
            short_mix(s)
            s[0] = s[0] + v[2] & MASK
            s[1] = s[1] + v[3] & MASK
            offset += 32
        if offset + 16 <= length:
            v = struct.unpack_from("<2Q", data, offset)
            s[2] = s[2] + v[0] & MASK
            s[3] = s[3] + v[1] & MASK
            short_mix(s)
            offset += 16
        s[3] = s[3] + (length << 56) & MASK
        tail = data[offset:]
        if tail:
            s[2] = s[2] + int.from_bytes(tail[:8], "little") & MASK
            s[3] = s[3] + int.from_bytes(tail[8:], "little") & MASK
        else:
            s[2] = s[2] + CONST & MASK
            s[3] = s[3] + CONST & MASK
        short_end(s)
        return (s[0], s[1])
    s = [seed[0], seed[1], CONST] * 4
    offset = 0
    while offset + 96 <= length:
        mix(struct.unpack_from("<12Q", data, offset), s)
        offset += 96
    remainder = length - offset
    tail = data[offset:] + bytes(95 - remainder) + bytes([remainder])
    v = struct.unpack("<12Q", tail)
    for i in range(12):
        s[i] = s[i] + v[i] & MASK
    for _ in range(3):
        end_partial(s)
    return (s[0], s[1])


def checksum(marker, version, data):
    h = spooky(marker.encode("utf-8"))
    h = spooky(struct.pack("<I", version), h)
    h = spooky(data, h)
    return struct.pack("<2Q", *h).hex()
