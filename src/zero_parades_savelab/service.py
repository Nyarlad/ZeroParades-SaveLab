"""Backup-first file operations. All live writes require explicit consent and guards."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from .codec import MAX_FILE_SIZE, decode, framing, strict_json
from .diff import compare
from .discovery import default_data_directory, ensure_game_closed
from .errors import FormatError, SafetyError
from .model import SaveModel, ticks_iso
from .registry import flag_descriptions


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def read_bytes(path: Path):
    if not path.is_file() or path.is_symlink():
        raise SafetyError("Select a regular save file, not a symlink.")
    if path.stat().st_size > MAX_FILE_SIZE:
        raise FormatError("Save exceeds the 64-MiB size limit.")
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_SIZE:
        raise FormatError("Save exceeds the 64-MiB size limit.")
    return raw


def write_new(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        try:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        except OSError:
            stream.close()
            path.unlink(missing_ok=True)
            raise
    if path.read_bytes() != raw:
        raise SafetyError("Output verification failed. The original remains backed up.")


@dataclass(frozen=True)
class OpenedSave:
    path: Path
    model: SaveModel


class SaveService:
    def __init__(self, backup_root=None, process_check=None):
        self.backup_root = Path(backup_root or default_data_directory() / "backups").resolve()
        self.process_check = process_check or ensure_game_closed

    def open(self, path):
        path = Path(path).absolute()
        if path.suffix.casefold() != ".sav":
            raise SafetyError("Select a .sav file.")
        return OpenedSave(path, SaveModel.from_bytes(read_bytes(path)))

    def stable(self, opened):
        if sha256(read_bytes(opened.path)) != opened.model.decoded.sha256:
            raise SafetyError(
                "The source changed since it was opened. Reopen it; no changes applied."
            )

    def list_saves(self, directory):
        directory = Path(directory)
        if not directory.is_dir():
            raise SafetyError("Save folder does not exist. Choose it manually.")
        rows = []
        for path in sorted(directory.glob("*.sav")):
            try:
                raw = read_bytes(path)
                header, _, _ = framing(raw)
                rows.append(
                    {
                        "path": str(path),
                        "label": header.get("SaveLabel") or path.stem,
                        "type": {0: "Manual", 1: "Autosave", 2: "Quick"}.get(
                            header.get("SaveType"), "Unknown"
                        ),
                        "updated_utc": ticks_iso(header.get("UpdatedOn")),
                        "error": "",
                    }
                )
            except (OSError, FormatError, SafetyError) as error:
                rows.append(
                    {
                        "path": str(path),
                        "label": path.name,
                        "type": "Invalid",
                        "updated_utc": "Unknown",
                        "error": str(error),
                    }
                )
        return sorted(rows, key=lambda row: row["updated_utc"], reverse=True)

    def backup(self, opened):
        self.stable(opened)
        directory = self._backup_snapshot(opened.path, opened.model.decoded.raw)
        self.stable(opened)
        return directory

    def _backup_snapshot(self, path, raw):
        source_directory = path.parent.resolve()
        if self.backup_root == source_directory or self.backup_root.is_relative_to(
            source_directory
        ):
            raise SafetyError("Keep backups outside the source save folder.")
        directory = self.backup_root / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
        )
        directory.mkdir(parents=True, exist_ok=False)
        write_new(directory / "original.sav", raw)
        record = {
            "schema": 1,
            "source": str(path),
            "filename": path.name,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "sha256": sha256(raw),
            "size": len(raw),
        }
        write_new(directory / "record.json", json.dumps(record, indent=2).encode())
        return directory

    def export_patch(self, opened, edits, output, *, experimental=False):
        output = Path(output).absolute()
        if (
            output.resolve() == opened.path.resolve()
            or output.parent.resolve() == opened.path.parent.resolve()
        ):
            raise SafetyError(
                "Export outside the source save folder. Use Apply for an explicit original replacement."
            )
        if output.suffix.casefold() != ".sav" or output.exists() or output.is_symlink():
            raise SafetyError("Choose a new, non-existing .sav output file.")
        if output.with_suffix(".receipt.json").exists():
            raise SafetyError("An export receipt already exists at the selected destination.")
        descriptions = flag_descriptions()
        if any(key not in descriptions for key in edits) and not experimental:
            raise SafetyError("Unknown flags require explicit experimental acknowledgement.")
        changes = {
            key: value for key, value in edits.items() if opened.model.flags.get(key) is not value
        }
        if not changes:
            raise SafetyError("No flag changes selected.")
        result = opened.model.edit_flags(changes)
        backup = self.backup(opened)
        self.stable(opened)
        write_new(output, result)
        reread = self.open(output)
        differences = list(compare(opened.model.normalized(), reread.model.normalized()))
        receipt = {
            "schema": 1,
            "source_sha256": opened.model.decoded.sha256,
            "candidate_sha256": reread.model.decoded.sha256,
            "backup": str(backup),
            "source": str(opened.path),
            "candidate": str(output),
            "changes": [entry.to_dict() for entry in differences],
            "applied": False,
        }
        write_new(
            output.with_suffix(".receipt.json"),
            json.dumps(receipt, indent=2, ensure_ascii=False).encode("utf-8"),
        )
        return receipt

    def _replace(self, target: Path, expected_hash: str, raw: bytes):
        """One same-directory atomic rename; backup was copied separately beforehand."""
        target = target.absolute()
        if sha256(read_bytes(target)) != expected_hash:
            raise SafetyError("Target changed before replacement.")
        descriptor, temp_name = tempfile.mkstemp(
            prefix=".savelab-", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.read_bytes() != raw:
                raise SafetyError("Staging verification failed.")
            self.process_check()
            if sha256(read_bytes(target)) != expected_hash:
                raise SafetyError("Target changed immediately before replacement.")
            os.replace(temporary, target)
            if read_bytes(target) != raw:
                raise SafetyError("Written file did not pass readback.")
        finally:
            temporary.unlink(missing_ok=True)

    def apply(self, opened, candidate, *, consent=False):
        if not consent:
            raise SafetyError("Replacing an original requires explicit confirmation.")
        self.process_check()
        self.stable(opened)
        new = self.open(candidate)
        # Applying arbitrary foreign files is not a patch: require an unchanged
        # header and only existing boolean flag changes, identical to Export.
        if opened.model.decoded.header_chunk.data != new.model.decoded.header_chunk.data:
            raise SafetyError("Candidate header identity does not match the original.")
        changes = {k: v for k, v in new.model.flags.items() if opened.model.flags.get(k) is not v}
        if not changes:
            raise SafetyError("Candidate contains no flag changes.")
        expected = opened.model.edit_flags(changes)
        if expected != new.model.decoded.raw:
            raise SafetyError("Candidate contains changes beyond verified boolean flag edits.")
        backup = self.backup(opened)
        try:
            self._replace(opened.path, opened.model.decoded.sha256, new.model.decoded.raw)
        except Exception as error:
            if sha256(read_bytes(opened.path)) != opened.model.decoded.sha256:
                raise SafetyError(
                    f"Apply failed after a write. Verified recovery copy: {backup}"
                ) from error
            raise
        return {
            "applied": True,
            "target": str(opened.path),
            "backup": str(backup),
            "sha256": new.model.decoded.sha256,
            "changed_flags": changes,
        }

    def restore(self, backup_directory, target, *, consent=False):
        if not consent:
            raise SafetyError("Restore requires explicit confirmation of the target file.")
        self.process_check()
        backup_directory = Path(backup_directory)
        record = strict_json((backup_directory / "record.json").read_bytes())
        raw = read_bytes(backup_directory / "original.sav")
        if (
            not isinstance(record, dict)
            or record.get("schema") != 1
            or sha256(raw) != record.get("sha256")
            or len(raw) != record.get("size")
        ):
            raise SafetyError("Backup checksum or manifest is invalid.")
        decode(raw)
        target = Path(target).absolute()
        if target.name != record.get("filename"):
            raise SafetyError("Restore target filename does not match this backup.")
        # A corrupted current save is a legitimate recovery case. Back it up as
        # opaque bytes; only the restoration source has to decode successfully.
        current_raw = read_bytes(target)
        current_hash = sha256(current_raw)
        rollback_backup = self._backup_snapshot(target, current_raw)
        self._replace(target, current_hash, raw)
        return {
            "restored": True,
            "target": str(target),
            "sha256": sha256(raw),
            "previous_state_backup": str(rollback_backup),
        }

    def list_backups(self):
        result = []
        if not self.backup_root.exists():
            return result
        for path in self.backup_root.glob("*/record.json"):
            try:
                row = strict_json(path.read_bytes())
                if (
                    not isinstance(row, dict)
                    or row.get("schema") != 1
                    or not all(
                        isinstance(row.get(key), str)
                        for key in ("source", "filename", "sha256", "created_utc")
                    )
                ):
                    continue
                row["directory"] = str(path.parent)
                result.append(row)
            except (OSError, FormatError, TypeError):
                continue
        return sorted(result, key=lambda row: row.get("created_utc", ""), reverse=True)
