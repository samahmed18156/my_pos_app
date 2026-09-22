# BKPOS Project Structure

## Source

- `app.py` — application entry point
- `core/` — core configuration, logging, migrations, permissions, and audit support
- `services/` — business/application services
- Root `.py` modules — feature modules retained for backward compatibility and packaging
- `jasper_reports/` — Jasper report integration
- `jasper_runtime/` — Jasper runtime dependencies
- `packaging/` — packaging and release configuration
- `tests/` — automated tests

## Documentation

- `docs/guides/` — current installation, testing, release, and usage guides
- `docs/history/` — historical phase, upgrade, hardening, acceptance, and release records

Historical documentation is organized separately so the source tree stays easy to navigate.
The documents are retained; nothing from the application's feature set is removed.

## Runtime/generated data

The developer/release distribution intentionally excludes local runtime artifacts such as:

- Python `__pycache__` / `.pyc` files
- local SQLite databases and backup databases
- generated receipts and report output
- nested project ZIP archives
- IDE metadata such as `.idea/`

These are runtime/build artifacts rather than application source and are recreated as needed.
