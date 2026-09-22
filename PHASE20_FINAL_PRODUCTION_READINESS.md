# Phase 20 — Final Production Readiness & Release Freeze

Final release-hardening layer for BKPOS. This phase is deliberately additive and
focuses on validating the application before packaging rather than changing
business behavior.

## Checks
- Required runtime and release files
- Required phase documentation
- Python compilation across the project
- Release version presence
- Windows entrypoint safety: `main()` must be defined before the `__main__` guard
- Existing automated regression suite

## Safety
The final-release validator is read-only. It does not alter sales, stock,
accounting, users, pricing, promotions, branches, or other business records.

## Release procedure
1. Run `python release_check.py`.
2. Run `python run_tests.py`.
3. Confirm the final ZIP contains no runtime database or generated receipt/report artifacts.
4. Verify the application starts through the Windows entrypoint.
5. Keep the release ZIP and SHA-256 checksum together.
