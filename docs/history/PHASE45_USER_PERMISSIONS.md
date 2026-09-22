# BKPOS Phase 45 — User Roles & Permissions
Adds Admin, Manager and Cashier permission policy. UI filtering is only a usability layer; protected actions must also call `require_permission()` before execution. Existing financial workflows are not mass-edited in this phase.
