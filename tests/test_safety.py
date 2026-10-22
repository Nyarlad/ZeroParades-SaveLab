import json
from pathlib import Path

import pytest

from zero_parades_savelab.demo import synthetic_save
from zero_parades_savelab.errors import SafetyError
from zero_parades_savelab.registry import load_presets
from zero_parades_savelab.service import SaveService


def test_process_check_does_not_mistake_editor_for_game():
    from zero_parades_savelab.discovery import is_game_process_name

    assert is_game_process_name("ZeroParades.exe")
    assert is_game_process_name("ZEROPARADES.EXE")
    assert not is_game_process_name("ZeroParades-SaveLab.exe")
    assert not is_game_process_name("savelab-cli.exe")


def export(service, source, tmp_path):
    opened = service.open(source)
    edits = load_presets()["reno-restore-train-dialogue"].edits(opened.model)
    output = tmp_path / "export" / source.name
    receipt = service.export_patch(opened, edits, output)
    return opened, output, receipt


def test_export_backups_before_writing_and_leaves_original(source, service, tmp_path):
    original = source.read_bytes()
    opened, output, receipt = export(service, source, tmp_path)
    assert source.read_bytes() == original
    backup = Path(receipt["backup"])
    assert (backup / "original.sav").read_bytes() == original
    assert service.open(output).model.flags["reno.HasRenoAskedForKibble"] is False
    assert len(receipt["changes"]) == 1
    assert json.loads(output.with_suffix(".receipt.json").read_text())["applied"] is False
    assert service.list_backups()[0]["sha256"] == opened.model.decoded.sha256


def test_explicit_apply_and_restore_preserve_other_files(source, service, tmp_path):
    original = source.read_bytes()
    neighbor = source.with_name("another.sav")
    neighbor.write_bytes(synthetic_save(label="Untouched"))
    neighbor_raw = neighbor.read_bytes()
    opened, output, receipt = export(service, source, tmp_path)
    with pytest.raises(SafetyError):
        service.apply(opened, output)
    applied = service.apply(opened, output, consent=True)
    assert source.read_bytes() == output.read_bytes()
    assert neighbor.read_bytes() == neighbor_raw
    with pytest.raises(SafetyError):
        service.restore(applied["backup"], source)
    service.restore(applied["backup"], source, consent=True)
    assert source.read_bytes() == original
    assert neighbor.read_bytes() == neighbor_raw
    assert not list(source.parent.glob(".savelab-*.tmp"))


def test_changed_source_refuses_copy_and_apply(source, service, tmp_path):
    opened = service.open(source)
    source.write_bytes(synthetic_save(label="Changed externally"))
    with pytest.raises(SafetyError, match="changed"):
        service.export_patch(
            opened, {"reno.HasRenoAskedForKibble": False}, tmp_path / "export/x.sav"
        )
    assert not (tmp_path / "export/x.sav").exists()


def test_game_running_blocks_live_changes(source, service, tmp_path):
    opened, output, _ = export(service, source, tmp_path)

    def running():
        raise SafetyError("Game running")

    service.process_check = running
    original = source.read_bytes()
    with pytest.raises(SafetyError, match="running"):
        service.apply(opened, output, consent=True)
    assert source.read_bytes() == original


def test_rename_failure_keeps_original_and_backup(source, service, tmp_path, monkeypatch):
    opened, output, _ = export(service, source, tmp_path)
    original = source.read_bytes()

    def fail(*args):
        raise OSError("Simulated sharing violation")

    monkeypatch.setattr("zero_parades_savelab.service.os.replace", fail)
    with pytest.raises(OSError):
        service.apply(opened, output, consent=True)
    assert source.read_bytes() == original
    assert not list(source.parent.glob(".savelab-*.tmp"))
    assert len(service.list_backups()) == 2


def test_backup_error_prevents_export(source, service, tmp_path, monkeypatch):
    import zero_parades_savelab.service as module

    original = source.read_bytes()

    def fail(*args):
        raise OSError("Disk full")

    monkeypatch.setattr(module, "write_new", fail)
    with pytest.raises(OSError):
        service.export_patch(
            service.open(source), {"reno.HasRenoAskedForKibble": False}, tmp_path / "export/a.sav"
        )
    assert source.read_bytes() == original
    assert not (tmp_path / "export/a.sav").exists()


def test_restore_can_recover_a_corrupted_current_file(source, service):
    original = source.read_bytes()
    backup = service.backup(service.open(source))
    source.write_bytes(b"damaged save")
    result = service.restore(backup, source, consent=True)
    assert source.read_bytes() == original
    assert (Path(result["previous_state_backup"]) / "original.sav").read_bytes() == b"damaged save"


def test_tampered_backup_is_refused(source, service):
    original = source.read_bytes()
    backup = service.backup(service.open(source))
    (backup / "original.sav").write_bytes(b"tampered")
    with pytest.raises(SafetyError):
        service.restore(backup, source, consent=True)
    assert source.read_bytes() == original


def test_unsafe_export_destinations_and_overwrite_are_refused(source, service, tmp_path):
    opened = service.open(source)
    edits = {"reno.HasRenoAskedForKibble": False}
    for path in [source, source.with_name("new.sav")]:
        with pytest.raises(SafetyError):
            service.export_patch(opened, edits, path)
    target = tmp_path / "existing.sav"
    target.write_bytes(b"preserve me")
    with pytest.raises(SafetyError):
        service.export_patch(opened, edits, target)
    assert target.read_bytes() == b"preserve me"


def test_unknown_flags_require_experimental_acknowledgement(source, service, tmp_path):
    opened = service.open(source)
    with pytest.raises(SafetyError, match="experimental"):
        service.export_patch(opened, {"synthetic.UnknownFlag": True}, tmp_path / "export/a.sav")
    result = service.export_patch(
        opened, {"synthetic.UnknownFlag": True}, tmp_path / "export/a.sav", experimental=True
    )
    assert len(result["changes"]) == 1
    with pytest.raises(SafetyError):
        opened.model.edit_flags({"missing.flag": True})
    with pytest.raises(SafetyError):
        opened.model.edit_flags({"synthetic.UnknownFlag": 1})


def test_foreign_candidate_cannot_change_inventory(source, service, tmp_path):
    opened = service.open(source)
    candidate = tmp_path / "foreign.sav"
    candidate.write_bytes(synthetic_save(returned=True))
    with pytest.raises(SafetyError, match="beyond"):
        service.apply(opened, candidate, consent=True)
    assert source.read_bytes() == opened.model.decoded.raw


def test_target_changed_at_final_guard_is_not_overwritten(source, service, tmp_path):
    opened, output, _ = export(service, source, tmp_path)
    external = synthetic_save(label="Concurrent external update")
    calls = []

    def process_check():
        calls.append(True)
        if len(calls) == 2:
            source.write_bytes(external)

    service.process_check = process_check
    with pytest.raises(SafetyError):
        service.apply(opened, output, consent=True)
    assert source.read_bytes() == external


def test_read_only_listing_keeps_invalid_file_visible(source, service):
    invalid = source.with_name("corrupt.sav")
    invalid.write_bytes(b"invalid")
    rows = service.list_saves(source.parent)
    assert len(rows) == 2
    assert next(row for row in rows if row["path"] == str(invalid))["type"] == "Invalid"
    assert invalid.read_bytes() == b"invalid"


def test_symlinks_are_refused(source, service, tmp_path):
    link = tmp_path / "linked.sav"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(SafetyError):
        service.open(link)


def test_backup_inside_save_folder_is_refused(source):
    service = SaveService(source.parent / "backups", process_check=lambda: None)
    with pytest.raises(SafetyError):
        service.backup(service.open(source))
