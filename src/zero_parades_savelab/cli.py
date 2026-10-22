"""Command-line interface over the same services used by the Windows GUI."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .codec import encrypt
from .diff import compare, filtered
from .discovery import default_save_directory
from .errors import SaveLabError, SafetyError
from .registry import flag_descriptions, load_presets
from .service import SaveService, write_new
from .profiles import VERIFIED_PROFILE


def parser():
    p = argparse.ArgumentParser(prog="savelab", description="Offline Zero Parades save editor")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--backup-dir", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="Discover local saves without modifying them")
    listing.add_argument("directory", nargs="?", type=Path, default=default_save_directory())
    inspect = sub.add_parser("inspect", help="Validate and decode one save")
    inspect.add_argument("file", type=Path)
    inspect.add_argument(
        "--decode-out", type=Path, help="Explicit local JSON export (private data)"
    )
    search = sub.add_parser("search", help="Search flag/counter IDs, values and descriptions")
    search.add_argument("file", type=Path)
    search.add_argument("query")
    diff = sub.add_parser("diff", help="Compare semantic state of two saves")
    diff.add_argument("left", type=Path)
    diff.add_argument("right", type=Path)
    diff.add_argument(
        "--category", choices=["all", "flags", "counters", "inventory", "other"], default="all"
    )
    diff.add_argument("--query", default="")
    diff.add_argument("--output", type=Path)
    presets = sub.add_parser("presets", help="List confirmed presets and applicability")
    presets.add_argument("--file", type=Path)
    patch = sub.add_parser("patch", help="Back up a source and create a separate patched file")
    patch.add_argument("file", type=Path)
    choice = patch.add_mutually_exclusive_group(required=True)
    choice.add_argument("--preset")
    choice.add_argument("--set", dest="edits", action="append", metavar="FLAG=true|false")
    patch.add_argument("--output", type=Path, required=True)
    patch.add_argument("--ack-experimental", action="store_true")
    apply = sub.add_parser(
        "apply", help="Explicitly replace ONE original with a verified candidate"
    )
    apply.add_argument("original", type=Path)
    apply.add_argument("candidate", type=Path)
    apply.add_argument("--confirm-original", action="store_true")
    apply.add_argument("--expect-sha256", required=True)
    restore = sub.add_parser("restore", help="Restore ONE verified backup to an existing save")
    restore.add_argument("backup", type=Path)
    restore.add_argument("target", type=Path)
    restore.add_argument("--confirm-original", action="store_true")
    restore.add_argument("--expect-sha256", required=True)
    sub.add_parser("backups", help="List local backup records")
    return p


def run(args):
    service = SaveService(args.backup_dir)
    command = args.command
    if command == "list":
        return service.list_saves(args.directory)
    if command == "backups":
        return service.list_backups()
    if command == "presets":
        model = service.open(args.file).model if args.file else None
        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "risk": p.risk,
                "evidence": p.evidence,
                "failures": p.failures(model) if model else None,
            }
            for p in load_presets().values()
        ]
    if command in ("inspect", "search", "patch"):
        opened = service.open(args.file)
        model = opened.model
        if command == "inspect":
            packed = model.decoded.content_chunk.data
            if (
                encrypt(model.decoded.plaintext, VERIFIED_PROFILE.seed, packed[:32], packed[32:48])
                != packed
            ):
                raise SafetyError("Cryptographic roundtrip failed.")
            if args.decode_out:
                if args.decode_out.suffix.casefold() != ".json":
                    raise SafetyError("Decoded export must use a new .json filename.")
                write_new(args.decode_out, model.decoded.plaintext)
            return {**model.metadata(), "internal_checksums_valid": True, "roundtrip_valid": True}
        if command == "search":
            descriptions = flag_descriptions()
            result = []
            for kind, mapping in [("flag", model.flags), ("counter", model.counters)]:
                for key, value in mapping.items():
                    detail = descriptions.get(
                        key,
                        {
                            "status": "Unknown",
                            "description": "Unknown meaning; experimental changes may damage story state.",
                        },
                    )
                    row = {"id": key, "value": value, "kind": kind, **detail}
                    if args.query.casefold() in json.dumps(row, ensure_ascii=False).casefold():
                        result.append(row)
            return result
        if args.preset:
            presets = load_presets()
            if args.preset not in presets:
                raise SafetyError("Unknown preset ID. Use savelab presets.")
            edits = presets[args.preset].edits(model)
        else:
            edits = {}
            for item in args.edits:
                key, separator, value = item.rpartition("=")
                if not separator or value not in ("true", "false") or key in edits:
                    raise SafetyError(
                        "Use distinct existing IDs as --set FLAG=true or --set FLAG=false."
                    )
                edits[key] = value == "true"
        return service.export_patch(opened, edits, args.output, experimental=args.ack_experimental)
    if command == "diff":
        left, right = service.open(args.left), service.open(args.right)
        rows = [
            entry.to_dict()
            for entry in filtered(
                compare(left.model.normalized(), right.model.normalized()),
                args.query,
                args.category,
            )
        ]
        if args.output:
            write_new(args.output, json.dumps(rows, indent=2, ensure_ascii=False).encode("utf-8"))
        return rows
    if command == "apply":
        opened = service.open(args.original)
        if opened.model.decoded.sha256 != args.expect_sha256.casefold():
            raise SafetyError("Original SHA-256 does not match the reviewed version.")
        return service.apply(opened, args.candidate, consent=args.confirm_original)
    if command == "restore":
        from .service import read_bytes, sha256

        if sha256(read_bytes(args.target)) != args.expect_sha256.casefold():
            raise SafetyError("Restore target SHA-256 does not match the reviewed version.")
        return service.restore(args.backup, args.target, consent=args.confirm_original)
    raise SafetyError("Unknown command.")


def main(argv=None):
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = run(parser().parse_args(argv))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (SaveLabError, OSError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
