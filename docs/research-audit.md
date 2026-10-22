# Audit of the earlier working implementation

The editor starts from an already verified local interoperability implementation. Format discovery was not repeated.

## Reused knowledge and implementation

- Scalar SpookyHash V2 arithmetic and the three-stage Unity Hash128 checksum sequence.
- The AES-256-CBC framing, 32-byte salt, 16-byte IV, PKCS#7 and PBKDF2 parameters.
- The independently verified build's seed and header/content versions.
- The nested JSON representation of FELD flag/counter dictionaries.
- The exact Reno flag ID and the two-stage repair confirmed through gameplay.

## Reworked for public use

- Removed hard-coded player paths, save IDs, SHA-256 values and metadata-table offsets.
- Removed all dependencies on local game assemblies, asset dumps and copied metadata.
- Replaced one-off target-file scripts with reusable codec/model/diff/service layers.
- Added strict bounds, duplicate-key/ID validation, build gating and guarded boolean edits.
- Added automatic verified backups, explicit replacement/restore consent, changed-source detection and atomic same-directory replacement.
- Added a real desktop UI, a shared CLI, a data-only preset registry and synthetic tests.
- Preserved recovery from corrupted current saves rather than requiring the damaged file to decode first.

The earlier Windows `File.Replace` operation proved unsuitable in the isolated environment: it moved the original to backup but failed to place the replacement.
The public service copies and verifies the backup first, then uses a single same-directory `os.replace` for the staged file.
Failure injection tests verify unchanged originals and retained backups when that rename is refused.

## Excluded material

No real save, screenshot, decoded player state, private SHA-256, local username/path,
game binary, metadata file, resource bundle, dialogue dump, decompiled source or analysis export is included.
Only the reusable implementation, format parameters and narrow preset identifiers were carried forward.
The original private evidence remains outside the repository.

Public CI uses synthetic data only. A local integration check may validate private backup copies outside the repository;
its public result is limited to aggregate counts and invariants, never file identities or gameplay contents.
