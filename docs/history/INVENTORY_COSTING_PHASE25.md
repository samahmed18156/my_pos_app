# BKPOS Phase 25 — Inventory Costing

## Costing method
BKPOS now uses **perpetual weighted-average cost** for inventory.

For each receipt:

`new average cost = ((opening quantity × opening average cost) + (received quantity × receipt cost)) / closing quantity`

The current `products.cost_price` is therefore the moving-average cost used for stock valuation and new sales.

## Historical COGS
Every new sale stores the moving-average unit cost used at posting time in `sale_items.cost_price`, and `sales_history.total_cost` is calculated from those costs. The caller-supplied legacy total cost is no longer authoritative.

This prevents later GRNs or product-master cost changes from rewriting the COGS of an earlier sale.

## Customer returns
Customer returns use the original sale line's historical cost and recalculate the moving-average inventory cost after the returned units are restored.

## Existing databases
Existing `products.cost_price` values are treated as the opening average cost for stock already on hand. No historical stock layers are invented, so old transactions remain untouched.

## Supplier credits
Supplier credits continue to use the originating GRN's invoice cost for the supplier liability/credit amount. The inventory valuation remains based on the moving-average cost. Any difference between supplier invoice cost and current inventory average is therefore not silently treated as a change to the supplier liability.
