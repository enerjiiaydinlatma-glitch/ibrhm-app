"""Nedensel (lookahead'siz) gostergeler. Tum kolonlar t anindaki bilgiyle hesaplanir."""
import numpy as np
import pandas as pd

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

def atr(df, n=14):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def adx(df, n=14):
    up = df["high"].diff(); dn = -df["low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * pd.Series(mdm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean().fillna(0)

def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV -> gostergeli + rejim kolonlu cerceve."""
    f = df.copy()
    c = f["close"]
    f["ema20"] = ema(c, 20); f["ema50"] = ema(c, 50)
    f["sma20"] = c.rolling(20).mean(); f["sma50"] = c.rolling(50).mean()
    sd = c.rolling(20).std()
    f["bb_lo"] = f["sma20"] - 2 * sd; f["bb_up"] = f["sma20"] + 2 * sd
    f["rsi"] = rsi(c); f["atr"] = atr(f); f["atrp"] = f["atr"] / c
    f["adx"] = adx(f)
    f["dc_hi55"] = f["high"].rolling(55).max().shift(1)
    f["dc_lo20"] = f["low"].rolling(20).min().shift(1)
    f["volavg"] = f["volume"].rolling(20).mean()
    f["ret20"] = c.pct_change(20)
    f["atrp_q90"] = f["atrp"].rolling(250, min_periods=60).quantile(0.9)
    f["regime"] = _regime(f)
    return f

def _regime(f):
    r = pd.Series("RANGE", index=f.index, dtype=object)
    trend = f["adx"] > 22
    r[trend & (f["close"] > f["sma50"])] = "TREND_UP"
    r[trend & (f["close"] < f["sma50"])] = "TREND_DOWN"
    r[f["atrp"] > f["atrp_q90"]] = "HIGH_VOL"
    r[f["sma50"].isna()] = "WARMUP"
    return r
