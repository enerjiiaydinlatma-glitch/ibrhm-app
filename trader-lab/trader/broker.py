"""Paper broker: cok para birimli cuzdanlar, gercekci maliyet (komisyon, vergi, kayma+piyasa etkisi, FX spread)."""
from dataclasses import dataclass, asdict
import pandas as pd
from .config import MARKETS, FX_SPREAD_BPS, FX_FEE_BPS, CASH_RATE

@dataclass
class Position:
    symbol: str; market: str; qty: float; avg: float; stop: float; strategy: str
    entry_date: pd.Timestamp; decision_id: int; ccy: str; cost_base: float = 0.0

class PaperBroker:
    def __init__(self, fx, base_ccy="USD", capital=100_000.0, funding="per_market", markets=("BIST", "US")):
        self.fx, self.base, self.funding = fx, base_ccy, funding
        self.markets = list(markets)
        self.cash = {base_ccy: 0.0}
        self.pos: dict[tuple, Position] = {}
        self.last_px: dict[tuple, float] = {}
        self.fees_base = 0.0; self.fx_cost_base = 0.0; self.impact_base = 0.0
        self.capital0 = capital; self.today = None
        if funding == "single_base":
            self.cash[base_ccy] = capital
        else:   # her borsaya esit pay, mid kurdan, maliyetsiz (yerel para yatirildigi varsayimi)
            share = capital / len(self.markets)
            for m in self.markets:
                c = MARKETS[m].ccy
                self.cash[c] = self.cash.get(c, 0.0) + share * self._mid(self.base, c)

    def _mid(self, a, b, d=None): return self.fx.rate(a, b, d or self.today or pd.Timestamp.today())

    def set_day(self, d):
        d = pd.Timestamp(d)
        if getattr(self, "_accr", None) is not None and d > self._accr:
            days = (d - self._accr).days
            for c in self.cash:
                if self.cash[c] > 0: self.cash[c] *= 1 + CASH_RATE.get(c, 0.0) * days / 365
        if getattr(self, "_accr", None) is None or d > self._accr: self._accr = d
        self.today = d

    # ---- degerleme ----
    def equity(self):
        e = sum(v * self._mid(c, self.base) for c, v in self.cash.items())
        for k, p in self.pos.items():
            e += p.qty * self.last_px.get(k, p.avg) * self._mid(p.ccy, self.base)
        return e

    def cash_base(self): return sum(v * self._mid(c, self.base) for c, v in self.cash.items())
    def exposure_base(self, market=None):
        return sum(p.qty * self.last_px.get(k, p.avg) * self._mid(p.ccy, self.base)
                   for k, p in self.pos.items() if market in (None, p.market))

    def buying_power(self, market):
        """Yerel para cinsinden harcanabilir tutar."""
        ccy = MARKETS[market].ccy; bp = self.cash.get(ccy, 0.0)
        if self.funding == "single_base" and ccy != self.base:
            ask = self._mid(self.base, ccy) * (1 - FX_SPREAD_BPS / 1e4 - FX_FEE_BPS / 1e4)  # kotu kur
            bp += self.cash.get(self.base, 0.0) * ask
        return bp

    # ---- maliyet ----
    def _costs(self, m, side, px, qty, adv):
        notional = px * qty
        fee = max(m.min_comm, notional * m.comm_bps / 1e4) + notional * (m.buy_extra_bps if side == "buy" else m.sell_extra_bps) / 1e4
        part = qty / adv if adv else 0
        slip = m.slip_bps / 1e4 + 0.4 * part   # taban kayma + gunluk hacme katilimla artan piyasa etkisi
        slip = min(slip, 0.03)
        fill = px * (1 + slip) if side == "buy" else px * (1 - slip)
        return fill, fee, abs(fill - px) * qty

    def _convert_in(self, ccy, needed):
        """single_base: eksik yerel parayi baz cuzdandan al, spread kaybi yaz."""
        short = needed - self.cash.get(ccy, 0.0)
        if short <= 0 or self.funding != "single_base" or ccy == self.base: return
        mid = self._mid(self.base, ccy); eff = mid * (1 - (FX_SPREAD_BPS + FX_FEE_BPS) / 1e4)
        base_spent = short / eff
        self.cash[self.base] -= base_spent
        self.cash[ccy] = self.cash.get(ccy, 0.0) + short
        self.fx_cost_base += base_spent - short / mid

    def _convert_out(self, ccy, amount):
        if self.funding != "single_base" or ccy == self.base or amount <= 0: return
        mid = self._mid(ccy, self.base); eff = mid * (1 - (FX_SPREAD_BPS + FX_FEE_BPS) / 1e4)
        self.cash[ccy] -= amount; self.cash[self.base] += amount * eff
        self.fx_cost_base += amount * mid - amount * eff

    # ---- emirler ----
    def buy(self, market, sym, px, qty, stop, strategy, date, did, adv):
        m = MARKETS[market]; qty = int(qty)
        if qty < 1: return None
        fill, fee, imp = self._costs(m, "buy", px, qty, adv)
        total = fill * qty + fee
        if total > self.buying_power(market): return None
        self._convert_in(m.ccy, total)
        self.cash[m.ccy] = self.cash.get(m.ccy, 0.0) - total
        mid = self._mid(m.ccy, self.base)
        self.fees_base += fee * mid; self.impact_base += imp * mid
        k = (market, sym); self.pos[k] = Position(sym, market, qty, fill, stop, strategy, pd.Timestamp(date), did, m.ccy, fee * mid)
        self.last_px[k] = px
        return dict(price=fill, fee=fee, qty=qty)

    def sell(self, key, px, adv, reason=""):
        p = self.pos[key]; m = MARKETS[p.market]
        fill, fee, imp = self._costs(m, "sell", px, p.qty, adv)
        proceeds = fill * p.qty - fee
        self.cash[m.ccy] = self.cash.get(m.ccy, 0.0) + proceeds
        mid = self._mid(m.ccy, self.base)
        before = self.fx_cost_base
        self._convert_out(m.ccy, proceeds)
        self.fees_base += fee * mid; self.impact_base += imp * mid
        pnl_local = (fill - p.avg) * p.qty - fee
        pnl_base = pnl_local * mid - p.cost_base
        del self.pos[key]; self.last_px.pop(key, None)
        return dict(price=fill, fee=fee, qty=p.qty, pnl_base=pnl_base, pct=(fill / p.avg - 1), fx_cost=self.fx_cost_base - before, pos=p)

    # ---- kalicilik ----
    def to_dict(self):
        return dict(base=self.base, funding=self.funding, markets=self.markets, cash=self.cash, capital0=self.capital0,
                    fees=self.fees_base, fxc=self.fx_cost_base, imp=self.impact_base, accr=str(getattr(self, '_accr', None)),
                    last_px={f"{a}|{b}": v for (a, b), v in self.last_px.items()},
                    pos=[{**asdict(p), "entry_date": str(p.entry_date)} for p in self.pos.values()])

    @classmethod
    def from_dict(cls, d, fx):
        b = cls(fx, d["base"], d["capital0"], d["funding"], d["markets"])
        b._accr = pd.Timestamp(d["accr"]) if d.get("accr") not in (None, "None") else None
        b.cash = d["cash"]; b.fees_base, b.fx_cost_base, b.impact_base = d["fees"], d["fxc"], d["imp"]
        b.last_px = {tuple(k.split("|")): v for k, v in d["last_px"].items()}
        for p in d["pos"]:
            p["entry_date"] = pd.Timestamp(p["entry_date"]); pos = Position(**p); b.pos[(pos.market, pos.symbol)] = pos
        return b
