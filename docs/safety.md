# Safety model and limitations

The source is opened read-only. A patch is an explicit mapping of existing boolean variable IDs to new boolean values.
No executable payload, script, arbitrary JSON path, counter, inventory edit or binary offset patch is accepted.
The codec is separate from presets and filesystem operations.

## Export transaction

1. Validate framing, sizes, versions, UTF-8, JSON, unique keys and both internal checksums.
2. Match the editable build profile and enforce preset or advanced-edit restrictions.
3. Prepare bytes in memory; reread them; compare all semantic data against the requested flag changes.
4. Verify the source still has its reviewed SHA-256.
5. Create and verify a separate backup, outside the source folder, before writing an export.
6. Create a new output exclusively; never overwrite an existing export or original implicitly.
7. Reread and verify the output; write a local change receipt.

## Original replacement and restore

Both require explicit UI confirmation or `--confirm-original` in the CLI. The CLI also requires a reviewed source SHA-256.
The standard Windows game process must be closed. Another verified backup is made before replacement.
The source hash and process list are rechecked immediately before a same-directory `os.replace` of a fully written temporary file.
The backup is copied separately first; the application does not use the multi-step Windows `File.Replace` backup operation.
Temporary files are cleaned up on ordinary failures. Backups are retained if an operation fails.

A verified backup can restore a corrupted current target; that target's opaque bytes are backed up first.
If an exceptional readback error occurs after replacement, keep the reported recovery directory and restore from it.
Power loss, filesystem failure, concurrent synchronization and game-script consequences cannot be fully prevented by static validation.

## Format and story scope

- Unsupported framing, duplicate IDs, duplicate JSON properties, invalid padding, checksum errors and oversized files fail closed.
- Files above 64 MiB are rejected. Only the verified header/content versions and encryption marker are supported.
- The verified editing profile is release 1.1 / changeset 40781 / revision 0. Other decodable builds are inspect-only.
- Unknown fields are retained and compared semantically; unedited saves can round-trip byte-for-byte.
- A confirmed flag description is evidence about its meaning, not proof that arbitrary edits to it are safe.
- Advanced flag editing requires player judgement; unknown flags require explicit experimental acknowledgement.
- Static checks do not execute the game's quest logic. Always verify the result in the game.

No network code, analytics, external account integration or automatic upload exists in the application.
Backups, decoded JSON, receipts and diffs can contain personal game state and local paths. Keep them private.
The repository's ignore rules and release audit help prevent accidental inclusion, but do not replace review before publishing.
