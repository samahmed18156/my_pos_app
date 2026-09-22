# Phase 41 Test Plan

1. Trigger a controlled generic exception and verify a user-friendly message.
2. Verify an error reference is displayed.
3. Verify technical details are written to the BKPOS error log.
4. Simulate a locked database and verify the specific guidance.
5. Simulate a read-only/permission failure and verify the specific guidance.
6. Verify database schema errors do not expose raw SQL/Python tracebacks.
7. Verify normal successful operations remain unchanged.
8. Verify no automatic deletion or replacement of `pos_store.db`.
