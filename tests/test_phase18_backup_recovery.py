import os, sqlite3
from backup_recovery_upgrade import backup_inventory, recovery_health, restore_drill, export_inventory
from services.production_hardening import backup_database

def make_db(tmp):
    p=os.path.join(tmp,'pos.db'); c=sqlite3.connect(p); c.execute('create table t(id integer)'); c.execute('insert into t values(1)'); c.commit(); c.close(); return p

def test_inventory_and_health(tmp_path):
    db=make_db(tmp_path); b=tmp_path/'backups'; b.mkdir(); target=b/'x.db'; backup_database(db,target)
    inv=backup_inventory(b); assert len(inv)==1 and inv[0]['verified']
    h=recovery_health(db,b,max_age_hours=24); assert h['database_integrity'] and h['verified_backups']==1 and h['status']=='READY'

def test_restore_drill_is_non_destructive(tmp_path):
    db=make_db(tmp_path); target=tmp_path/'b.db'; backup_database(db,target)
    result=restore_drill(target); assert result['success'] and result['tables']==1; assert os.path.exists(db)

def test_bad_backup_rejected(tmp_path):
    p=tmp_path/'bad.db'; p.write_text('not sqlite')
    try: restore_drill(p)
    except ValueError: pass
    else: assert False

def test_export(tmp_path):
    out=tmp_path/'inventory.csv'; export_inventory([{'name':'x.db','modified':'now','size_bytes':10,'verified':True}],out); assert out.exists() and 'x.db' in out.read_text()
