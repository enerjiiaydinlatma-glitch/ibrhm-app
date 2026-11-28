"""Piyasa tanimlari: para birimi, maliyetler, evren. Maliyetler muhafazakar/yaklasik degerlerdir;
gercek aracı kurum tarifenle guncelle."""
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Market:
    code: str
    name: str
    ccy: str
    suffix: str            # yfinance eki
    comm_bps: float        # komisyon (her yon)
    min_comm: float        # asgari komisyon (yerel para)
    buy_extra_bps: float   # alis vergisi (orn. UK damga)
    sell_extra_bps: float  # satis vergisi/harci (BSMV, SEC vb. yaklasik)
    slip_bps: float        # taban kayma
    price_div: float = 1.0 # LSE pence -> GBP
    symbols: tuple = ()
    benchmark: str = ""    # piyasa genel yonu icin endeks (yfinance kodu)

MARKETS = {
    "BIST": Market("BIST", "Borsa Istanbul", "TRY", ".IS", 15, 0, 0, 1.0, 12, 1.0,
                   ("THYAO", "GARAN", "ASELS", "EREGL", "BIMAS", "KCHOL", "AKBNK", "TUPRS"), benchmark="XU100.IS"),
    "US": Market("US", "ABD (NYSE/Nasdaq)", "USD", "", 0, 0, 0, 0.3, 5, 1.0,
                 ("AAPL", "MSFT", "NVDA", "JPM", "XOM", "SPY", "QQQ", "AMZN"), benchmark="SPY"),
    "LSE": Market("LSE", "Londra", "GBP", ".L", 8, 0, 50, 0, 10, 100.0,
                  ("SHEL", "AZN", "HSBA", "ULVR"), benchmark="^FTSE"),
    "XETRA": Market("XETRA", "Frankfurt/XETRA", "EUR", ".DE", 8, 0, 0, 0, 8, 1.0,
                    ("SAP", "SIE", "ALV"), benchmark="^GDAXI"),
    "TSE": Market("TSE", "Tokyo", "JPY", ".T", 5, 0, 0, 0, 8, 1.0, ("7203", "6758", "9984"), benchmark="^N225"),
    "HKEX": Market("HKEX", "Hong Kong", "HKD", ".HK", 10, 0, 13, 13, 10, 1.0, ("0700", "0005", "9988"), benchmark="^HSI"),
}

FX_SPREAD_BPS = 30   # gercek cevirimde (alinan/satilan) spread; kayip buradan dogar
FX_FEE_BPS = 5

# USD basina yerel para (sentetik FX icin baslangic degerleri; gercek modda Yahoo'dan gelir)
SYNTH_FX = {"USD": 1.0, "TRY": 35.0, "EUR": 0.92, "GBP": 0.79, "JPY": 150.0, "HKD": 7.8}
SYNTH_FX_DRIFT = {"TRY": 0.0008}   # gunluk deger kaybi egilimi (TRY)

@dataclass
class RiskConfig:
    risk_per_trade: float = 0.01      # islem basi sermayenin %1'i riske
    max_pos_pct: float = 0.15         # tek hisse en fazla %15
    max_positions: int = 8
    max_market_pct: float = 0.50      # tek borsa en fazla %50
    max_adv_participation: float = 0.05
    daily_loss_halt: float = 0.03
    max_drawdown_halt: float = 0.15

def yf_ticker(m: Market, sym: str) -> str:
    return f"{sym}{m.suffix}"

# Nakit faizi (yillik, VARSAYIM - kendi mevduat/repo oranina gore degistir). Bos TRY nakdi kur kaybini kismen telafi eder.
CASH_RATE = {"USD": 0.04, "TRY": 0.30, "EUR": 0.02, "GBP": 0.04, "JPY": 0.005, "HKD": 0.04}
