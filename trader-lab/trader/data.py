"""Veri saglayicilar: Yahoo (gercek) + Sentetik (offline/test). Kaynak her zaman etiketlenir."""
import hashlib, os, time
from datetime import date
import numpy as np
import pandas as pd
from .config import MARKETS, SYNTH_FX, SYNTH_FX_DRIFT, yf_ticker

CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")

def _seed(s): return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)

def _bdays(n, end=None):
    end = pd.Timestamp(end or date.today())
    return pd.bdate_range(end=end, periods=n)

class SyntheticProvider:
    """Rejim degisen GBM. Deterministik (sembole gore seed). GERCEK VERI DEGILDIR."""
    name = "SENTETIK"
    def __init__(self, days=900, end=None): self.days, self.end = days, end

    def ohlcv(self, market, sym):
        rng = np.random.default_rng(_seed(market + sym))
        n = self.days; idx = _bdays(n, self.end)
        mu = np.zeros(n); sig = np.zeros(n)
        i = 0
        while i < n:
            L = int(rng.integers(40, 160))
            kind = rng.choice(["up", "down", "range", "wild"], p=[.35, .2, .3, .15])
            m, s = {"up": (0.0009, 0.011), "down": (-0.0008, 0.014), "range": (0.0, 0.009), "wild": (0.0, 0.025)}[kind]
            mu[i:i + L] = m; sig[i:i + L] = s; i += L
        mu = mu + SYNTH_FX_DRIFT.get(MARKETS[market].ccy, 0.0)   # enflasyonist para: nominal fiyatlar da kayar
        r = rng.normal(mu, sig)
        base = float(rng.uniform(20, 300))
        close = base * np.exp(np.cumsum(r))
        gap = rng.normal(0, sig * 0.3)
        open_ = np.r_[close[0], close[:-1]] * np.exp(gap)
        hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, sig * 0.5)))
        lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, sig * 0.5)))
        vol = rng.lognormal(14, 0.4, n) * (1 + 3 * np.abs(r) / (sig + 1e-9) * 0.1)
        return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": vol}, index=idx)

    def fx_table(self):
        idx = _bdays(self.days, self.end); out = {}
        for ccy, v in SYNTH_FX.items():
            rng = np.random.default_rng(_seed("fx" + ccy))
            steps = rng.normal(SYNTH_FX_DRIFT.get(ccy, 0.0), 0.003 if ccy != "USD" else 0, len(idx))
            out[ccy] = pd.Series(v * np.exp(np.cumsum(steps)), index=idx)   # USD basina yerel para
        return pd.DataFrame(out)

class YahooProvider:
    name = "YAHOO"
    def __init__(self, period="4y"):
        self.period = period; os.makedirs(CACHE, exist_ok=True)

    def _get(self, ticker):
        path = os.path.join(CACHE, ticker.replace("/", "_").replace("=", "_") + ".csv")
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < 6 * 3600:
            return pd.read_csv(path, index_col=0, parse_dates=True)
        import yfinance as yf
        df = yf.download(ticker, period=self.period, interval="1d", auto_adjust=True, progress=False)
        if df is None or df.empty: raise RuntimeError(f"veri yok: {ticker}")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.to_csv(path); return df

    def ohlcv(self, market, sym):
        m = MARKETS[market]; df = self._get(yf_ticker(m, sym))
        if m.price_div != 1.0:
            for c in ("open", "high", "low", "close"): df[c] = df[c] / m.price_div
        return df

    def fx_table(self):
        cols = {"USD": None}
        idx = None; out = {}
        for ccy in SYNTH_FX:
            if ccy == "USD": continue
            s = self._get(f"USD{ccy}=X")["close"]; out[ccy] = s
        df = pd.DataFrame(out).sort_index().ffill().bfill()
        df.insert(0, "USD", 1.0); return df

def get_provider(kind="auto"):
    """auto: Yahoo'yu dene, olmazsa sentetige dus (kaynak etiketi degisir)."""
    if kind == "synthetic": return SyntheticProvider()
    if kind in ("yahoo", "auto"):
        try:
            p = YahooProvider(); p.ohlcv("US", "SPY"); return p
        except Exception:
            if kind == "yahoo": raise
    return SyntheticProvider()

class FxTable:
    def __init__(self, df): self.df = df  # kolon: ccy, deger: USD basina yerel para
    def rate(self, a, b, d):
        """1 a = ? b (mid)."""
        if a == b: return 1.0
        row = self.df.loc[:pd.Timestamp(d)].iloc[-1]
        return float(row[b] / row[a])
