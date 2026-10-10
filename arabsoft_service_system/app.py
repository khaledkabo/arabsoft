import os, sys, csv, shutil, sqlite3, datetime, hashlib, secrets, subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from .db import DB, now, hash_password, verify_password
from .services import STATUSES, PRIORITIES, PAY_METHODS, status_label, next_ticket, repair_totals, log

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    PDF_OK=True
except Exception: PDF_OK=False
try:
    import qrcode
    QR_OK=True
except Exception: QR_OK=False

FONT=('Tahoma',10); TITLE=('Tahoma',18,'bold'); BIG=('Tahoma',24,'bold')
BG='#F5F7FA'; NAV='#0F172A'; ACCENT='#2563EB'


def val(w):
    return w.get('1.0','end-1c').strip() if isinstance(w,tk.Text) else w.get().strip()

def entry(parent,w=34):
    return ttk.Entry(parent,width=w,justify='right')

def text(parent,w=34,h=4):
    return tk.Text(parent,width=w,height=h,font=FONT)

def money(x):
    try:return f'{float(x or 0):,.2f}'
    except:return '0.00'

class Login:
    def __init__(self,root,db,done):
        self.root,self.db,self.done=root,db,done
        root.title('ARAB SOFT | تسجيل الدخول'); root.geometry('440x390'); root.resizable(False,False)
        f=ttk.Frame(root,padding=35); f.pack(fill='both',expand=True)
        ttk.Label(f,text='ARAB SOFT',font=('Tahoma',26,'bold')).pack(pady=5)
        ttk.Label(f,text='نظام إدارة مركز الصيانة',font=('Tahoma',12)).pack(pady=3)
        ttk.Separator(f).pack(fill='x',pady=18)
        ttk.Label(f,text='اسم المستخدم').pack(anchor='e'); self.u=entry(f); self.u.pack(fill='x',pady=6); self.u.insert(0,'admin')
        ttk.Label(f,text='كلمة المرور').pack(anchor='e'); self.p=entry(f); self.p.pack(fill='x',pady=6); self.p.configure(show='*')
        self.msg=ttk.Label(f,text=''); self.msg.pack(pady=4)
        ttk.Button(f,text='دخول',command=self.login).pack(fill='x',pady=12)
        ttk.Label(f,text='الافتراضي: admin / admin',font=('Tahoma',9)).pack()
        self.p.bind('<Return>',lambda e:self.login()); self.u.focus_set()
    def login(self):
        r=self.db.one('SELECT * FROM users WHERE username=? AND active=1',(self.u.get().strip(),))
        if not r or not verify_password(self.p.get(),r['salt'],r['password_hash']):
            self.msg.configure(text='بيانات الدخول غير صحيحة'); return
        self.done(r)

class App:
    def __init__(self,root,db,user):
        self.root,self.db,self.user=root,db,user
        self.root.title('ARAB SOFT | إدارة مركز الصيانة'); self.root.geometry('1440x850'); self.root.minsize(1150,700)
        self.style=ttk.Style(); self.style.theme_use('clam'); self.style.configure('Treeview',rowheight=29,font=FONT); self.style.configure('Treeview.Heading',font=('Tahoma',10,'bold'))
        self.build_shell(); self.dashboard()
    def setting(self,k):
        r=self.db.one('SELECT value FROM settings WHERE key=?',(k,)); return r['value'] if r else ''
    def can(self,*roles): return self.user['role']=='admin' or self.user['role'] in roles
    def build_shell(self):
        top=ttk.Frame(self.root,padding=10); top.pack(fill='x')
        self.shop= tk.StringVar(value=self.setting('shop_name'))
        ttk.Label(top,textvariable=self.shop,font=TITLE).pack(side='right')
        ttk.Label(top,text=f"{self.user['username']} | {self.user['role']}").pack(side='left')
        nav=ttk.Frame(self.root,padding=(8,2)); nav.pack(fill='x')
        tabs=[('الرئيسية',self.dashboard),('استلام وصيانة',self.repairs_page),('العملاء',self.customers_page),('الفنيون',self.tech_page),('المخزن',self.parts_page),('الحسابات',self.finance_page),('التقارير',self.reports_page),('الإعدادات',self.settings_page)]
        for t,c in tabs: ttk.Button(nav,text=t,command=c).pack(side='right',padx=2)
        self.body=ttk.Frame(self.root,padding=10); self.body.pack(fill='both',expand=True)
        self.status=ttk.Label(self.root,text='جاهز',anchor='e',padding=5); self.status.pack(fill='x')
    def clear(self):
        for w in self.body.winfo_children(): w.destroy()
    def title(self,t,button=None):
        b=ttk.Frame(self.body); b.pack(fill='x',pady=(0,10)); ttk.Label(b,text=t,font=TITLE).pack(side='right')
        if button: ttk.Button(b,text=button[0],command=button[1]).pack(side='left')
    def cards(self,items):
        f=ttk.Frame(self.body); f.pack(fill='x',pady=5)
        for a,b in items:
            x=ttk.LabelFrame(f,text=a,padding=12); x.pack(side='right',fill='x',expand=True,padx=4); ttk.Label(x,text=str(b),font=BIG).pack()
    def tree(self,parent,cols,heights=18):
        wrap=ttk.Frame(parent); wrap.pack(fill='both',expand=True)
        ids=[c[0] for c in cols]; tr=ttk.Treeview(wrap,columns=ids,show='headings',height=heights)
        for k,l,*rest in cols: tr.heading(k,text=l); tr.column(k,width=(rest[0] if rest else 120),anchor='e')
        ys=ttk.Scrollbar(wrap,orient='vertical',command=tr.yview); xs=ttk.Scrollbar(wrap,orient='horizontal',command=tr.xview); tr.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        tr.pack(side='left',fill='both',expand=True); ys.pack(side='right',fill='y'); xs.pack(side='bottom',fill='x'); return tr
    def dialog(self,title,fields,initial=None,size='600x650'):
        initial=initial or {}; w=tk.Toplevel(self.root); w.title(title); w.geometry(size); w.transient(self.root); w.grab_set()
        outer=ttk.Frame(w,padding=18); outer.pack(fill='both',expand=True); widgets={}
        for i,(k,label,kind,options) in enumerate(fields):
            ttk.Label(outer,text=label).grid(row=i,column=1,sticky='e',padx=7,pady=5)
            if kind=='multi': x=text(outer,36,4)
            elif kind=='combo': x=ttk.Combobox(outer,width=34,values=options or [],state='readonly')
            elif kind=='check': x=tk.BooleanVar(value=bool(initial.get(k,False))); widgets[k]=x; continue
            else: x=entry(outer,36)
            x.grid(row=i,column=0,sticky='ew',pady=5); widgets[k]=x
            if k in initial and initial[k] is not None:
                if kind=='multi': x.insert('1.0',str(initial[k]))
                elif kind=='combo': x.set(str(initial[k]))
                else: x.insert(0,str(initial[k]))
        out={}
        def save():
            for k,x in widgets.items(): out[k]=x.get('1.0','end-1c').strip() if isinstance(x,tk.Text) else (x.get() if hasattr(x,'get') else x)
            w.destroy()
        ttk.Button(outer,text='حفظ',command=save).grid(row=len(fields),column=0,pady=15); ttk.Button(outer,text='إلغاء',command=w.destroy).grid(row=len(fields),column=1,pady=15)
        w.wait_window(); return out or None
    def selected(self,tr):
        s=tr.selection(); return int(s[0]) if s else None

    def dashboard(self):
        self.clear(); self.title('لوحة التحكم',('تحديث',self.dashboard))
        total=self.db.one('SELECT COUNT(*) n FROM repairs')['n']; active=self.db.one("SELECT COUNT(*) n FROM repairs WHERE status NOT IN ('delivered','cancelled')")['n']; ready=self.db.one("SELECT COUNT(*) n FROM repairs WHERE status='ready'")['n']
        today=self.db.one("SELECT COUNT(*) n FROM repairs WHERE date(created_at)=date('now','localtime')")['n']; rev=self.db.one("SELECT COALESCE(SUM(amount),0)n FROM payments")['n']; exp=self.db.one("SELECT COALESCE(SUM(amount),0)n FROM expenses")['n']
        self.cards([('إجمالي الأوامر',total),('أجهزة اليوم',today),('قيد العمل',active),('جاهز للتسليم',ready),('التحصيل',money(rev)),('المصروفات',money(exp))])
        low=self.db.one('SELECT COUNT(*) n FROM parts WHERE qty<=min_qty')['n']; self.cards([('أصناف تحتاج شراء',low),('صافي التحصيل',money(rev-exp))])
        ttk.Label(self.body,text='آخر أوامر الصيانة',font=('Tahoma',13,'bold')).pack(anchor='e',pady=8)
        tr=self.tree(self.body,[('ticket','رقم الأمر',110),('customer','العميل',170),('device','الجهاز',180),('status','الحالة',150),('tech','الفني',130),('total','الإجمالي',100),('due','المتبقي',100),('created','التاريخ',160)])
        rows=self.db.many("SELECT r.*,c.name customer,t.name tech FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id ORDER BY r.id DESC LIMIT 15")
        for r in rows:
            total,paid,due=repair_totals(self.db,r['id']); tr.insert('', 'end',iid=str(r['id']),values=(r['ticket_no'],r['customer'],f"{r['device_type'] or ''} {r['model'] or ''}",status_label(r['status']),r['tech'] or '',money(total),money(due),r['created_at']))

    # Repairs
    def repairs_page(self):
        self.clear(); self.title('استلام ومتابعة الأجهزة',('استلام جهاز جديد',self.add_repair))
        bar=ttk.Frame(self.body); bar.pack(fill='x',pady=5); self.rsearch=tk.StringVar(); e=entry(bar,45); e.pack(side='right'); e.configure(textvariable=self.rsearch); e.bind('<KeyRelease>',lambda e:self.load_repairs()); ttk.Label(bar,text='بحث بالعميل / الهاتف / IMEI / Serial / رقم الأمر:').pack(side='right',padx=8)
        self.rt=self.tree(self.body,[('id','ID',55),('ticket','أمر',105),('customer','العميل',150),('phone','الهاتف',120),('device','الجهاز',170),('status','الحالة',145),('tech','الفني',120),('total','الإجمالي',95),('paid','المدفوع',95),('due','المتبقي',95),('date','التاريخ',150)])
        self.rt.bind('<Double-1>',lambda e:self.repair_detail())
        b=ttk.Frame(self.body); b.pack(fill='x',pady=8)
        for txt,fn in [('فتح الأمر',self.repair_detail),('تعديل',self.edit_repair),('الحالة',self.change_status),('دفعة',self.take_payment),('تسليم',self.deliver_repair),('طباعة استلام',lambda:self.print_receipt('receipt')),('طباعة تسليم',lambda:self.print_receipt('delivery')),('حذف',self.delete_repair)]: ttk.Button(b,text=txt,command=fn).pack(side='right',padx=2)
        self.load_repairs()
    def load_repairs(self):
        if not hasattr(self,'rt'): return
        for i in self.rt.get_children(): self.rt.delete(i)
        q=getattr(self,'rsearch',tk.StringVar()).get().strip(); like=f'%{q}%'
        rows=self.db.many('''SELECT r.*,c.name customer,c.phone,t.name tech FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id WHERE r.ticket_no LIKE ? OR c.name LIKE ? OR c.phone LIKE ? OR r.imei LIKE ? OR r.serial LIKE ? ORDER BY r.id DESC''',(like,like,like,like,like))
        for r in rows:
            total,paid,due=repair_totals(self.db,r['id']); self.rt.insert('', 'end',iid=str(r['id']),values=(r['id'],r['ticket_no'],r['customer'],r['phone'] or '',f"{r['device_type'] or ''} {r['model'] or ''}",status_label(r['status']),r['tech'] or '',money(total),money(paid),money(due),r['created_at']))
    def add_repair(self):
        cs=self.db.many('SELECT id,name,phone FROM customers ORDER BY name'); ts=self.db.many('SELECT id,name FROM technicians WHERE active=1 ORDER BY name')
        d=self.dialog('استلام جهاز',[('customer','العميل','combo',[f"{x['id']} | {x['name']} | {x['phone'] or ''}" for x in cs]),('device_type','نوع الجهاز','text',None),('model','الموديل','text',None),('imei','IMEI','text',None),('serial','Serial','text',None),('color','اللون','text',None),('accessories','الملحقات','text',None),('condition','حالة الجهاز الخارجية','multi',None),('customer_issue','عطل العميل','multi',None),('priority','الأولوية','combo',[x[1] for x in PRIORITIES]),('technician','الفني','combo',[f"{x['id']} | {x['name']}" for x in ts]),('estimated_cost','التكلفة المتوقعة','text',None),('labor','المصنعية','text',None),('warranty_days','الضمان بالأيام','text',None),('notes','ملاحظات','multi',None)],size='680x760')
        if not d or not d.get('customer'): return
        cid=int(d['customer'].split('|')[0]); tid=int(d['technician'].split('|')[0]) if d.get('technician') else None
        cur=self.db.execute('''INSERT INTO repairs(ticket_no,customer_id,device_type,model,imei,serial,color,accessories,condition,customer_issue,technician_id,priority,estimated_cost,labor,warranty_days,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(next_ticket(self.db),cid,d['device_type'],d['model'],d['imei'],d['serial'],d['color'],d['accessories'],d['condition'],d['customer_issue'],tid,dict(PRIORITIES).get(d['priority'],'normal'),float(d['estimated_cost'] or 0),float(d['labor'] or 0),int(float(d['warranty_days'] or self.setting('warranty_default') or 0)),d['notes'],now(),now()))
        log(self.db,self.user['id'],'create','repair',cur.lastrowid,'استلام جهاز'); self.load_repairs(); self.status['text']='تم استلام الجهاز بنجاح'
    def edit_repair(self):
        rid=self.selected(self.rt)
        if not rid:return
        r=self.db.one('SELECT * FROM repairs WHERE id=?',(rid,)); cs=self.db.many('SELECT id,name,phone FROM customers ORDER BY name'); ts=self.db.many('SELECT id,name FROM technicians WHERE active=1 ORDER BY name')
        init=dict(r); init['customer']=next((f"{x['id']} | {x['name']} | {x['phone'] or ''}" for x in cs if x['id']==r['customer_id']),''); init['technician']=next((f"{x['id']} | {x['name']}" for x in ts if x['id']==r['technician_id']),''); init['priority']=dict(PRIORITIES).get(r['priority'],r['priority'])
        d=self.dialog('تعديل أمر الصيانة',[('customer','العميل','combo',[f"{x['id']} | {x['name']} | {x['phone'] or ''}" for x in cs]),('device_type','نوع الجهاز','text',None),('model','الموديل','text',None),('imei','IMEI','text',None),('serial','Serial','text',None),('color','اللون','text',None),('accessories','الملحقات','text',None),('condition','الحالة الخارجية','multi',None),('customer_issue','عطل العميل','multi',None),('technical_diagnosis','التشخيص الفني','multi',None),('priority','الأولوية','combo',[x[1] for x in PRIORITIES]),('technician','الفني','combo',[f"{x['id']} | {x['name']}" for x in ts]),('estimated_cost','التكلفة المتوقعة','text',None),('labor','المصنعية','text',None),('discount','الخصم','text',None),('warranty_days','الضمان بالأيام','text',None),('notes','ملاحظات','multi',None)],init,'680x800')
        if not d:return
        cid=int(d['customer'].split('|')[0]); tid=int(d['technician'].split('|')[0]) if d.get('technician') else None
        self.db.execute('''UPDATE repairs SET customer_id=?,device_type=?,model=?,imei=?,serial=?,color=?,accessories=?,condition=?,customer_issue=?,technical_diagnosis=?,technician_id=?,priority=?,estimated_cost=?,labor=?,discount=?,warranty_days=?,notes=?,updated_at=? WHERE id=?''',(cid,d['device_type'],d['model'],d['imei'],d['serial'],d['color'],d['accessories'],d['condition'],d['customer_issue'],d['technical_diagnosis'],tid,dict((v,k) for k,v in PRIORITIES).get(d['priority'],d['priority']),float(d['estimated_cost'] or 0),float(d['labor'] or 0),float(d['discount'] or 0),int(float(d['warranty_days'] or 0)),d['notes'],now(),rid)); log(self.db,self.user['id'],'update','repair',rid,'تعديل أمر'); self.load_repairs()
    def repair_detail(self):
        rid=self.selected(self.rt)
        if not rid:return
        r=self.db.one('''SELECT r.*,c.name customer,c.phone,c.address,t.name tech FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id WHERE r.id=?''',(rid,)); w=tk.Toplevel(self.root); w.title(f"أمر الصيانة {r['ticket_no']}"); w.geometry('1000x720')
        top=ttk.Frame(w,padding=12); top.pack(fill='x'); ttk.Label(top,text=r['ticket_no'],font=TITLE).pack(side='right'); ttk.Label(top,text=f"{r['customer']} | {r['phone'] or ''} | {r['device_type'] or ''} {r['model'] or ''}").pack(side='left')
        nb=ttk.Notebook(w); nb.pack(fill='both',expand=True,padx=10,pady=10)
        info=ttk.Frame(nb,padding=15); nb.add(info,text='بيانات الجهاز')
        data=[('العطل',r['customer_issue']),('التشخيص',r['technical_diagnosis']),('الحالة',status_label(r['status'])),('الفني',r['tech']),('IMEI',r['imei']),('Serial',r['serial']),('الملحقات',r['accessories']),('حالة الجهاز',r['condition']),('ملاحظات',r['notes'])]
        for i,(a,b) in enumerate(data): ttk.Label(info,text=a+':',font=('Tahoma',10,'bold')).grid(row=i,column=1,sticky='ne',pady=6); ttk.Label(info,text=b or '-',wraplength=650,justify='right').grid(row=i,column=0,sticky='e',pady=6)
        parts=ttk.Frame(nb,padding=10); nb.add(parts,text='قطع الغيار'); pt=self.tree(parts,[('id','ID',50),('sku','SKU',100),('name','الصنف',220),('qty','الكمية',90),('price','السعر',100),('total','الإجمالي',120)])
        rows=self.db.many('SELECT rp.*,p.sku,p.name FROM repair_parts rp JOIN parts p ON p.id=rp.part_id WHERE rp.repair_id=?',(rid,));
        for x in rows: pt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['sku'] or '',x['name'],x['qty'],money(x['unit_price']),money(x['qty']*x['unit_price'])))
        pb=ttk.Frame(parts); pb.pack(fill='x',pady=8); ttk.Button(pb,text='إضافة قطعة',command=lambda:self.add_repair_part(rid,pt)).pack(side='right'); ttk.Button(pb,text='حذف القطعة',command=lambda:self.remove_repair_part(pt,rid)).pack(side='right')
        hist=ttk.Frame(nb,padding=10); nb.add(hist,text='المدفوعات'); h=self.tree(hist,[('id','ID',60),('amount','المبلغ',100),('method','طريقة الدفع',120),('note','ملاحظة',250),('date','التاريخ',170)])
        for x in self.db.many('SELECT * FROM payments WHERE repair_id=? ORDER BY id DESC',(rid,)): h.insert('', 'end',values=(x['id'],money(x['amount']),x['method'],x['note'] or '',x['created_at']))
        total,paid,due=repair_totals(self.db,r); ttk.Label(hist,text=f"الإجمالي: {money(total)}   |   المدفوع: {money(paid)}   |   المتبقي: {money(due)}",font=('Tahoma',13,'bold')).pack(anchor='e',pady=10)
        ttk.Button(w,text='إضافة صور الجهاز',command=lambda:self.add_photos(rid)).pack(side='right',padx=4,pady=8); ttk.Button(w,text='الصور والمرفقات',command=lambda:self.show_photos(rid)).pack(side='right',padx=4,pady=8); ttk.Button(w,text='طباعة إيصال',command=lambda:self.print_receipt('receipt',rid)).pack(side='right',padx=4,pady=8); ttk.Button(w,text='إغلاق',command=w.destroy).pack(side='left',padx=8,pady=8)
    def add_repair_part(self,rid,pt):
        parts=self.db.many('SELECT * FROM parts WHERE qty>0 ORDER BY name'); d=self.dialog('إضافة قطعة للصيانة',[('part','الصنف','combo',[f"{x['id']} | {x['name']} | متاح {x['qty']}" for x in parts]),('qty','الكمية','text',None),('price','سعر البيع','text',None)],size='520x300')
        if not d:return
        p=next((x for x in parts if x['id']==int(d['part'].split('|')[0])),None)
        if not p:return
        q=float(d['qty'] or 0); price=float(d['price'] or p['sale_price']);
        if q<=0 or q>p['qty']: messagebox.showerror('خطأ','الكمية غير متاحة'); return
        self.db.execute('INSERT INTO repair_parts(repair_id,part_id,qty,unit_price) VALUES(?,?,?,?)',(rid,p['id'],q,price)); self.db.execute('UPDATE parts SET qty=qty-? WHERE id=?',(q,p['id'])); self.db.execute('INSERT INTO stock_moves(part_id,type,qty,unit_price,reference,created_at) VALUES(?,?,?,?,?,?)',(p['id'],'repair_out',q,price,f'أمر صيانة {rid}',now()));
        for i in pt.get_children(): pt.delete(i)
        for x in self.db.many('SELECT rp.*,p.sku,p.name FROM repair_parts rp JOIN parts p ON p.id=rp.part_id WHERE rp.repair_id=?',(rid,)): pt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['sku'] or '',x['name'],x['qty'],money(x['unit_price']),money(x['qty']*x['unit_price'])))
    def remove_repair_part(self,pt,rid):
        s=pt.selection();
        if not s:return
        x=self.db.one('SELECT * FROM repair_parts WHERE id=?',(int(s[0]),)); self.db.execute('UPDATE parts SET qty=qty+? WHERE id=?',(x['qty'],x['part_id'])); self.db.execute('DELETE FROM repair_parts WHERE id=?',(x['id'],))
        for i in pt.get_children(): pt.delete(i)
        for x in self.db.many('SELECT rp.*,p.sku,p.name FROM repair_parts rp JOIN parts p ON p.id=rp.part_id WHERE rp.repair_id=?',(rid,)): pt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['sku'] or '',x['name'],x['qty'],money(x['unit_price']),money(x['qty']*x['unit_price'])))
    def change_status(self):
        rid=self.selected(self.rt); 
        if not rid:return
        r=self.db.one('SELECT status FROM repairs WHERE id=?',(rid,)); d=self.dialog('تغيير حالة',[('status','الحالة','combo',[x[1] for x in STATUSES])],{'status':status_label(r['status'])},'450x220')
        if d:
            key=next((k for k,v in STATUSES if v==d['status']),d['status']); self.db.execute('UPDATE repairs SET status=?,updated_at=? WHERE id=?',(key,now(),rid)); log(self.db,self.user['id'],'status','repair',rid,key); self.load_repairs()
    def take_payment(self):
        rid=self.selected(self.rt); 
        if not rid:return
        total,paid,due=repair_totals(self.db,rid)
        if due<=0: messagebox.showinfo('الحساب','لا يوجد مبلغ مستحق'); return
        d=self.dialog('تسجيل دفعة',[('amount','المبلغ','text',None),('method','طريقة الدفع','combo',PAY_METHODS),('note','ملاحظة','text',None)],{'amount':str(due),'method':'نقدي'},'500x300')
        if not d:return
        amount=float(d['amount'] or 0)
        if amount<=0 or amount>due: messagebox.showerror('خطأ','المبلغ غير صحيح'); return
        self.db.execute('UPDATE repairs SET paid=paid+?,updated_at=? WHERE id=?',(amount,now(),rid)); r=self.db.one('SELECT customer_id FROM repairs WHERE id=?',(rid,)); self.db.execute('INSERT INTO payments(repair_id,customer_id,amount,method,note,created_at) VALUES(?,?,?,?,?,?)',(rid,r['customer_id'],amount,d['method'],d['note'],now())); log(self.db,self.user['id'],'payment','repair',rid,str(amount)); self.load_repairs()
    def deliver_repair(self):
        rid=self.selected(self.rt); 
        if not rid:return
        total,paid,due=repair_totals(self.db,rid)
        if due>0 and not messagebox.askyesno('متبقي','يوجد متبقي '+money(due)+'، هل تريد التسليم؟'): return
        days=self.db.one('SELECT warranty_days FROM repairs WHERE id=?',(rid,))['warranty_days'] or 0; until=(datetime.date.today()+datetime.timedelta(days=days)).isoformat() if days else None
        self.db.execute("UPDATE repairs SET status='delivered',delivered_at=?,warranty_until=?,updated_at=? WHERE id=?",(now(),until,now(),rid)); log(self.db,self.user['id'],'deliver','repair',rid,'تسليم الجهاز'); self.load_repairs(); self.print_receipt('delivery',rid)
    def delete_repair(self):
        rid=self.selected(self.rt)
        if rid and self.can('manager') and messagebox.askyesno('تأكيد','حذف أمر الصيانة؟'):
            # restore stock
            for x in self.db.many('SELECT part_id,qty FROM repair_parts WHERE repair_id=?',(rid,)): self.db.execute('UPDATE parts SET qty=qty+? WHERE id=?',(x['qty'],x['part_id']))
            self.db.execute('DELETE FROM repairs WHERE id=?',(rid,)); self.load_repairs()
    def add_photos(self,rid):
        paths=filedialog.askopenfilenames(title='اختيار صور الجهاز',filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp'),('All files','*.*')])
        if not paths:return
        folder=os.path.join(os.path.dirname(self.db.path),'attachments',str(rid)); os.makedirs(folder,exist_ok=True)
        for src in paths:
            try:
                name=os.path.basename(src); dest=os.path.join(folder,f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{name}"); shutil.copy2(src,dest)
                self.db.execute('INSERT INTO repair_photos(repair_id,path,caption,created_at) VALUES(?,?,?,?)',(rid,dest,'',now()))
            except Exception as e: messagebox.showerror('خطأ',f'تعذر حفظ الصورة: {e}')
        messagebox.showinfo('تم','تم حفظ الصور مع أمر الصيانة')
    def show_photos(self,rid):
        w=tk.Toplevel(self.root);w.title('صور الجهاز');w.geometry('760x450');tr=self.tree(w,[('id','ID',60),('path','الملف',500),('date','التاريخ',160)])
        rows=self.db.many('SELECT * FROM repair_photos WHERE repair_id=? ORDER BY id DESC',(rid,))
        for x in rows:tr.insert('', 'end',iid=str(x['id']),values=(x['id'],x['path'],x['created_at']))
        def open_photo():
            s=tr.selection();
            if not s:return
            x=self.db.one('SELECT path FROM repair_photos WHERE id=?',(int(s[0]),)); path=x['path'] if x else ''
            if os.path.exists(path):
                try:os.startfile(path)
                except Exception:
                    try:subprocess.Popen(['xdg-open',path])
                    except:pass
            else:messagebox.showerror('خطأ','ملف الصورة غير موجود')
        def remove():
            s=tr.selection();
            if not s:return
            x=self.db.one('SELECT path FROM repair_photos WHERE id=?',(int(s[0]),))
            if x:
                try:
                    if os.path.exists(x['path']):os.remove(x['path'])
                except:pass
                self.db.execute('DELETE FROM repair_photos WHERE id=?',(int(s[0]),));tr.delete(s[0])
        ttk.Button(w,text='فتح الصورة',command=open_photo).pack(side='right',padx=5,pady=8);ttk.Button(w,text='حذف',command=remove).pack(side='right',padx=5,pady=8)

    # Customers
    def customers_page(self):
        self.clear(); self.title('العملاء',('إضافة عميل',self.add_customer)); self.ct=self.tree(self.body,[('id','ID',60),('name','الاسم',200),('phone','الهاتف',150),('phone2','هاتف إضافي',150),('address','العنوان',250),('date','التاريخ',160)]); self.load_customers(); b=ttk.Frame(self.body); b.pack(fill='x',pady=8); ttk.Button(b,text='سجل العميل',command=self.customer_history).pack(side='right'); ttk.Button(b,text='تعديل',command=self.edit_customer).pack(side='right'); ttk.Button(b,text='حذف',command=self.delete_customer).pack(side='right')
    def load_customers(self):
        for i in self.ct.get_children():self.ct.delete(i)
        for x in self.db.many('SELECT * FROM customers ORDER BY id DESC'):self.ct.insert('', 'end',iid=str(x['id']),values=(x['id'],x['name'],x['phone'] or '',x['phone2'] or '',x['address'] or '',x['created_at']))
    def add_customer(self):
        d=self.dialog('إضافة عميل',[('name','اسم العميل','text',None),('phone','الهاتف','text',None),('phone2','هاتف إضافي','text',None),('address','العنوان','text',None),('notes','ملاحظات','multi',None)],size='550x420')
        if d and d['name']:self.db.execute('INSERT INTO customers(name,phone,phone2,address,notes,created_at) VALUES(?,?,?,?,?,?)',(d['name'],d['phone'],d['phone2'],d['address'],d['notes'],now()));self.load_customers()
    def edit_customer(self):
        cid=self.selected(self.ct)
        if not cid:return
        r=self.db.one('SELECT * FROM customers WHERE id=?',(cid,)); d=self.dialog('تعديل عميل',[('name','اسم العميل','text',None),('phone','الهاتف','text',None),('phone2','هاتف إضافي','text',None),('address','العنوان','text',None),('notes','ملاحظات','multi',None)],dict(r), '550x420')
        if d:self.db.execute('UPDATE customers SET name=?,phone=?,phone2=?,address=?,notes=? WHERE id=?',(d['name'],d['phone'],d['phone2'],d['address'],d['notes'],cid));self.load_customers()
    def customer_history(self):
        cid=self.selected(self.ct)
        if not cid:return
        c=self.db.one('SELECT * FROM customers WHERE id=?',(cid,))
        w=tk.Toplevel(self.root);w.title(f"سجل العميل | {c['name']}");w.geometry('1050x600')
        ttk.Label(w,text=f"{c['name']} | {c['phone'] or ''}",font=TITLE).pack(anchor='e',padx=15,pady=12)
        tr=self.tree(w,[('ticket','الأمر',110),('device','الجهاز',220),('status','الحالة',150),('total','الإجمالي',110),('paid','المدفوع',110),('due','المتبقي',110),('date','التاريخ',160)])
        for r in self.db.many('SELECT * FROM repairs WHERE customer_id=? ORDER BY id DESC',(cid,)):
            total,paid,due=repair_totals(self.db,r['id'])
            tr.insert('', 'end',iid=str(r['id']),values=(r['ticket_no'],f"{r['device_type'] or ''} {r['model'] or ''}",status_label(r['status']),money(total),money(paid),money(due),r['created_at']))
        ttk.Button(w,text='فتح أمر الصيانة',command=lambda:self.open_repair_from_history(tr,w)).pack(side='right',padx=8,pady=10)
    def open_repair_from_history(self,tr,w):
        s=tr.selection()
        if not s:return
        w.destroy()
        # Open the repair directly in a focused detail window.
        rid=int(s[0])
        self.open_repair_detail(rid)
    def open_repair_detail(self,rid):
        old=self.selected(self.rt) if hasattr(self,'rt') else None
        if old==rid:self.repair_detail();return
        # Detail logic is shared by temporarily selecting the repair when the list exists.
        if hasattr(self,'rt') and self.rt.exists(str(rid)):
            self.rt.selection_set(str(rid)); self.rt.focus(str(rid)); self.repair_detail()
        else:
            messagebox.showinfo('معلومة','افتح شاشة استلام وصيانة ثم اختر الأمر لعرض التفاصيل.')

    def delete_customer(self):
        cid=self.selected(self.ct)
        if cid and messagebox.askyesno('تأكيد','حذف العميل؟'):
            try:self.db.execute('DELETE FROM customers WHERE id=?',(cid,));self.load_customers()
            except sqlite3.IntegrityError:messagebox.showerror('خطأ','لا يمكن حذف عميل مرتبط بأوامر صيانة')
    # Technicians
    def tech_page(self):
        self.clear();self.title('الفنيون',('إضافة فني',self.add_tech));self.tt=self.tree(self.body,[('id','ID',60),('name','الفني',180),('phone','الهاتف',140),('specialty','التخصص',220),('salary','المرتب',110),('active','نشط',80)]);
        for x in self.db.many('SELECT * FROM technicians ORDER BY id DESC'):self.tt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['name'],x['phone'] or '',x['specialty'] or '',money(x['salary']), 'نعم' if x['active'] else 'لا'))
        b=ttk.Frame(self.body);b.pack(fill='x',pady=8);ttk.Button(b,text='تعديل',command=self.edit_tech).pack(side='right');ttk.Button(b,text='تعطيل',command=self.delete_tech).pack(side='right')
    def add_tech(self):
        d=self.dialog('إضافة فني',[('name','الاسم','text',None),('phone','الهاتف','text',None),('specialty','التخصص','text',None),('salary','المرتب','text',None)],size='520x350')
        if d and d['name']:self.db.execute('INSERT INTO technicians(name,phone,specialty,salary,created_at) VALUES(?,?,?,?,?)',(d['name'],d['phone'],d['specialty'],float(d['salary'] or 0),now()));self.tech_page()
    def edit_tech(self):
        tid=self.selected(self.tt)
        if not tid:return
        r=self.db.one('SELECT * FROM technicians WHERE id=?',(tid,));d=self.dialog('تعديل فني',[('name','الاسم','text',None),('phone','الهاتف','text',None),('specialty','التخصص','text',None),('salary','المرتب','text',None)],dict(r),'520x350')
        if d:self.db.execute('UPDATE technicians SET name=?,phone=?,specialty=?,salary=? WHERE id=?',(d['name'],d['phone'],d['specialty'],float(d['salary'] or 0),tid));self.tech_page()
    def delete_tech(self):
        tid=self.selected(self.tt)
        if tid:self.db.execute('UPDATE technicians SET active=0 WHERE id=?',(tid,));self.tech_page()
    # Parts
    def parts_page(self):
        self.clear();self.title('المخزن وقطع الغيار',('إضافة صنف',self.add_part));self.pt=self.tree(self.body,[('id','ID',55),('sku','SKU',100),('name','الصنف',230),('category','التصنيف',150),('supplier','المورد',160),('qty','الكمية',90),('min','الحد الأدنى',100),('purchase','شراء',100),('sale','بيع',100)]);
        for x in self.db.many('SELECT * FROM parts ORDER BY id DESC'):self.pt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['sku'] or '',x['name'],x['category'] or '',x['supplier'] or '',x['qty'],x['min_qty'],money(x['purchase_price']),money(x['sale_price'])))
        b=ttk.Frame(self.body);b.pack(fill='x',pady=8);ttk.Button(b,text='تعديل',command=self.edit_part).pack(side='right');ttk.Button(b,text='توريد',command=lambda:self.stock_move('in')).pack(side='right');ttk.Button(b,text='صرف',command=lambda:self.stock_move('out')).pack(side='right');ttk.Button(b,text='حذف',command=self.delete_part).pack(side='right')
    def add_part(self):
        d=self.dialog('إضافة صنف',[('sku','SKU','text',None),('name','اسم الصنف','text',None),('category','التصنيف','text',None),('supplier','المورد','text',None),('qty','الكمية الابتدائية','text',None),('min_qty','حد إعادة الطلب','text',None),('purchase_price','سعر الشراء','text',None),('sale_price','سعر البيع','text',None)],size='560x560')
        if d and d['name']:self.db.execute('INSERT INTO parts(sku,name,category,supplier,qty,min_qty,purchase_price,sale_price,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(d['sku'],d['name'],d['category'],d['supplier'],float(d['qty'] or 0),float(d['min_qty'] or 0),float(d['purchase_price'] or 0),float(d['sale_price'] or 0),now()));self.parts_page()
    def edit_part(self):
        pid=self.selected(self.pt)
        if not pid:return
        r=self.db.one('SELECT * FROM parts WHERE id=?',(pid,));d=self.dialog('تعديل صنف',[('sku','SKU','text',None),('name','اسم الصنف','text',None),('category','التصنيف','text',None),('supplier','المورد','text',None),('min_qty','حد إعادة الطلب','text',None),('purchase_price','سعر الشراء','text',None),('sale_price','سعر البيع','text',None)],dict(r),'560x500')
        if d:self.db.execute('UPDATE parts SET sku=?,name=?,category=?,supplier=?,min_qty=?,purchase_price=?,sale_price=? WHERE id=?',(d['sku'],d['name'],d['category'],d['supplier'],float(d['min_qty'] or 0),float(d['purchase_price'] or 0),float(d['sale_price'] or 0),pid));self.parts_page()
    def stock_move(self,typ):
        pid=self.selected(self.pt)
        if not pid:return
        p=self.db.one('SELECT * FROM parts WHERE id=?',(pid,));d=self.dialog('حركة مخزن',[('qty','الكمية','text',None),('unit_price','السعر','text',None),('reference','المرجع / المورد','text',None)],{'unit_price':str(p['purchase_price'] if typ=='in' else p['sale_price'])},'520x320')
        if not d:return
        q=float(d['qty'] or 0); sign=1 if typ=='in' else -1
        if q<=0 or (sign<0 and q>p['qty']):messagebox.showerror('خطأ','الكمية غير متاحة');return
        self.db.execute('UPDATE parts SET qty=qty+? WHERE id=?',(sign*q,pid));self.db.execute('INSERT INTO stock_moves(part_id,type,qty,unit_price,reference,created_at) VALUES(?,?,?,?,?,?)',(pid,typ,q,float(d['unit_price'] or 0),d['reference'],now()));self.parts_page()
    def delete_part(self):
        pid=self.selected(self.pt)
        if pid and messagebox.askyesno('تأكيد','حذف الصنف؟'):
            try:self.db.execute('DELETE FROM parts WHERE id=?',(pid,));self.parts_page()
            except sqlite3.IntegrityError:messagebox.showerror('خطأ','الصنف مستخدم في أوامر صيانة')
    # Finance
    def finance_page(self):
        self.clear();self.title('الحسابات',('إضافة مصروف',self.add_expense));rev=self.db.one('SELECT COALESCE(SUM(amount),0)n FROM payments')['n'];exp=self.db.one('SELECT COALESCE(SUM(amount),0)n FROM expenses')['n'];parts_cost=self.db.one('SELECT COALESCE(SUM(qty*unit_price),0)n FROM repair_parts')['n'];self.cards([('إجمالي التحصيل',money(rev)),('المصروفات',money(exp)),('تكلفة قطع الغيار',money(parts_cost)),('صافي الحركة',money(rev-exp))])
        nb=ttk.Notebook(self.body);nb.pack(fill='both',expand=True); p=ttk.Frame(nb,padding=5);nb.add(p,text='المصروفات');self.et=self.tree(p,[('id','ID',60),('title','البيان',240),('amount','المبلغ',120),('category','التصنيف',150),('date','التاريخ',170)]);
        for x in self.db.many('SELECT * FROM expenses ORDER BY id DESC'):self.et.insert('', 'end',values=(x['id'],x['title'],money(x['amount']),x['category'] or '',x['created_at']))
        pay=ttk.Frame(nb,padding=5);nb.add(pay,text='المدفوعات');pt=self.tree(pay,[('id','ID',60),('ticket','الأمر',110),('customer','العميل',180),('amount','المبلغ',110),('method','الطريقة',110),('date','التاريخ',170)])
        for x in self.db.many('SELECT p.*,r.ticket_no,c.name FROM payments p LEFT JOIN repairs r ON r.id=p.repair_id LEFT JOIN customers c ON c.id=p.customer_id ORDER BY p.id DESC'):pt.insert('', 'end',values=(x['id'],x['ticket_no'] or '-',x['name'] or '-',money(x['amount']),x['method'],x['created_at']))
    def add_expense(self):
        d=self.dialog('إضافة مصروف',[('title','البيان','text',None),('amount','المبلغ','text',None),('category','التصنيف','text',None),('note','ملاحظات','multi',None)],size='520x400')
        if d and d['title']:self.db.execute('INSERT INTO expenses(title,amount,category,note,created_at) VALUES(?,?,?,?,?)',(d['title'],float(d['amount'] or 0),d['category'],d['note'],now()));self.finance_page()
    # Reports
    def reports_page(self):
        self.clear();self.title('التقارير')
        today=datetime.date.today().isoformat(); rev=self.db.one("SELECT COALESCE(SUM(amount),0)n FROM payments WHERE date(created_at)=date('now','localtime')")['n'];exp=self.db.one("SELECT COALESCE(SUM(amount),0)n FROM expenses WHERE date(created_at)=date('now','localtime')")['n']; rec=self.db.one("SELECT COUNT(*)n FROM repairs WHERE date(created_at)=date('now','localtime')")['n'];delv=self.db.one("SELECT COUNT(*)n FROM repairs WHERE status='delivered' AND date(delivered_at)=date('now','localtime')")['n']
        self.cards([('استلام اليوم',rec),('تسليم اليوم',delv),('تحصيل اليوم',money(rev)),('مصروفات اليوم',money(exp)),('صافي اليوم',money(rev-exp))])
        b=ttk.Frame(self.body);b.pack(fill='x',pady=10)
        for txt,fn in [('تقرير الصيانة CSV',self.export_repairs),('تقرير العملاء CSV',self.export_customers),('المدفوعات CSV',self.export_payments),('المخزن CSV',self.export_parts),('تقرير مالي CSV',self.export_finance),('نسخة احتياطية',self.backup)]:ttk.Button(b,text=txt,command=fn).pack(side='right',padx=3)
        ttk.Label(self.body,text='الأجهزة المتأخرة / الجاهزة',font=('Tahoma',13,'bold')).pack(anchor='e',pady=10);tr=self.tree(self.body,[('ticket','الأمر',100),('customer','العميل',170),('device','الجهاز',180),('status','الحالة',150),('tech','الفني',140),('date','التاريخ',160)])
        for x in self.db.many("SELECT r.ticket_no,c.name customer,r.device_type,r.model,r.status,t.name tech,r.created_at FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id WHERE r.status NOT IN ('delivered','cancelled') ORDER BY r.id DESC"):tr.insert('', 'end',values=(x['ticket_no'],x['customer'],f"{x['device_type'] or ''} {x['model'] or ''}",status_label(x['status']),x['tech'] or '',x['created_at']))
    def export_query(self,q,name):
        p=filedialog.asksaveasfilename(defaultextension='.csv',initialfile=name); 
        if not p:return
        rows=self.db.many(q)
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(rows[0].keys() if rows else []);[w.writerow(list(x)) for x in rows]
        messagebox.showinfo('تم','تم التصدير')
    def export_repairs(self):self.export_query("SELECT r.*,c.name customer,c.phone,t.name technician FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id ORDER BY r.id DESC",'repairs.csv')
    def export_customers(self):self.export_query('SELECT * FROM customers ORDER BY id DESC','customers.csv')
    def export_payments(self):self.export_query('SELECT * FROM payments ORDER BY id DESC','payments.csv')
    def export_parts(self):self.export_query('SELECT * FROM parts ORDER BY id DESC','parts.csv')
    def export_finance(self):self.export_query("SELECT 'payment' type,amount,method,note,created_at FROM payments UNION ALL SELECT 'expense',amount,category,note,created_at FROM expenses ORDER BY created_at DESC",'finance.csv')
    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension='.db',initialfile=f'ARAB_SOFT_backup_{datetime.date.today()}.db');
        if p:self.db.backup(p);messagebox.showinfo('تم','تم حفظ النسخة الاحتياطية')
    # Settings/users/custom fields
    def settings_page(self):
        self.clear();self.title('الإعدادات',('المستخدمون',self.users_page));f=ttk.Frame(self.body,padding=20);f.pack(fill='x'); entries={}
        settings=[('shop_name','اسم المركز'),('shop_phone','الهاتف'),('shop_address','العنوان'),('currency','العملة'),('warranty_default','الضمان الافتراضي بالأيام'),('receipt_footer','نص أسفل الإيصال')]
        for i,(k,l) in enumerate(settings):ttk.Label(f,text=l).grid(row=i,column=1,sticky='e',pady=7);e=entry(f,60);e.grid(row=i,column=0,padx=10);e.insert(0,self.setting(k));entries[k]=e
        def save():
            for k,e in entries.items():self.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,e.get()))
            self.shop.set(self.setting('shop_name'));messagebox.showinfo('تم','تم الحفظ')
        ttk.Button(f,text='حفظ الإعدادات',command=save).grid(row=7,column=0,pady=12);ttk.Button(f,text='الحقول المخصصة',command=self.custom_fields_page).grid(row=7,column=1,pady=12); ttk.Button(f,text='تغيير كلمة المرور',command=self.change_my_password).grid(row=8,column=0,pady=8)
    def change_my_password(self):
        d=self.dialog('تغيير كلمة المرور',[('old','كلمة المرور الحالية','text',None),('new','كلمة المرور الجديدة','text',None),('confirm','تأكيد كلمة المرور','text',None)],size='520x320')
        if not d:return
        u=self.db.one('SELECT * FROM users WHERE id=?',(self.user['id'],))
        if not verify_password(d['old'],u['salt'],u['password_hash']):
            messagebox.showerror('خطأ','كلمة المرور الحالية غير صحيحة');return
        if len(d['new'])<6 or d['new']!=d['confirm']:
            messagebox.showerror('خطأ','كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل ومتطابقة');return
        salt,h=hash_password(d['new']);self.db.execute('UPDATE users SET salt=?,password_hash=? WHERE id=?',(salt,h,self.user['id']))
        messagebox.showinfo('تم','تم تغيير كلمة المرور بنجاح')

    def users_page(self):
        if not self.can('manager'):return
        w=tk.Toplevel(self.root);w.title('إدارة المستخدمين');w.geometry('850x520');tr=self.tree(w,[('id','ID',60),('username','المستخدم',180),('email','البريد',220),('role','الصلاحية',120),('active','نشط',70),('date','التاريخ',160)]);
        def load():
            for i in tr.get_children():tr.delete(i)
            for x in self.db.many('SELECT * FROM users ORDER BY id'):tr.insert('', 'end',iid=str(x['id']),values=(x['id'],x['username'],x['email'] or '',x['role'],x['active'],x['created_at']))
        def add():
            d=self.dialog('مستخدم جديد',[('username','اسم المستخدم','text',None),('email','البريد','text',None),('password','كلمة المرور','text',None),('role','الصلاحية','combo',['admin','manager','employee','technician'])],size='520x380')
            if not d:return
            salt,h=hash_password(d['password']);
            try:self.db.execute('INSERT INTO users(username,email,salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(d['username'],d['email'],salt,h,d['role'] or 'employee',now()));load()
            except sqlite3.IntegrityError:messagebox.showerror('خطأ','اسم المستخدم موجود')
        def toggle():
            s=tr.selection();
            if s:self.db.execute('UPDATE users SET active=1-active WHERE id=?',(int(s[0]),));load()
        ttk.Button(w,text='إضافة مستخدم',command=add).pack(side='right',pady=8,padx=5);ttk.Button(w,text='تفعيل/تعطيل',command=toggle).pack(side='right',pady=8);load()
    def custom_fields_page(self):
        w=tk.Toplevel(self.root);w.title('الحقول المخصصة');w.geometry('600x450');tr=self.tree(w,[('id','ID',70),('name','اسم الحقل',350)]);
        def load():
            for i in tr.get_children():tr.delete(i)
            for x in self.db.many('SELECT * FROM custom_fields ORDER BY id'):tr.insert('', 'end',iid=str(x['id']),values=(x['id'],x['name']))
        def add():
            d=self.dialog('حقل جديد',[('name','اسم الحقل','text',None)],size='450x220')
            if d and d['name']:
                try:self.db.execute('INSERT INTO custom_fields(name) VALUES(?)',(d['name'],));load()
                except sqlite3.IntegrityError:messagebox.showerror('خطأ','اسم الحقل موجود')
        def delete():
            s=tr.selection();
            if s:self.db.execute('DELETE FROM custom_fields WHERE id=?',(int(s[0]),));load()
        ttk.Button(w,text='إضافة',command=add).pack(side='right',pady=8);ttk.Button(w,text='حذف',command=delete).pack(side='right',pady=8);load()
    # Printing
    def pdf_font(self):
        candidates=['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf','C:/Windows/Fonts/tahoma.ttf']
        for p in candidates:
            if os.path.exists(p):
                try:pdfmetrics.registerFont(TTFont('ArabSoftFont',p));return 'ArabSoftFont'
                except:pass
        return 'Helvetica'
    def print_receipt(self,kind,rid=None):
        if rid is None:rid=self.selected(self.rt)
        if not rid:return
        if not PDF_OK:messagebox.showerror('خطأ','مكتبة PDF غير مثبتة');return
        r=self.db.one('''SELECT r.*,c.name customer,c.phone,c.address,t.name tech FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id WHERE r.id=?''',(rid,));total,paid,due=repair_totals(self.db,rid)
        out=filedialog.asksaveasfilename(defaultextension='.pdf',initialfile=f"{r['ticket_no']}_{kind}.pdf")
        if not out:return
        font=self.pdf_font(); c=canvas.Canvas(out,pagesize=A4);W,H=A4
        c.setFont(font,16);c.drawRightString(W-45,H-50,self.setting('shop_name'));c.setFont(font,11);c.drawRightString(W-45,H-72,self.setting('shop_phone'));c.drawRightString(W-45,H-90,self.setting('shop_address'))
        title='إيصال استلام جهاز' if kind=='receipt' else 'إيصال تسليم جهاز';c.setFont(font,15);c.drawCentredString(W/2,H-125,title);c.setFont(font,11);y=H-155
        lines=[f"رقم الأمر: {r['ticket_no']}",f"العميل: {r['customer']}",f"الهاتف: {r['phone'] or '-'}",f"الجهاز: {r['device_type'] or ''} {r['model'] or ''}",f"IMEI: {r['imei'] or '-'}",f"Serial: {r['serial'] or '-'}",f"الملحقات: {r['accessories'] or '-'}",f"العطل: {r['customer_issue'] or '-'}",f"حالة الجهاز: {r['condition'] or '-'}",f"الفني: {r['tech'] or '-'}",f"الإجمالي: {money(total)} {self.setting('currency')}",f"المدفوع: {money(paid)} {self.setting('currency')}",f"المتبقي: {money(due)} {self.setting('currency')}"]
        for line in lines:c.drawRightString(W-45,y,line);y-=25
        if kind=='delivery':c.drawRightString(W-45,y,f"الضمان حتى: {r['warranty_until'] or 'بدون ضمان'}");y-=25
        if QR_OK:
            qrpath=out+'.png';qrcode.make(r['ticket_no']).save(qrpath);c.drawImage(qrpath,45,H-240,width=85,height=85);os.remove(qrpath)
        c.setFont(font,9);c.drawRightString(W-45,55,self.setting('receipt_footer'));c.drawString(45,55,'ARAB SOFT');c.save();
        try:os.startfile(out)
        except Exception:
            try:subprocess.Popen(['xdg-open',out])
            except:pass
        messagebox.showinfo('تم','تم إنشاء الإيصال PDF')


def launch():
    db=DB(); root=tk.Tk();
    def logged(user):
        for w in root.winfo_children():w.destroy()
        App(root,db,user)
    Login(root,db,logged); root.mainloop()
