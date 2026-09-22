# BKPOS Phase 41 — System Error Handling

## Goal
Make unexpected application errors safe and understandable for normal users.

## Added
- Central `core/error_handler.py`
- User-safe error messages for common database/filesystem failures
- Technical exception logging to `%APPDATA%\BKPOS\logs\bkpos_errors.log`
- Unique error reference IDs
- Last-resort global exception handler
- No business/accounting logic was rewritten in this phase

## Safety principle
The user sees a simple explanation and reference number rather than a Python
traceback. Technical details remain in the log for diagnosis.

## Adoption
Existing screens/actions can progressively call `handle_exception(...)` around
their top-level operations. This keeps the phase low-risk and allows testing
screen by screen.

## Important
A logged error is not proof that a transaction failed or succeeded. Financial
transactions must continue to use the application's existing database
transaction/rollback rules.
