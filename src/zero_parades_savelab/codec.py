"""Bounded, strict save framing and crypto. No filesystem writes or quest logic."""

from dataclasses import dataclass
import hashlib
import json
import re
import struct

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from .errors import FormatError
from .hash128 import checksum
from .profiles import VERIFIED_PROFILE, editable_profile

MAX_FILE_SIZE = 64 * 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text: str | bytes):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="strict")
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise FormatError(f"Invalid UTF-8 JSON: {error}") from error


class Reader:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.raw) - self.offset:
            raise FormatError("Truncated or invalid save block size.")
        result = self.raw[self.offset : self.offset + size]
        self.offset += size
        return result

    def string(self, limit=256) -> str:
        length = 0
        for index in range(5):
            value = self.take(1)[0]
            if index == 4 and value > 15:
                raise FormatError("Invalid 7-bit string length.")
            length |= (value & 127) << (index * 7)
            if not value & 128:
                break
        else:
            raise FormatError("Invalid 7-bit string length.")
        if length > limit:
            raise FormatError("Unexpectedly long framing string.")
        try:
            return self.take(length).decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise FormatError("Invalid framing string encoding.") from error


@dataclass(frozen=True)
class Chunk:
    marker: str
    version: int
    data: bytes
    start: int
    end: int


def read_chunk(reader: Reader, marker: str, version: int) -> Chunk:
    start = reader.offset
    if reader.string() != marker:
        raise FormatError(f"Expected {marker}.")
    actual_version, length = struct.unpack("<ii", reader.take(8))
    if actual_version != version:
        raise FormatError(f"Unsupported {marker} version {actual_version}.")
    data = reader.take(length)
    stored = reader.string(32)
    if not re.fullmatch("[0-9a-f]{32}", stored):
        raise FormatError("Invalid checksum representation.")
    if stored != checksum(marker, actual_version, data):
        raise FormatError(f"{marker} checksum mismatch. No editing is allowed.")
    return Chunk(marker, version, data, start, reader.offset)


def write_string(text: str) -> bytes:
    data = text.encode("utf-8")
    length = len(data)
    prefix = bytearray()
    while length >= 128:
        prefix.append((length & 127) | 128)
        length >>= 7
    prefix.append(length)
    return bytes(prefix) + data


def write_chunk(marker: str, version: int, data: bytes) -> bytes:
    return (
        write_string(marker)
        + struct.pack("<ii", version, len(data))
        + data
        + write_string(checksum(marker, version, data))
    )


def decrypt(packed: bytes, seed: bytes) -> bytes:
    if len(packed) < 64 or len(packed) % 16:
        raise FormatError("Invalid encrypted payload size.")
    key = hashlib.pbkdf2_hmac("sha1", seed, packed[:32], 1000, 32)
    try:
        return unpad(AES.new(key, AES.MODE_CBC, packed[32:48]).decrypt(packed[48:]), 16)
    except ValueError as error:
        raise FormatError("Cannot decrypt this save with the supported format profile.") from error


def encrypt(plain: bytes, seed: bytes, salt: bytes, iv: bytes) -> bytes:
    if len(salt) != 32 or len(iv) != 16:
        raise FormatError("Invalid salt or IV.")
    key = hashlib.pbkdf2_hmac("sha1", seed, salt, 1000, 32)
    return salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plain, 16))


@dataclass(frozen=True)
class DecodedSave:
    raw: bytes
    header: dict
    content: dict
    plaintext: bytes
    header_chunk: Chunk
    content_chunk: Chunk

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def editable(self):
        return editable_profile(self.header) is not None


def framing(raw: bytes):
    if not 1 <= len(raw) <= MAX_FILE_SIZE:
        raise FormatError("Save size is outside the supported 1-byte to 64-MiB limit.")
    reader = Reader(raw)
    header_chunk = read_chunk(reader, "C4SaveFileHeader", 1)
    header = strict_json(header_chunk.data)
    if not isinstance(header, dict):
        raise FormatError("Save header must be a JSON object.")
    if reader.take(1) != b"\x01":
        raise FormatError("Unsupported encryption marker; expected 0x01.")
    content_chunk = read_chunk(reader, "C4SaveFileContent", 0)
    if reader.offset != len(raw):
        raise FormatError("Unexpected trailing bytes.")
    return header, header_chunk, content_chunk


def decode(raw: bytes) -> DecodedSave:
    header, header_chunk, content_chunk = framing(raw)
    plaintext = decrypt(content_chunk.data, VERIFIED_PROFILE.seed)
    content = strict_json(plaintext)
    if not isinstance(content, dict):
        raise FormatError("Save content must be a JSON object.")
    return DecodedSave(raw, header, content, plaintext, header_chunk, content_chunk)


def encode_plaintext(save: DecodedSave, plaintext: bytes) -> bytes:
    if not save.editable:
        raise FormatError("This build is inspect-only. No verified editable profile matches.")
    if plaintext == save.plaintext:
        return save.raw
    strict_json(plaintext)
    packed = save.content_chunk.data
    new_packed = encrypt(plaintext, VERIFIED_PROFILE.seed, packed[:32], packed[32:48])
    result = save.raw[: save.content_chunk.start] + write_chunk("C4SaveFileContent", 0, new_packed)
    reread = decode(result)
    if reread.plaintext != plaintext or reread.header_chunk.data != save.header_chunk.data:
        raise FormatError("Encoded save did not pass its readback check.")
    return result
