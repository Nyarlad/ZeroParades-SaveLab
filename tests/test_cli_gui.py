import json
import os

import pytest

from zero_parades_savelab.cli import main


def test_cli_inspect_search_export_and_diff(source, tmp_path, capsys):
    assert main(["inspect", str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["roundtrip_valid"] is True
    assert main(["search", str(source), "unknownflag"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "Unknown"
    output = tmp_path / "export/synthetic.sav"
    assert (
        main(
            [
                "--backup-dir",
                str(tmp_path / "recovery"),
                "patch",
                str(source),
                "--preset",
                "reno-restore-train-dialogue",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["diff", str(source), str(output), "--category", "flags"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1


def test_cli_replacement_requires_confirmation(source, tmp_path, capsys):
    from zero_parades_savelab.service import sha256

    original = source.read_bytes()
    assert main(["apply", str(source), str(source), "--expect-sha256", sha256(original)]) == 2
    assert "explicit" in capsys.readouterr().err
    assert source.read_bytes() == original


@pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"), reason="Tk requires a display"
)
def test_hidden_gui_with_synthetic_data_only(tmp_path):
    from zero_parades_savelab.gui import smoke_test

    result = smoke_test(tmp_path / "gui-result.json")
    assert result["ok"] and result["synthetic_only"]
