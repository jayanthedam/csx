"""csx ui — tiny local web front-end for the csx session index.

Served by csx itself (`csx ui`). No deps, no build step, no external requests.
Click a row to copy its resume command; click the id chip to copy the raw id.
"""
import html as _html
import json
import os
import re
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PAGE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>csx — sessions</title>
<style>
:root{--bg:#fff;--fg:#111;--dim:#6b7280;--line:#e5e7eb;--hl:#fde68a;--card:#f9fafb;
      --cc:#0284c7;--cx:#b45309;--sa:#6b7280;--acc:#2563eb}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0b0d10;--fg:#e5e7eb;--dim:#8b95a5;--line:#1f2530;--hl:#7c5f10;--card:#12161c;--acc:#60a5fa;
      --cc:#38bdf8;--cx:#fbbf24;--sa:#9ca3af}}
:root[data-theme="dark"]{--bg:#0b0d10;--fg:#e5e7eb;--dim:#8b95a5;--line:#1f2530;--hl:#7c5f10;--card:#12161c;--acc:#60a5fa;--cc:#38bdf8;--cx:#fbbf24;--sa:#9ca3af}
*{box-sizing:border-box}
body{margin:0;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 14px;z-index:5}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
input[type=search]{flex:1;min-width:220px;padding:7px 10px;border:1px solid var(--line);border-radius:6px;
  background:var(--card);color:var(--fg);font:inherit}
button,select{padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);
  color:var(--fg);font:inherit;cursor:pointer}
button.on{border-color:var(--acc);color:var(--acc)}
#folder{max-width:250px}
select{max-width:170px}
.hint{color:var(--dim);font-size:12px;padding-top:6px}
main{padding:6px 0 40px}
.row{display:grid;grid-template-columns:72px 88px 122px 68px 148px 1fr 86px;gap:10px;align-items:baseline;
  padding:6px 14px;border-bottom:1px solid var(--line);cursor:pointer}
.row:hover{background:var(--card)}
.tag{font-size:10.5px;font-weight:700;letter-spacing:.03em;text-align:center;border-radius:999px;
  padding:1px 0;border:1px solid currentColor}
.claude{color:var(--cc)}.codex{color:var(--cx)}.subagent{color:var(--sa)}
.id{color:var(--dim);cursor:copy}
.id:hover{color:var(--acc);text-decoration:underline}
.when,.turns,.proj{color:var(--dim);font-size:12px}
.act{opacity:0;text-align:right;color:var(--acc);font-size:11.5px;white-space:nowrap}
.row:hover .act{opacity:1}
.proj{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hits{padding:2px 14px 8px 184px;color:var(--dim);font-size:12px}
.hits b{color:var(--fg);opacity:.65;font-weight:600}
.empty{padding:40px 14px;color:var(--dim);text-align:center}
.hits div{padding:1px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
mark{background:var(--hl);color:inherit}
#toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--fg);color:var(--bg);
  padding:8px 14px;border-radius:6px;opacity:0;transition:.15s;pointer-events:none;font-size:12px}
#toast.show{opacity:1}
#panel{position:fixed;inset:0;background:var(--bg);display:none;flex-direction:column}
#panel.open{display:flex}
#phead{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#pbody{overflow:auto;padding:12px 14px}
.turn{border-left:2px solid var(--line);padding:2px 0 10px 10px;margin-bottom:10px}
.turn b{font-size:11px;letter-spacing:.04em}
.turn.user{border-color:var(--acc)}
.turn pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-word;font:inherit}
.cmd{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;cursor:copy}
.cmd:hover{border-color:var(--acc)}
</style>
<header>
  <div class="bar">
    <input type="search" id="q" placeholder="Search sessions…" autofocus>
    <span style="color:var(--dim)">search in:</span>
    <button id="mTitle" class="on" title="Match the session title only — instant">Titles</button>
    <button id="mDeep" title="Match anything you or the agent said">Messages</button>
    <button id="mGlob" title="Messages + tool calls + subagent runs">Everything</button>
    <select id="folder" title="Limit to one working folder">
      <option value="">All folders</option></select>
    <label style="color:var(--dim)" title="Include sessions from folders nested inside the one you picked">
      <input type="checkbox" id="subdirs" checked> + subfolders</label>
    <select id="src" title="Which tool the session belongs to">
      <option value="">Claude + Codex</option><option value="claude">Claude Code only</option>
      <option value="codex">Codex only</option></select>
    <label style="color:var(--dim)" title="Background agents launched inside a session">
      <input type="checkbox" id="subs"> include subagent runs</label>
    <button id="theme" title="Switch between light, dark and system theme">Theme: Auto</button>
  </div>
  <div class="hint" id="hint">Click a row to copy its resume command · double-click to read the transcript</div>
</header>
<main id="list"></main>
<div id="toast"></div>
<div id="panel"><div id="phead"></div><div id="pbody"></div></div>
<script>
const $ = s => document.querySelector(s);
let mode = "title", timer = null;

function toast(t){ const e=$("#toast"); e.textContent=t; e.classList.add("show");
  setTimeout(()=>e.classList.remove("show"), 1100); }

async function copy(text, what){
  try {
    await navigator.clipboard.writeText(text);
    // only read back when already granted — never triggers a permission prompt
    let ok = true;
    try {
      const perm = await navigator.permissions.query({name:"clipboard-read"});
      if (perm.state === "granted") ok = (await navigator.clipboard.readText()) === text;
    } catch(e){}
    if (ok){ toast("copied " + what); return; }
  } catch(e){}
  try {
    const ta=document.createElement("textarea"); ta.value=text;
    ta.style.cssText="position:fixed;opacity:0"; document.body.appendChild(ta);
    ta.select(); const ok=document.execCommand("copy"); ta.remove();
    if (ok){ toast("copied " + what); return; }
  } catch(e){}
  manual(text);                     // clipboard blocked — show it, pre-selected, for ctrl-c
}

function manual(text){
  let box = document.querySelector("#manual");
  if (!box){ box = document.createElement("div"); box.id="manual";
    box.style.cssText="position:fixed;left:50%;bottom:22px;transform:translateX(-50%);display:flex;gap:6px;"+
      "background:var(--card);border:1px solid var(--acc);border-radius:6px;padding:6px 8px;z-index:9";
    box.innerHTML='<input style="width:52ch;font:inherit;border:0;background:transparent;color:var(--fg)">'+
      '<button>×</button>';
    box.querySelector("button").onclick=()=>box.remove();
    document.body.appendChild(box);
  }
  const i = box.querySelector("input"); i.value = text; i.focus(); i.select();
}

const esc = s => s.replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function mark(s, q){
  s = esc(s);
  (q||"").split(/\s+/).filter(Boolean).forEach(t => {
    s = s.replace(new RegExp("("+t.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+")","ig"), "<mark>$1</mark>");
  });
  return s;
}

async function load(){
  const q = $("#q").value.trim();
  const p = new URLSearchParams({q, mode, src: $("#src").value, subs: $("#subs").checked ? "1":"0",
                                 folder: $("#folder").value, subdirs: $("#subdirs").checked ? "1":"0"});
  $("#hint").textContent = "searching…";
  const r = await fetch("/api/list?"+p);
  const d = await r.json();
  if (!d.rows.length){
    $("#list").innerHTML = `<div class="empty">Nothing matched “${esc(q)}”.` +
      (mode==="title" ? ` Try <b>Messages</b> or <b>Everything</b>.` : ``) + `</div>`;
    $("#hint").textContent = `0 results · ${d.ms}ms`;
    return;
  }
  $("#list").innerHTML = d.rows.map(e => `
    <div class="row" data-id="${e.id}" data-cmd="${esc(e.cmd)}"
         title="Click to copy:  ${esc(e.cmd)}">
      <span class="tag ${e.tag}">${e.label}</span>
      <span class="id" data-copy="${e.id}" title="Click to copy the session id">${e.id.slice(0,8)}</span>
      <span class="when" title="${e.full_when}">${e.when}</span>
      <span class="turns">${e.turns} msgs</span>
      <span class="proj" title="${esc(e.cwd)}">${esc(e.proj)}</span>
      <span class="title">${mark(e.title||"(no message text)", q)}</span>
      <span class="act">copy resume ⧉</span>
    </div>` + (e.hits && e.hits.length ? `<div class="hits">` +
      e.hits.map(h=>`<div><b>${h[0]}</b> <span class="when">${h[1]}</span> …${mark(h[2], q)}…</div>`).join("") + `</div>` : "")
  ).join("");
  const what = mode==="title" ? "titles" : (mode==="deep" ? "messages" : "everything");
  $("#hint").textContent =
    `${d.rows.length}${d.partial?"+ (showing first 80)":(q?" matching":"")} of ${d.total} sessions` +
    (q?` · searched ${what} in ${(d.ms/1000).toFixed(1)}s`:``) +
    ` · click a row to copy its resume command · double-click to read it`;
}

$("#list").addEventListener("click", e => {
  const idc = e.target.closest(".id");
  if (idc){ copy(idc.dataset.copy, "id"); e.stopPropagation(); return; }
  const row = e.target.closest(".row");
  if (row) copy(row.dataset.cmd, "resume command");
});
$("#list").addEventListener("dblclick", e => {
  const row = e.target.closest(".row");
  if (row) open_session(row.dataset.id);
});

async function open_session(id){
  const r = await fetch("/api/session?id="+encodeURIComponent(id));
  const d = await r.json();
  const agent = d.src === "codex" ? "Codex" : "Claude";
  $("#phead").innerHTML = `<button id="close">← Back to list</button>
    <b>${esc(d.label)}</b>
    <span class="when">${esc(d.cwd)} · ${d.turns} messages · ${d.start} → ${d.end}</span>
    <span class="cmd" id="pcmd" title="Click to copy">${esc(d.cmd)} ⧉</span>`;
  $("#pbody").innerHTML = d.turns_list.map(t =>
    `<div class="turn ${t[0]}"><b>${t[0]==="user"?"You":agent} · ${t[1]}</b>` +
    `<pre>${esc(t[2])}</pre></div>`).join("");
  $("#panel").classList.add("open");
  $("#pbody").scrollTop = 0;
  $("#close").onclick = () => $("#panel").classList.remove("open");
  $("#pcmd").onclick = () => copy(d.cmd, "resume command");
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape") $("#panel").classList.remove("open");
  if (e.key === "/" && document.activeElement !== $("#q")) { e.preventDefault(); $("#q").focus(); }
});

const THEMES = ["auto", "light", "dark"];
function applyTheme(t){
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  $("#theme").textContent = "Theme: " + t[0].toUpperCase() + t.slice(1);
  try { localStorage.setItem("csx-theme", t); } catch(e){}
}
let theme = (() => { try { return localStorage.getItem("csx-theme") || "auto"; }
                     catch(e){ return "auto"; } })();
applyTheme(theme);
$("#theme").onclick = () => applyTheme(theme = THEMES[(THEMES.indexOf(theme) + 1) % 3]);

function setMode(m){ mode = m;
  [["title","#mTitle"],["deep","#mDeep"],["global","#mGlob"]].forEach(([k,s]) =>
    $(s).classList.toggle("on", k===m));
  load(); }
$("#mTitle").onclick = () => setMode("title");
$("#mDeep").onclick  = () => setMode("deep");
$("#mGlob").onclick  = () => setMode("global");
$("#src").onchange = load; $("#subs").onchange = load;
$("#folder").onchange = load; $("#subdirs").onchange = load;

async function loadFolders(){
  const d = await (await fetch("/api/folders")).json();
  const sel = $("#folder");
  sel.innerHTML = `<option value="">All folders (${d.total} sessions)</option>` +
    d.folders.map(f => `<option value="${esc(f.path)}">${esc(f.short)} — ${f.deep}</option>`).join("");
}
loadFolders();
$("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(load, mode==="title"?120:450); };
load();
</script>
"""


def build(csx):
    """Return a request handler bound to the csx module (avoids a circular import)."""

    def rows_for(q, mode, src, subs, limit=5000, hitcap=80, folder="", subdirs=True):
        idx = csx.load(quiet=True)
        if folder:
            idx = [e for e in idx if csx.in_tree(e.get("cwd"), folder, subdirs)]
        if not subs and mode != "global":
            idx = [e for e in idx if e.get("kind") != "sub"]
        if src == "codex":
            idx = [e for e in idx if e.get("src") == "codex"]
        elif src == "claude":
            idx = [e for e in idx if e.get("src") != "codex"]

        terms = [t for t in q.split() if t]
        out = []
        if not terms:
            sel = idx
        elif mode == "title":
            sel = [e for e in idx
                   if all(t.lower() in (e["title"] + " " + e.get("project", "") + " "
                                        + e.get("cwd", "")).lower() for t in terms)]
        else:
            meta = mode == "global"
            pats = [re.compile(re.escape(t), re.I) for t in terms]

            needles = [t.lower().encode("utf-8", "replace") for t in terms]
            sel = []
            for e in idx:
                if not csx.raw_hit(e["path"], needles):
                    continue
                hits = []
                agent = "Codex" if e.get("src") == "codex" else "Claude"
                if all(p.search(e["title"]) for p in pats):
                    hits.append(["Title", (e.get("start") or "")[:16], " ".join(e["title"].split())])
                for role, ts, text in csx.msgs(e, meta):
                    if all(p.search(text) for p in pats):
                        m = pats[0].search(text)
                        hits.append(["You" if role == "user" else agent, ts[:16],
                                     " ".join(text[max(0, m.start() - 100):m.start() + 140].split())])
                    if len(hits) >= 3:
                        break
                if not hits:
                    continue
                sel.append(dict(e, _hits=hits))
                if len(sel) >= hitcap:
                    break

        for e in sel[:limit]:
            when = csx.dt.datetime.fromtimestamp(e["mtime"])
            tag = "subagent" if e.get("kind") == "sub" else (
                "codex" if e.get("src") == "codex" else "claude")
            out.append({
                "id": e["id"],
                "tag": tag,
                "label": {"claude": "Claude", "codex": "Codex", "subagent": "Subagent"}[tag],
                "when": when.strftime("%b %d, %H:%M"),
                "full_when": when.strftime("%A %d %B %Y, %H:%M") + f"  ({csx.ago(e['mtime'])} ago)",
                "turns": e["turns"],
                "proj": csx.proj(e),
                "cwd": e.get("cwd") or "",
                "title": e["title"],
                "cmd": csx.resume_cmd(e),
                "hits": e.get("_hits", []),
            })
        return out, len(sel)

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, body, ctype):
            b = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path == "/":
                return self._send(PAGE, "text/html; charset=utf-8")
            if u.path == "/api/list":
                t0 = csx.dt.datetime.now()
                rows, total = rows_for(qs.get("q", ""), qs.get("mode", "title"),
                                       qs.get("src", ""), qs.get("subs") == "1",
                                       folder=qs.get("folder", ""),
                                       subdirs=qs.get("subdirs", "1") == "1")
                partial = qs.get("mode", "title") != "title" and total >= 80
                ms = int((csx.dt.datetime.now() - t0).total_seconds() * 1000)
                return self._send(json.dumps({"rows": rows, "total": total, "ms": ms,
                                              "partial": partial}),
                                  "application/json")
            if u.path == "/api/folders":
                idx = [e for e in csx.load(quiet=True) if e.get("kind") != "sub"]
                home = os.path.expanduser("~")
                fl = [{"path": c,
                       "short": ("~" + c[len(home):]) if c.startswith(home) else c,
                       "own": own, "deep": deep}
                      for c, own, deep in csx.folders(idx)]
                return self._send(json.dumps({"folders": fl, "total": len(idx)}),
                                  "application/json")

            if u.path == "/api/session":
                idx = csx.load(quiet=True)
                e = csx.pick(idx, qs.get("id", ""))[0]
                turns = []
                for role, ts, text in csx.msgs(e, True):
                    if role == "user" and csx.is_noise(text):
                        continue
                    turns.append([role, ts[:19], text[:20000]])
                agent = "Codex" if e.get("src") == "codex" else "Claude Code"
                if e.get("kind") == "sub":
                    agent += " subagent"
                return self._send(json.dumps({
                    "id": e["id"], "src": e.get("src", "claude"), "cwd": e.get("cwd") or "?",
                    "label": f"{agent} · {e['id'][:8]}",
                    "turns": e["turns"], "start": e["start"][:16], "end": e["end"][:16],
                    "cmd": csx.resume_cmd(e), "turns_list": turns}), "application/json")
            self.send_error(404)

    return H


def serve(csx, port=8787, open_browser=True):
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), build(csx))
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"no free port in {port}..{port + 19}")
    url = f"http://127.0.0.1:{p}/"
    print(f"csx ui → {url}   (ctrl-c to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
