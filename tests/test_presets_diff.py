import json

import pytest

from zero_parades_savelab.demo import synthetic_save
from zero_parades_savelab.diff import compare, filtered
from zero_parades_savelab.errors import SafetyError
from zero_parades_savelab.model import SaveModel
from zero_parades_savelab.registry import load_presets


@pytest.mark.parametrize(
    "returned,asked,preset,target",
    [
        (False, True, "reno-restore-train-dialogue", False),
        (True, False, "reno-restore-historical-flag", True),
    ],
)
def test_confirmed_presets_change_one_flag_only(returned, asked, preset, target):
    before = SaveModel.from_bytes(synthetic_save(returned=returned, asked=asked))
    edits = load_presets()[preset].edits(before)
    assert edits == {"reno.HasRenoAskedForKibble": target}
    after = SaveModel.from_bytes(before.edit_flags(edits))
    diff = list(compare(before.normalized(), after.normalized()))
    assert len(diff) == 1
    assert diff[0].path == "/FELDState/m_flagsValues/reno.HasRenoAskedForKibble"
    assert before.decoded.content["Inventory"] == after.decoded.content["Inventory"]
    assert list(filtered(diff, "Reno", "flags")) == diff
    assert not list(filtered(diff, category="inventory"))


def test_presets_fail_closed_on_wrong_story_phase():
    before = SaveModel.from_bytes(synthetic_save())
    after = SaveModel.from_bytes(synthetic_save(returned=True, asked=False))
    registry = load_presets()
    with pytest.raises(SafetyError):
        registry["reno-restore-historical-flag"].edits(before)
    with pytest.raises(SafetyError):
        registry["reno-restore-train-dialogue"].edits(after)


def test_previously_read_train_option_is_refused():
    model = SaveModel.from_bytes(synthetic_save())
    model.feld["m_cardReadValues"].append("lh4o6ux99v416vjs")
    with pytest.raises(SafetyError):
        load_presets()["reno-restore-train-dialogue"].edits(model)


def test_malicious_preset_descriptor_cannot_execute_code(tmp_path):
    path = tmp_path / "presets.json"
    original = next(iter(load_presets().values()))
    row = {name: getattr(original, name) for name in original.__dataclass_fields__}
    row["conditions"] = [{"kind": "eval", "id": "__import__('os').system('bad')"}]
    path.write_text(json.dumps([row]))
    with pytest.raises(SafetyError):
        load_presets(path)


def test_diff_distinguishes_missing_null_and_types():
    result = list(compare({"a": None, "b": True, "list": [1]}, {"b": 1, "c": None, "list": []}))
    assert {entry.kind for entry in result} == {"removed", "added", "changed"}
    assert next(e for e in result if e.path == "/b").kind == "changed"
