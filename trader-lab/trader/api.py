import math, os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .lab import Lab
from .strategies import ALL

STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if hasattr(o, "item"): o = o.item()
    if isinstance(o, float) and (math.isinf(o) or math.isnan(o)): return None
    return o

class Cfg(BaseModel):
    mode: str | None = None; funding: str | None = None; base: str | None = None
    capital: float | None = None; markets: list[str] | None = None; per_market: int | None = None; source: str | None = None

def create_app(lab: Lab | None = None):
    app = FastAPI(title="trader-lab"); L = lab or Lab()
    import threading
    def warm():
        try: L.state()
        except Exception as e: print("[veri] onyukleme hatasi:", repr(e), flush=True)
    threading.Thread(target=warm, daemon=True).start()
    def guard(fn, *a, **k):
        try: return clean(fn(*a, **k))
        except ValueError as e: raise HTTPException(400, str(e))
        except Exception as e: raise HTTPException(500, f"{type(e).__name__}: {e}")
    @app.get("/api/state")
    def state(): return guard(L.state)
    @app.post("/api/config")
    def config(c: Cfg): return guard(L.configure, **c.model_dump())
    @app.post("/api/scan")
    def scan(replay_days: int = 0): return guard(L.scan, min(max(replay_days, 0), 400))
    @app.post("/api/reset")
    def reset(): L.reset(); return {"ok": True}
    @app.get("/api/journal")
    def journal(limit: int = 100, action: str | None = None): return guard(L.journal, min(limit, 500), action)
    @app.get("/api/analytics")
    def analytics(): return guard(L.analytics)
    @app.get("/api/ledger/verify")
    def verify(): ok, bad = L.ledger.verify(); return {"ok": ok, "first_bad_id": bad}
    @app.post("/api/backtest")
    def backtest(): return guard(L.backtest)
    @app.post("/api/compare-funding")
    def cmp(): return guard(L.compare_funding)
    @app.post("/api/walkforward")
    def wf(strategy: str = "trend"):
        if strategy not in ALL: raise HTTPException(400, "strateji")
        return guard(L.walkforward, strategy)
    @app.get("/api/health")
    def health(): return {"ok": True}
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    @app.get("/")
    def index(): return FileResponse(os.path.join(STATIC, "index.html"))
    return app

app = None
def get_app():
    global app
    app = app or create_app(); return app
