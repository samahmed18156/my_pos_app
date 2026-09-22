# Phase 1 — UI/UX Polish

This phase improves presentation and cashier ergonomics without changing business logic or removing features.

## Changes

- Centralized the primary visual palette and ttk styling in `ui/theme.py`.
- Improved Treeview readability with consistent row height, headings, selection state, and typography.
- Added consistent hover/active behavior to the primary POS action buttons.
- Improved input-field focus visibility for barcode, quantity, price, and customer fields.
- Added a persistent `READY` indicator to the POS status bar.
- Added `Ctrl+L` to return focus to barcode entry and select its contents.
- Added `Esc` to clear transient product-entry fields without clearing the cart.
- Updated the main POS window title to remove the obsolete hard-coded January 2026 label.

## Safety

- No business services were changed.
- No database schema was changed.
- No POS features were removed.
- Existing function/class inventory remains intact.
- Existing automated tests remain the regression gate.

## Validation

- Python compilation: passed.
- Automated tests: **152 passed**.
- Existing subtests: **20 passed**.
