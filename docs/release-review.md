# Publication review

The initial version is **0.1.0**. Build artifacts and source are prepared locally; nothing is published automatically.
The owner must approve the public repository contents and release assets before a repository is created remotely or a release is uploaded.

## Intended Git contents

- Python source under `src/`, including the shared core, GUI, CLI and synthetic demo generator.
- Narrow known-flag and preset JSON descriptors.
- Synthetic-only tests under `tests/`.
- Build, frozen-smoke and release-audit scripts.
- English README, Windows guides, format/architecture/safety/preset/test/research documentation.
- MIT license, dependency notices, contribution guide, changelog and release notes.
- GitHub Actions test/build workflows and `.gitignore`.

No `dist/`, `.venv/`, `build/`, backups, real saves, game data, private logs or binary artifacts are committed.
Windows ZIPs are separate release assets, not source-tree files. No repository remote is configured by the development workflow.

## Checks before publication

1. Run tests, lint and formatting checks.
2. Build on Windows and run frozen CLI/GUI smoke tests.
3. Run `python scripts/audit_release.py` and inspect its entire candidate file list.
4. Inspect `git diff --cached --stat`, `git diff --cached` and `git status`.
5. Review the generated portable ZIP, license notices and SHA-256 file.
6. Confirm that private local integration evidence stayed outside the repository and assets.
7. Obtain owner approval naming the repository and files/assets to publish.

GitHub Actions may build artifacts for a push or manual dispatch. They contain no publish token workflow and do not run `gh release create`.
First-publication actions are intentionally left for a separately approved step.
