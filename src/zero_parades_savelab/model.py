"""Semantic save model and exact-span JSON edits; independent of filesystem I/O."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from .codec import DecodedSave, decode, encode_plaintext, strict_json
from .errors import FormatError, SafetyError


def ticks_iso(ticks):
    try:
        return (
            datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(ticks) // 10)
        ).isoformat()
    except (ValueError, TypeError, OverflowError):
        return "Unknown"


def json_span(text: str, path: list[str | int]) -> tuple[int, int]:
    """Find a parsed JSON value's exact character span, preserving all other text."""
    decoder = json.JSONDecoder()

    def whitespace(index):
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    def find(index, remaining):
        index = whitespace(index)
        if not remaining:
            _, end = decoder.raw_decode(text, index)
            return index, end
        wanted, *rest = remaining
        if text[index] == "{":
            index = whitespace(index + 1)
            while text[index] != "}":
                key, index = decoder.raw_decode(text, index)
                index = whitespace(index)
                if text[index] != ":":
                    raise FormatError("Invalid JSON object separator.")
                index = whitespace(index + 1)
                if key == wanted:
                    return find(index, rest)
                _, index = decoder.raw_decode(text, index)
                index = whitespace(index)
                if text[index] == ",":
                    index = whitespace(index + 1)
                else:
                    break
        elif text[index] == "[" and isinstance(wanted, int):
            index = whitespace(index + 1)
            number = 0
            while text[index] != "]":
                if number == wanted:
                    return find(index, rest)
                _, index = decoder.raw_decode(text, index)
                index = whitespace(index)
                if text[index] != ",":
                    break
                index = whitespace(index + 1)
                number += 1
        raise FormatError("Requested JSON field is missing.")

    return find(0, path)


def _mapping(feld, section, expected_type):
    obj = feld.get(section)
    if not isinstance(obj, dict):
        raise FormatError(f"Missing FELD dictionary {section}.")
    keys, values = obj.get("m_keys"), obj.get("m_values")
    if not isinstance(keys, list) or not isinstance(values, list) or len(keys) != len(values):
        raise FormatError(f"Unmatched FELD arrays in {section}.")
    if any(not isinstance(k, str) for k in keys) or len(set(keys)) != len(keys):
        raise FormatError(f"Invalid or duplicate variable IDs in {section}.")
    if any(type(value) not in expected_type for value in values):
        raise FormatError(f"Unexpected value type in {section}.")
    return dict(zip(keys, values))


@dataclass
class SaveModel:
    decoded: DecodedSave
    feld: dict
    flags: dict
    counters: dict

    @classmethod
    def from_bytes(cls, raw: bytes):
        save = decode(raw)
        text = save.content.get("FELDState")
        if not isinstance(text, str):
            raise FormatError("FELDState must be a nested JSON string.")
        feld = strict_json(text)
        if not isinstance(feld, dict):
            raise FormatError("FELDState must contain an object.")
        flags = _mapping(feld, "m_flagsValues", (bool,))
        counters = _mapping(feld, "m_countersValues", (int, float))
        return cls(save, feld, flags, counters)

    def has_item(self, entity_id: str) -> bool:
        items = self.decoded.content.get("Inventory", {}).get("Items")
        if not isinstance(items, list):
            raise FormatError("Inventory items cannot be verified.")
        for item in items:
            if not isinstance(item, dict):
                raise FormatError("Malformed inventory item.")
            amount = item.get("Amount", 0)
            if (
                item.get("EntityID") == entity_id
                and isinstance(amount, (int, float))
                and amount > 0
            ):
                return True
        return False

    def metadata(self):
        h = self.decoded.header
        return {
            "name": h.get("SaveName", "Unknown"),
            "label": h.get("SaveLabel", ""),
            "type": {0: "Manual", 1: "Autosave", 2: "Quick"}.get(h.get("SaveType"), "Unknown"),
            "updated_utc": ticks_iso(h.get("UpdatedOn")),
            "sha256": self.decoded.sha256,
            "build": f"{h.get('AppVersionMajor')}.{h.get('AppVersionMinor')}.{h.get('UpdatedOnChangeSet')}",
            "editable": self.decoded.editable,
            "flag_count": len(self.flags),
            "counter_count": len(self.counters),
        }

    def normalized(self):
        content = dict(self.decoded.content)
        feld = dict(self.feld)
        feld["m_flagsValues"] = self.flags
        feld["m_countersValues"] = self.counters
        content["FELDState"] = feld
        return content

    def edit_flags(self, edits: dict[str, bool]) -> bytes:
        if not self.decoded.editable:
            raise SafetyError("Editing is disabled for this unverified build.")
        text = self.decoded.content["FELDState"]
        spans = []
        for key, value in edits.items():
            if key not in self.flags or type(value) is not bool:
                raise SafetyError("Only existing boolean flags can be edited.")
            if self.flags[key] == value:
                continue
            index = self.feld["m_flagsValues"]["m_keys"].index(key)
            start, end = json_span(text, ["m_flagsValues", "m_values", index])
            spans.append((start, end, "true" if value else "false"))
        for start, end, replacement in sorted(spans, reverse=True):
            text = text[:start] + replacement + text[end:]
        outer = self.decoded.plaintext.decode("utf-8")
        start, end = json_span(outer, ["FELDState"])
        outer = outer[:start] + json.dumps(text, ensure_ascii=False) + outer[end:]
        if not spans:
            return self.decoded.raw
        blob = encode_plaintext(self.decoded, outer.encode("utf-8"))
        result = SaveModel.from_bytes(blob)
        expected = dict(self.flags)
        expected.update(edits)
        if result.flags != expected:
            raise SafetyError("Flag readback differs from the requested edits.")
        left, right = self.normalized(), result.normalized()
        left["FELDState"]["m_flagsValues"] = expected
        if left != right or self.decoded.header_chunk.data != result.decoded.header_chunk.data:
            raise SafetyError("Unexpected game data changed; output refused.")
        return blob
