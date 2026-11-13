"""입력·계산 결과·법령 자료집을 함께 보관하는 개인용 SQLite 저장소."""
from pathlib import Path
import json, sqlite3
from uuid import uuid4
from .models import Trip, Result, dumps, now

class Store:
    def __init__(self,path='local_data/trips.sqlite3'):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS trips (
                  id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
                  updated_at TEXT NOT NULL, trip_json TEXT NOT NULL, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                  revision INTEGER PRIMARY KEY AUTOINCREMENT, trip_id TEXT NOT NULL,
                  saved_at TEXT NOT NULL, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self,trip:Trip,result:Result):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO trips VALUES(?,?,?,?,?,?)',
                (trip.id,trip.meta.get('출장명','제목 없음'),trip.kind,now(),dumps(trip.to_dict()),dumps(result.to_dict())))
            db.execute('INSERT INTO revisions(trip_id,saved_at,result_json) VALUES(?,?,?)',(trip.id,now(),dumps(result.to_dict())))

    def list(self,query=''):
        with self.connect() as db:
            return db.execute('SELECT id,title,kind,updated_at FROM trips WHERE instr(title,?)>0 ORDER BY updated_at DESC',(query,)).fetchall()

    def load(self,id):
        with self.connect() as db:
            row=db.execute('SELECT trip_json,result_json FROM trips WHERE id=?',(id,)).fetchone()
        if row is None: raise ValueError('저장된 출장을 찾지 못했습니다.')
        return Trip.from_dict(json.loads(row[0])),Result.from_dict(json.loads(row[1]))

    def copy(self,id):
        trip,_=self.load(id)
        trip.id=uuid4().hex[:12]
        trip.meta['출장명']=trip.meta.get('출장명','')+' (복사)'
        return trip

    def delete(self,id):
        with self.connect() as db:
            db.execute('DELETE FROM revisions WHERE trip_id=?',(id,))
            db.execute('DELETE FROM trips WHERE id=?',(id,))

    def preference(self,key,default=None):
        with self.connect() as db:
            row=db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_preference(self,key,value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',(key,dumps(value)))
