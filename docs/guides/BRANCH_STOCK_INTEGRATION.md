# Branch Stock Integration

This build makes branch stock authoritative by branch while retaining `products.soh` as the global total for legacy screens/reports.

## Rules
- POS sales reduce the logged-in user's branch stock.
- GRNs increase the logged-in user's branch stock.
- Customer returns restore stock to the branch recorded on the active POS session.
- Standalone POS credit notes restore stock to the active branch.
- Supplier stock credit notes reduce stock at the active branch.
- Voiding a sale restores stock to the branch stored on the original sale, so an administrator can safely void a sale from another branch.
- Transfers reduce the source branch and increase the destination branch in one transaction.
- `products.soh` changes by the same net amount as branch stock, so it remains the global total.

## Important
Existing `products.soh` values are treated as Main Store (branch 1) stock only when a branch_stock row does not already exist. This preserves the existing database.

A future reporting pass should add branch filters to every management report so branch-specific and consolidated figures are clearly distinguished.
