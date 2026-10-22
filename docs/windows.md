# Windows player guide

## Locate and inspect saves

Extract the entire portable ZIP to a normal folder. Run `ZeroParades-SaveLab.exe`; do not place it inside the game's installation or Saves folder.
Use **Find saves** for `%USERPROFILE%\AppData\LocalLow\ZAUM Studio\Zero Parades\Saves`.
If your Windows profile or installation differs, use **Choose folder** or **Open file**.
The game need not be modified, and the editor never changes Steam Cloud settings.

Open a save to see its label, timestamp in UTC, build, SHA-256 and integrity result.
Corrupted saves stay visible in the list with an error; they cannot be edited.

## Preview, export, apply

The Overview tab explains each supported repair and its risks. **Check conditions & preview repair** only queues changes in memory.
The table below shows the exact flag transition. An unmet condition stops the preset.

**Export patched copy** creates a backup first, writes a separate `.sav` outside the source folder and verifies it again.
It also writes a local `.receipt.json` with the change list and backup location. Originals are not replaced during export.
The copied save retains the original internal identity and label; it is intended to replace that selected slot, not create a differently named game slot.

Close the game before **Apply exported copy to original**. The confirmation names the original and its reviewed SHA-256.
The editor rechecks the process list and source hash, takes another backup, then replaces one `.sav` and reads it back.
PNG previews and other saves are untouched. Select the same original slot when loading the game.

If the source changed while you were inspecting it, reopen it and prepare a new copy. Do not bypass the refusal.

## Backups and recovery

Default backup location: `%LOCALAPPDATA%\ZeroParadesSaveLab\backups`.
Each backup directory contains `original.sav` and `record.json` with its SHA-256, size, original filename and local source path.
Keep these files together. The Backups tab lists records; choose one, select its original target file and explicitly confirm restore.
The current target is backed up even if it is corrupted. Backup checksum failure prevents restore.

A crash or interrupted write does not invalidate a verified backup. If necessary, close the game and manually copy `original.sav` from the correct backup back under its recorded original filename.
Restore only the intended slot, not an entire old save folder over newer progress.

Steam may sync local files when the game starts or stops. The editor does not manage that synchronization.
If a sync prompt appears, compare timestamps and keep the verified backup before choosing a version.

## Advanced Flag Explorer

Search by NPC name/ID, variable ID, value or description. Known meanings are marked Confirmed; everything else is Unknown.
Counters are read-only. Queue True/False for an existing boolean flag; unknown flags additionally require the experimental checkbox.
Advanced edits do not validate quest dependencies. Review the pending changes, export a copy and test in the game.

Compare saves with the Diff tab. Filter flags, counters, inventory or other data and export matching entries as JSON.
The table shows at most 2000 rows; JSON export includes every matching entry. These exports may reveal your story choices and should remain private.
