from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from core import bus

app = FastAPI(title="Hivework", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/topics/{hive}/{topic}")
async def topic(hive: str, topic: str, count: int = 50):
    if not 1 <= count <= 500:
        raise HTTPException(status_code=400, detail="count must be between 1 and 500")
    try:
        events = await bus.latest(f"{hive}:{topic}", count)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc
    return {"hive": hive, "topic": topic, "events": events}


@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!doctype html><html><head><meta charset='utf-8'><title>Hivework</title>
    <style>body{font:16px system-ui;max-width:900px;margin:3rem auto;padding:0 1rem;background:#101820;color:#eef}pre{background:#1b2833;padding:1rem;border-radius:8px;overflow:auto}.muted{color:#adbac7}</style></head>
    <body><h1>Hivework</h1><p class='muted'>Local hive activity · demo mode</p><h2>Recent status</h2><pre id='events'>Loading…</pre>
    <script>async function refresh(){try{let r=await fetch('/api/topics/kalshi/status?count=30');let d=await r.json();document.querySelector('#events').textContent=JSON.stringify(d.events,null,2)}catch(e){document.querySelector('#events').textContent='Could not load status'} }refresh();setInterval(refresh,5000)</script></body></html>"""
