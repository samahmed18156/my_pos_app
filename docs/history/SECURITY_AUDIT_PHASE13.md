# BKPOS Phase 13 — Security, Branch Isolation & Audit Controls

## Implemented
- Central authorization helpers in `security_controls.py`.
- New permissions: void sales, issue credit notes, manage users, manage branches, cash-up, manage expenses.
- Existing `users` databases are migrated automatically with the new permission columns.
- Login now carries the user's assigned `branch_id` and new permissions into the application session.
- Completed-sale void requires `can_void_sales`.
- POS F12 credit notes require `can_issue_credit_notes`.
- Branch-aware operations can enforce that non-admin users only operate on their assigned branch.
- Audit log now has append-only SQLite triggers preventing UPDATE/DELETE of history.
- F12 credit-note stock movement errors are no longer silently swallowed.

## Authorization rule
UI visibility is convenience only. Business operations should call `require_permission()` before sensitive mutation and `require_branch()` before branch-sensitive mutation.

## New permission columns
- `can_void_sales`
- `can_issue_credit_notes`
- `can_manage_users`
- `can_manage_branches`
- `can_cashup`
- `can_manage_expenses`

Admins retain full access. Existing non-admin users default to the new permissions being disabled until explicitly granted.

## Manual acceptance
1. Create a cashier without void permission; attempt a completed-sale void — it must be rejected.
2. Create a cashier without credit-note permission; attempt F12 credit note — it must be rejected.
3. A branch-2 user must not operate on branch 1 through branch-sensitive service calls.
4. Admin can operate across branches.
5. Perform a void/credit action and verify it appears in Audit Log.
6. Attempt to edit/delete an audit row from a database tool — SQLite must reject it.
