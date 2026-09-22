"""Transactional promotion calculation for BKPOS Phase 8.

Promotions are evaluated against the current cart without mutating the cart.
The service chooses the single highest-value eligible promotion to keep pricing
predictable and prevent accidental promotion stacking.
"""
from datetime import datetime


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS promotion_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promotion_id INTEGER NOT NULL,
        sale_id INTEGER NOT NULL UNIQUE,
        discount_amount REAL NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")


def _money(v):
    return round(float(v or 0), 2)


def _active_promotions(conn, sale_date=None):
    sale_date = sale_date or datetime.now().strftime('%Y-%m-%d')
    try:
        rows = conn.execute("""SELECT id,name,promo_type,value,start_date,end_date,min_spend,active,notes
            FROM promotions WHERE active=1 AND date(start_date)<=date(?) AND date(end_date)>=date(?)
            ORDER BY id""", (sale_date, sale_date)).fetchall()
    except Exception:
        return []
    return rows


def _buy_get_discount(cart, buy, get):
    if buy <= 0 or get <= 0:
        return 0.0
    total_qty = sum(float(i.get('qty', 0) or 0) for i in cart)
    groups = int(total_qty // (buy + get))
    if groups <= 0:
        return 0.0
    unit_prices = []
    for item in cart:
        qty = int(float(item.get('qty', 0) or 0))
        price = _money(item.get('price', 0))
        unit_prices.extend([price] * max(0, qty))
    unit_prices.sort()
    free_units = min(len(unit_prices), groups * get)
    return _money(sum(unit_prices[:free_units]))


def calculate_best_promotion(conn, cart, sale_date=None):
    """Return the best single promotion and discounted cart.

    Buy X Get Y uses ``notes`` such as ``buy=2,get=1``. Percentage and fixed
    amount promotions are cart-wide and subject to min_spend.
    """
    base = _money(sum(float(i.get('qty', 0) or 0) * _money(i.get('price', 0)) for i in cart))
    if base <= 0 or not cart:
        return {'promotion_id': None, 'name': '', 'discount': 0.0, 'total': base, 'cart': [dict(i) for i in cart]}
    candidates = []
    for pid, name, ptype, value, start, end, min_spend, active, notes in _active_promotions(conn, sale_date):
        if base + 0.005 < _money(min_spend):
            continue
        discount = 0.0
        if ptype == 'Percentage':
            discount = _money(base * min(100.0, max(0.0, float(value))) / 100.0)
        elif ptype == 'Fixed Amount':
            discount = min(base, _money(value))
        elif ptype == 'Buy X Get Y':
            import re
            buy = get = 0
            m1 = re.search(r'\bbuy\s*=\s*(\d+)', notes or '', re.I)
            m2 = re.search(r'\bget\s*=\s*(\d+)', notes or '', re.I)
            if m1 and m2:
                buy, get = int(m1.group(1)), int(m2.group(1))
            discount = min(base, _buy_get_discount(cart, buy, get))
        discount = min(base, max(0.0, _money(discount)))
        if discount > 0:
            candidates.append((discount, int(pid), name, ptype))
    if not candidates:
        return {'promotion_id': None, 'name': '', 'discount': 0.0, 'total': base, 'cart': [dict(i) for i in cart]}
    discount, pid, name, ptype = max(candidates, key=lambda x: (x[0], -x[1]))
    factor = (base - discount) / base if base else 1.0
    new_cart = []
    remaining_discount = discount
    for idx, item in enumerate(cart):
        clone = dict(item)
        line_base = _money(float(item.get('qty', 0) or 0) * _money(item.get('price', 0)))
        if idx == len(cart) - 1:
            line_discount = remaining_discount
        else:
            line_discount = _money(line_base * (1 - factor))
            remaining_discount = _money(remaining_discount - line_discount)
        qty = float(item.get('qty', 0) or 0)
        clone['value'] = _money(line_base - line_discount)
        clone['promotion_discount'] = line_discount
        clone['original_price'] = _money(item.get('price', 0))
        clone['price'] = _money(clone['value'] / qty) if qty else 0.0
        new_cart.append(clone)
    return {'promotion_id': pid, 'name': name, 'discount': discount, 'total': _money(base-discount), 'cart': new_cart, 'type': ptype}


def record_redemption(conn, promotion_id, sale_id, discount_amount):
    if not promotion_id or discount_amount <= 0:
        return
    ensure_schema(conn)
    conn.execute("INSERT OR IGNORE INTO promotion_redemptions(promotion_id,sale_id,discount_amount) VALUES(?,?,?)",
                 (int(promotion_id), int(sale_id), _money(discount_amount)))
