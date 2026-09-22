"""BKPOS Phase 67 — hardened cash-up controls.

Adds deterministic cash-count validation, variance reasons/approval metadata,
and a database-level guard against duplicate open shifts.
"""
from __future__ import annotations
import json
from datetime import datetime

DENOMINATIONS = (200, 100, 50, 20, 10, 5, 2, 1, 0.50, 0.20, 0.10)

def ensure_schema(conn):
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_cashier_shifts_one_open_per_cashier ON cashier_shifts(cashier) WHERE status='OPEN'")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cashup_records'").fetchone():
        cols = {r[1] for r in conn.execute('PRAGMA table_info(cashup_records)').fetchall()}
        additions = {
            'counted_at': 'TEXT', 'count_json': 'TEXT', 'variance_reason': 'TEXT DEFAULT \'\'',
            'approved_by': 'TEXT', 'approval_note': 'TEXT DEFAULT \'\''
        }
        for name, typ in additions.items():
            if name not in cols:
                conn.execute(f'ALTER TABLE cashup_records ADD COLUMN {name} {typ}')

def validate_denominations(counts):
    if counts is None:
        return {}, None
    if not isinstance(counts, dict):
        raise ValueError('Cash denomination counts must be a dictionary.')
    cleaned = {}
    total = 0.0
    for key, value in counts.items():
        try: denom = float(key); qty = int(value)
        except Exception as exc: raise ValueError(f'Invalid denomination count: {key}={value}') from exc
        if denom not in DENOMINATIONS:
            raise ValueError(f'Unsupported cash denomination: {denom:g}')
        if qty < 0:
            raise ValueError('Cash denomination quantities cannot be negative.')
        cleaned[('%.2f' % denom).rstrip('0').rstrip('.')] = qty
        total += denom * qty
    return cleaned, round(total, 2)

def validate_cashup(*, expected_cash, actual_cash, denomination_counts=None, variance_reason='', approved_by=''):
    expected = round(float(expected_cash), 2); actual = round(float(actual_cash), 2)
    if actual < 0: raise ValueError('Actual cash cannot be negative.')
    counts, counted_total = validate_denominations(denomination_counts)
    if counted_total is not None and abs(counted_total - actual) > 0.009:
        raise ValueError(f'Denomination count R {counted_total:,.2f} does not equal actual cash R {actual:,.2f}.')
    variance = round(actual - expected, 2)
    reason = str(variance_reason or '').strip()
    approver = str(approved_by or '').strip()
    if abs(variance) > 0.009 and not reason:
        raise ValueError('A reason is required when the cash-up has a variance.')
    if approver and not reason and abs(variance) > 0.009:
        raise ValueError('Variance approval requires a variance reason.')
    return {'expected_cash': expected, 'actual_cash': actual, 'difference': variance,
            'count_json': json.dumps(counts, sort_keys=True), 'counted_total': counted_total,
            'variance_reason': reason, 'approved_by': approver,
            'counted_at': datetime.now().isoformat(timespec='seconds') if denomination_counts is not None else None}
