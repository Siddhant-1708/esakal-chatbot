import asyncio
import json
import time
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from schemas import ChatRequest, ChatResponse
from app.agents.workflow import graph
from app.agents.state import GraphState
from app import quintype, smartflow
from app.claude_client import call_answer
from app.config import SAKAL_PLUS_SUBSCRIPTION_URL, SUGGESTIONS_CACHE_TTL, SMARTFLOW_XML_DIR, SMARTFLOW_INDEX_URL

limiter = Limiter(key_func=get_remote_address)
smartflow.init(SMARTFLOW_XML_DIR, index_url=SMARTFLOW_INDEX_URL)

# Cost rates (USD per 1M tokens) — update when pricing changes
_COST_RATES = {
    "openai":  {"prompt": 0.15,  "completion": 0.60},   # gpt-4o-mini
    "groq":    {"prompt": 0.0,   "completion": 0.0},    # free tier
}

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ask Esakal — Token Usage Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; }
  header { background: #c0392b; color: #fff; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 1.3rem; }
  header small { opacity: .8; font-size: .8rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; padding: 24px; }
  .card { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
  .card h3 { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: #888; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; color: #c0392b; }
  .card .sub { font-size: .8rem; color: #555; margin-top: 4px; }
  .card.hero { border-top: 4px solid #c0392b; }
  .card.hero-cost { border-top-color: #27ae60; }
  .card.hero-cost .value { color: #27ae60; }
  .hero-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; padding: 24px 24px 0; }
  .section-label { padding: 20px 24px 4px; font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; color: #aaa; font-weight: 600; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 0 24px 24px; }
  @media (max-width: 700px) { .charts { grid-template-columns: 1fr; } }
  .chart-card { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
  .chart-card h3 { font-size: .85rem; font-weight: 600; margin-bottom: 12px; color: #555; }
  .actions { padding: 0 24px 24px; display: flex; gap: 12px; }
  button { padding: 8px 18px; border-radius: 6px; border: none; cursor: pointer; font-size: .9rem; }
  .btn-reset { background: #e74c3c; color: #fff; }
  .btn-refresh { background: #3498db; color: #fff; }
  .refresh-note { font-size: .75rem; color: #888; padding: 0 24px 12px; }
</style>
</head>
<body>
<header>
  <h1>Ask Esakal — Token Usage Dashboard</h1>
  <small id="last-updated">Loading…</small>
</header>
<p class="section-label">Overview</p>
<div class="hero-row" id="hero-cards"></div>
<p class="section-label">By Provider</p>
<div class="hero-row" id="provider-cards"></div>
<div class="actions">
  <button class="btn-refresh" onclick="load()">Refresh</button>
  <button class="btn-reset" onclick="resetStats()">Reset All</button>
</div>
<p class="refresh-note">Auto-refreshes every 30 seconds.</p>
<div class="charts">
  <div class="chart-card"><h3>Daily Token Usage</h3><canvas id="dailyChart"></canvas></div>
  <div class="chart-card"><h3>Provider Breakdown (total tokens)</h3><canvas id="providerChart"></canvas></div>
</div>
<script>
// USD per 1M tokens converted to INR (1 USD ≈ 84 INR)
const USD_TO_INR = 95.11;
const RATES = {openai:{prompt:0.15*USD_TO_INR,completion:0.60*USD_TO_INR},groq:{prompt:0,completion:0}};
let dailyChartInst, providerChartInst;

function fmt(n){if(n>=1e6)return(n/1e6).toFixed(2)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'k';return n;}
function cost(p,pt,ct){const r=RATES[p]||{prompt:0,completion:0};return((pt/1e6)*r.prompt+(ct/1e6)*r.completion);}
function fmtCost(c){return c<1?'<₹1':'₹'+c.toFixed(2);}

async function load(){
  const res = await fetch('/stats');
  const data = await res.json();
  renderCards(data);
  renderCharts(data);
  document.getElementById('last-updated').textContent='Updated '+new Date().toLocaleTimeString();
}

function renderCards(data){
  const totals=data.token_usage||{};
  let grandTotal=0,grandCost=0,grandCalls=0;
  let providerHtml='';
  for(const[p,t] of Object.entries(totals)){
    const total=(t.prompt_tokens||0)+(t.completion_tokens||0);
    const c=cost(p,t.prompt_tokens||0,t.completion_tokens||0);
    grandTotal+=total;grandCost+=c;grandCalls+=t.calls||0;
    providerHtml+=`
      <div class="card hero">
        <h3>${p.toUpperCase()} — Tokens</h3>
        <div class="value">${fmt(total)}</div>
        <div class="sub">${fmt(t.prompt_tokens||0)} prompt / ${fmt(t.completion_tokens||0)} completion</div>
        <div class="sub">${t.calls||0} calls</div>
      </div>
      <div class="card hero hero-cost">
        <h3>${p.toUpperCase()} — Est. Cost</h3>
        <div class="value">${fmtCost(c)}</div>
        <div class="sub">${p==='groq'?'Free tier':'gpt-4o-mini rates'}</div>
      </div>`;
  }
  document.getElementById('hero-cards').innerHTML=`
    <div class="card hero">
      <h3>Total Tokens</h3>
      <div class="value">${fmt(grandTotal)}</div>
      <div class="sub">${grandCalls} total API calls</div>
    </div>
    <div class="card hero hero-cost">
      <h3>Total Est. Cost</h3>
      <div class="value">${fmtCost(grandCost)}</div>
      <div class="sub">@ ₹${USD_TO_INR}/USD</div>
    </div>`;
  document.getElementById('provider-cards').innerHTML=providerHtml||'<div class="card"><div class="sub">No data yet.</div></div>';
}

function renderCharts(data){
  const daily=data.daily||{};
  const days=Object.keys(daily).sort();
  const dsOpenai=days.map(d=>(daily[d].openai?.prompt_tokens||0)+(daily[d].openai?.completion_tokens||0));
  const dsGroq=days.map(d=>(daily[d].groq?.prompt_tokens||0)+(daily[d].groq?.completion_tokens||0));

  if(dailyChartInst)dailyChartInst.destroy();
  dailyChartInst=new Chart(document.getElementById('dailyChart'),{
    type:'bar',
    data:{labels:days,datasets:[
      {label:'OpenAI',data:dsOpenai,backgroundColor:'#e74c3c'},
      {label:'Groq',data:dsGroq,backgroundColor:'#3498db'},
    ]},
    options:{responsive:true,scales:{x:{stacked:true},y:{stacked:true}}}
  });

  const totals=data.token_usage||{};
  const labels=Object.keys(totals);
  const vals=labels.map(p=>(totals[p].prompt_tokens||0)+(totals[p].completion_tokens||0));
  if(providerChartInst)providerChartInst.destroy();
  providerChartInst=new Chart(document.getElementById('providerChart'),{
    type:'doughnut',
    data:{labels,datasets:[{data:vals,backgroundColor:['#e74c3c','#3498db','#2ecc71']}]},
    options:{responsive:true}
  });
}

async function resetStats(){
  if(!confirm('Reset all token usage data?'))return;
  await fetch('/stats/reset',{method:'POST'});
  load();
}

load();
setInterval(load,30000);
</script>
</body>
</html>"""


async def _validation_error_handler(request: Request, exc: RequestValidationError):
    print(f"[422] {request.method} {request.url.path} — {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
app = FastAPI(title="Ask Esakal")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(RequestValidationError, _validation_error_handler)

BASE_DIR = Path(__file__).parent
app.mount("/widget", StaticFiles(directory=BASE_DIR / "widget"), name="widget")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FALLBACK_SUGGESTIONS = [
    "What happened in Maharashtra today?",
    "What is the latest on Pune?",
    "What did the state government announce this week?",
    "Explain the latest political developments in Maharashtra.",
]

def _build_initial_state(body: ChatRequest) -> GraphState:
    return GraphState(
        question=body.question,
        source=body.source,
        lang=body.lang,
        history=body.history,
        analysis=None,
        current_query=None,
        chunks=[],
        sources=[],
        attempts=0,
        context_enough=False,
        generic_query=False,
        suggested_query=None,
        steps=[],
        response=None,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    from app import usage_store
    return {
        "token_usage": usage_store.get_totals(),
        "daily": usage_store.get_daily(),
        "smartflow_indexed": smartflow.is_ready(),
    }


@app.post("/stats/reset")
async def stats_reset():
    from app import usage_store
    usage_store.reset()
    return {"status": "reset"}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return _DASHBOARD_HTML


@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    from app.claude_client import AllProvidersRateLimited
    from fastapi import HTTPException
    state = _build_initial_state(body)
    try:
        result = await graph.ainvoke(state)
    except AllProvidersRateLimited as e:
        raise HTTPException(status_code=503, detail=str(e))
    return result["response"]


@app.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(request: Request, body: ChatRequest):
    async def event_stream() -> AsyncGenerator[str, None]:
        state = _build_initial_state(body)
        try:
            async for event in graph.astream(state):
                for node_name, node_state in event.items():
                    steps = node_state.get("steps", [])
                    if steps:
                        latest_step = steps[-1]
                        note = {
                            "title": latest_step.title,
                            "detail": latest_step.detail,
                            "source_numbers": latest_step.source_numbers,
                        }
                        yield f"data: {json.dumps({'kind': 'process', 'note': note})}\n\n"

            final_state = await graph.ainvoke(_build_initial_state(body))
            response = final_state["response"]
            yield f"data: {json.dumps({'kind': 'final', 'response': response.model_dump()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'kind': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


FALLBACK_SUGGESTIONS_MR = [
    "आज महाराष्ट्रात काय घडले?",
    "पुण्यातील ताज्या बातम्या काय आहेत?",
    "राज्य सरकारने या आठवड्यात काय जाहीर केले?",
    "महाराष्ट्रातील राजकीय घडामोडी काय आहेत?",
]

_suggestions_cache: dict = {"mr": {"data": None, "expires": 0}, "en": {"data": None, "expires": 0}}

SKIP_KEYWORDS = [
    "chapati", "diet", "weight", "health", "recipe", "food", "skin", "hair",
    "beauty", "yoga", "exercise", "surgery", "actress", "actor", "celebrity",
    "panchang", "rashifal", "horoscope", "rashī", "zodiac", "festival",
    "bandage", "nasal", "plastic", "wellness", "ayurved",
]


@app.get("/suggestions")
async def get_suggestions(lang: str = "mr"):
    if lang not in ("mr", "en"):
        lang = "mr"
    now = time.time()
    cache = _suggestions_cache[lang]
    if cache["data"] and now < cache["expires"]:
        return {"suggestions": cache["data"]}

    fallback = FALLBACK_SUGGESTIONS_MR if lang == "mr" else FALLBACK_SUGGESTIONS

    try:
        articles = await quintype.top_stories(limit=5)
        headlines = [a.get("headline", "") for a in articles if a.get("headline")]
        if not headlines:
            return {"suggestions": fallback}

        news_headlines = [
            h for h in headlines
            if not any(kw in h.lower() for kw in SKIP_KEYWORDS)
        ] or headlines

        if lang == "mr":
            prompt = (
                "खालील ई सकाळ बातम्यांच्या शीर्षकांवर आधारित, वाचकाला विचारता येतील असे नेमके ४ लहान प्रश्न मराठीत तयार करा.\n"
                "नियम:\n"
                "- प्रश्न राजकारण, सरकार, महाराष्ट्र, गुन्हेगारी, अर्थव्यवस्था किंवा स्थानिक नागरी विषयांवर असावेत.\n"
                "- आरोग्य टिप्स, जेवण, सेलिब्रिटी, ज्योतिष किंवा जीवनशैलीबद्दल प्रश्न नको.\n"
                "- प्रत्येक प्रश्न दिलेल्या शीर्षकांपैकी एकावर थेट उत्तर देता येणारा असावा.\n"
                "- सर्व प्रश्न मराठीतच लिहा.\n"
                "- फक्त ४ स्ट्रिंग्सचा JSON array परत करा. markdown नको.\n\n"
                "शीर्षके:\n"
                + "\n".join(f"- {h}" for h in news_headlines)
                + "\n\nफक्त JSON द्या."
            )
        else:
            prompt = (
                "Given these Esakal news headlines, generate exactly 4 short questions in English "
                "that a reader could ask and get a direct answer from these specific news stories.\n"
                "Rules:\n"
                "- Questions MUST be about politics, government, Maharashtra news, crime, economy, or local civic issues.\n"
                "- Do NOT generate questions about health tips, diets, recipes, celebrity gossip, plastic surgery, astrology, festivals, or lifestyle.\n"
                "- Each question must be directly answerable from one of the headlines provided.\n"
                "- Write all questions in English only, even if the headlines are in Marathi.\n"
                "- Return a JSON array of exactly 4 strings. No extra fields, no markdown.\n\n"
                "Headlines:\n"
                + "\n".join(f"- {h}" for h in news_headlines)
                + "\n\nRespond with JSON only."
            )

        raw = call_answer("", [{"role": "user", "content": prompt}])
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        suggestions = json.loads(raw)[:4]
        if SUGGESTIONS_CACHE_TTL > 0:
            cache["data"] = suggestions
            cache["expires"] = now + SUGGESTIONS_CACHE_TTL
        return {"suggestions": suggestions}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[suggestions] error: {e}")
        return {"suggestions": fallback}


@app.get("/", response_class=HTMLResponse)
async def demo_page():
    html = (BASE_DIR / "widget" / "demo.html").read_text()
    return html.replace("__SAKAL_PLUS_URL__", SAKAL_PLUS_SUBSCRIPTION_URL)


if __name__ == "__main__":
    import uvicorn
    from app.config import PORT
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
