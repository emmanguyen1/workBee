from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse

from core import bus
from hives.kalshi.client import DemoUnavailable, portfolio

app = FastAPI(title="Hivework", version="0.1.0")


@app.get("/api/kalshi/portfolio")
async def demo_portfolio(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return await portfolio()
    except DemoUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    main{width:min(100% - 40px,1120px);margin:0 auto;padding:34px 0 64px}
    header{display:flex;align-items:center;justify-content:space-between;margin-bottom:40px}
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
    .section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:22px}
    .section-head h1{font-size:clamp(30px,4vw,40px)}
    .section-head .eyebrow{margin-bottom:7px}
    .snapshot-note{margin:0 0 4px;color:var(--muted);font-size:12px;text-align:right}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
    .metric{min-height:104px;padding:17px 19px}
    .metric .label{margin-bottom:8px}
    .metric-value{font-size:23px;font-weight:700;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
    .metric-value.positive{color:var(--green)}
    .negative{color:#ff9d9d}
    .metric small{display:block;color:var(--muted);font-size:11px;margin-top:6px}
    .portfolio{margin-bottom:34px}
    .positions{overflow:hidden}
    .portfolio-tabs{display:flex;align-items:center;gap:26px;padding:0 22px;border-bottom:1px solid var(--line)}
    .portfolio-tabs button{position:relative;padding:15px 0 13px;border:0;background:none;color:var(--muted);font:inherit;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
    .portfolio-tabs button[aria-selected="true"]{color:var(--text)}
    .portfolio-tabs button[aria-selected="true"]::after{position:absolute;right:0;bottom:-1px;left:0;height:2px;background:#a8c7ff;content:""}
    .empty-position{display:grid;justify-items:center;gap:7px;min-height:150px;align-content:center;color:var(--muted);text-align:center}
    .empty-icon{display:grid;place-items:center;width:38px;height:38px;margin-bottom:3px;border-radius:50%;background:#202a3c;color:#9eabc1;font-size:19px}
    .empty-position strong{color:#cbd4e5;font-size:15px}
    .empty-position span{font-size:13px}
    .hive-section{margin-top:0}
    .subhead{margin:0 0 15px;font-size:20px;letter-spacing:-.02em}
    @media(max-width:760px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @media(max-width:640px){main{width:min(100% - 28px,1120px);padding-top:26px}header{margin-bottom:32px}.section-head{align-items:flex-start;flex-direction:column}.snapshot-note{text-align:left;margin-top:-10px}.metrics{gap:9px}.metric{min-height:94px;padding:14px}.metric-value{font-size:20px}.grid{grid-template-columns:1fr}.summary{min-height:136px}.updated{min-height:122px}.updated time{margin-top:12px}.row{grid-template-columns:1fr auto;gap:6px;padding:10px 0}.row .mode{grid-column:1/-1}.rows{padding:0 18px}.history-head{padding:18px}.footer{font-size:11px}.portfolio-tabs{gap:20px;padding:0 16px}}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="brand"><span class="mark" aria-hidden="true">H</span><span>Hivework</span></div>
      <div class="live"><span class="live-dot" aria-hidden="true"></span>Live monitor</div>
    </header>
    <section class="portfolio" aria-labelledby="portfolio-title">
      <div class="section-head">
        <div><p class="eyebrow">Kalshi demo account</p><h1 id="portfolio-title">Portfolio</h1></div>
        <p class="snapshot-note">Connecting to Kalshi demo…</p>
      </div>
      <div class="metrics" aria-label="Demo portfolio metrics">
        <article class="card metric"><p class="label">Total account value</p><div id="account-total" class="metric-value">—</div></article>
        <article class="card metric"><p class="label">Cash</p><div id="account-cash" class="metric-value">—</div></article>
        <article class="card metric"><p class="label">Positions value</p><div id="account-value" class="metric-value">—</div></article>
        <article class="card metric"><p class="label">Open positions</p><div id="account-count" class="metric-value">—</div></article>
        <article class="card metric"><p class="label">Unrealized gain / loss</p><div id="account-pnl" class="metric-value">—</div><small id="pnl-detail">Current value minus position cost · before fees</small></article>
        <article class="card metric"><p class="label">Open position cost</p><div id="account-cost" class="metric-value">—</div><small>Cost of remaining contracts</small></article>
        <article class="card metric"><p class="label">Fees on open markets</p><div id="account-fees" class="metric-value">—</div><small>Reported fees, including earlier trades in these markets</small></article>
        <article class="card metric"><p class="label">Value change since opening page</p><div id="account-change" class="metric-value">—</div><small>Account value movement · includes deposits and trades</small></article>
      </div>
      <div class="card positions">
        <div class="portfolio-tabs" role="tablist" aria-label="Portfolio sections">
          <button type="button" role="tab" id="tab-positions" aria-selected="true" aria-controls="portfolio-empty" data-copy="No open positions">Positions</button>
          <button type="button" role="tab" id="tab-orders" aria-selected="false" aria-controls="portfolio-empty" data-copy="No open orders">Orders</button>
          <button type="button" role="tab" id="tab-history" aria-selected="false" aria-controls="portfolio-empty" data-copy="No portfolio history yet">History</button>
        </div>
        <div class="empty-position" id="portfolio-empty" role="tabpanel" aria-live="polite">
          <span class="empty-icon" aria-hidden="true">⌁</span><strong>No open positions</strong><span>Demo portfolio snapshot</span>
        </div>
      </div>
    </section>
    <section class="hive-section" aria-labelledby="hive-title">
      <div class="section-head"><div><p class="eyebrow">Kalshi hive</p><h2 class="subhead" id="hive-title">Hive status</h2></div><p class="snapshot-note">Read-only demo connection</p></div>
      <p class="intro">Live connection to your Kalshi demo account.</p>
      <section class="grid" aria-label="Current hive status">
      <div class="card summary">
        <div><p class="label">Current state</p><div id="current-state" class="state"><span class="state-dot" aria-hidden="true"></span><span>Loading</span></div></div>
        <span class="pill">Demo only</span>
      </div>
      <div class="card updated"><p class="label">Last update</p><time id="last-update">—</time><small id="update-relative">Waiting for Kalshi demo</small></div>
    </section>
      <section class="card history" aria-labelledby="history-title">
        <div class="history-head"><h2 id="history-title">Recent connection checks</h2><span id="event-count" class="count">Loading</span></div>
        <div id="events" class="rows" aria-live="polite"><div class="message">Connecting to the status stream…</div></div>
      </section>
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
        const status=document.createElement('span');status.className='row-state';const dot=document.createElement('span');dot.className='state-dot'+(['running','connected'].includes(String(event.state).toLowerCase())?'':' idle');dot.setAttribute('aria-hidden','true');const label=document.createElement('span');label.textContent=String(event.state||'unknown');status.append(dot,label);
        const mode=document.createElement('span');mode.className='mode';mode.textContent=String(event.mode||'—');row.append(stamp,status,mode);eventsNode.append(row)
      }
    }
    let portfolioData=null;
    let startingValue=null;
    const checks=[];
    const money=cents=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(cents)/100);
    function amount(selector,value,signed=false){
      const node=document.querySelector(selector);
      node.textContent=value==null?'Unavailable':(signed&&value>0?'+':'')+money(value);
      node.classList.toggle('positive',signed&&value>0);node.classList.toggle('negative',signed&&value<0);
    }
    function showPortfolio(){
      const panel=document.querySelector('#portfolio-empty');panel.replaceChildren();
      const selected=document.querySelector('[role="tab"][aria-selected="true"]').id;
      const kind=selected==='tab-positions'?'positions':selected==='tab-orders'?'orders':'fills';
      const items=portfolioData?.[kind]||[];
      if(!portfolioData||!items.length){
        const title=document.createElement('strong');title.textContent=portfolioData?(kind==='fills'?'No recent fills':`No open ${kind}`):'Waiting for live demo data';
        const note=document.createElement('span');note.textContent=kind==='fills'?'Most recent 50 fills':'Kalshi demo · read only';panel.append(title,note);return;
      }
      panel.style.display='block';panel.style.textAlign='left';panel.style.padding='0 24px';
      for(const item of items){
        const row=document.createElement('div');row.className='row';
        const ticker=document.createElement('strong');ticker.textContent=item.ticker||item.market_ticker||'Market';
        const detail=document.createElement('span');
        detail.textContent=kind==='positions'?`Position: ${item.position_fp??item.position??'—'}`:`${item.action||''} ${item.side||''} · ${item.remaining_count_fp??item.remaining_count??item.count_fp??item.count??'—'} contracts`;
        if(kind==='positions'&&item.market_exposure_dollars!=null)detail.textContent+=` · Cost ${money(Number(item.market_exposure_dollars)*100)}`;
        const extra=document.createElement('span');extra.className='mode';extra.textContent=kind==='positions'?'Open position':(item.created_time||item.status||'');
        row.append(ticker,detail,extra);panel.append(row);
      }
    }
    for(const tab of document.querySelectorAll('[role="tab"]')){
      tab.addEventListener('click',()=>{
        document.querySelectorAll('[role="tab"]').forEach(item=>item.setAttribute('aria-selected',String(item===tab)));showPortfolio();
      });
    }
    async function refresh(){
      try{
        const response=await fetch('/api/kalshi/portfolio',{cache:'no-store'});
        const data=await response.json();if(!response.ok)throw new Error(data.detail||'Kalshi demo unavailable');
        portfolioData=data;
        document.querySelector('#account-total').textContent=money(data.cash_cents+data.positions_value_cents);
        document.querySelector('#account-cash').textContent=money(data.cash_cents);
        document.querySelector('#account-value').textContent=money(data.positions_value_cents);
        document.querySelector('#account-count').textContent=data.positions.length;
        amount('#account-pnl',data.unrealized_pnl_cents,true);
        amount('#account-cost',data.open_cost_cents);
        amount('#account-fees',data.open_market_fees_cents);
        const total=data.cash_cents+data.positions_value_cents;
        if(startingValue===null)startingValue=total;
        amount('#account-change',total-startingValue,true);
        const percent=data.unrealized_return_percent;
        const direction=data.unrealized_pnl_cents==null?'Return unavailable':data.unrealized_pnl_cents>0?'Gaining value':data.unrealized_pnl_cents<0?'Losing value':'Break even';
        document.querySelector('#pnl-detail').textContent=direction+(percent==null?'':` · ${percent>0?'+':''}${percent.toFixed(2)}%`)+' · before fees';
        showPortfolio();
        const stamp=new Date(data.updated_at);
        document.querySelector('.portfolio .snapshot-note').textContent=`Live demo · updated ${stamp.toLocaleTimeString()}`;
        checks.push({id:String(stamp.getTime())+'-0',state:'connected',mode:'Kalshi demo · read only'});if(checks.length>10)checks.shift();
        render(checks);document.querySelector('#current-state .state-dot').classList.remove('idle');
        document.querySelector('#refresh-time').textContent='Refreshes every 15 seconds';
        document.querySelector('.live').lastChild.textContent='Live demo';
      }catch(error){
        document.querySelector('.portfolio .snapshot-note').textContent=portfolioData?'Connection lost · showing last successful update':'Kalshi demo unavailable';
        document.querySelector('#event-count').textContent='Unavailable';document.querySelector('#current-state').lastElementChild.textContent='Disconnected';
        document.querySelector('#current-state .state-dot').classList.add('idle');
        document.querySelector('#update-relative').textContent=portfolioData?'Last successful connection':'No successful connection';
        setMessage(error.message,true);document.querySelector('#refresh-time').textContent='Retrying automatically';
        document.querySelector('.live').lastChild.textContent='Disconnected';
      }
    }
    refresh();setInterval(refresh,15000);
  </script>
</body>
</html>"""
