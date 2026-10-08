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
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1020">
  <title>Hivework · Hive status</title>
  <style>
    :root{color-scheme:dark;--bg:#0b1020;--panel:#121a2b;--line:#253047;--text:#edf2ff;--muted:#98a5bd;--green:#55d6a0;--amber:#ffc66d}
    *{box-sizing:border-box}
    body{margin:0;min-height:100vh;background:radial-gradient(ellipse at 50% -20%,#263754 0,transparent 55%),var(--bg);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    main{width:min(100% - 40px,960px);margin:0 auto;padding:42px 0 64px}
    header{display:flex;align-items:center;justify-content:space-between;margin-bottom:54px}
    .brand{display:flex;align-items:center;gap:11px;font-size:16px;font-weight:700;letter-spacing:.01em}
    .mark{display:grid;place-items:center;width:36px;height:36px;border:1px solid #35425d;border-radius:12px;background:#18243a;color:#a8c7ff;font-size:17px}
    .live{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}
    .live-dot,.state-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 12px #55d6a066}
    .eyebrow{margin:0 0 10px;color:#91a8cf;font-size:12px;font-weight:700;letter-spacing:.13em;text-transform:uppercase}
    h1{margin:0;font-size:clamp(32px,5vw,46px);line-height:1.1;letter-spacing:-.04em}
    .intro{margin:12px 0 30px;color:var(--muted);font-size:16px}
    .grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(220px,.8fr);gap:16px;margin-bottom:24px}
    .card{border:1px solid var(--line);border-radius:18px;background:linear-gradient(145deg,#151f33,#101727);box-shadow:0 16px 40px #0002}
    .summary{display:flex;align-items:center;justify-content:space-between;min-height:156px;padding:26px 28px}
    .label{margin:0 0 12px;color:var(--muted);font-size:13px;font-weight:600}
    .state{display:flex;align-items:center;gap:12px;font-size:30px;font-weight:700;letter-spacing:-.03em;text-transform:capitalize}
    .state-dot{width:11px;height:11px}
    .state-dot.idle{background:var(--amber);box-shadow:0 0 12px #ffc66d55}
    .pill{display:inline-flex;align-items:center;min-height:30px;padding:0 11px;border:1px solid #655035;border-radius:99px;background:#332719;color:#ffdba4;font-size:12px;font-weight:700}
    .updated{min-height:156px;padding:26px 24px}
    .updated time{display:block;margin-top:20px;font-size:20px;font-weight:650;letter-spacing:-.02em}
    .updated small{display:block;margin-top:4px;color:var(--muted)}
    .history{overflow:hidden}
    .history-head{display:flex;align-items:center;justify-content:space-between;padding:21px 24px;border-bottom:1px solid var(--line)}
    h2{margin:0;font-size:16px;letter-spacing:-.01em}
    .count{color:var(--muted);font-size:12px}
    .rows{padding:0 24px}
    .row{display:grid;grid-template-columns:minmax(120px,1fr) minmax(80px,.6fr) auto;align-items:center;gap:12px;min-height:58px;border-bottom:1px solid #202a3c}
    .row:last-child{border-bottom:0}
    .row time{color:#c5cee0;font-variant-numeric:tabular-nums;font-size:13px}
    .row-state{display:flex;align-items:center;gap:8px;font-weight:600;text-transform:capitalize}
    .row .state-dot{width:7px;height:7px}
    .mode{color:var(--muted);font-size:12px}
    .message{padding:28px 24px;color:var(--muted)}
    .footer{display:flex;justify-content:space-between;gap:12px;margin-top:17px;color:#7e8ba4;font-size:12px}
    .error{color:#ff9d9d}
    @media(max-width:640px){main{width:min(100% - 28px,960px);padding-top:26px}header{margin-bottom:40px}.grid{grid-template-columns:1fr}.summary{min-height:136px}.updated{min-height:122px}.updated time{margin-top:12px}.row{grid-template-columns:1fr auto;gap:6px;padding:10px 0}.row .mode{grid-column:1/-1}.rows{padding:0 18px}.history-head{padding:18px}.footer{font-size:11px}}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand"><span class="mark" aria-hidden="true">H</span><span>Hivework</span></div>
      <div class="live"><span class="live-dot" aria-hidden="true"></span>Live monitor</div>
    </header>
    <p class="eyebrow">Kalshi hive</p>
    <h1>Hive status</h1>
    <p class="intro">A live view of the latest bot activity.</p>
    <section class="grid" aria-label="Current hive status">
      <div class="card summary">
        <div><p class="label">Current state</p><div id="current-state" class="state"><span class="state-dot" aria-hidden="true"></span><span>Loading</span></div></div>
        <span class="pill">Demo only</span>
      </div>
      <div class="card updated"><p class="label">Last update</p><time id="last-update">—</time><small id="update-relative">Waiting for status</small></div>
    </section>
    <section class="card history" aria-labelledby="history-title">
      <div class="history-head"><h2 id="history-title">Recent activity</h2><span id="event-count" class="count">Loading</span></div>
      <div id="events" class="rows" aria-live="polite"><div class="message">Connecting to the status stream…</div></div>
    </section>
    <div class="footer"><span>Refreshes automatically</span><span id="refresh-time">—</span></div>
  </main>
  <script>
    const eventsNode=document.querySelector('#events');
    function eventTime(id){const ms=Number(String(id).split('-')[0]);return Number.isFinite(ms)?new Date(ms):null}
    function setMessage(text,isError=false){eventsNode.innerHTML='';const message=document.createElement('div');message.className='message'+(isError?' error':'');message.textContent=text;eventsNode.append(message)}
    function render(events){
      const newest=[...events].reverse();
      document.querySelector('#event-count').textContent=`${events.length} update${events.length===1?'':'s'}`;
      if(!newest.length){document.querySelector('#current-state').lastElementChild.textContent='No data';document.querySelector('#last-update').textContent='—';document.querySelector('#update-relative').textContent='No events received';setMessage('No status events yet.');return}
      const latest=newest[0],state=String(latest.state||'unknown');
      document.querySelector('#current-state').lastElementChild.textContent=state;
      document.querySelector('#current-state').querySelector('.state-dot').classList.toggle('idle',state.toLowerCase()!=='running');
      const time=eventTime(latest.id),timeNode=document.querySelector('#last-update');
      timeNode.textContent=time?time.toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'}):'Unknown';
      timeNode.dateTime=time?time.toISOString():'';
      document.querySelector('#update-relative').textContent=time?time.toLocaleDateString([],{month:'short',day:'numeric',year:'numeric'}):'Timestamp unavailable';
      eventsNode.innerHTML='';
      for(const event of newest.slice(0,10)){
        const row=document.createElement('div');row.className='row';
        const stamp=document.createElement('time');const eventDate=eventTime(event.id);stamp.textContent=eventDate?eventDate.toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit'}):'Unknown time';if(eventDate)stamp.dateTime=eventDate.toISOString();
        const status=document.createElement('span');status.className='row-state';const dot=document.createElement('span');dot.className='state-dot'+(String(event.state).toLowerCase()==='running'?'':' idle');dot.setAttribute('aria-hidden','true');const label=document.createElement('span');label.textContent=String(event.state||'unknown');status.append(dot,label);
        const mode=document.createElement('span');mode.className='mode';mode.textContent=String(event.mode||'—');row.append(stamp,status,mode);eventsNode.append(row)
      }
    }
    async function refresh(){
      try{const response=await fetch('/api/topics/kalshi/status?count=30',{cache:'no-store'});if(!response.ok)throw new Error(`Status request failed (${response.status})`);const data=await response.json();render(data.events||[]);document.querySelector('#refresh-time').textContent=`Updated ${new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}`}
      catch(error){document.querySelector('#event-count').textContent='Unavailable';document.querySelector('#current-state').lastElementChild.textContent='Offline';document.querySelector('#current-state').querySelector('.state-dot').classList.add('idle');document.querySelector('#last-update').textContent='—';document.querySelector('#update-relative').textContent='Could not reach the status stream';setMessage('Status data is temporarily unavailable. Retrying automatically.',true);document.querySelector('#refresh-time').textContent='Retrying'}
    }
    refresh();setInterval(refresh,5000);
  </script>
</body>
</html>"""
