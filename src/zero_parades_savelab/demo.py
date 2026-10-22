"""Entirely synthetic, deterministic demonstration data. Contains no player data."""

import json
from pathlib import Path

from .codec import encrypt, write_chunk
from .profiles import VERIFIED_PROFILE


def synthetic_save(*, returned=False, asked=True, changeset="40781", label="Synthetic demo"):
    flags = {
        "reno.HasRenoAskedForKibble": asked,
        "reno.GreetDone": True,
        "reno.GotKibble": True,
        "king_of_trade.BoughtKibble": True,
        "reno.GivesYouUVsExitPapers": True,
        "reno.AlternateGoodByeAtEnd": True,
        "orphanage.TrainRepairSuccessful": True,
        "reno.MissingTrain": True,
        "reno.ReturnedHisModelTrain": returned,
        "synthetic.UnknownFlag": False,
    }
    feld = {
        "m_projectId": "synthetic-project",
        "m_flagsValues": {"m_keys": list(flags), "m_values": list(flags.values())},
        "m_countersValues": {"m_keys": ["synthetic.counter"], "m_values": [42]},
        "m_cardReadValues": [],
        "synthetic_unknown_nested": {"keep": [1, None, "Пример / sample"]},
    }
    items = [{"EntityID": "synthetic-papers", "Amount": 1}]
    if not returned:
        items.append({"EntityID": "modeltrain", "Amount": 1})
    header = {
        "SaveName": "synthetic",
        "SaveLabel": label,
        "SaveType": 0,
        "SaveRevision": 0,
        "UpdatedOn": 637134336000000000,
        "AppVersionMajor": 1,
        "AppVersionMinor": 1,
        "UpdatedOnChangeSet": changeset,
        "BuildTypeName": "RELEASE",
        "SyntheticUnknownHeader": "preserved",
    }
    content = {
        "FELDState": json.dumps(feld, ensure_ascii=False, separators=(",", ":")),
        "Inventory": {"Items": items},
        "SyntheticProgress": {"unchanged": True},
    }
    raw_header = json.dumps(header, separators=(",", ":")).encode()
    plain = json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = encrypt(plain, VERIFIED_PROFILE.seed, bytes(range(32)), bytes(range(16)))
    return (
        write_chunk("C4SaveFileHeader", 1, raw_header)
        + b"\x01"
        + write_chunk("C4SaveFileContent", 0, packed)
    )


def create_demo(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    before = directory / "synthetic.sav"
    after = directory / "synthetic-after.sav"
    before.write_bytes(synthetic_save(label="Synthetic — before train handover"))
    after.write_bytes(
        synthetic_save(returned=True, asked=False, label="Synthetic — after handover")
    )
    return before, after
