# BKPOS Phase 15 — Advanced Pricing & Promotion Management

## Scope
Additive management controls for pricing governance. Existing checkout, promotion application, sales, stock and accounting behavior is preserved.

## Added
- Pricing catalog with selling price, cost and margin analysis.
- Minimum-margin alerts and margin-protected scheduled prices.
- Scheduled price definitions with effective/end dates and optional branch scope.
- Promotion calendar and overlapping active-promotion detection.
- Price-change audit storage for future controlled application workflows.
- CSV export of the pricing catalog.
- Utility menu integration.

## Safety
- Scheduled prices are definitions; they do not silently overwrite live prices.
- Margin protection rejects schedules below the configured minimum margin.
- Existing promotion checkout remains unchanged and continues to use the Phase 8 promotion service.
- No existing features or functions were deleted.

## Verification
- 201 tests passed
- 20 subtests passed
- Python compilation passed
