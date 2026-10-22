"""Structural diffs with semantic flag IDs and typed, filterable entries."""

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class Difference:
    path: str
    kind: str
    category: str
    before: object
    after: object

    def to_dict(self):
        return asdict(self)


def _category(path):
    if path.startswith("/FELDState/m_flagsValues/"):
        return "flags"
    if path.startswith("/FELDState/m_countersValues/"):
        return "counters"
    if path.startswith("/Inventory/"):
        return "inventory"
    return "other"


def compare(left, right, path=""):
    if type(left) is type(right) and isinstance(left, dict):
        for key in sorted(left.keys() | right.keys()):
            p = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in right:
                yield Difference(p, "removed", _category(p), left[key], None)
            elif key not in left:
                yield Difference(p, "added", _category(p), None, right[key])
            else:
                yield from compare(left[key], right[key], p)
    elif type(left) is type(right) and isinstance(left, list):
        for index in range(max(len(left), len(right))):
            p = f"{path}/{index}"
            if index >= len(right):
                yield Difference(p, "removed", _category(p), left[index], None)
            elif index >= len(left):
                yield Difference(p, "added", _category(p), None, right[index])
            else:
                yield from compare(left[index], right[index], p)
    elif type(left) is not type(right) or left != right:
        yield Difference(path, "changed", _category(path), left, right)


def filtered(entries, query="", category="all"):
    query = query.casefold()
    for entry in entries:
        if category != "all" and entry.category != category:
            continue
        if query and query not in json.dumps(entry.to_dict(), ensure_ascii=False).casefold():
            continue
        yield entry
