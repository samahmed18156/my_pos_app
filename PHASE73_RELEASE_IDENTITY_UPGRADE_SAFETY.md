# BKPOS Phase 73 — Release Identity & Upgrade Safety

Phase 73 hardens the release boundary after the installer/desktop polish work in Phase 72.

## Changes
- Added `core/release_identity.py` as the single source of truth for BKPOS release identity.
- Synchronized `VERSION.txt` and `RELEASE_VERSION.txt` to `BKPOS 10.0.0-rc1`.
- Added read-only consistency validation for installer/spec/version metadata.
- Removed the Phase 72 `SetupIconFile` references because the referenced `branding/BKPOS.ico` asset was not present in the release tree. This prevents an Inno Setup build from failing on a missing file.
- Kept per-user installation (`PrivilegesRequired=lowest`) unchanged.
- Kept the installed BKPOS executable and live `%APPDATA%\BKPOS` database untouched.

## Upgrade/data safety policy
The installer package contains application code only. Live business data remains in the user's writable BKPOS data directory and is not packaged into the release ZIP. Updating the application therefore does not intentionally replace the live database.
