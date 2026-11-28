"""Karar defteri: her karar girdi+gerekce+gecersizlik kosuluyla yazilir; hash zinciri ile degistirilemezlik kontrolu."""
import hashlib, json, sqlite3, threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, symbol TEXT, market TEXT,
 strategy TEXT, regime TEXT, brain TEXT, action TEXT, size_mult REAL, qty REAL, price REAL, features TEXT,
 rationale TEXT, invalidation TEXT, risk_note TEXT, outcome_pct REAL, closed INTEGER DEFAULT 0, shadow10 REAL,
 prev_hash TEXT, hash TEXT);
CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, symbol TEXT, market TEXT, side TEXT,
 qty REAL, price REAL, fee REAL, fx_cost_base REAL, pnl_base REAL, reason TEXT, decision_id INTEGER);
CREATE TABLE IF NOT EXISTS equity(date TEXT PRIMARY KEY, equity REAL, cash REAL);
CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY, v TEXT);
"""

class Ledger:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row; self.lock = threading.RLock()
        self.db.executescript(SCHEMA); self.db.commit()

    def _last_hash(self):
        r = self.db.execute("SELECT hash FROM decisions ORDER BY id DESC LIMIT 1").fetchone()
        return r["hash"] if r else "GENESIS"

    @staticmethod
    def _digest(prev, d):
        return hashlib.sha256((prev + json.dumps(d, sort_keys=True, default=str)).encode()).hexdigest()

    CORE = ("date", "symbol", "market", "strategy", "regime", "brain", "action", "size_mult", "price", "rationale", "invalidation")

    @classmethod
    def _core(cls, d):
        o = {k: d.get(k) for k in cls.CORE}
        for k in ("size_mult", "price"): o[k] = round(float(o[k] if o[k] is not None else 1), 8)
        return o

    def decision(self, **d):
        with self.lock:
            prev = self._last_hash()
            core = self._core(d)
            h = self._digest(prev, core)
            cur = self.db.execute(
                "INSERT INTO decisions(date,symbol,market,strategy,regime,brain,action,size_mult,qty,price,features,rationale,invalidation,risk_note,prev_hash,hash)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (d["date"], d["symbol"], d["market"], d["strategy"], d["regime"], d["brain"], d["action"], d.get("size_mult", 1),
                 d.get("qty", 0), d["price"], json.dumps(d.get("features", {})), d["rationale"], d.get("invalidation", ""),
                 d.get("risk_note", ""), prev, h))
            self.db.commit(); return cur.lastrowid

    def set_qty(self, did, qty, note=""):
        with self.lock:
            self.db.execute("UPDATE decisions SET qty=?, risk_note=? WHERE id=?", (qty, note, did)); self.db.commit()

    def close_decision(self, did, pct):
        with self.lock:
            self.db.execute("UPDATE decisions SET outcome_pct=?, closed=1 WHERE id=?", (pct, did)); self.db.commit()

    def set_shadow(self, did, v):
        with self.lock:
            self.db.execute("UPDATE decisions SET shadow10=? WHERE id=?", (v, did)); self.db.commit()

    def trade(self, **t):
        with self.lock:
            self.db.execute("INSERT INTO trades(date,symbol,market,side,qty,price,fee,fx_cost_base,pnl_base,reason,decision_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (t["date"], t["symbol"], t["market"], t["side"], t["qty"], t["price"], t["fee"], t.get("fx_cost_base", 0),
                 t.get("pnl_base"), t.get("reason", ""), t.get("decision_id")))
            self.db.commit()

    def snapshot(self, date, equity, cash):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO equity VALUES(?,?,?)", (str(date), equity, cash)); self.db.commit()

    def verify(self):
        prev = "GENESIS"
        for r in self.db.execute("SELECT * FROM decisions ORDER BY id"):
            core = self._core(dict(r))
            if r["prev_hash"] != prev or r["hash"] != self._digest(prev, core): return False, r["id"]
            prev = r["hash"]
        return True, None

    def rows(self, sql, args=()):
        with self.lock: return [dict(r) for r in self.db.execute(sql, args)]

    def put_state(self, k, v):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (k, json.dumps(v))); self.db.commit()
    def get_state(self, k, default=None):
        r = self.db.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default
