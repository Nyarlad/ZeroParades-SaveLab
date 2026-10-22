import json
import struct

import pytest

from zero_parades_savelab.codec import (
    MAX_FILE_SIZE,
    Reader,
    decode,
    encode_plaintext,
    encrypt,
    framing,
    read_chunk,
    strict_json,
    write_chunk,
    write_string,
)
from zero_parades_savelab.demo import synthetic_save
from zero_parades_savelab.errors import FormatError, SafetyError
from zero_parades_savelab.hash128 import spooky
from zero_parades_savelab.model import SaveModel
from zero_parades_savelab.profiles import VERIFIED_PROFILE


def replace_parts(raw, *, header=None, plain=None, packed=None):
    save = decode(raw)
    raw_header = save.header_chunk.data if header is None else json.dumps(header).encode()
    if plain is not None:
        old = save.content_chunk.data
        packed = encrypt(plain, VERIFIED_PROFILE.seed, old[:32], old[32:48])
    if packed is None:
        packed = save.content_chunk.data
    return (
        write_chunk("C4SaveFileHeader", 1, raw_header)
        + b"\x01"
        + write_chunk("C4SaveFileContent", 0, packed)
    )


def test_public_spooky_empty_vector():
    # Bob Jenkins' SpookyHash V2, empty message, zero seeds.
    assert spooky(b"") == (0x232706FC6BF50919, 0x8B72EE65B4E851C7)


@pytest.mark.parametrize("length", [0, 1, 15, 16, 31, 32, 95, 96, 191, 192, 193, 384])
def test_framing_boundary_lengths(length):
    data = bytes(i % 256 for i in range(length))
    reader = Reader(write_chunk("test", 0, data))
    chunk = read_chunk(reader, "test", 0)
    assert chunk.data == data and reader.offset == len(reader.raw)


def test_exact_crypto_roundtrip_and_unknown_fields():
    raw = synthetic_save()
    save = decode(raw)
    packed = save.content_chunk.data
    assert encrypt(save.plaintext, VERIFIED_PROFILE.seed, packed[:32], packed[32:48]) == packed
    assert encode_plaintext(save, save.plaintext) == raw
    model = SaveModel.from_bytes(raw)
    edited = SaveModel.from_bytes(model.edit_flags({"reno.HasRenoAskedForKibble": False}))
    assert edited.decoded.header_chunk.data == save.header_chunk.data
    assert edited.feld["synthetic_unknown_nested"] == model.feld["synthetic_unknown_nested"]
    assert edited.decoded.content["SyntheticProgress"] == model.decoded.content["SyntheticProgress"]


@pytest.mark.parametrize("location", [30, -40, -1])
def test_corruption_is_rejected(location):
    raw = bytearray(synthetic_save())
    raw[location] ^= 1
    with pytest.raises(FormatError):
        decode(bytes(raw))


@pytest.mark.parametrize("cut", [0, 1, 17, 25, 100, -1, -33])
def test_truncation_is_rejected(cut):
    raw = synthetic_save()
    with pytest.raises(FormatError):
        decode(raw[:cut])


def test_trailing_unknown_flag_version_and_bad_length():
    raw = synthetic_save()
    with pytest.raises(FormatError):
        decode(raw + b"trailing")
    save = decode(raw)
    for byte in [0, 2]:
        with pytest.raises(FormatError):
            decode(raw[: save.header_chunk.end] + bytes([byte]) + raw[save.header_chunk.end + 1 :])
    altered = write_string("C4SaveFileHeader") + struct.pack("<ii", 2, 0)
    with pytest.raises(FormatError):
        framing(altered)
    with pytest.raises(FormatError):
        framing(write_string("C4SaveFileHeader") + struct.pack("<ii", 1, -1))
    with pytest.raises(FormatError):
        framing(bytes(MAX_FILE_SIZE + 1))
    with pytest.raises(FormatError):
        Reader(b"\xff\xff\xff\xff\xff").string()


def test_correct_checksum_does_not_hide_invalid_crypto_or_json():
    raw = synthetic_save()
    save = decode(raw)
    with pytest.raises(FormatError):
        decode(replace_parts(raw, packed=save.content_chunk.data[:49]))
    for plain in [b"\xff", b"[]", b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}']:
        with pytest.raises(FormatError):
            decode(replace_parts(raw, plain=plain))


def test_unknown_build_is_inspect_only():
    model = SaveModel.from_bytes(synthetic_save(changeset="unverified"))
    assert not model.decoded.editable
    assert model.flags["reno.GotKibble"] is True
    with pytest.raises(SafetyError):
        model.edit_flags({"reno.HasRenoAskedForKibble": False})


def test_duplicate_feld_id_and_non_boolean_flags_are_refused():
    raw = synthetic_save()
    save = decode(raw)
    for duplicate in [True, False]:
        content = dict(save.content)
        feld = strict_json(content["FELDState"])
        if duplicate:
            feld["m_flagsValues"]["m_keys"][1] = feld["m_flagsValues"]["m_keys"][0]
        else:
            feld["m_flagsValues"]["m_values"][0] = 1
        content["FELDState"] = json.dumps(feld)
        bad = replace_parts(raw, plain=json.dumps(content).encode())
        with pytest.raises(FormatError):
            SaveModel.from_bytes(bad)


def test_irregular_json_whitespace_and_unicode_are_preserved_semantically():
    save = decode(synthetic_save())
    content = dict(save.content)
    feld = strict_json(content["FELDState"])
    content["FELDState"] = json.dumps(feld, indent=3, ensure_ascii=True)
    raw = replace_parts(save.raw, plain=json.dumps(content, indent=2).encode())
    before = SaveModel.from_bytes(raw)
    after = SaveModel.from_bytes(before.edit_flags({"reno.HasRenoAskedForKibble": False}))
    assert after.feld["synthetic_unknown_nested"] == before.feld["synthetic_unknown_nested"]
    assert after.decoded.header_chunk.data == before.decoded.header_chunk.data
