BKPOS – Six Major Upgrades
============================

This package is based on your uploaded my_pos_app(4) project and adds six grouped upgrades while preserving the existing POS modules.

1. Security & Audit Trail
   - Audit log window
   - Login/logout
   - Sales, returns, GRNs
   - Product price and stock changes
   - User/role/branch context

2. Advanced Reports
   - Date-range sales
   - VAT (VAT-inclusive selling prices)
   - Cost and estimated gross profit
   - Cash/card
   - Refunds
   - Stock valuation
   - Top products
   - CSV export

3. Barcode & Label Printing
   - Product search
   - Code 128 barcode labels
   - PDF label generation
   - Print the generated PDF using the Windows label printer

4. Customer Management
   - Customer details
   - Phone/email/address
   - Credit limit
   - Search and edit

5. Multi-Branch / Stock Transfers
   - Branch stock ledger
   - Branch-to-branch transfers
   - Transfer history
   - Cashier branch context

6. Advanced Backup & Disaster Recovery
   - Verified database backups
   - Safe restore with a pre-restore safety backup
   - Backup integrity checking
   - Backup folder access

New feature modules:
- audit_log.py
- advanced_reports.py
- barcode_labels.py
- customers.py
- multi_branch.py
- disaster_recovery.py
- pos_six_upgrades.py

Important:
- Your existing app.py, payment.py, receipt_printer.py, returns.py, stock.py, GRN system, permissions, multi-invoice system, shifts, dashboard and existing management upgrades are retained.
- app_old.py and existing backup/working files are retained.
- GRN printing was NOT added.
- VAT remains inclusive: a displayed selling price is the customer price; VAT is calculated as total * 15 / 115.

Before replacing your live project:
1. Close the POS.
2. Make a copy of your current pos_store.db.
3. Extract this ZIP.
4. Run app.py as you normally do.
5. Log in and test the existing POS first.
6. Then open the new Upgrades menu and test each feature.

The six upgrades create/upgrade their database tables automatically; no manual SQL editing is required.

Note: barcode label generation uses ReportLab, which is already used by the receipt/PDF functionality in this project. The existing project also uses tkcalendar, so keep the dependencies already required by your current POS installation.
