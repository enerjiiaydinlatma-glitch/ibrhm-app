"""Backtest + walk-forward + analitik. Ayni Engine, ayni maliyet modeli."""
import math
import numpy as np, pandas as pd
from .broker import PaperBroker
from .config import MARKETS, RiskConfig
from .data import FxTable
from .engine import Engine
from .indicators import prepare
from .ledger import Ledger
from .risk import RiskEngine
from .strategies import build
from .brain import RuleBrain

def load_universe(provider, markets, per_market=None):
    data = {}
    for m in markets:
        for s in MARKETS[m].symbols[:per_market]:
            try: data[(m, s)] = prepare(provider.ohlcv(m, s))
            except Exception: continue
    return data

def metrics(eq: pd.Series, trades: list, extra=None):
    if len(eq) < 3: return {}
    r = eq.pct_change().dropna(); yrs = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    dd = (eq / eq.cummax() - 1).min()
    sells = [t for t in trades if t["side"] == "sell"]
    pnl = [t["pnl_base"] for t in sells if t["pnl_base"] is not None]
    gp = sum(x for x in pnl if x > 0); gl = -sum(x for x in pnl if x < 0)
    out = dict(total_return=float(eq.iloc[-1] / eq.iloc[0] - 1), cagr=float((eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1),
               max_dd=float(dd), sharpe=float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else 0.0,
               trades=len(sells), win_rate=float(np.mean([x > 0 for x in pnl])) if pnl else 0.0,
               profit_factor=float(gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0))
    out.update(extra or {}); return out

def run_backtest(data, start=None, end=None, base="USD", capital=100_000.0, funding="per_market",
                 markets=None, strategies=None, params=None, risk_cfg=None, fx=None, warmup=60):
    markets = markets or sorted({k[0] for k in data})
    ledger = Ledger(":memory:"); broker = PaperBroker(fx, base, capital, funding, markets)
    eng = Engine(data, broker, RiskEngine(risk_cfg or RiskConfig()), RuleBrain(), ledger, build(strategies, params), "rule")
    dates = sorted(set().union(*[set(f.index) for f in data.values()]))
    if start: dates = [d for d in dates if d >= pd.Timestamp(start)]
    if end: dates = [d for d in dates if d <= pd.Timestamp(end)]
    for d in dates: eng.run_date(d)
    eng.finalize()
    eq = pd.Series({pd.Timestamp(r["date"]): r["equity"] for r in ledger.rows("SELECT * FROM equity ORDER BY date")})
    trades = ledger.rows("SELECT * FROM trades")
    ex = dict(fees_base=broker.fees_base, fx_cost_base=broker.fx_cost_base, impact_base=broker.impact_base,
              cost_pct_of_capital=(broker.fees_base + broker.fx_cost_base + broker.impact_base) / capital)
    return dict(metrics=metrics(eq, trades, ex), equity=eq, trades=trades, ledger=ledger, engine=eng)

def walk_forward(data, fx, strategy, train=504, test=126, **kw):
    """Her katlamada gridden egitimde en iyi parametre secilir, SONRAKI doneminde test edilir (gormedigi veri)."""
    dates = sorted(set().union(*[set(f.index) for f in data.values()]))
    cls = build([strategy])[0].__class__
    folds, oos_eq, i = [], [], 0
    while i + train + test <= len(dates):
        tr0, tr1, te1 = dates[i], dates[i + train - 1], dates[i + train + test - 1]
        best, bs = None, -1e9
        for p in cls.grid:
            res = run_backtest(data, tr0, tr1, strategies=[strategy], params={strategy: p}, fx=fx, **kw)
            sc = res["metrics"].get("sharpe", -9) if res["metrics"].get("trades", 0) >= 3 else -9
            if sc > bs: best, bs = p, sc
        best = best if best is not None else cls.grid[0]
        # test: egitim donemini isinma icin kullan ama sadece test araligini olc
        res = run_backtest(data, dates[i + train - 60], te1, strategies=[strategy], params={strategy: best}, fx=fx, **kw)
        eq = res["equity"][res["equity"].index >= dates[i + train]]
        m = metrics(eq, res["trades"]) if len(eq) > 5 else {}
        folds.append(dict(train=f"{tr0.date()}..{tr1.date()}", test=f"{dates[i+train].date()}..{te1.date()}",
                          params=best, is_sharpe=bs, oos=m))
        if len(eq) > 5: oos_eq.append(eq / eq.iloc[0])
        i += test
    pos = sum(1 for f in folds if f["oos"].get("total_return", 0) > 0)
    rets = [f["oos"].get("total_return", 0) for f in folds]
    sh = [f["oos"].get("sharpe", 0) for f in folds if f["oos"]]
    pf = [f["oos"].get("profit_factor", 0) for f in folds if f["oos"]]
    n = len(folds)
    verdict = dict(folds=n, positive_folds=pos, mean_oos_return=float(np.mean(rets)) if rets else 0,
                   mean_oos_sharpe=float(np.mean(sh)) if sh else 0, median_oos_pf=float(np.median(pf)) if pf else 0)
    verdict["gate_passed"] = bool(n >= 3 and pos / n >= 0.6 and verdict["mean_oos_sharpe"] > 0 and verdict["median_oos_pf"] > 1.1)
    return dict(strategy=strategy, folds=folds, summary=verdict)

def analytics(ledger):
    q = ledger.rows
    by_strat = q("""SELECT strategy, COUNT(*) n, ROUND(AVG(outcome_pct)*100,2) avg_pct,
        ROUND(100.0*SUM(outcome_pct>0)/COUNT(*),1) win FROM decisions WHERE closed=1 GROUP BY strategy""")
    by_reg = q("""SELECT regime, COUNT(*) n, ROUND(AVG(outcome_pct)*100,2) avg_pct FROM decisions WHERE closed=1 GROUP BY regime""")
    by_mkt = q("""SELECT market, COUNT(*) n, ROUND(AVG(outcome_pct)*100,2) avg_pct FROM decisions WHERE closed=1 GROUP BY market""")
    veto = q("""SELECT COUNT(*) n, ROUND(AVG(shadow10)*100,2) avg_shadow10_pct FROM decisions WHERE action='veto' AND shadow10 IS NOT NULL""")
    taken = q("""SELECT brain, action, COUNT(*) n FROM decisions GROUP BY brain, action""")
    return dict(by_strategy=by_strat, by_regime=by_reg, by_market=by_mkt, veto_value=veto[0] if veto else {}, decisions=taken,
                ledger_ok=ledger.verify()[0])
