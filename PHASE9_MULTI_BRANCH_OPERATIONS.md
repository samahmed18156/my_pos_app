# Phase 9 — Multi-Branch Operations & Synchronization

Phase 9 adds branch-level operational visibility and a conservative synchronization workflow without removing existing features.

## Added
- Multi-Branch Operations window under Utility.
- Branch inventory overview and transfer history.
- Stock reconciliation between global `products.soh` and summed branch stock.
- Branch sync bundles (`BKPOS_BRANCH_SYNC_V1`) for offline/portable exchange.
- Idempotent bundle staging with conflict detection.
- Imports never overwrite live stock automatically; differences are staged for review.
- Transfer posting remains transactional through the existing branch stock service.

## Safety
The synchronization layer deliberately avoids blind last-write-wins stock replacement. A bundle is evidence of another branch's state, not permission to overwrite local inventory.
