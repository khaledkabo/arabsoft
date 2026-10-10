import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv, os, datetime
from .db import DB, now, hash_password, verify_password
from .services import *

FONT=('Tahoma',10); TITLE=('Tahoma',18,'bold'); SMALL=('Tahoma',9)

def rtl_entry(parent, width=30):
    e=ttk.Entry(parent,width=width); e.configure(justify='right'); return e

def clear_tree(tree):
    for i in tree.get_children(): tree.delete(i)

def dialog(parent,title,fields,initial=None):
    win=tk.Toplevel(parent); win.title(title); win.transient(parent); win.grab_set(); win.geometry('520x560')
    vals={}; initial=initial or {}
    frm=ttk.Frame(win,padding=18); frm.pack(fill='both',expand=True)
    for i,(key,label,kind) in enumerate(fields):
        ttk.Label(frm,text=label).grid(row=i,column=1,sticky='e',pady=6)
        if kind=='text': w=rtl_entry(frm,34)
        elif kind=='multiline': w=tk.Text(frm,width=34,height=4); w.configure(font=FONT)
        elif kind=='combo': w=ttk.Combobox(frm,width=31,values=label if isinstance(label,(list,tuple)) else [],state='readonly');
        else: w=rtl_entry(frm,34)
        w.grid(row=i,column=0,padx=10,pady=6)
        val=initial.get(key,'')
        if kind=='multiline': w.insert('1.0',val)
        else:
            if val: w.set(val) if hasattr(w,'set') else w.insert(0,str(val))
        vals[key]=w
    result={}
    def ok():
        for k,w in vals.items(): result[k]=w.get('1.0','end-1c') if isinstance(w,tk.Text) else w.get()
        win.destroy()
    ttk.Button(frm,text='حفظ',command=ok).grid(row=len(fields),column=0,pady=18)
    ttk.Button(frm,text='إلغاء',command=win.destroy).grid(row=len(fields),column=1,pady=18)
    win.wait_window(); return result or None

class Login:
    def __init__(self,root,db,on_login):
        self.root=root; self.db=db; self.on_login=on_login
        root.title('تسجيل الدخول - ARAB SOFT'); root.geometry('420x330'); root.resizable(False,False)
        f=ttk.Frame(root,padding=30); f.pack(fill='both',expand=True)
        ttk.Label(f,text='ARAB SOFT',font=('Tahoma',24,'bold')).pack(pady=8)
        ttk.Label(f,text='نظام إدارة الصيانة').pack(pady=3)
        self.u=rtl_entry(f,32); self.u.pack(pady=8); self.u.insert(0,'admin')
        self.p=rtl_entry(f,32); self.p.pack(pady=8); self.p.configure(show='*')
        ttk.Button(f,text='دخول',command=self.login).pack(pady=12,fill='x')
        ttk.Label(f,text='الحساب الافتراضي: admin / admin',font=SMALL).pack()
        self.p.bind('<Return>',lambda e:self.login())
    def login(self):
        r=self.db.one('SELECT * FROM users WHERE username=? AND active=1',(self.u.get().strip(),))
        if not r or not verify_password(self.p.get(),r['salt'],r['password_hash']): messagebox.showerror('خطأ','اسم المستخدم أو كلمة المرور غير صحيحة'); return
        self.on_login(r)

class App:
    def __init__(self,root,db,user):
        self.root=root; self.db=db; self.user=user; self.root.title('ARAB SOFT - نظام إدارة الصيانة'); self.root.geometry('1280x760'); self.root.minsize(1050,650)
        self.build()
    def build(self):
        self.style=ttk.Style();
        try:self.style.theme_use('clam')
        except:pass
        top=ttk.Frame(self.root,padding=10); top.pack(fill='x')
        self.shop=tk.StringVar(value=self.setting('shop_name'))
        ttk.Label(top,textvariable=self.shop,font=TITLE).pack(side='right')
        ttk.Label(top,text=f"المستخدم: {self.user['username']} ({self.user['role']})").pack(side='left')
        self.nav=ttk.Frame(self.root); self.nav.pack(fill='x',padx=10)
        tabs=[('الرئيسية',self.dashboard),('استلام وصيانة',self.repairs_page),('العملاء',self.customers_page),('الفنيون',self.tech_page),('المخزن',self.parts_page),('الحسابات',self.finance_page),('التقارير',self.reports_page),('الإعدادات',self.settings_page)]
        for t,c in tabs: ttk.Button(self.nav,text=t,command=c).pack(side='right',padx=3)
        self.body=ttk.Frame(self.root,padding=10); self.body.pack(fill='both',expand=True)
        self.dashboard()
    def setting(self,k):
        r=self.db.one('SELECT value FROM settings WHERE key=?',(k,)); return r['value'] if r else ''
    def clear(self):
        for w in self.body.winfo_children(): w.destroy()
    def page_title(self,t,action=None):
        bar=ttk.Frame(self.body); bar.pack(fill='x',pady=(0,10)); ttk.Label(bar,text=t,font=TITLE).pack(side='right')
        if action: ttk.Button(bar,text=action[0],command=action[1]).pack(side='left')
    def cards(self,items):
        f=ttk.Frame(self.body); f.pack(fill='x',pady=8)
        for title,value in items:
            c=ttk.LabelFrame(f,text=title,padding=15); c.pack(side='right',fill='x',expand=True,padx=5); ttk.Label(c,text=str(value),font=('Tahoma',20,'bold')).pack()
    def dashboard(self):
        self.clear(); self.page_title('لوحة التحكم',('تحديث',self.dashboard))
        total=self.db.one('SELECT COUNT(*) n FROM repairs')['n']; ready=self.db.one("SELECT COUNT(*) n FROM repairs WHERE status='ready'")['n']; active=self.db.one("SELECT COUNT(*) n FROM repairs WHERE status NOT IN ('delivered','cancelled')")['n'];
        revenue=self.db.one("SELECT COALESCE(SUM(amount),0) n FROM payments")['n']; expenses=self.db.one("SELECT COALESCE(SUM(amount),0) n FROM expenses")['n']
        self.cards([('إجمالي أوامر الصيانة',total),('قيد العمل',active),('جاهز للتسليم',ready),('التحصيل',f'{revenue:.2f}'),('المصروفات',f'{expenses:.2f}')])
        ttk.Label(self.body,text='آخر أوامر الصيانة',font=('Tahoma',13,'bold')).pack(anchor='e',pady=10)
        tree=self.make_tree(self.body,[('ticket_no','رقم الأمر'),('customer','العميل'),('device','الجهاز'),('status','الحالة'),('created_at','التاريخ')])
        rows=self.db.many("SELECT r.ticket_no,c.name customer,COALESCE(r.device_type,'')||' '||COALESCE(r.model,'') device,r.status,r.created_at FROM repairs r JOIN customers c ON c.id=r.customer_id ORDER BY r.id DESC LIMIT 12")
        for x in rows: tree.insert('', 'end', values=(x['ticket_no'],x['customer'],x['device'],status_label(x['status']),x['created_at']))
    def make_tree(self,parent,cols):
        wrap=ttk.Frame(parent); wrap.pack(fill='both',expand=True)
        ids=[x[0] for x in cols]; tree=ttk.Treeview(wrap,columns=ids,show='headings')
        for k,label in cols: tree.heading(k,text=label); tree.column(k,width=max(110,800//len(cols)),anchor='e')
        sy=ttk.Scrollbar(wrap,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=sy.set); tree.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y'); return tree
    def repairs_page(self):
        self.clear(); self.page_title('استلام ومتابعة الأجهزة',('استلام جهاز جديد',self.add_repair))
        bar=ttk.Frame(self.body); bar.pack(fill='x',pady=4); self.search=tk.StringVar(); e=rtl_entry(bar,45); e.pack(side='right'); e.bind('<KeyRelease>',lambda ev:self.load_repairs()); ttk.Label(bar,text='بحث:').pack(side='right',padx=6)
        self.rt=self.make_tree(self.body,[('id','ID'),('ticket','رقم الأمر'),('customer','العميل'),('phone','الهاتف'),('device','الجهاز'),('issue','العطل'),('status','الحالة'),('tech','الفني'),('total','الإجمالي'),('paid','المدفوع'),('due','المتبقي'),('created','التاريخ')])
        self.rt.bind('<Double-1>',lambda e:self.edit_repair())
        buttons=ttk.Frame(self.body); buttons.pack(fill='x',pady=8)
        for txt,fn in [('تعديل',self.edit_repair),('تغيير الحالة',self.change_status),('تسجيل دفعة',self.take_payment),('تسليم الجهاز',self.deliver_repair),('حذف',self.delete_repair),('تصدير CSV',self.export_repairs)]: ttk.Button(buttons,text=txt,command=fn).pack(side='right',padx=3)
        self.load_repairs()
    def load_repairs(self):
        clear_tree(self.rt); q=getattr(self,'search',tk.StringVar()).get().strip(); like=f'%{q}%'
        rows=self.db.many('''SELECT r.*,c.name customer,c.phone,t.name tech FROM repairs r JOIN customers c ON c.id=r.customer_id LEFT JOIN technicians t ON t.id=r.technician_id WHERE r.ticket_no LIKE ? OR c.name LIKE ? OR c.phone LIKE ? OR r.imei LIKE ? OR r.serial LIKE ? ORDER BY r.id DESC''',(like,like,like,like,like))
        for r in rows:
            total,paid,due=repair_totals(self.db,r['id']); self.rt.insert('', 'end', values=(r['id'],r['ticket_no'],r['customer'],r['phone'] or '',f"{r['device_type'] or ''} {r['model'] or ''}",r['customer_issue'] or '',status_label(r['status']),r['tech'] or '',f'{total:.2f}',f'{paid:.2f}',f'{due:.2f}',r['created_at']),iid=str(r['id']))
    def selected_id(self,tree):
        s=tree.selection(); return int(s[0]) if s else None
    def add_repair(self):
        customers=self.db.many('SELECT id,name,phone FROM customers ORDER BY name'); techs=self.db.many('SELECT id,name FROM technicians WHERE active=1 ORDER BY name')
        fields=[('customer','العميل','combo'),('phone','الهاتف','text'),('device_type','نوع الجهاز','text'),('model','الموديل','text'),('imei','IMEI','text'),('serial','Serial','text'),('color','اللون','text'),('accessories','الملحقات','text'),('condition','حالة الجهاز','multiline'),('issue','عطل العميل','multiline'),('priority','الأولوية','combo'),('technician','الفني','combo'),('estimated','التكلفة المتوقعة','text'),('labor','المصنعية','text'),('warranty','ضمان بالأيام','text'),('notes','ملاحظات','multiline')]
        # custom dialog combo values
        win=tk.Toplevel(self.root); win.title('استلام جهاز'); win.geometry('600x760'); win.grab_set(); f=ttk.Frame(win,padding=18); f.pack(fill='both',expand=True); widgets={}
        customer_values=[f"{x['id']} | {x['name']} | {x['phone'] or ''}" for x in customers]; tech_values=[f"{x['id']} | {x['name']}" for x in techs]
        for i,(k,l,kind) in enumerate(fields):
            ttk.Label(f,text=l).grid(row=i,column=1,sticky='e',pady=4); w=tk.Text(f,width=34,height=3,font=FONT) if kind=='multiline' else (ttk.Combobox(f,width=32,values=(customer_values if k=='customer' else tech_values if k=='technician' else [x[1] for x in PRIORITIES]),state='readonly') if kind=='combo' else rtl_entry(f,34)); w.grid(row=i,column=0,padx=8,pady=4); widgets[k]=w
        def save():
            def get(k):
                w=widgets[k]; return w.get('1.0','end-1c').strip() if isinstance(w,tk.Text) else w.get().strip()
            cv=get('customer');
            if not cv: messagebox.showerror('خطأ','اختر العميل'); return
            cid=int(cv.split('|')[0]); tv=get('technician'); tid=int(tv.split('|')[0]) if tv else None; pri=get('priority') or 'عادي'; pkey=next((x[0] for x in PRIORITIES if x[1]==pri),'normal')
            vals=(next_ticket(self.db),cid,get('device_type'),get('model'),get('imei'),get('serial'),get('color'),get('accessories'),get('condition'),get('issue'),tid,pkey,float(get('estimated') or 0),float(get('labor') or 0),int(get('warranty') or self.setting('warranty_default') or 0),get('notes'),now(),now())
            self.db.execute('''INSERT INTO repairs(ticket_no,customer_id,device_type,model,imei,serial,color,accessories,condition,customer_issue,technician_id,priority,estimated_cost,labor,warranty_days,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',vals); rid=self.db.conn.execute('SELECT last_insert_rowid()').fetchone()[0]; log(self.db,self.user['id'],'create','repair',rid,vals[0]); win.destroy(); self.load_repairs(); messagebox.showinfo('تم','تم استلام الجهاز بنجاح')
        ttk.Button(f,text='حفظ الاستلام',command=save).grid(row=len(fields),column=0,pady=14); ttk.Button(f,text='إلغاء',command=win.destroy).grid(row=len(fields),column=1,pady=14)
    def edit_repair(self):
        rid=self.selected_id(self.rt)
        if not rid:return
        r=self.db.one('SELECT * FROM repairs WHERE id=?',(rid,)); customers=self.db.many('SELECT id,name FROM customers ORDER BY name'); techs=self.db.many('SELECT id,name FROM technicians WHERE active=1')
        flds=[('customer','العميل','text'),('device_type','نوع الجهاز','text'),('model','الموديل','text'),('imei','IMEI','text'),('serial','Serial','text'),('color','اللون','text'),('accessories','الملحقات','text'),('condition','الحالة الخارجية','multiline'),('customer_issue','عطل العميل','multiline'),('technical_diagnosis','التشخيص الفني','multiline'),('estimated_cost','التكلفة المتوقعة','text'),('labor','المصنعية','text'),('discount','الخصم','text'),('warranty_days','ضمان بالأيام','text'),('notes','ملاحظات','multiline')]
        initial=dict(r); initial['customer']=self.db.one('SELECT name FROM customers WHERE id=?',(r['customer_id'],))['name']
        vals=dialog(self.root,'تعديل أمر الصيانة',flds,initial)
        if not vals:return
        self.db.execute('''UPDATE repairs SET device_type=?,model=?,imei=?,serial=?,color=?,accessories=?,condition=?,customer_issue=?,technical_diagnosis=?,estimated_cost=?,labor=?,discount=?,warranty_days=?,notes=?,updated_at=? WHERE id=?''',(vals['device_type'],vals['model'],vals['imei'],vals['serial'],vals['color'],vals['accessories'],vals['condition'],vals['customer_issue'],vals['technical_diagnosis'],float(vals['estimated_cost'] or 0),float(vals['labor'] or 0),float(vals['discount'] or 0),int(vals['warranty_days'] or 0),vals['notes'],now(),rid)); log(self.db,self.user['id'],'update','repair',rid); self.load_repairs()
    def change_status(self):
        rid=self.selected_id(self.rt)
        if not rid:return
        labels=[x[1] for x in STATUSES]; d=dialog(self.root,'تغيير الحالة',[('status',labels,'combo')],{'status':status_label(self.db.one('SELECT status FROM repairs WHERE id=?',(rid,))['status'])})
        if d:
            key=next((x[0] for x in STATUSES if x[1]==d['status']),d['status']); self.db.execute('UPDATE repairs SET status=?,updated_at=? WHERE id=?',(key,now(),rid)); log(self.db,self.user['id'],'status','repair',rid,key); self.load_repairs()
    def take_payment(self):
        rid=self.selected_id(self.rt)
        if not rid:return
        r=self.db.one('SELECT customer_id FROM repairs WHERE id=?',(rid,)); total,paid,due=repair_totals(self.db,rid)
        d=dialog(self.root,'تسجيل دفعة',[('amount','المبلغ','text'),('method',PAY_METHODS,'combo'),('note','ملاحظات','text')])
        if d:
            amount=float(d['amount'] or 0); self.db.execute('INSERT INTO payments(repair_id,customer_id,amount,method,note,created_at) VALUES(?,?,?,?,?,?)',(rid,r['customer_id'],amount,d['method'],d['note'],now())); self.db.execute('UPDATE repairs SET paid=paid+?,updated_at=? WHERE id=?',(amount,now(),rid)); self.load_repairs()
    def deliver_repair(self):
        rid=self.selected_id(self.rt)
        if not rid:return
        total,paid,due=repair_totals(self.db,rid)
        if due>0.009 and not messagebox.askyesno('متبقي','يوجد مبلغ متبقي. هل تريد التسليم رغم ذلك؟'):return
        self.db.execute("UPDATE repairs SET status='delivered',delivered_at=?,updated_at=? WHERE id=?",(now(),now(),rid)); log(self.db,self.user['id'],'deliver','repair',rid); self.load_repairs()
    def delete_repair(self):
        rid=self.selected_id(self.rt)
        if rid and messagebox.askyesno('تأكيد','حذف أمر الصيانة؟'): self.db.execute('DELETE FROM repairs WHERE id=?',(rid,)); log(self.db,self.user['id'],'delete','repair',rid); self.load_repairs()
    def export_repairs(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='repairs.csv')
        if not path:return
        rows=self.db.many('SELECT r.*,c.name customer,c.phone FROM repairs r JOIN customers c ON c.id=r.customer_id ORDER BY r.id DESC')
        with open(path,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f); w.writerow(rows[0].keys() if rows else ['id']); [w.writerow(list(x)) for x in rows]
        messagebox.showinfo('تم',f'تم التصدير إلى {path}')
    def customers_page(self):
        self.clear(); self.page_title('العملاء',('إضافة عميل',self.add_customer)); self.ct=self.make_tree(self.body,[('id','ID'),('name','الاسم'),('phone','الهاتف'),('phone2','هاتف إضافي'),('address','العنوان'),('count','الأجهزة'),('created','تاريخ الإضافة')]); self.load_customers(); b=ttk.Frame(self.body); b.pack(fill='x',pady=8); ttk.Button(b,text='تعديل',command=self.edit_customer).pack(side='right'); ttk.Button(b,text='حذف',command=self.delete_customer).pack(side='right')
    def load_customers(self):
        clear_tree(self.ct); rows=self.db.many('SELECT c.*,COUNT(r.id) count FROM customers c LEFT JOIN repairs r ON r.customer_id=c.id GROUP BY c.id ORDER BY c.id DESC'); [self.ct.insert('', 'end',iid=str(x['id']),values=(x['id'],x['name'],x['phone'] or '',x['phone2'] or '',x['address'] or '',x['count'],x['created_at'])) for x in rows]
    def add_customer(self):
        d=dialog(self.root,'إضافة عميل',[('name','اسم العميل','text'),('phone','الهاتف','text'),('phone2','هاتف إضافي','text'),('address','العنوان','text'),('notes','ملاحظات','multiline')]);
        if d and d['name']: self.db.execute('INSERT INTO customers(name,phone,phone2,address,notes,created_at) VALUES(?,?,?,?,?,?)',(d['name'],d['phone'],d['phone2'],d['address'],d['notes'],now())); self.load_customers()
    def edit_customer(self):
        cid=self.selected_id(self.ct)
        if not cid:return
        r=self.db.one('SELECT * FROM customers WHERE id=?',(cid,)); d=dialog(self.root,'تعديل عميل',[('name','اسم العميل','text'),('phone','الهاتف','text'),('phone2','هاتف إضافي','text'),('address','العنوان','text'),('notes','ملاحظات','multiline')],dict(r));
        if d:self.db.execute('UPDATE customers SET name=?,phone=?,phone2=?,address=?,notes=? WHERE id=?',(d['name'],d['phone'],d['phone2'],d['address'],d['notes'],cid)); self.load_customers()
    def delete_customer(self):
        cid=self.selected_id(self.ct)
        if cid and messagebox.askyesno('تأكيد','حذف العميل؟'):
            try:self.db.execute('DELETE FROM customers WHERE id=?',(cid,)); self.load_customers()
            except:messagebox.showerror('خطأ','لا يمكن حذف العميل المرتبط بأوامر صيانة')
    def tech_page(self):
        self.clear(); self.page_title('الفنيون',('إضافة فني',self.add_tech)); self.tt=self.make_tree(self.body,[('id','ID'),('name','الفني'),('phone','الهاتف'),('specialty','التخصص'),('salary','المرتب'),('active','نشط')]); rows=self.db.many('SELECT * FROM technicians ORDER BY id DESC'); [self.tt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['name'],x['phone'] or '',x['specialty'] or '',x['salary'], 'نعم' if x['active'] else 'لا')) for x in rows]; b=ttk.Frame(self.body); b.pack(fill='x',pady=8); ttk.Button(b,text='تعديل',command=self.edit_tech).pack(side='right'); ttk.Button(b,text='حذف',command=self.delete_tech).pack(side='right')
    def add_tech(self):
        d=dialog(self.root,'إضافة فني',[('name','اسم الفني','text'),('phone','الهاتف','text'),('specialty','التخصص','text'),('salary','المرتب','text')]);
        if d and d['name']:self.db.execute('INSERT INTO technicians(name,phone,specialty,salary,created_at) VALUES(?,?,?,?,?)',(d['name'],d['phone'],d['specialty'],float(d['salary'] or 0),now())); self.tech_page()
    def edit_tech(self):
        tid=self.selected_id(self.tt)
        if not tid:return
        r=self.db.one('SELECT * FROM technicians WHERE id=?',(tid,)); d=dialog(self.root,'تعديل فني',[('name','اسم الفني','text'),('phone','الهاتف','text'),('specialty','التخصص','text'),('salary','المرتب','text')],dict(r));
        if d:self.db.execute('UPDATE technicians SET name=?,phone=?,specialty=?,salary=? WHERE id=?',(d['name'],d['phone'],d['specialty'],float(d['salary'] or 0),tid)); self.tech_page()
    def delete_tech(self):
        tid=self.selected_id(self.tt)
        if tid and messagebox.askyesno('تأكيد','حذف الفني؟'): self.db.execute('UPDATE technicians SET active=0 WHERE id=?',(tid,)); self.tech_page()
    def parts_page(self):
        self.clear(); self.page_title('المخزن وقطع الغيار',('إضافة صنف',self.add_part)); self.pt=self.make_tree(self.body,[('id','ID'),('sku','SKU'),('name','الصنف'),('category','التصنيف'),('supplier','المورد'),('qty','الكمية'),('min','الحد الأدنى'),('purchase','شراء'),('sale','بيع')]); self.load_parts(); b=ttk.Frame(self.body); b.pack(fill='x',pady=8); ttk.Button(b,text='تعديل',command=self.edit_part).pack(side='right'); ttk.Button(b,text='توريد',command=self.stock_in).pack(side='right'); ttk.Button(b,text='صرف',command=self.stock_out).pack(side='right')
    def load_parts(self):
        clear_tree(self.pt); rows=self.db.many('SELECT * FROM parts ORDER BY id DESC'); [self.pt.insert('', 'end',iid=str(x['id']),values=(x['id'],x['sku'] or '',x['name'],x['category'] or '',x['supplier'] or '',x['qty'],x['min_qty'],x['purchase_price'],x['sale_price'])) for x in rows]
    def add_part(self):
        d=dialog(self.root,'إضافة صنف',[('sku','SKU','text'),('name','اسم الصنف','text'),('category','التصنيف','text'),('supplier','المورد','text'),('qty','الكمية','text'),('min_qty','الحد الأدنى','text'),('purchase_price','سعر الشراء','text'),('sale_price','سعر البيع','text')]);
        if d and d['name']:
            self.db.execute('INSERT INTO parts(sku,name,category,supplier,qty,min_qty,purchase_price,sale_price,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(d['sku'],d['name'],d['category'],d['supplier'],float(d['qty'] or 0),float(d['min_qty'] or 0),float(d['purchase_price'] or 0),float(d['sale_price'] or 0),now())); self.load_parts()
    def edit_part(self):
        pid=self.selected_id(self.pt)
        if not pid:return
        r=self.db.one('SELECT * FROM parts WHERE id=?',(pid,)); d=dialog(self.root,'تعديل صنف',[('sku','SKU','text'),('name','اسم الصنف','text'),('category','التصنيف','text'),('supplier','المورد','text'),('min_qty','الحد الأدنى','text'),('purchase_price','سعر الشراء','text'),('sale_price','سعر البيع','text')],dict(r));
        if d:self.db.execute('UPDATE parts SET sku=?,name=?,category=?,supplier=?,min_qty=?,purchase_price=?,sale_price=? WHERE id=?',(d['sku'],d['name'],d['category'],d['supplier'],float(d['min_qty'] or 0),float(d['purchase_price'] or 0),float(d['sale_price'] or 0),pid)); self.load_parts()
    def stock_move(self,typ):
        pid=self.selected_id(self.pt)
        if not pid:return
        d=dialog(self.root,'حركة مخزن',[('qty','الكمية','text'),('unit_price','السعر','text'),('reference','المرجع/ملاحظات','text')]);
        if d:
            q=float(d['qty'] or 0); sign=1 if typ=='in' else -1; cur=self.db.one('SELECT qty FROM parts WHERE id=?',(pid,))['qty'];
            if sign<0 and q>cur: messagebox.showerror('خطأ','الكمية غير متاحة'); return
            self.db.execute('UPDATE parts SET qty=qty+? WHERE id=?',(sign*q,pid)); self.db.execute('INSERT INTO stock_moves(part_id,type,qty,unit_price,reference,created_at) VALUES(?,?,?,?,?,?)',(pid,typ,q,float(d['unit_price'] or 0),d['reference'],now())); self.load_parts()
    def stock_in(self):self.stock_move('in')
    def stock_out(self):self.stock_move('out')
    def finance_page(self):
        self.clear(); self.page_title('الحسابات',('إضافة مصروف',self.add_expense)); rev=self.db.one('SELECT COALESCE(SUM(amount),0) x FROM payments')['x']; exp=self.db.one('SELECT COALESCE(SUM(amount),0) x FROM expenses')['x']; due=self.db.one("SELECT COALESCE(SUM((labor+discount*0)-paid),0) x FROM repairs WHERE status!='cancelled'")['x']; self.cards([('التحصيل',f'{rev:.2f}'),('المصروفات',f'{exp:.2f}'),('صافي الحركة',f'{rev-exp:.2f}')]); self.et=self.make_tree(self.body,[('id','ID'),('title','البيان'),('amount','المبلغ'),('category','التصنيف'),('date','التاريخ')]); rows=self.db.many('SELECT * FROM expenses ORDER BY id DESC'); [self.et.insert('', 'end',values=(x['id'],x['title'],x['amount'],x['category'] or '',x['created_at'])) for x in rows]
    def add_expense(self):
        d=dialog(self.root,'إضافة مصروف',[('title','البيان','text'),('amount','المبلغ','text'),('category','التصنيف','text'),('note','ملاحظات','text')]);
        if d and d['title']:self.db.execute('INSERT INTO expenses(title,amount,category,note,created_at) VALUES(?,?,?,?,?)',(d['title'],float(d['amount'] or 0),d['category'],d['note'],now())); self.finance_page()
    def reports_page(self):
        self.clear(); self.page_title('التقارير')
        items=[('أوامر الصيانة اليوم',"SELECT COUNT(*) n FROM repairs WHERE date(created_at)=date('now','localtime')"),('تم التسليم اليوم',"SELECT COUNT(*) n FROM repairs WHERE status='delivered' AND date(delivered_at)=date('now','localtime')"),('إيرادات اليوم',"SELECT COALESCE(SUM(amount),0) n FROM payments WHERE date(created_at)=date('now','localtime')"),('مصروفات اليوم',"SELECT COALESCE(SUM(amount),0) n FROM expenses WHERE date(created_at)=date('now','localtime')")]; self.cards([(a,self.db.one(q)['n']) for a,q in items]);
        f=ttk.Frame(self.body); f.pack(fill='x',pady=15); ttk.Button(f,text='تصدير العملاء CSV',command=self.export_customers).pack(side='right',padx=4); ttk.Button(f,text='تصدير المدفوعات CSV',command=self.export_payments).pack(side='right',padx=4); ttk.Button(f,text='نسخة احتياطية',command=self.backup).pack(side='right',padx=4)
    def export_customers(self):self.export_query('SELECT * FROM customers','customers.csv')
    def export_payments(self):self.export_query('SELECT * FROM payments','payments.csv')
    def export_query(self,q,name):
        p=filedialog.asksaveasfilename(defaultextension='.csv',initialfile=name); 
        if not p:return
        rows=self.db.many(q)
        with open(p,'w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f); w.writerow(rows[0].keys() if rows else []); [w.writerow(list(r)) for r in rows]
    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension='.db',initialfile='service_backup.db');
        if p:self.db.backup(p); messagebox.showinfo('تم','تم حفظ النسخة الاحتياطية')
    def settings_page(self):
        self.clear(); self.page_title('الإعدادات')
        f=ttk.Frame(self.body,padding=20); f.pack(fill='x')
        entries={}
        for i,(k,l) in enumerate([('shop_name','اسم المحل'),('shop_phone','الهاتف'),('shop_address','العنوان'),('currency','العملة'),('warranty_default','الضمان الافتراضي'),('receipt_footer','نص أسفل الإيصال')]):
            ttk.Label(f,text=l).grid(row=i,column=1,sticky='e',pady=8); e=rtl_entry(f,50); e.grid(row=i,column=0,padx=10); e.insert(0,self.setting(k)); entries[k]=e
        def save():
            for k,e in entries.items():self.db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,e.get()))
            self.shop.set(self.setting('shop_name')); messagebox.showinfo('تم','تم حفظ الإعدادات')
        ttk.Button(f,text='حفظ الإعدادات',command=save).grid(row=7,column=0,pady=15)
        ttk.Button(f,text='إدارة المستخدمين',command=self.users_page).grid(row=7,column=1,pady=15)
    def users_page(self):
        win=tk.Toplevel(self.root); win.title('المستخدمون'); win.geometry('700x450'); tree=self.make_tree(win,[('id','ID'),('username','المستخدم'),('email','البريد'),('role','الصلاحية'),('active','نشط'),('created','التاريخ')]); rows=self.db.many('SELECT * FROM users ORDER BY id'); [tree.insert('', 'end',values=(x['id'],x['username'],x['email'] or '',x['role'],x['active'],x['created_at'])) for x in rows]
        def add():
            d=dialog(win,'إضافة مستخدم',[('username','اسم المستخدم','text'),('email','البريد','text'),('password','كلمة المرور','text'),('role',['admin','manager','employee','technician'],'combo')]);
            if d and d['username'] and d['password']:
                salt,h=hash_password(d['password']);
                try:self.db.execute('INSERT INTO users(username,email,salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',(d['username'],d['email'],salt,h,d['role'] or 'employee',now())); win.destroy(); self.users_page()
                except:messagebox.showerror('خطأ','اسم المستخدم موجود')
        ttk.Button(win,text='إضافة مستخدم',command=add).pack(pady=8)
