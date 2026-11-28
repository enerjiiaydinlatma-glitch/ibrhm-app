"""Kural tabanli stratejiler (yalniz long). Hepsi onceden hazirlanmis cerceve uzerinde, nedensel."""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Signal:
    strategy: str
    strength: float            # 0..1
    stop: float
    reason: str
    invalidation: str
    features: dict = field(default_factory=dict)

def _feat(r):
    return {k: round(float(r[k]), 4) for k in ("close", "rsi", "adx", "atrp", "ret20") if k in r and r[k] == r[k]}

class Strategy:
    name = ""; allowed = ()
    grid = [{}]
    def __init__(self, **p): self.p = {**self.defaults, **p}
    defaults = {}

class TrendFollow(Strategy):
    name = "trend"; allowed = ("TREND_UP",)
    defaults = {"adx_min": 22, "atr_mult": 2.5}
    grid = [{"adx_min": a, "atr_mult": m} for a in (18, 24) for m in (2.0, 3.0)]
    def entry(self, f, i):
        r = f.iloc[i]
        if r["regime"] not in self.allowed: return None
        if r["ema20"] > r["ema50"] and r["close"] > r["ema50"] and r["adx"] >= self.p["adx_min"] and r["ret20"] > 0:
            stop = r["close"] - self.p["atr_mult"] * r["atr"]
            return Signal(self.name, min(1, r["adx"] / 40), stop,
                          f"EMA20>EMA50, ADX {r['adx']:.0f}>= {self.p['adx_min']}, 20g getiri {r['ret20']:+.1%}",
                          "EMA20 EMA50 altina inerse veya iz suren stop kirilirsa tez gecersiz", _feat(r))
    def manage(self, f, i, pos):
        r = f.iloc[i]
        new_stop = max(pos.stop, r["close"] - self.p["atr_mult"] * r["atr"])
        if r["ema20"] < r["ema50"]: return new_stop, "EMA20<EMA50 (trend bitti)"
        return new_stop, None

class MeanReversion(Strategy):
    name = "meanrev"; allowed = ("RANGE",)
    defaults = {"rsi_in": 30, "atr_mult": 2.0, "max_hold": 10}
    grid = [{"rsi_in": a, "atr_mult": m} for a in (25, 35) for m in (1.5, 2.5)]
    def entry(self, f, i):
        r = f.iloc[i]
        if r["regime"] not in self.allowed: return None
        if r["rsi"] < self.p["rsi_in"] and r["close"] < r["bb_lo"]:
            return Signal(self.name, min(1, (self.p["rsi_in"] + 10 - r["rsi"]) / 30 + .3),
                          r["close"] - self.p["atr_mult"] * r["atr"],
                          f"Yatay rejimde RSI {r['rsi']:.0f}<{self.p['rsi_in']} ve alt Bollinger disinda",
                          "Rejim TREND_DOWN/HIGH_VOL'a donerse veya stop kirilirsa gecersiz", _feat(r))
    def manage(self, f, i, pos):
        r = f.iloc[i]
        if r["rsi"] > 55 or r["close"] > r["sma20"]: return pos.stop, "ortalamaya donus tamam"
        if (f.index[i] - pos.entry_date).days > self.p["max_hold"] * 1.5: return pos.stop, "zaman asimi"
        return pos.stop, None

class Breakout(Strategy):
    name = "breakout"; allowed = ("TREND_UP", "RANGE")
    defaults = {"atr_mult": 2.0, "vol_x": 1.2}
    grid = [{"atr_mult": m, "vol_x": v} for m in (1.5, 2.5) for v in (1.0, 1.5)]
    def entry(self, f, i):
        r = f.iloc[i]
        if r["regime"] not in self.allowed or r["dc_hi55"] != r["dc_hi55"]: return None
        if r["close"] > r["dc_hi55"] and r["volume"] > self.p["vol_x"] * r["volavg"]:
            return Signal(self.name, 0.7, r["close"] - self.p["atr_mult"] * r["atr"],
                          f"55g zirve kirildi, hacim {r['volume']/r['volavg']:.1f}x ortalama",
                          "Fiyat kirilan seviyenin altina kapanirsa sahte kirilim", _feat(r))
    def manage(self, f, i, pos):
        r = f.iloc[i]
        if r["close"] < r["dc_lo20"]: return pos.stop, "20g dip kirildi"
        return max(pos.stop, r["close"] - self.p["atr_mult"] * r["atr"]), None

ALL = {c.name: c for c in (TrendFollow, MeanReversion, Breakout)}
def build(names=None, params=None):
    params = params or {}
    return [ALL[n](**params.get(n, {})) for n in (names or ALL)]
