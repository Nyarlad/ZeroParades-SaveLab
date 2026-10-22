"""Build and smoke-test portable Windows executables. No publication or game I/O."""

import hashlib
from importlib.metadata import distribution, version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

from audit_release import audit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from zero_parades_savelab import __version__  # noqa: E402
from zero_parades_savelab.demo import synthetic_save  # noqa: E402


def licenses(destination):
    destination.mkdir(parents=True)
    for name in ["pycryptodome", "pyinstaller"]:
        package = distribution(name)
        count = 0
        for relative in package.files or []:
            if relative.name.casefold() in ["license", "license.rst", "license.txt", "copying.txt"]:
                raw = Path(package.locate_file(relative)).read_bytes()
                output = destination / f"{name}-{count}-{relative.name}"
                output.write_bytes(raw)
                count += 1
        if not count:
            raise RuntimeError(f"Missing license for {name}")
    base = Path(sys.base_prefix)
    python_license = base / "LICENSE.txt"
    if not python_license.exists():
        raise RuntimeError("Python distribution license not found")
    shutil.copy2(python_license, destination / "Python-LICENSE.txt")
    for index, path in enumerate((base / "tcl").glob("**/license.terms")):
        shutil.copy2(path, destination / f"TclTk-{index}-license.terms")


def run_frozen(executable, arguments, **kwargs):
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    return subprocess.run(
        [str(executable), *map(str, arguments)],
        env=environment,
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=120,
        check=True,
        **kwargs,
    )


def main():
    if os.name != "nt":
        raise SystemExit("Build on Windows; PyInstaller does not cross-compile this application.")
    review = audit()
    if not review["ok"]:
        raise RuntimeError("Publication file audit failed: " + json.dumps(review["rejected"]))
    build = ROOT / "build" / ("release-" + uuid.uuid4().hex)
    dist = ROOT / "dist"
    artifacts = ROOT / "artifacts"
    build.mkdir(parents=True)
    artifacts.mkdir(exist_ok=True)
    for name, entry, mode in [
        ("ZeroParades-SaveLab", "launch_gui.py", "--windowed"),
        ("savelab-cli", "launch_cli.py", "--console"),
    ]:
        print("Building " + name, flush=True)
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            mode,
            "--noupx",
            "--name",
            name,
            "--paths",
            str(ROOT / "src"),
            "--collect-data",
            "zero_parades_savelab",
            "--distpath",
            str(dist),
            "--workpath",
            str(build / name),
            "--specpath",
            str(build),
            str(ROOT / "scripts" / entry),
        ]
        with (build / (name + ".log")).open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        if result.returncode:
            raise RuntimeError(f"Build failed; inspect {build / (name + '.log')}")
    print("Checking frozen GUI and CLI with synthetic data and no Python on PATH", flush=True)
    with tempfile.TemporaryDirectory(prefix="savelab-frozen-") as temporary:
        temp = Path(temporary)
        gui_result = temp / "gui-result.json"
        run_frozen(dist / "ZeroParades-SaveLab.exe", ["--smoke-test", "--result", gui_result])
        gui = json.loads(gui_result.read_text())
        assert gui["ok"] and gui["synthetic_only"]
        sample = temp / "synthetic.sav"
        sample.write_bytes(synthetic_save())
        result = run_frozen(
            dist / "savelab-cli.exe",
            ["inspect", sample],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        cli = json.loads(result.stdout)
        assert cli["roundtrip_valid"] and cli["internal_checksums_valid"]
    portable = build / "portable"
    portable.mkdir()
    for name in ["ZeroParades-SaveLab.exe", "savelab-cli.exe"]:
        shutil.copy2(dist / name, portable / name)
    for name in ["README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"]:
        shutil.copy2(ROOT / name, portable / name)
    shutil.copytree(ROOT / "docs", portable / "docs")
    licenses(portable / "THIRD_PARTY_LICENSES")
    report = {
        "version": __version__,
        "python": sys.version.split()[0],
        "pycryptodome": version("pycryptodome"),
        "pyinstaller": version("pyinstaller"),
        "frozen_gui_synthetic_smoke": gui,
        "frozen_cli_decode": True,
        "system_python_on_path": False,
        "unsigned": True,
        "published": False,
        "executables": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in portable.glob("*.exe")
        },
    }
    (portable / "BUILD_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    archive = artifacts / f"ZeroParades-SaveLab-{__version__}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for path in sorted(portable.rglob("*")):
            if path.is_file():
                output.write(path, str(Path("ZeroParades-SaveLab") / path.relative_to(portable)))
    source_archive = artifacts / f"ZeroParades-SaveLab-{__version__}-source.zip"
    with zipfile.ZipFile(source_archive, "w", zipfile.ZIP_DEFLATED) as output:
        for item in review["files"]:
            output.write(ROOT / item["file"], str(Path("ZeroParades-SaveLab") / item["file"]))
    sums = "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
        for p in [archive, source_archive]
    )
    (artifacts / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
    (artifacts / "build-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Prepared {archive.name} and {source_archive.name}; publication was not performed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
