# BKPOS Security Hardening

This release keeps all existing POS features and application modules while tightening authentication.

## Changes

- Plaintext password authentication fallback has been removed.
- Legacy plaintext password values are migrated to salted PBKDF2 hashes before authentication and cleared.
- New installations generate a random initial `admin` password unless `BKPOS_INITIAL_ADMIN_PASSWORD` is supplied.
- Generated first-run credentials are written to `.bkpos_initial_admin_password` beside the database with restrictive permissions where supported.
- The initial admin account is marked `must_change_password=1` and must choose a new password of at least 10 characters at first login.
- Admin password changes clear the forced-change flag.
- Newly created admin users are also required to rotate their password on first login.
- Login and admin portal messages no longer disclose a universal default password.

## Deployment

For automated deployments, set `BKPOS_INITIAL_ADMIN_PASSWORD` before the first database initialization. Do not commit that value to source control.

For normal first-run installs, read the generated `.bkpos_initial_admin_password` file next to `pos_store.db`, sign in as `admin`, and immediately choose a new password.

## Compatibility

The legacy `users.password` column remains in the schema so existing databases and migration code continue to work. It is not used for credential verification. Legacy values are converted to `password_hash` and blanked during login/database preparation.

No POS business feature, service, report, workflow, or application function was intentionally removed by this hardening pass.
