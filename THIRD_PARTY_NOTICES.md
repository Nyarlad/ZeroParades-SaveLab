# Third-party notices

Project source is MIT-licensed. These dependencies and algorithm references keep their own terms.
No game files or decompiled source are distributed.

| Component | Use | License / reference |
| --- | --- | --- |
| Python / CPython | Runtime, standard library, Tkinter | [PSF licensing](https://docs.python.org/3/license.html) |
| Tcl/Tk | Native GUI toolkit bundled with Python | [Tcl/Tk license](https://www.tcl-lang.org/software/tcltk/license.html) |
| PyCryptodome | AES primitive; PBKDF2 is in Python's hashlib | BSD 2-Clause and public-domain portions; [upstream](https://www.pycryptodome.org/src/license) |
| PyInstaller bootloader | Standalone Windows packaging | GPL with the bootloader exception permitting independent application licensing; [upstream](https://pyinstaller.org/en/stable/license.html) |
| SpookyHash V2 | Hash128 scalar algorithm, independently expressed in Python | Bob Jenkins, public domain / Unlicense; [author's project](https://github.com/bobjen/spookyhash) |

The Windows ZIP includes `THIRD_PARTY_LICENSES/`, collected from the actual Python/dependency installation used for the build.
PyInstaller, pytest and Ruff are build/test tools; their full source is not incorporated into this project.

Game names and identifiers are used for interoperability and identification. ZA/UM's trademarks and game content remain with their owners.
The save encryption seed is a format parameter, not a player's credential. No game executable, resource or metadata file is required to run this implementation.
