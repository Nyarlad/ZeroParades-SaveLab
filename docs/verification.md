# Local release-candidate verification

Version: **0.1.0**, prepared on 2026-10-22. Status: local owner review; unpublished.

## Public synthetic checks

- 54 automated tests pass on the local Windows environment.
- Codec boundary cases, malformed inputs, both preset phases and one-flag semantic invariants pass.
- Backup, explicit apply/restore, corrupted-target recovery, concurrent-update refusal and injected write/rename failures pass.
- The Windows game detector distinguishes `ZeroParades.exe` from the editor's own executable.
- Hidden Tk tests cover save listing, search, both presets, copy export, diff filtering, backups and confirmed apply/restore to synthetic files only.
- Long preset text is scrollable and original-write actions remain pinned below the review area.
- Ruff checks and formatting validation pass.

## Private compatibility check

Outside the repository, the new implementation validated **85 cached backup files representing 45 unique contents**.
Both internal checksums and byte-identical no-edit roundtrips passed for every file.
Each Reno preset was applied to its already observed before/after-handover backup copy: each diff contained exactly one flag.
All those source copies remained unchanged. Active saves were not accessed for this check.
No private file, filename, label, hash, decoded state or per-file report is included here; only these aggregate results are public.

## Windows distribution

The build script produces standalone GUI and CLI executables and verifies them with Python removed from PATH.
Frozen checks use only synthetic files, including confirmed one-file apply/restore to a temporary synthetic directory.
The portable ZIP includes user guides, license notices and build metadata; the adjacent SHA-256 file covers both release ZIPs.
Executables are unsigned.

Local build runtime: Python 3.11.1, PyCryptodome 4.1.0, PyInstaller 6.22.3.
The prepared CI uses a fresh hosted Python installation. Rebuild with the current patched supported Python before a broad production rollout.

## What is not claimed

Hosted GitHub Actions have not run, because no remote publication has been authorized.
Linux matrix execution, broader story-state compatibility and repeated in-game tests of this standalone GUI are not claimed.
The underlying two-stage Reno repair was previously accepted and checked in the original local game session;
the public editor reproduces that same one-flag behavior with stricter guards.
