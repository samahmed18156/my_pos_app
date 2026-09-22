# Phase 8 — Integrated Promotions, Loyalty & Checkout

Phase 8 connects the Phase 6 promotion catalogue to the transactional checkout while adding an auditable customer loyalty ledger.

## Behaviour
- The best single eligible promotion is selected for each checkout.
- Percentage and fixed promotions are supported directly.
- Buy-X/Get-Y uses promotion notes such as `buy=2,get=1`.
- Promotion discounts are stored as transaction redemption records.
- Customer sales earn 1 point per R10 of completed sale value.
- Voids reverse all points earned by the sale.
- Returns reverse loyalty points proportionally to returned value.
- Existing open carts are not mutated by promotion calculation.

## Safety
Promotion and loyalty operations are transaction-bound and do not change stock/accounting rules outside the existing sale/return/void transaction.
