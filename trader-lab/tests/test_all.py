import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd, pytest
from fastapi.testclient import TestClient
from trader.api import create_app
from trader.backtest import load_universe, run_backtest, walk_forward
from trader.brain import HybridBrain, AgentBrain, LLMClient, RuleBrain, effective_mode
from trader.broker import PaperBroker
from trader.data import SyntheticProvider, FxTable
from trader.indicators import prepare
from trader.lab import Lab
from trader.ledger import Ledger
from trader.strategies import Signal

P = SyntheticProvider(days=700); FX = FxTable(P.fx_table())

def test_no_lookahead_indicators():
    df = P.ohlcv("US", "AAPL"); a = prepare(df); b = prepare(df.iloc[:400])
    pd.testing.assert_series_equal(a["rsi"].iloc[:400], b["rsi"], check_names=False)
    assert (a["regime"].iloc[:400] == b["regime"]).all()

def test_broker_costs_and_fx():
    b = PaperBroker(FX, "USD", 100_000, "single_base", ["BIST"]); b.set_day(FX.df.index[-1])
    r = b.buy("BIST", "THYAO", 100.0, 1000, 90.0, "trend", b.today, 1, adv=1e6)
    assert r and r["fee"] > 0 and b.fx_cost_base > 0 and r["price"] > 100
    s = b.sell(("BIST", "THYAO"), 100.0, 1e6)
    assert s["price"] < 100 and b.equity() < 100_000          # gidis-donus maliyeti zarar yazar

def test_per_market_has_no_fx_cost():
    b = PaperBroker(FX, "USD", 100_000, "per_market", ["BIST", "US"]); b.set_day(FX.df.index[-1])
    b.buy("BIST", "X", 50.0, 100, 40.0, "trend", b.today, 1, 1e6); assert b.fx_cost_base == 0

def test_broker_roundtrip_serialization():
    b = PaperBroker(FX, "USD", 50_000, "per_market", ["US"]); b.set_day(FX.df.index[-1])
    b.buy("US", "AAPL", 100.0, 10, 90.0, "trend", b.today, 1, 1e6)
    c = PaperBroker.from_dict(b.to_dict(), FX); assert abs(c.equity() - b.equity()) < 1e-6

def test_ledger_chain_detects_tamper():
    L = Ledger()
    for i in range(3): L.decision(date="2026-01-0%d" % (i + 1), symbol="A", market="US", strategy="trend", regime="TREND_UP",
                                  brain="rule", action="approve", size_mult=1, price=10.0, rationale="x", invalidation="y")
    assert L.verify()[0]
    L.db.execute("UPDATE decisions SET rationale='degisti' WHERE id=2"); L.db.commit()
    assert L.verify() == (False, 2)

def test_backtest_runs_and_is_deterministic():
    d = load_universe(P, ["BIST", "US"], 3)
    a = run_backtest(d, fx=FX, markets=["BIST", "US"])["metrics"]; b = run_backtest(d, fx=FX, markets=["BIST", "US"])["metrics"]
    assert a == b and a["trades"] > 0

def test_risk_limits_hold():
    d = load_universe(P, ["US"], 5); r = run_backtest(d, fx=FX, markets=["US"])
    maxpos = max(len(x) for x in [r["engine"].broker.pos]) if r["engine"].broker.pos else 0
    assert maxpos <= 8
    assert r["ledger"].verify()[0]

def test_walk_forward_structure():
    d = load_universe(P, ["US"], 3); w = walk_forward(d, FX, "trend", train=300, test=100, markets=["US"])
    assert w["summary"]["folds"] >= 1 and "gate_passed" in w["summary"]

class FakeLLM:
    available = True
    def __init__(self, out): self.out = out
    def ask(self, *a, **k): return self.out

def _ctx():
    return dict(signal=Signal("trend", .9, 90, "r", "i", {}), regime="TREND_UP", market="US", symbol="A",
                portfolio={"pozisyon": 0, "exposure_pct": 0.1}, stats={})

def test_llm_can_only_reduce_or_veto():
    up = HybridBrain(FakeLLM('{"action":"approve","size_mult":5,"rationale":"x"}')).decide(_ctx())
    assert up.size_mult <= RuleBrain().decide(_ctx()).size_mult
    assert HybridBrain(FakeLLM('{"action":"veto","size_mult":0,"rationale":"x"}')).decide(_ctx()).action == "veto"
    assert HybridBrain(FakeLLM("sacma")).decide(_ctx()).action in ("approve", "reduce")   # bozuk cikti -> kural

def test_agent_ignores_invented_symbols():
    rows = [{"symbol": "AAPL", "market": "US"}]
    a = AgentBrain(FakeLLM('[{"symbol":"AAPL","market":"US"},{"symbol":"UYDURMA","market":"US"}]'))
    assert [p["symbol"] for p in a.propose(rows, {})] == ["AAPL"]

def test_effective_mode_falls_back_without_key():
    assert effective_mode("hybrid", LLMClient(key=None)) in ("rule", "hybrid")

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Lab(str(tmp_path / "l.db"), provider=P)))

def test_api_flow(client):
    assert client.get("/api/health").json()["ok"]
    assert client.post("/api/config", json={"mode": "bogus"}).status_code == 400
    assert client.post("/api/scan?replay_days=90").json()["processed"] == 91
    s = client.get("/api/state").json(); assert s["synthetic"] and s["equity"] > 0
    assert client.get("/api/journal").status_code == 200
    assert client.get("/api/ledger/verify").json()["ok"]
    assert client.get("/api/analytics").status_code == 200
    assert client.post("/api/scan").json()["processed"] == 0     # idempotent
    assert client.get("/").status_code == 200

def test_state_persists_across_restart(tmp_path):
    db = str(tmp_path / "p.db"); a = Lab(db, provider=P); a.scan(replay_days=120); eq = a.state()["equity"]
    b = Lab(db, provider=P); assert abs(b.state()["equity"] - eq) < 1e-6 and b.scan()["processed"] == 0
