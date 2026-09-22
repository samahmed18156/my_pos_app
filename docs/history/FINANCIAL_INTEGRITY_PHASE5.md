# BKPOS Phase 5 — Financial Integrity & Reconciliation

This phase adds a read-only financial reconciliation layer and automated tests.

## Rules
- POS selling prices are VAT-inclusive at 15%.
- Voided sales are excluded from sales, cash/card and profit summaries.
- Returns reduce net sales and restore the returned cost of goods.
- Expenses reduce net profit; structured `operating_expenses` is preferred, with legacy `expenses` as fallback.
- Branch filters apply to sales/returns/expenses; returns use the original sale's branch.
- Customer balances are debit minus credit in `customer_account_transactions`.
- Supplier balances are PURCHASE transactions minus PAYMENT transactions.

## New module
`services/financial_reconciliation.py`

The module is intentionally read-only. It centralizes calculations so reports and tests can use the same formulas.

## Tests
`tests/test_financial_reconciliation.py` adds coverage for VAT, profit, returns, void exclusion, branch isolation, expenses, customer balances and supplier balances.

Run:

    python run_tests.py

Expected result for this build: **53 tests passing**.
