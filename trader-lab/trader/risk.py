"""Risk motoru: beyin/LLM ne derse desin bu limitler asilamaz."""
from dataclasses import dataclass
from .config import RiskConfig, MARKETS

@dataclass
class Verdict:
    qty: int
    note: str

class RiskEngine:
    def __init__(self, cfg: RiskConfig | None = None):
        self.cfg = cfg or RiskConfig(); self.peak = 0.0; self.day_start = {}

    COOLDOWN_DAYS = 20

    def on_day(self, date, equity):
        self._today = equity; self.day_start[str(date)] = equity
        if getattr(self, "_cool", 0) > 0:
            self._cool -= 1
            if self._cool == 0: self.peak = equity        # soguma bitti: tepe yeniden belirlenir
        elif self.peak and equity < self.peak * (1 - self.cfg.max_drawdown_halt):
            self._cool = self.COOLDOWN_DAYS               # fren: yeni giris yok, sonra yeniden basla
        self.peak = max(self.peak, equity)

    def halted(self, broker):
        e = broker.equity()
        if getattr(self, "_cool", 0) > 0: return "max drawdown limiti (soguma)"
        if getattr(self, "_today", 0) and e < self._today * (1 - self.cfg.daily_loss_halt): return "gunluk kayip limiti"
        return None

    def size(self, broker, market, price, stop, size_mult, adv):
        c = self.cfg; m = MARKETS[market]
        h = self.halted(broker)
        if h: return Verdict(0, f"HALT: {h}")
        if len(broker.pos) >= c.max_positions: return Verdict(0, "azami pozisyon sayisi")
        eq = broker.equity()
        if broker.exposure_base(market) > c.max_market_pct * eq: return Verdict(0, f"{market} borsa limiti")
        risk_per_share = price - stop
        if risk_per_share <= 0: return Verdict(0, "gecersiz stop")
        fx = broker._mid(broker.base, m.ccy)
        risk_cash = eq * c.risk_per_trade * size_mult * fx
        q_risk = risk_cash / risk_per_share
        q_cap = eq * c.max_pos_pct * size_mult * fx / price
        q_adv = c.max_adv_participation * adv if adv else q_cap
        q_cash = broker.buying_power(market) / (price * 1.01)
        q = int(min(q_risk, q_cap, q_adv, q_cash))
        why = {q_risk: "risk", q_cap: "pozisyon %", q_adv: "likidite", q_cash: "nakit"}
        return Verdict(q, f"boyut siniri: {why[min(why)]}" if q > 0 else "boyut 0")
