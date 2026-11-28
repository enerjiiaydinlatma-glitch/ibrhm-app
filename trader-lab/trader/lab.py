"""Uygulama servisi: ayarlar, kalici paper hesap, tarama, backtest."""
import os, threading
import pandas as pd
from .backtest import load_universe, run_backtest, walk_forward, analytics
from .broker import PaperBroker
from .brain import LLMClient, make_brain, effective_mode
from .config import MARKETS, RiskConfig
from .data import FxTable, get_provider
from .engine import Engine
from .ledger import Ledger
from .risk import RiskEngine
from .strategies import build

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ledger.db")
DEFAULTS = dict(mode="rule", funding="per_market", base="USD", capital=100_000.0, markets=["BIST", "US"], per_market=5, source="auto")

class Lab:
    def __init__(self, db=DB, provider=None):
        os.makedirs(os.path.dirname(db), exist_ok=True) if db != ":memory:" else None
        self.ledger = Ledger(db); self.lock = threading.RLock()
        self.cfg = {**DEFAULTS, **self.ledger.get_state("cfg", {})}
        self._provider = provider; self._loaded = None; self.engine = None
        self.llm = LLMClient()

    # ---------- veri ----------
    @property
    def provider(self):
        if self._provider is None: self._provider = get_provider(self.cfg["source"])
        return self._provider
    def _data(self, refresh=False):
        key = (tuple(self.cfg["markets"]), self.cfg["per_market"], self.provider.name)
        if refresh or self._loaded is None or self._loaded[0] != key:
            self._loaded = (key, load_universe(self.provider, self.cfg["markets"], self.cfg["per_market"]),
                            FxTable(self.provider.fx_table()))
        return self._loaded[1], self._loaded[2]

    # ---------- ayarlar ----------
    def configure(self, **kw):
        with self.lock:
            for k, v in kw.items():
                if k in DEFAULTS and v is not None: self.cfg[k] = v
            bad = [m for m in self.cfg["markets"] if m not in MARKETS]
            if bad: raise ValueError(f"bilinmeyen borsa: {bad}")
            if self.cfg["mode"] not in ("rule", "hybrid", "agent"): raise ValueError("mode")
            if self.cfg["funding"] not in ("per_market", "single_base"): raise ValueError("funding")
            self.ledger.put_state("cfg", self.cfg); return self.cfg

    def reset(self):
        with self.lock:
            for t in ("decisions", "trades", "equity", "state"): self.ledger.db.execute(f"DELETE FROM {t}")
            self.ledger.db.commit(); self.engine = None; self._loaded = None
            self.cfg = dict(DEFAULTS)

    # ---------- canli paper ----------
    def _engine(self):
        data, fx = self._data()
        if self.engine is None:
            saved = self.ledger.get_state("broker")
            broker = PaperBroker.from_dict(saved, fx) if saved else PaperBroker(
                fx, self.cfg["base"], self.cfg["capital"], self.cfg["funding"], self.cfg["markets"])
            risk = RiskEngine(); rs = self.ledger.get_state("risk", {})
            risk.peak, risk._cool = rs.get("peak", 0.0), rs.get("cool", 0)
            eff = effective_mode(self.cfg["mode"], self.llm)
            self.engine = Engine(data, broker, risk, make_brain(eff, self.llm), self.ledger, build(), eff)
            self.engine.pending = [dict(o, key=tuple(o["key"])) for o in self.ledger.get_state("pending", [])]
            self.engine.exits = [(tuple(k), w) for k, w in self.ledger.get_state("exits", [])]
        else:
            self.engine.data = data; self.engine.broker.fx = fx
        return self.engine

    def scan(self, replay_days=0):
        """Yeni gunleri isler. Ilk calistirmada replay_days>0 ise o kadar gun GECMISTEN hizlandirilmis tekrar oynatilir (demo)."""
        with self.lock:
            self.engine = None if self.engine and self.engine.mode != effective_mode(self.cfg["mode"], self.llm) else self.engine
            e = self._engine(); data = e.data
            dates = sorted(set().union(*[set(f.index) for f in data.values()]))
            last = self.ledger.get_state("last_date")
            if last: todo = [d for d in dates if d > pd.Timestamp(last)]
            else: todo = dates[-(replay_days + 1):] if replay_days > 0 else dates[-1:]
            for d in todo: e.run_date(d)
            if todo:
                e.finalize()
                self.ledger.put_state("last_date", str(todo[-1].date()))
                self.ledger.put_state("broker", e.broker.to_dict())
                self.ledger.put_state("risk", {"peak": e.risk.peak, "cool": getattr(e.risk, "_cool", 0)})
                self.ledger.put_state("pending", [dict(o, key=list(o["key"])) for o in e.pending])
                self.ledger.put_state("exits", [[list(k), w] for k, w in e.exits])
            return dict(processed=len(todo), last_date=str(todo[-1].date()) if todo else last)

    def state(self):
        with self.lock:
            e = self._engine(); b = e.broker
            eq = self.ledger.rows("SELECT date,equity FROM equity ORDER BY date")
            pos = []
            for (m, s), p in b.pos.items():
                last = b.last_px.get((m, s), p.avg); mid = b._mid(p.ccy, b.base)
                pos.append(dict(market=m, symbol=s, qty=p.qty, avg=p.avg, last=last, stop=p.stop, strategy=p.strategy, ccy=p.ccy,
                                pnl_pct=last / p.avg - 1, value_base=p.qty * last * mid))
            eff = effective_mode(self.cfg["mode"], self.llm)
            return dict(cfg=self.cfg, effective_mode=eff, llm_available=self.llm.available,
                        data_source=self.provider.name, synthetic=self.provider.name == "SENTETIK",
                        equity=b.equity(), capital0=b.capital0, base=b.base, cash=b.cash, positions=pos,
                        costs=dict(fees=b.fees_base, fx=b.fx_cost_base, impact=b.impact_base),
                        halted=e.risk.halted(b), curve=eq[-400:], last_date=self.ledger.get_state("last_date"),
                        markets={k: dict(name=v.name, ccy=v.ccy) for k, v in MARKETS.items()})

    def journal(self, limit=100, action=None):
        q = "SELECT * FROM decisions" + (" WHERE action=?" if action else "") + " ORDER BY id DESC LIMIT ?"
        return self.ledger.rows(q, ((action, limit) if action else (limit,)))

    def analytics(self): return analytics(self.ledger)

    # ---------- arastirma ----------
    def backtest(self, funding=None, strategies=None):
        data, fx = self._data()
        r = run_backtest(data, fx=fx, base=self.cfg["base"], capital=self.cfg["capital"], funding=funding or self.cfg["funding"],
                         markets=self.cfg["markets"], strategies=strategies)
        eq = r["equity"]
        return dict(metrics=r["metrics"], curve=[[str(d.date()), v] for d, v in eq.items()][::3],
                    analytics=analytics(r["ledger"]), data_source=self.provider.name)

    def compare_funding(self):
        return {f: self.backtest(funding=f)["metrics"] for f in ("per_market", "single_base")}

    def walkforward(self, strategy):
        data, fx = self._data()
        return walk_forward(data, fx, strategy, base=self.cfg["base"], capital=self.cfg["capital"],
                            funding=self.cfg["funding"], markets=self.cfg["markets"])
