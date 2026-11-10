"""SQLite persistence and atomic, collision-safe demo restaurant reservations."""
from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_DURATION_MIN = 90

class DomainError(ValueError):
    pass


def now_ist() -> datetime:
    return datetime.now(IST)


def validate_slot(date: str, time: str, party_size: int):
    try:
        dt = datetime.fromisoformat(f"{date}T{time}")
    except ValueError:
        raise DomainError("Use a valid date (YYYY-MM-DD) and time (HH:MM).")
    if dt.strftime("%Y-%m-%d") != date or dt.strftime("%H:%M") != time:
        raise DomainError("Use a valid date (YYYY-MM-DD) and time (HH:MM).")
    if party_size < 1 or party_size > 8:
        raise DomainError("This demo supports parties of 1–8.")
    if dt.replace(tzinfo=IST) < now_ist() - timedelta(minutes=1):
        raise DomainError("Choose a future reservation time.")
    if not (11 <= dt.hour <= 22):
        raise DomainError("Reservations are available between 11:00 and 22:00.")
    return dt

class Storage:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def conn(self, immediate: bool = False):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        with sqlite3.connect(self.path) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript('''
            CREATE TABLE IF NOT EXISTS tables (
              id TEXT PRIMARY KEY, seats INTEGER NOT NULL CHECK (seats>=1),
              floor_status TEXT NOT NULL DEFAULT 'ready' CHECK(floor_status IN ('ready','occupied','dirty','blocked'))
            );
            CREATE TABLE IF NOT EXISTS reservations (
              id TEXT PRIMARY KEY, table_id TEXT NOT NULL REFERENCES tables(id),
              guest_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', party_size INTEGER NOT NULL,
              booking_date TEXT NOT NULL, booking_time TEXT NOT NULL,
              duration_min INTEGER NOT NULL DEFAULT 90,
              status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','cancelled')),
              source TEXT NOT NULL DEFAULT 'manager', notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reservations_date ON reservations(booking_date,status);
            CREATE TABLE IF NOT EXISTS calls (
              id TEXT PRIMARY KEY, source TEXT NOT NULL, caller TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
              last_intent TEXT NOT NULL DEFAULT '', pending_json TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS turns (
              id TEXT PRIMARY KEY, call_id TEXT NOT NULL REFERENCES calls(id),
              role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, call_id TEXT NOT NULL DEFAULT '', title TEXT NOT NULL,
              notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS menu (
              id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '', price_inr INTEGER NOT NULL, available INTEGER NOT NULL DEFAULT 1
            );
            ''')
            if not c.execute("SELECT 1 FROM tables LIMIT 1").fetchone():
                c.executemany("INSERT INTO tables(id,seats) VALUES(?,?)", [
                    ("T01",2),("T02",2),("T03",4),("T04",4),
                    ("T05",4),("T06",6),("T07",6),("T08",8)
                ])
            if not c.execute("SELECT 1 FROM menu LIMIT 1").fetchone():
                c.executemany("INSERT INTO menu(category,name,description,price_inr) VALUES(?,?,?,?)", [
                    ("Starters","Paneer Tikka","Tandoor roasted, mint chutney",320),
                    ("Starters","Crispy Corn","Chilli, lime and coriander",240),
                    ("Mains","Butter Chicken","Rich tomato gravy",420),
                    ("Mains","Dal Makhani","Slow cooked black lentils",310),
                    ("Mains","Veg Biryani","Saffron rice and raita",330),
                    ("Breads","Garlic Naan","Tandoor baked",95),
                    ("Drinks","Fresh Lime Soda","Sweet or salted",120),
                    ("Dessert","Gulab Jamun","Two pieces",150)
                ])

    @staticmethod
    def rows(cursor):
        return [dict(r) for r in cursor.fetchall()]

    def list_tables(self):
        with self.conn() as c:
            return self.rows(c.execute("SELECT * FROM tables ORDER BY id"))

    def update_table(self, table_id: str, status: str):
        if status not in {"ready","occupied","dirty","blocked"}:
            raise DomainError("Invalid table status")
        with self.conn(True) as c:
            cur=c.execute("UPDATE tables SET floor_status=? WHERE id=?", (status,table_id))
            if cur.rowcount != 1: raise DomainError("Table not found")
        return {"id": table_id, "floor_status": status}

    def _free_tables(self,c,dt: datetime,party_size: int,ignore_id: str=''):
        start=dt.isoformat(timespec="minutes")
        end=(dt+timedelta(minutes=DEFAULT_DURATION_MIN)).isoformat(timespec="minutes")
        rows=self.rows(c.execute('''
          SELECT t.* FROM tables t WHERE t.seats>=?
           AND t.floor_status NOT IN ('blocked')
           AND NOT EXISTS (
              SELECT 1 FROM reservations r WHERE r.table_id=t.id AND r.status='confirmed'
              AND r.id != ?
              AND (r.booking_date || 'T' || r.booking_time) < ?
              AND datetime(r.booking_date || 'T' || r.booking_time, '+' || r.duration_min || ' minutes') > datetime(?)
           ) ORDER BY t.seats,t.id
        ''',(party_size,ignore_id,end,start)))
        # 'occupied'/'dirty' prevents immediate booking; for future bookings a manager may prepare it.
        if dt.date() == now_ist().date() and dt <= now_ist().replace(tzinfo=None)+timedelta(minutes=90):
            rows=[r for r in rows if r['floor_status']=='ready']
        return rows

    def availability(self, date: str,time: str,party_size: int):
        dt=validate_slot(date,time,party_size)
        with self.conn() as c:
            return self._free_tables(c,dt,party_size)

    def create_reservation(self, *,guest_name: str,party_size: int,date: str,time: str, phone: str='',source: str='manager',notes: str='',table_id: str|None=None):
        dt=validate_slot(date,time,party_size)
        if len(guest_name.strip())<2: raise DomainError('Guest name is required.')
        if len(notes)>500: raise DomainError('Notes too long')
        with self.conn(True) as c:
            free=self._free_tables(c,dt,party_size)
            if table_id:
                selected=c.execute('SELECT * FROM tables WHERE id=?',(table_id,)).fetchone()
                if selected is None: raise DomainError('Selected table was not found.')
                if selected['seats']<party_size: raise DomainError('Selected table cannot seat this party.')
                free=[table for table in free if table['id']==table_id]
                if not free: raise DomainError('Selected table is not available for this time.')
            if not free: raise DomainError('No suitable table remains available for this time.')
            rid='RES-'+uuid.uuid4().hex[:9].upper()
            c.execute('''INSERT INTO reservations (id,table_id,guest_name,phone,party_size,booking_date,booking_time,duration_min,status,source,notes,created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',(
              rid,free[0]['id'],guest_name.strip(),phone[:50],party_size,date,time,
              DEFAULT_DURATION_MIN,'confirmed',source,notes,now_ist().isoformat()))
            return dict(c.execute('SELECT * FROM reservations WHERE id=?',(rid,)).fetchone())

    def list_reservations(self,date: str|None=None):
        with self.conn() as c:
            if date:
                return self.rows(c.execute("SELECT * FROM reservations WHERE booking_date=? ORDER BY booking_time,created_at",(date,)))
            return self.rows(c.execute("SELECT * FROM reservations ORDER BY booking_date DESC,booking_time DESC LIMIT 300"))

    def list_reservations_range(self,start_date: str,end_date: str):
        try:
            start=datetime.strptime(start_date,'%Y-%m-%d').date()
            end=datetime.strptime(end_date,'%Y-%m-%d').date()
        except ValueError:
            raise DomainError('Use valid dates in YYYY-MM-DD format.')
        if start.isoformat()!=start_date or end.isoformat()!=end_date or end<start:
            raise DomainError('Choose a valid date range with the end on or after the start.')
        with self.conn() as c:
            return self.rows(c.execute('''
                SELECT * FROM reservations
                WHERE booking_date>=? AND booking_date<=?
                ORDER BY booking_date,booking_time,created_at
            ''',(start_date,end_date)))

    def cancel_reservation(self,rid: str):
        with self.conn(True) as c:
            row=c.execute("SELECT * FROM reservations WHERE id=?",(rid,)).fetchone()
            if row is None: raise DomainError('Booking reference not found.')
            if row['status']=='cancelled': raise DomainError('Booking is already cancelled.')
            c.execute("UPDATE reservations SET status='cancelled' WHERE id=?",(rid,))
            return {**dict(row),'status':'cancelled'}

    def modify_reservation(self,rid: str,date: str,time: str,party_size: int,table_id: str|None=None,guest_name: str|None=None,notes: str|None=None):
        dt=validate_slot(date,time,party_size)
        if guest_name is not None and len(guest_name.strip())<2: raise DomainError('Guest name is required.')
        if notes is not None and len(notes)>500: raise DomainError('Notes too long')
        with self.conn(True) as c:
            row=c.execute("SELECT * FROM reservations WHERE id=? AND status='confirmed'",(rid,)).fetchone()
            if row is None: raise DomainError('Active booking reference not found.')
            free=self._free_tables(c,dt,party_size,ignore_id=rid)
            if table_id:
                selected=c.execute('SELECT * FROM tables WHERE id=?',(table_id,)).fetchone()
                if selected is None: raise DomainError('Selected table was not found.')
                if selected['seats']<party_size: raise DomainError('Selected table cannot seat this party.')
                free=[table for table in free if table['id']==table_id]
                if not free: raise DomainError('Selected table is not available; original booking remains unchanged.')
            if not free: raise DomainError('Requested slot is unavailable; original booking remains unchanged.')
            c.execute('''UPDATE reservations SET booking_date=?,booking_time=?,party_size=?,table_id=?,
                         guest_name=COALESCE(?,guest_name),notes=COALESCE(?,notes) WHERE id=?''',
                      (date,time,party_size,free[0]['id'],guest_name.strip() if guest_name is not None else None,notes,rid))
            return dict(c.execute('SELECT * FROM reservations WHERE id=?',(rid,)).fetchone())

    def menu(self):
        with self.conn() as c: return self.rows(c.execute('SELECT * FROM menu ORDER BY category,name'))

    def get_call(self,call_id: str):
        with self.conn() as c:
            r=c.execute('SELECT * FROM calls WHERE id=?',(call_id,)).fetchone()
            return dict(r) if r else None

    def create_call(self,call_id: str,source: str='browser',caller: str=''):
        with self.conn(True) as c:
            c.execute('''INSERT OR IGNORE INTO calls(id,source,caller,created_at,updated_at) VALUES(?,?,?,?,?)''',
                      (call_id,source,caller[:80],now_ist().isoformat(),now_ist().isoformat()))
        return self.get_call(call_id)

    def update_call(self,call_id: str,*,pending=None,intent=None,status=None):
        cols=['updated_at=?'];vals=[now_ist().isoformat()]
        if pending is not None: cols.append('pending_json=?');vals.append(json.dumps(pending,ensure_ascii=False) if pending else '')
        if intent is not None: cols.append('last_intent=?');vals.append(intent)
        if status is not None: cols.append('status=?');vals.append(status)
        vals.append(call_id)
        with self.conn(True) as c:c.execute('UPDATE calls SET '+','.join(cols)+' WHERE id=?',vals)

    def add_turn(self,call_id:str,role:str,content:str):
        with self.conn(True) as c:
            c.execute('INSERT INTO turns VALUES(?,?,?,?,?)',(uuid.uuid4().hex,call_id,role,content[:5000],now_ist().isoformat()))
            c.execute('UPDATE calls SET updated_at=? WHERE id=?',(now_ist().isoformat(),call_id))

    def turns(self,call_id:str):
        with self.conn() as c:return self.rows(c.execute('SELECT role,content,created_at FROM turns WHERE call_id=? ORDER BY created_at,id',(call_id,)))

    def list_calls(self):
        with self.conn() as c:return self.rows(c.execute('SELECT * FROM calls ORDER BY updated_at DESC LIMIT 100'))

    def create_task(self,call_id:str,title:str,notes:str):
        tid='TASK-'+uuid.uuid4().hex[:7].upper()
        with self.conn(True) as c:c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?)',(tid,call_id,title[:120],notes[:1000],'open',now_ist().isoformat()))
        return {'id':tid,'call_id':call_id,'title':title,'notes':notes,'status':'open'}

    def list_tasks(self):
        with self.conn() as c:return self.rows(c.execute('SELECT * FROM tasks ORDER BY created_at DESC'))

    def update_task(self,task_id:str,status:str):
        if status not in ('open','done'):raise DomainError('Invalid task status')
        with self.conn(True) as c:
            r=c.execute('UPDATE tasks SET status=? WHERE id=?',(status,task_id))
            if not r.rowcount:raise DomainError('Task not found')
        return {'id':task_id,'status':status}

    def dashboard(self):
        reservations=self.list_reservations()
        calls=self.list_calls();tasks=self.list_tasks()
        today=now_ist().date().isoformat()
        return {'today':today,'reservation_count':sum(x['booking_date']==today and x['status']=='confirmed' for x in reservations),
           'call_count':len(calls),'open_tasks':sum(t['status']=='open' for t in tasks),'tables':self.list_tables(),
           'reservations':reservations[:75],'calls':calls[:30],'tasks':tasks[:40],'menu':self.menu()}
