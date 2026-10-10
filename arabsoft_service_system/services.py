from .db import now

STATUSES = [('received','تم الاستلام'),('checking','تحت الفحص'),('waiting_customer','انتظار موافقة العميل'),('repairing','جاري الإصلاح'),('waiting_part','انتظار قطعة غيار'),('repaired','تم الإصلاح'),('ready','جاهز للتسليم'),('delivered','تم التسليم'),('cancelled','ملغي')]
PRIORITIES=[('low','منخفض'),('normal','عادي'),('high','عاجل')]
PAY_METHODS=['نقدي','تحويل','بطاقة','محفظة']

def status_label(key): return dict(STATUSES).get(key,key)

def next_ticket(db):
    row=db.one("SELECT ticket_no FROM repairs ORDER BY id DESC LIMIT 1")
    n=1
    if row:
        try:n=int(row['ticket_no'].split('-')[-1])+1
        except: n=row['id']+1
    return f"SR-{n:06d}"

def repair_totals(db, repair_id):
    r=db.one('SELECT labor,discount,paid FROM repairs WHERE id=?',(repair_id,))
    parts=db.one('SELECT COALESCE(SUM(qty*unit_price),0) total FROM repair_parts WHERE repair_id=?',(repair_id,))
    total=(r['labor'] or 0)+(parts['total'] or 0)-(r['discount'] or 0)
    return total, r['paid'] or 0, total-(r['paid'] or 0)

def log(db,user_id,action,entity,eid,details=''):
    db.execute('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(user_id,action,entity,eid,details,now()))
