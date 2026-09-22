# BKPOS Phase 13 — Advanced Inventory Forecasting & Demand Planning

Phase 13 adds read-only demand planning on top of the existing inventory and purchasing features. Existing stock, purchasing, sales and checkout behavior is unchanged.

## Included
- Historical average daily demand
- Recent-demand weighting for a more responsive forecast
- Configurable forward forecast horizon
- Days-of-stock-cover calculation
- Stockout/watch risk classification
- Weekly sales seasonality and peak weekday analysis
- Inventory risk view
- CSV export
- Utility menu integration

## Safety
This phase is analytical only. It does not post stock movements, purchase orders, GRNs, price changes, sales, returns or accounting entries.

## Verification
- 193 tests passed
- 20 subtests passed
- Python compilation passed
