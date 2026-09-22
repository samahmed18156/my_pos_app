"""Purchase order lifecycle for BKPOS. POs reserve no stock and create no liability."""
from datetime import datetime
from core.document_numbers import next_document_number

def _audit(conn, action, po_no, details, username='Unknown'):
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,event_time TEXT,username TEXT,action TEXT,entity_type TEXT,entity_id TEXT,details TEXT,branch_id INTEGER,event_type TEXT)''')
    conn.execute("INSERT INTO audit_log(event_time,username,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?)",(username or 'Unknown',action,'PURCHASE_ORDER',str(po_no),details,1,action))

def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS purchase_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, po_no TEXT UNIQUE NOT NULL,
        supplier_id INTEGER NOT NULL, supplier_account TEXT, supplier_name TEXT NOT NULL,
        order_date TEXT NOT NULL, expected_date TEXT, notes TEXT, status TEXT NOT NULL DEFAULT 'DRAFT',
        total REAL NOT NULL DEFAULT 0, created_by TEXT DEFAULT 'Unknown', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS purchase_order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, po_id INTEGER NOT NULL, barcode TEXT NOT NULL,
        description TEXT, ordered_qty REAL NOT NULL, unit_cost REAL NOT NULL, received_qty REAL NOT NULL DEFAULT 0,
        value REAL NOT NULL DEFAULT 0)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_po_items_po ON purchase_order_items(po_id)')
    # Link GRNs back to the PO that they fulfil.
    cols={r[1] for r in conn.execute('PRAGMA table_info(grn_headers)')}
    if 'po_no' not in cols: conn.execute('ALTER TABLE grn_headers ADD COLUMN po_no TEXT')

def create_purchase_order(conn, *, supplier_id, supplier_account, supplier_name, items,
                          expected_date='', notes='', created_by='Unknown', po_no=None):
    ensure_schema(conn)
    if not supplier_id or not supplier_name: raise ValueError('A supplier account is required.')
    if not items: raise ValueError('A purchase order must contain at least one item.')
    prepared=[]; total=0
    for item in items:
        code=str(item.get('barcode') or '').strip(); qty=float(item.get('qty',0) or 0); cost=round(float(item.get('cost',0) or 0),2)
        if not code or qty<=0 or cost<0: raise ValueError('Each PO item needs a product, positive quantity and non-negative cost.')
        row=conn.execute('SELECT description FROM products WHERE barcode=?',(code,)).fetchone()
        if not row: raise ValueError(f'Product {code} was not found in Product Master.')
        value=round(qty*cost,2); total+=value; prepared.append((code,item.get('description') or row[0] or code,qty,cost,value))
    no=po_no or next_document_number(conn,'po','PO')
    stamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur=conn.execute('''INSERT INTO purchase_orders(po_no,supplier_id,supplier_account,supplier_name,order_date,expected_date,notes,status,total,created_by,created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(no,int(supplier_id),supplier_account or '',supplier_name,stamp[:10],expected_date or '',notes or '','DRAFT',round(total,2),created_by or 'Unknown',stamp))
    pid=cur.lastrowid
    for code,desc,qty,cost,value in prepared:
        conn.execute('''INSERT INTO purchase_order_items(po_id,barcode,description,ordered_qty,unit_cost,received_qty,value) VALUES(?,?,?,?,?,?,?)''',(pid,code,desc,qty,cost,0,value))
    _audit(conn,'PURCHASE_ORDER_CREATED',no,f'{len(prepared)} item(s); total R {total:,.2f}',created_by)
    return {'po_id':pid,'po_no':no,'total':round(total,2),'item_count':len(prepared)}

def set_status(conn, po_id, status):
    ensure_schema(conn); allowed={'DRAFT','ORDERED','PARTIALLY RECEIVED','FULLY RECEIVED','CANCELLED'}
    status=str(status).upper()
    if status not in allowed: raise ValueError('Invalid purchase order status.')
    row=conn.execute('SELECT status FROM purchase_orders WHERE id=?',(po_id,)).fetchone()
    if not row: raise ValueError('Purchase order not found.')
    if row[0]=='FULLY RECEIVED' and status!='FULLY RECEIVED': raise ValueError('A fully received purchase order cannot be reopened.')
    if row[0]=='CANCELLED' and status!='CANCELLED': raise ValueError('A cancelled purchase order cannot be reopened.')
    conn.execute('UPDATE purchase_orders SET status=? WHERE id=?',(status,po_id))
    no=conn.execute('SELECT po_no FROM purchase_orders WHERE id=?',(po_id,)).fetchone()[0]
    _audit(conn,f'PURCHASE_ORDER_{status.replace(" ","_")}',no,f'Status changed to {status}', 'Unknown')

def update_receipts_for_po(conn, po_no):
    ensure_schema(conn)
    po=conn.execute('SELECT id,status FROM purchase_orders WHERE po_no=?',(po_no,)).fetchone()
    if not po: raise ValueError(f'Purchase order {po_no} was not found.')
    rows=conn.execute('''SELECT poi.id, poi.ordered_qty, COALESCE(SUM(gi.qty_received),0)
                         FROM purchase_order_items poi LEFT JOIN grn_headers gh ON gh.po_no=?
                         LEFT JOIN grn_items gi ON gi.grn_id=gh.id AND gi.barcode=poi.barcode
                         WHERE poi.po_id=? GROUP BY poi.id,poi.ordered_qty''',(po_no,po[0])).fetchall()
    total_ordered=sum(float(r[1]) for r in rows); total_received=sum(float(r[2]) for r in rows)
    for r in rows: conn.execute('UPDATE purchase_order_items SET received_qty=? WHERE id=?',(float(r[2]),r[0]))
    old=po[1]
    if old=='CANCELLED': return old
    new='FULLY RECEIVED' if rows and all(float(r[2])>=float(r[1]) for r in rows) else ('PARTIALLY RECEIVED' if total_received>0 else old)
    if new=='PARTIALLY RECEIVED' and old=='DRAFT': new='PARTIALLY RECEIVED'
    conn.execute('UPDATE purchase_orders SET status=? WHERE id=?',(new,po[0]))
    if new != old:
        _audit(conn,f'PURCHASE_ORDER_{new.replace(" ","_")}',po_no,f'Receipts updated: {total_received:g} of {total_ordered:g} units')
    return new
