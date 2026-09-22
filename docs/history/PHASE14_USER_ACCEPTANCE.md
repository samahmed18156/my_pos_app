# BKPOS Phase 14 — User Acceptance & Security Test Plan

## Goal
Validate role enforcement and branch isolation from the application/service boundary.

## Roles
- ADMIN: unrestricted management access
- MANAGER: management functions explicitly granted by permissions
- CASHIER: normal POS operations only

## Required negative tests
1. Cashier cannot void a completed sale without `can_void_sales`.
2. Cashier cannot issue a stock/supplier credit note without `can_issue_credit_notes`.
3. A user assigned to Branch A cannot perform branch-scoped stock operations against Branch B.
4. Permission checks cannot be bypassed by calling the service directly.
5. Audit records for sensitive operations cannot be edited or deleted.

## Required positive tests
1. Admin can perform permitted cross-branch management operations.
2. A manager with an explicit permission can perform that operation.
3. A cashier can complete normal sales and permitted customer/payment operations.

## Manual GUI acceptance
On the real Windows machine, create/test one Admin, one Manager and one Cashier.
For each role, attempt both an allowed and a deliberately forbidden operation.
Record the result before release.

## Release rule
Any forbidden operation that succeeds is a release blocker.
