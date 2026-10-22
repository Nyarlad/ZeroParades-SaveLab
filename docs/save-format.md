# Verified save format

Observed profile: release 1.1 / changeset 40781, save revision 0.
This describes the files that were actually decoded and round-tripped, not all possible future game formats.

## Framing

Strings in the framing use a .NET BinaryWriter-style 7-bit encoded byte length followed by UTF-8 bytes.
Integers are signed little-endian 32-bit values, with lengths validated against the remaining file size.

| Order | Field |
| --- | --- |
| 1 | String `C4SaveFileHeader` |
| 2 | int32 version `1` |
| 3 | int32 JSON header length |
| 4 | Header JSON, UTF-8 without BOM |
| 5 | String of 32 lower-case hexadecimal checksum characters |
| 6 | Byte `0x01`, encrypted-content marker |
| 7 | String `C4SaveFileContent` |
| 8 | int32 version `0` |
| 9 | int32 encrypted payload length |
| 10 | Encrypted payload |
| 11 | String of 32 lower-case hexadecimal checksum characters |

No trailing bytes are accepted. An extension `.sav` alone is never sufficient to recognize a file.

## Encryption

Payload = `salt[32] || IV[16] || AES-256-CBC ciphertext`.
Padding is PKCS#7 with a 16-byte block size.
The 32-byte key is PBKDF2-HMAC-SHA1 over the UTF-8 seed, salt and 1000 iterations.
The profile's interoperability seed is `f52163935dc25a145a3eb5693a084752`.

The decrypted payload is UTF-8 JSON; no additional compression was needed for the observed profile.
The seed is not an account credential. These formats and noncryptographic checksums are not a tamper-proof security boundary.
For minimal, reproducible edits the codec preserves the source salt and IV. It does not generate new game saves from scratch in the public editing workflow.

## Internal checksum

This is Unity `Hash128`, matching SpookyHash V2 short/long paths, **not MD5**.

```text
h = Spooky128(UTF8(chunk_marker), seed=(0, 0))
h = Spooky128(LE32(chunk_version), seed=h)
h = Spooky128(payload_bytes, seed=h)
text = HEX_LOWER(LE64(h.first) || LE64(h.second))
```

The header hashes its original JSON bytes. The content hashes its encrypted payload, including salt and IV.
The file length fields and framing prefixes are not substituted for that sequence.
SHA-256 is separately used by SaveLab for reviewed versions, backups and receipts.

## Semantic state

The content contains inventory, progression, persistent-object snapshots and other game sections.
`FELDState` is itself a JSON string inside the outer JSON. Its `m_flagsValues` and `m_countersValues`
each use parallel `m_keys` and `m_values` arrays. The editor verifies equal array lengths, unique string IDs and value types.

Editing locates a parsed flag value by ID, replaces only that boolean token in the nested JSON,
replaces the corresponding outer string token, encrypts the payload and recalculates its checksum.
The header bytes remain unchanged. A full semantic comparison rejects changes beyond the requested flags.
All other sections are preserved, including unknown fields. Arrays are not reordered.

No game assemblies, metadata or assets are needed at runtime and none are included in the project.
