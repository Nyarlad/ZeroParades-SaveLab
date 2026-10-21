# ZeroParades-SaveLab

An offline Windows save inspector and backup-first editor for **Zero Parades: For Dead Spies**.
Open a save, inspect its state, preview a supported repair and export a verified copy.
Replacing an original is a separate action that requires confirmation.

**Unofficial. Not affiliated with, endorsed by, or supported by ZA/UM.**
There are no accounts, uploads, telemetry, local web servers or automatic updates.

## Windows quick start

1. Download the Windows ZIP from the project's Releases page **when a release has been published**.
   For an unpublished local build, use the ZIP produced in `artifacts/` instead.
2. Extract the ZIP and run `ZeroParades-SaveLab.exe`. Python is not required.
3. Choose **Find saves**, or select your Saves folder manually. Double-click a save.
4. Choose a confirmed repair and click **Check conditions & preview repair**.
5. Review its explanation and pending changes, then **Export patched copy** outside the Saves folder.
6. To use that copy, close the game and choose **Apply exported copy to original**. Confirm the exact file.
7. Load that save in the game and check the result. Keep the backup.

The application is unsigned; Windows may show a publisher warning. Obtain builds only from a source you trust.
See [Windows instructions](docs/windows.md), [Russian instructions](docs/windows-ru.md) and [safety notes](docs/safety.md).

## What works

- Windows save-folder discovery and manual folder/file selection.
- Save labels, manual/auto/quick types, timestamps, build metadata and SHA-256.
- Strict framing, internal Hash128 checksums, AES decoding and readback verification.
- Flag and counter search by NPC ID, variable ID, value and known description.
- Confirmed flag descriptions; everything else explicitly marked **Unknown**.
- Data-only preset registry, with two steps of the confirmed Reno repair.
- Advanced edits to existing boolean flags; unknown flags require experimental acknowledgement.
- Structural diff with semantic flag IDs, categories, text filters and local JSON export.
- Verified local backups before patched exports, original replacement and restore.
- Recovery of a corrupted current file from a verified backup.
- A GUI and CLI sharing one codec, model and file-operation service.

Counters, inventory and arbitrary JSON are **read-only**. This is not a general quest-state simulator.
Editing is enabled only for the observed **1.1 / changeset 40781 / save revision 0** profile.
Other builds may be inspected if they decode, but writes are blocked. Unrecognized framing or checksum failure stops the operation.

## Reno: two-step train repair

The tested issue routes Reno's post-kibble conversation directly to `Goodbye`, bypassing the ordinary menu.

1. **Reno — Restore Train Dialogue** temporarily changes only `reno.HasRenoAskedForKibble` from `true` to `false`.
   Its conditions require a completed kibble deal, papers, a repaired train still in inventory and no completed train handover.
2. Load the corrected save and hand over the train **through the game**. Do not repeat the kibble transaction.
3. Make a **new manual save** after the handover and close the game.
4. Open that new save and use **Reno — Restore Historical Flag** to return the same flag to `true`.

The game removes the train and sets its handover state. The editor does not simulate those consequences.
The temporary flag also affects conditional lines in other conversations; the second step restores its historical value.
Reno may return to `Goodbye` after the second step, once the train has already been accepted.
See the [preset catalogue](docs/presets.md). No other quest fixes are claimed.

## CLI

The Windows package includes `savelab-cli.exe`. From source:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m zero_parades_savelab list
.\.venv\Scripts\python -m zero_parades_savelab inspect "C:\path\to\save.sav"
.\.venv\Scripts\python -m zero_parades_savelab search "C:\path\to\save.sav" reno
.\.venv\Scripts\python -m zero_parades_savelab presets --file "C:\path\to\save.sav"
.\.venv\Scripts\python -m zero_parades_savelab patch "C:\path\to\save.sav" --preset reno-restore-train-dialogue --output "C:\exports\repair\save.sav"
.\.venv\Scripts\python -m zero_parades_savelab diff "C:\path\to\save.sav" "C:\exports\repair\save.sav" --category flags
```

Explicit original replacement additionally requires the SHA-256 of the version you reviewed:

```powershell
savelab apply "C:\path\to\save.sav" "C:\exports\repair\save.sav" --expect-sha256 ORIGINAL_SHA256 --confirm-original
savelab backups
savelab restore "C:\backup-directory" "C:\path\to\save.sav" --expect-sha256 CURRENT_SHA256 --confirm-original
```

Use `savelab --help` or `savelab COMMAND --help` for other options.
`--backup-dir` is a global option, before the command. JSON exports and backups contain private game state: keep them out of Git.

## Development and build

Python 3.11+ and Tk are required for source GUI use. Linux can run core/CLI tests; live original replacement is Windows-only.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m zero_parades_savelab.gui --demo
.\.venv\Scripts\python scripts\build_windows.py
```

The build produces two standalone executables, third-party notices, a portable ZIP and SHA-256 checksums.
It runs a hidden synthetic GUI check and a frozen CLI decode check. GitHub Actions run tests and provide build artifacts; they do not publish releases automatically.

Read [architecture](docs/architecture.md), [save format](docs/save-format.md), [test plan](docs/testing.md),
[research audit](docs/research-audit.md) and [release review](docs/release-review.md).

## Privacy, licensing and contributions

The repository contains original interoperability code, documentation, descriptors and **synthetic-only** tests.
It contains no real saves, player identities, game binaries, assets, decompiled source or dialogue dumps.
The MIT license covers project code. Bundled dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).

When reporting an issue, start with the tool version, game build and error message. Do not publicly attach your save or a decoded JSON/diff.
New presets must identify their evidence, precise preconditions, risks and a tested recovery path. Never describe an inferred flag meaning as confirmed.
