# BKPOS Automated Testing

## Run the full automated suite

From the `my_pos_app` folder:

```bash
python run_tests.py
```

or:

```bash
python -m unittest discover -s tests -v
```

The suite is intentionally based on Python's standard `unittest` library, so it does not require pytest or another external test package.

## What is covered

The current suite checks:

- Password hashing, salts, malformed hashes, and empty-password handling
- Successful login, failed login, unknown users, and legacy-password migration
- Branch stock seeding and branch/global stock consistency
- Stock additions, deductions, insufficient-stock protection, and concurrency guards
- Branch transfers, transfer numbering, validation, and rollback behavior
- Stock movement recording and transaction participation
- Schema setup idempotency and preservation of product data
- Database migration entry point

## Hardware tests

Receipt printers, cash drawers, and barcode scanners are **manual hardware tests**. They should not run as part of the automated suite because they depend on physical Windows devices.

## Development rule

Any new financial or stock-changing feature should add an automated test before it is considered complete.


## Phase 4 sales lifecycle coverage

The automated suite now includes `tests/test_sales_lifecycle.py`. It exercises the transactional sales service without Tkinter or physical hardware, including cash, card, split payments, credit accounts, branch-specific stock, payment detail fields, unknown products, insufficient stock, partial multi-item rollback, and customer-ledger rollback.

The POS checkout now delegates its database transaction to `services/sales_service.py`, so the same business logic is directly testable.
