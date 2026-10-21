# Contributing

Use Python 3.11+ and install `.[dev]` into a virtual environment.
Run pytest, Ruff and the release audit before submitting a change.
Windows is required to build/test the frozen GUI and live file-operation integration.

Never commit real saves, decoded state, screenshots, asset bundles, game assemblies or private analysis reports.
Use the synthetic fixture generator. Describe regressions with synthetic reproductions when possible.

Codec changes need malformed-input tests and byte-identical roundtrip checks.
File-operation changes need refusal, backup and recovery tests.
New presets need documented evidence, precise preconditions, minimal changes, gameplay verification and a recovery plan.
Do not infer a flag's meaning from its name and call it confirmed.

Contributions are submitted under the project's MIT license; dependency/game content rights are not transferred.
