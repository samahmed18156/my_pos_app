# BKPOS Phase 58 — Release & Codebase Quality

Phase 58 builds on Phase 57 and adds a read-only release-quality layer.

## Purpose

Prevent development artifacts, invalid Python files, missing release essentials,
and accidental database/runtime files from being included in a distributable
BKPOS build.

## Added

- `services/release_quality.py`
  - Python syntax-tree compilation checks
  - release-tree artifact scanning
  - required release-file validation
  - exact duplicate-content detection for source files
  - machine-readable quality summary
- `tests/test_phase58_release_quality.py`
- Fixed a latent exception-variable bug in `core/config.py` found during review.

## Release policy

The release-quality checks are read-only. They do not migrate, repair, vacuum,
analyze, or modify the live BKPOS database.

Known legacy compatibility modules are not deleted automatically; they remain
subject to the existing architecture registry and migration strategy.

## Result

Phase 58 is intended as a release gate before future packaging work.
