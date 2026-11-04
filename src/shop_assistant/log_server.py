"""Live agent steps on port 8002. Memory only. Dies with the API process."""

import threading

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Agent logs</title>
<style>
  body{margin:0;font:15px/1.4 ui-sans-serif,system-ui,sans-serif;background:#101412;color:#e7eee9}
  header{position:sticky;top:0;padding:16px 20px;background:#17201b;border-bottom:1px solid #2a3830}
  h1{margin:0;font-size:18px}
  p{margin:4px 0 0;color:#9aaba1}
  main{max-width:760px;margin:0 auto;padding:16px}
  .now{padding:14px 16px;border-radius:12px;background:#1e2b24;margin-bottom:14px}
  .now b{display:block;font-size:18px}
  .now.bad{background:#3a1c1c}
  article{display:grid;grid-template-columns:88px 1fr;gap:8px;
    padding:10px 0;border-top:1px solid #24302a}
  time{color:#8ea094;font-size:12px}
  .bad b{color:#ffb4b4}
  .empty{color:#8ea094}
</style>
</head>
<body>
<header><h1>Agent logs</h1><p>Live for this API run. Nothing is saved.</p></header>
<main>
<div id="now" class="now"><b>Idle</b><span>Waiting for the agent.</span></div>
<div id="list"></div>
</main>
<script>
async function tick(){
  const rows = await fetch('/steps').then(r => r.json());
  const now = document.getElementById('now');
  const list = document.getElementById('list');
  if(!rows.length){
    now.className = 'now';
    now.innerHTML = '<b>Idle</b><span>Waiting for the agent.</span>';
    list.innerHTML = '<p class="empty">No steps yet.</p>';
    return;
  }
  const top = rows[0];
  now.className = top.ok ? 'now' : 'now bad';
  now.innerHTML = '<b>'+top.name+'</b><span>'+top.detail+'</span>';
  list.innerHTML = rows.map(row => {
    const clock = new Date(row.created_at*1000).toLocaleTimeString();
    const who = row.conversation_id == null ? '' : 'Session '+row.conversation_id;
    return '<article class="'+(row.ok?'':'bad')+'"><time>'+clock
      +'</time><div><b>'+row.name+'</b> '+who
      +'<div>'+row.detail+'</div></div></article>';
  }).join('');
}
tick();
setInterval(() => tick().catch(() => {}), 1000);
</script>
</body>
</html>
"""


def start_log_server(port: int = 8002) -> None:
    """Serve the live log page. Safe to call once from the API lifespan."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse
    from starlette.routing import Route

    from shop_assistant.services.batch import recent_steps

    async def home(_: Request) -> HTMLResponse:
        return HTMLResponse(PAGE)

    async def steps(_: Request) -> JSONResponse:
        return JSONResponse(recent_steps())

    app = Starlette(routes=[Route("/", home), Route("/steps", steps)])

    def run() -> None:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    threading.Thread(target=run, daemon=True, name="agent-logs").start()
