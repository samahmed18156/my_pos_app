# BKPOS Phase 61 — Startup & Shutdown Hardening

Phase 61 hardens the application lifecycle without changing business data.

## Included

- Records a runtime lifecycle state under the BKPOS writable data directory.
- Records startup time, process ID, packaged/source mode and previous-run status.
- Detects when the previous run did not record a clean shutdown.
- Records a clean shutdown only after `main()` returns normally.
- Installs an uncaught-exception hook that logs the exception while deliberately
  leaving the lifecycle state as `running`, so the next launch can detect the
  abnormal termination.
- Adds lifecycle status to the Phase 60 production support diagnostic report.
- Uses atomic temporary-file replacement for lifecycle state writes.
- Does not modify the SQLite business database.

## Recovery behaviour

A normal BKPOS close records `clean_shutdown`. If BKPOS crashes or is forcibly
terminated, the previous state remains `running`. On the next launch BKPOS
reports that the previous run was not clean and records the new run as `running`.

## Scope

This phase is operational hardening only. No business transaction logic or
installed production executable is modified.
