"""Uc karar modu:
 A rule   : tamamen deterministik (backtest edilebilir)
 B hybrid : kural sinyali + LLM yalniz ONAY/AZALT/VETO diyebilir (boyutu artiramaz)
 C agent  : LLM aday onerir; yine risk motorundan ve stop kurallarindan gecer
LLM yoksa/erisilemezse sistem kural moduna duser ve bunu acikca bildirir."""
import json, os, re
from dataclasses import dataclass

@dataclass
class Verdict:
    action: str          # approve | reduce | veto
    size_mult: float
    rationale: str
    source: str

class RuleBrain:
    name = "rule"
    def decide(self, ctx):
        s = ctx["signal"]; reg = ctx["regime"]; pf = ctx["portfolio"]
        if reg in ("TREND_DOWN", "HIGH_VOL", "WARMUP"):
            return Verdict("veto", 0, f"Rejim {reg}: yeni alim yok", "rule")
        m = 0.6 + 0.4 * s.strength; why = [s.reason]
        if pf["exposure_pct"] > 0.7: m *= 0.5; why.append("portfoy %70+ dolu, boyut yariya")
        act = "approve" if m >= 0.85 else "reduce"
        return Verdict(act, round(m, 2), "; ".join(why), "rule")

class LLMClient:
    URL = "https://api.anthropic.com/v1/messages"
    def __init__(self, key=None, model=None):
        self.key = key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("TRADER_LLM_MODEL", "claude-sonnet-5-5")
    @property
    def available(self): return bool(self.key)
    def ask(self, system, user, max_tokens=500):
        import requests
        r = requests.post(self.URL, timeout=30, headers={"x-api-key": self.key, "anthropic-version": "2023-06-01",
                          "content-type": "application/json"},
                          json={"model": self.model, "max_tokens": max_tokens, "system": system,
                                "messages": [{"role": "user", "content": user}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])

def _json(text):
    m = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(m.group(0)) if m else None

SYS = ("Sen bir paper-trading risk komitesi uyesisin. Gercek para yok ama disiplinli davran. "
       "Sana deterministik hesaplanmis sinyal ozellikleri verilir. Yalniz JSON dondur: "
       '{"action":"approve|reduce|veto","size_mult":0..1,"rationale":"Turkce, en fazla 2 cumle, celiskileri belirt"}. '
       "Sayi uydurma; yalniz verilen verilere dayan. Emin degilsen reduce veya veto de.")

class HybridBrain:
    name = "hybrid"
    def __init__(self, llm: LLMClient): self.llm, self.rule = llm, RuleBrain()
    def decide(self, ctx):
        v = self.rule.decide(ctx)
        if v.action == "veto" or not self.llm.available: 
            if not self.llm.available and v.action != "veto": v.rationale += " [LLM yok: kural modu]"
            return v
        s = ctx["signal"]
        user = json.dumps({"sembol": ctx["symbol"], "borsa": ctx["market"], "strateji": s.strategy, "rejim": ctx["regime"],
                           "ozellikler": s.features, "gerekce": s.reason, "portfoy": ctx["portfolio"],
                           "strateji_gecmisi": ctx.get("stats", {})}, ensure_ascii=False)
        try:
            j = _json(self.llm.ask(SYS, user)) or {}
            act = j.get("action", "approve"); mult = float(j.get("size_mult", v.size_mult))
            if act not in ("approve", "reduce", "veto"): act = "reduce"
            mult = max(0.0, min(mult, v.size_mult))          # LLM boyutu ASLA artiramaz
            if act == "veto" or mult <= 0: return Verdict("veto", 0, j.get("rationale", "LLM veto"), "llm")
            return Verdict("reduce" if mult < v.size_mult - 1e-9 or act == "reduce" else "approve", mult,
                           f"{v.rationale} | LLM: {j.get('rationale','')}", "llm")
        except Exception as e:
            v.rationale += f" [LLM hatasi: {type(e).__name__}, kural modu]"; return v

SYS_AGENT = ("Sen bir portfoy yoneticisisin (paper-trading). Verilen aday tablosundan EN FAZLA 3 hisse sec. "
             'Yalniz JSON liste dondur: [{"symbol":"...","market":"...","conviction":0..1,"atr_mult":1.5..3.5,"rationale":"Turkce","invalidation":"Turkce"}]. '
             "Yalniz tabloda olan sembolleri sec; veri uydurma. Uygun aday yoksa [] dondur.")

class AgentBrain(HybridBrain):
    name = "agent"
    def propose(self, rows, portfolio):
        if not self.llm.available or not rows: return []
        try:
            out = _json(self.llm.ask(SYS_AGENT, json.dumps({"adaylar": rows, "portfoy": portfolio}, ensure_ascii=False), 900)) or []
            valid = {(r["market"], r["symbol"]) for r in rows}
            return [p for p in out if isinstance(p, dict) and (p.get("market"), p.get("symbol")) in valid][:3]
        except Exception:
            return []

def make_brain(mode, llm=None):
    llm = llm or LLMClient()
    return {"rule": RuleBrain, "hybrid": lambda: HybridBrain(llm), "agent": lambda: AgentBrain(llm)}[mode]()

def effective_mode(mode, llm=None):
    llm = llm or LLMClient()
    return mode if mode == "rule" or llm.available else "rule"
