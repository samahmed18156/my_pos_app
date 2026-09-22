# BKPOS Phase 84 — Purchase Orders

Adds a supplier Purchase Order workflow without duplicating GRN/accounting functions.

- Create and save draft purchase orders.
- Mark a PO as Ordered.
- Track ordered vs received quantities.
- Create a GRN preloaded from the outstanding PO quantities.
- GRNs link back to the PO and update PO status to Partially Received / Fully Received.
- View/reprint a PO through JasperViewer.
- PO creation does not change stock, supplier liability, or accounting balances.
- Purchase-order actions are recorded in the audit log.

Menu: **Creditors → Purchase Orders**.

Tests: `tests/test_purchase_orders.py` plus the existing purchase lifecycle tests.
