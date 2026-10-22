"""Review Git candidates; reject binary/game/private material before publication."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitignore",
    ".gitattributes",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "PUBLICATION_REVIEW.txt",
}
SOURCE_DIRS = {"src", "tests", "docs", "scripts", ".github", "release"}
EXTENSIONS = {".py", ".json", ".toml", ".md", ".txt", ".yml", ".yaml"}


def audit(root=ROOT, deny_tokens=()):
    root = Path(root).resolve()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    names = sorted(set(name.decode("utf-8") for name in result.stdout.split(b"\0") if name))
    approved, rejected = [], []
    for name in names:
        path = root / name
        parts = Path(name).parts
        reasons = []
        if not parts or ".." in parts or path.is_symlink():
            reasons.append("unsafe path")
        if not (name in ROOT_FILES or (parts[0] in SOURCE_DIRS and path.suffix in EXTENSIONS)):
            reasons.append("outside public-source allowlist")
        if any(
            word in path.name.casefold()
            for word in [
                "manifest",
                "decoded",
                "readback",
                "steam_autocloud",
                "gameassembly",
                "global-metadata",
            ]
        ):
            reasons.append("private/game artifact name")
        if not path.is_file() or path.stat().st_size > 256 * 1024:
            reasons.append("missing or oversized source file")
        if reasons:
            rejected.append({"file": name, "reasons": reasons})
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            reasons.append("non-UTF-8 source")
            text = ""
        if b"\0" in raw or raw.startswith((b"MZ", b"UnityFS\0", b"\x10C4SaveFileHeader")):
            reasons.append("binary payload")
        if re.search(
            r"[A-Za-z]:[\\/]+Users[\\/]+(?!Public[\\/]|Default[\\/])[^\\/\s]+", text, re.I
        ):
            reasons.append("literal private Windows profile path")
        if any(token and str(token).casefold() in text.casefold() for token in deny_tokens):
            reasons.append("private review token")
        if reasons:
            rejected.append({"file": name, "reasons": reasons})
        else:
            approved.append(
                {"file": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            )
    return {
        "ok": not rejected,
        "candidate_count": len(names),
        "files": approved,
        "rejected": rejected,
        "network_publication_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--deny-token", action="append", default=[])
    args = parser.parse_args()
    result = audit(deny_tokens=args.deny_token)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
