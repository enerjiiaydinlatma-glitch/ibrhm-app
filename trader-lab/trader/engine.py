"""Tek motor: backtest ve canli-paper AYNI kodu kullanir (backtest-canli sapmasi olmasin)."""
import pandas as pd
from .config import MARKETS
from .strategies import Strategy, Signal, build
from .brain import RuleBrain, Verdict

class AgentManaged(Strategy):
    name = "agent"; allowed = ()
    def entry(self, f, i): return None
    def manage(self, f, i, pos):
        r = f.iloc[i]
        st = max(pos.stop, r["close"] - 2.5 * r["atr"])
        if r["regime"] == "TREND_DOWN" or r["ema20"] < r["ema50"]: return st, "trend zayifladi"
        return st, None

class Engine:
    MAX_NEW_PER_DAY = 3
    def __init__(self, data, broker, risk, brain, ledger, strategies=None, mode="rule"):
        self.data, self.broker, self.risk, self.brain, self.ledger = data, broker, risk, brain, ledger
        self.strats = {s.name: s for s in (strategies or build())}
        self.strats["agent"] = AgentManaged()
        self.mode = mode
        self.pending, self.exits = [], []   # bir sonraki acilista islenecek emirler

    # ---------- yardimcilar ----------
    def _adv(self, f, i): v = f["volavg"].iloc[i]; return float(v) if v == v else 0.0
    def _stats(self, name):
        rows = self.ledger.rows("SELECT outcome_pct FROM decisions WHERE strategy=? AND closed=1", (name,))
        if not rows: return {"islem": 0}
        w = sum(1 for r in rows if r["outcome_pct"] > 0)
        return {"islem": len(rows), "isabet": round(w / len(rows), 2)}
    def _portfolio(self):
        eq = self.broker.equity()
        return {"pozisyon": len(self.broker.pos), "exposure_pct": round(self.broker.exposure_base() / eq, 2) if eq else 0}

    # ---------- bir gun ----------
    def run_date(self, d):
        d = pd.Timestamp(d); b = self.broker; b.set_day(d)
        idx = {}
        for k, f in self.data.items():
            if d in f.index: idx[k] = f.index.get_loc(d)
        self.risk.on_day(d, b.equity())
        # 1) cikislar (dunku karar) acilista
        for k, why in list(self.exits):
            if k in b.pos and k in idx:
                f = self.data[k]; self._sell(k, float(f["open"].iloc[idx[k]]), self._adv(f, idx[k]), why, d)
        self.exits = []
        # 2) giris emirleri acilista
        for o in self.pending:
            k = o["key"]
            if k not in idx or k in b.pos: continue
            f = self.data[k]; i = idx[k]; px = float(f["open"].iloc[i])
            if px <= o["stop"]: self.ledger.set_qty(o["did"], 0, "acilis stop altinda, iptal"); continue
            v = self.risk.size(b, k[0], px, o["stop"], o["size_mult"], self._adv(f, i))
            if v.qty < 1: self.ledger.set_qty(o["did"], 0, v.note); continue
            res = b.buy(k[0], k[1], px, v.qty, o["stop"], o["strategy"], d, o["did"], self._adv(f, i))
            if res:
                self.ledger.set_qty(o["did"], res["qty"], v.note)
                self.ledger.trade(date=str(d.date()), symbol=k[1], market=k[0], side="buy", qty=res["qty"], price=res["price"],
                                  fee=res["fee"], reason=o["strategy"], decision_id=o["did"])
            else: self.ledger.set_qty(o["did"], 0, "nakit yetersiz")
        self.pending = []
        # 3) stop kontrolu (gun ici) ve fiyat guncelleme
        for k, i in idx.items():
            f = self.data[k]
            if k in b.pos:
                p = b.pos[k]
                if float(f["low"].iloc[i]) <= p.stop:
                    self._sell(k, min(float(f["open"].iloc[i]), p.stop), self._adv(f, i), "stop", d)
        for k in list(b.pos):
            if k in idx: b.last_px[k] = float(self.data[k]["close"].iloc[idx[k]])
        # 4) pozisyon yonetimi (kapanis)
        for k, p in list(b.pos.items()):
            if k not in idx: continue
            f = self.data[k]; i = idx[k]
            st, why = self.strats.get(p.strategy, self.strats["agent"]).manage(f, i, p)
            p.stop = st
            if why: self.exits.append((k, why))
        # 5) yeni sinyaller
        self._signals(d, idx)
        # 6) gunluk kayit
        b.set_day(d); self.ledger.snapshot(d.date(), b.equity(), b.cash_base())

    def _sell(self, k, px, adv, why, d):
        r = self.broker.sell(k, px, adv, why)
        p = r["pos"]
        self.ledger.trade(date=str(d.date()), symbol=k[1], market=k[0], side="sell", qty=r["qty"], price=r["price"], fee=r["fee"],
                          fx_cost_base=r["fx_cost"], pnl_base=r["pnl_base"], reason=why, decision_id=p.decision_id)
        self.ledger.close_decision(p.decision_id, r["pct"])

    def _signals(self, d, idx):
        queued = {o["key"] for o in self.pending}
        cands = []
        if self.mode == "agent" and hasattr(self.brain, "propose"):
            rows = []
            for k, i in idx.items():
                if k in self.broker.pos: continue
                r = self.data[k].iloc[i]
                if r["regime"] == "WARMUP": continue
                rows.append({"symbol": k[1], "market": k[0], "regime": r["regime"], "rsi": round(float(r["rsi"]), 1),
                             "adx": round(float(r["adx"]), 1), "ret20": round(float(r["ret20"]), 3), "atrp": round(float(r["atrp"]), 4)})
            for p in self.brain.propose(rows, self._portfolio()):
                k = (p["market"], p["symbol"]); r = self.data[k].iloc[idx[k]]
                m = max(1.5, min(3.5, float(p.get("atr_mult", 2.5))))
                cands.append((k, idx[k], Signal("agent", float(p.get("conviction", .5)), float(r["close"] - m * r["atr"]),
                              p.get("rationale", ""), p.get("invalidation", ""), {"rsi": float(r["rsi"]), "adx": float(r["adx"])})))
        else:
            for k, i in idx.items():
                if k in self.broker.pos or k in queued: continue
                best = None
                for s in self.strats.values():
                    sig = s.entry(self.data[k], i)
                    if sig and (best is None or sig.strength > best.strength): best = sig
                if best: cands.append((k, i, best))
        cands.sort(key=lambda c: -c[2].strength)
        for n, (k, i, sig) in enumerate(cands):
            f = self.data[k]; r = f.iloc[i]
            ctx = dict(signal=sig, regime=r["regime"], market=k[0], symbol=k[1], portfolio=self._portfolio(), stats=self._stats(sig.strategy))
            v = self.brain.decide(ctx) if self.mode != "agent" else Verdict("approve", max(.3, sig.strength), sig.reason, "agent")
            if n >= self.MAX_NEW_PER_DAY and v.action != "veto": v = Verdict("veto", 0, "gunluk yeni islem siniri", "rule")
            did = self.ledger.decision(date=str(d.date()), symbol=k[1], market=k[0], strategy=sig.strategy, regime=r["regime"],
                                       brain=v.source, action=v.action, size_mult=v.size_mult, price=float(r["close"]),
                                       features=sig.features, rationale=v.rationale, invalidation=sig.invalidation)
            if v.action != "veto":
                self.pending.append(dict(key=k, stop=float(sig.stop), size_mult=v.size_mult, strategy=sig.strategy, did=did))

    def finalize(self):
        """Veto edilen sinyallerin 10 gun sonraki 'golge' getirisi: beyin vetosu deger katti mi?"""
        for r in self.ledger.rows("SELECT id,date,symbol,market,price FROM decisions WHERE action='veto' AND shadow10 IS NULL"):
            f = self.data.get((r["market"], r["symbol"]))
            if f is None: continue
            pos = f.index.searchsorted(pd.Timestamp(r["date"]))
            if pos + 10 < len(f): self.ledger.set_shadow(r["id"], float(f["close"].iloc[pos + 10] / r["price"] - 1))
