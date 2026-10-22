"""Data-only preset registry: no eval, imports, scripts or arbitrary assignments."""

from dataclasses import dataclass
from importlib.resources import files
import json
from pathlib import Path

from .errors import SafetyError


def flag_descriptions():
    return json.loads(files("zero_parades_savelab").joinpath("data/flags.json").read_text("utf-8"))


@dataclass(frozen=True)
class Preset:
    id: str
    title: str
    description: str
    evidence: str
    risk: str
    conditions: list
    changes: list

    def failures(self, model):
        errors = []
        if not model.decoded.editable:
            errors.append("Unverified build: editing is disabled.")
        for condition in self.conditions:
            key = condition["id"]
            if condition["kind"] == "flag":
                if condition.get("existing") and key not in model.flags:
                    errors.append(f"Required existing flag is missing: {key}")
                elif model.flags.get(key, False) is not condition["value"]:
                    errors.append(f"Required flag state: {key} = {condition['value']}")
            elif condition["kind"] == "card_unread":
                cards = model.feld.get("m_cardReadValues")
                if not isinstance(cards, list) or key in cards:
                    errors.append("The tested train handover option is not verified as unread.")
            elif model.has_item(key) != condition["present"]:
                errors.append(f"Required inventory state: {key}, present={condition['present']}")
        for change in self.changes:
            if model.flags.get(change["id"]) is not change["before"]:
                errors.append(f"Edit precondition failed: {change['id']}")
        return errors

    def edits(self, model):
        errors = self.failures(model)
        if errors:
            raise SafetyError("Preset refused:\n" + "\n".join(errors))
        return {c["id"]: c["after"] for c in self.changes}


def load_presets(path: Path | None = None):
    text = (
        path.read_text("utf-8")
        if path
        else files("zero_parades_savelab").joinpath("data/presets.json").read_text("utf-8")
    )
    rows = json.loads(text)
    if not isinstance(rows, list) or len(rows) > 100:
        raise SafetyError("Invalid preset registry.")
    presets = {}
    for row in rows:
        try:
            for condition in row["conditions"]:
                if condition["kind"] not in ("flag", "item", "card_unread") or not isinstance(
                    condition["id"], str
                ):
                    raise ValueError("Unsupported condition")
                if condition["kind"] == "card_unread":
                    continue
                value = (
                    condition.get("value")
                    if condition["kind"] == "flag"
                    else condition.get("present")
                )
                if type(value) is not bool:
                    raise ValueError("Condition must use a boolean")
            if not row["changes"]:
                raise ValueError("Empty changes")
            for change in row["changes"]:
                if (
                    not isinstance(change["id"], str)
                    or type(change["before"]) is not bool
                    or type(change["after"]) is not bool
                    or change["before"] == change["after"]
                ):
                    raise ValueError("Only boolean transitions are allowed")
            if len({c["id"] for c in row["changes"]}) != len(row["changes"]):
                raise ValueError("Duplicate changes")
            preset = Preset(**{key: row[key] for key in Preset.__dataclass_fields__})
            if preset.id in presets:
                raise ValueError("Duplicate preset ID")
            presets[preset.id] = preset
        except (KeyError, TypeError, ValueError) as error:
            raise SafetyError(f"Invalid preset descriptor: {error}") from error
    return presets
