"""csx ui — tiny local web front-end for the csx session index.

Served by csx itself (`csx ui`). No deps, no build step, no external requests.
Click a row to copy its resume command; click the id chip to copy the raw id.
"""
import html as _html
import json
import os
import re
import shlex
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
.row{display:grid;grid-template-columns:72px 88px 122px 60px 132px 110px 1fr 132px;gap:9px;align-items:baseline;
  padding:6px 14px;border-bottom:1px solid var(--line);cursor:pointer}
.row:hover{background:var(--card)}
.tag{font-size:10.5px;font-weight:700;letter-spacing:.03em;text-align:center;border-radius:999px;
  padding:1px 0;border:1px solid currentColor}
.claude{color:var(--cc)}.codex{color:var(--cx)}.subagent{color:var(--sa)}
.id{color:var(--dim);cursor:copy}
.id:hover{color:var(--acc);text-decoration:underline}
.when,.turns,.proj{color:var(--dim);font-size:12px}
.act{opacity:0;text-align:right;white-space:nowrap}
.row:hover .act,.row.sel .act{opacity:1}
.act button{padding:1px 7px;font-size:11px;border-radius:5px;line-height:1.5}
.row.sel{background:var(--card);box-shadow:inset 3px 0 0 var(--acc)}
.gone{color:var(--sa);font-style:italic}
#day{padding:8px 14px;border-bottom:1px solid var(--line);color:var(--dim);font-size:12.5px;display:none}
#day.on{display:block}
#day b{color:var(--fg)}
.proj{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.branch{color:var(--dim);font-size:11.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hits{padding:2px 14px 8px 184px;color:var(--dim);font-size:12px}
.hits b{color:var(--fg);opacity:.65;font-weight:600}
.empty{padding:40px 14px;color:var(--dim);text-align:center}
.hits div{padding:1px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
mark{background:var(--hl);color:inherit}
#toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--fg);color:var(--bg);
  padding:8px 14px;border-radius:6px;opacity:0;transition:.15s;pointer-events:none;font-size:12px}
#toast.show{opacity:1}
#panel{position:fixed;inset:0;background:var(--bg);display:none;flex-direction:column;z-index:50}
#panel.open{display:flex}
#phead{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;gap:10px;
  align-items:center;flex-wrap:wrap;flex:0 0 auto;background:var(--bg)}
#pbody{overflow:auto;padding:14px;flex:1 1 auto}
#pbody>*:first-child{margin-top:0}
.turn{border-left:2px solid var(--line);padding:2px 0 10px 10px;margin-bottom:10px}
.turn b{font-size:11px;letter-spacing:.04em}
.turn.user{border-color:var(--acc)}
.turn pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-word;font:inherit}
.md{margin-top:4px;font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:13.5px;
  line-height:1.62;max-width:none}
.md h1,.md h2,.md h3,.md h4{margin:14px 0 6px;line-height:1.3}
.md h1{font-size:1.35em}.md h2{font-size:1.2em}.md h3{font-size:1.08em}.md h4{font-size:1em}
.md p{margin:8px 0}
.md ul,.md ol{margin:8px 0;padding-left:22px}
.md li{margin:3px 0}
.md code{font-family:ui-monospace,Menlo,monospace;font-size:.9em;background:var(--card);
  border:1px solid var(--line);border-radius:4px;padding:0 4px}
.md pre.code{background:var(--card);border:1px solid var(--line);border-radius:6px;
  padding:10px 12px;overflow-x:auto;margin:10px 0}
.md pre.code code{background:none;border:0;padding:0;font-size:12.5px}
.md blockquote{margin:8px 0;padding:2px 0 2px 12px;border-left:3px solid var(--line);color:var(--dim)}
.md table{border-collapse:collapse;margin:10px 0;display:block;overflow-x:auto}
.md th,.md td{border:1px solid var(--line);padding:4px 9px;text-align:left}
.md th{background:var(--card)}
.md hr{border:0;border-top:1px solid var(--line);margin:14px 0}
.md a{color:var(--acc)}
.md p:first-child code:only-child{color:var(--dim)}
.turn.tool{opacity:.62}
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
    <button id="mPrompt" title="Every prompt you have typed, even from deleted sessions">Prompts</button>
    <button id="today" title="Only sessions you touched today">Today</button>
    <select id="folder" title="Limit to one working folder">
      <option value="">All folders</option></select>
    <label style="color:var(--dim)" title="Include sessions from folders nested inside the one you picked">
      <input type="checkbox" id="subdirs"> + subfolders</label>
    <select id="src" title="Which tool the session belongs to">
      <option value="">Claude + Codex</option><option value="claude">Claude Code only</option>
      <option value="codex">Codex only</option></select>
    <label style="color:var(--dim)" title="Background agents launched inside a session">
      <input type="checkbox" id="subs"> include subagent runs</label>
    <button id="theme" title="Switch between light, dark and system theme">Theme: Auto</button>
  </div>
  <div class="hint" id="hint">↑↓ move · Enter read · <b>o</b> open in terminal · <b>y</b> copy · / search</div>
</header>
<div id="day"></div>
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
  const day = todayOn ? new Date().toLocaleDateString("en-CA") : "";
  const p = new URLSearchParams({q, mode, src: $("#src").value, subs: $("#subs").checked ? "1":"0",
                                 folder: $("#folder").value,
                                 subdirs: $("#subdirs").checked ? "1":"0", day});
  dayStrip(day);
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
      <span class="branch" title="git branch">${esc(e.branch || "")}</span>
      <span class="title">${mark(e.title||"(no message text)", q)}</span>
      <span class="act">${e.cmd ? `<button class="go" data-id="${e.id}" title="Open a terminal already resumed in this session">▶ Resume</button>` +
        (e.forkable ? ` <button class="fork" data-id="${e.id}" title="Resume as a new branch of this session (--fork-session), leaving the original untouched">⑂ Fork</button>` : ``) : `<span class="gone">session gone</span>`}</span>
    </div>` + (e.hits && e.hits.length ? `<div class="hits">` +
      e.hits.map(h=>`<div><b>${h[0]}</b> <span class="when">${h[1]}</span> …${mark(h[2], q)}…</div>`).join("") + `</div>` : "")
  ).join("");
  const what = mode==="title" ? "titles" : (mode==="deep" ? "messages" : "everything");
  const f = $("#folder"), scope = f.value
    ? ` in ${f.options[f.selectedIndex].text.split(" — ")[0]}` +
      ($("#subdirs").checked ? " + subfolders" : "") : ``;
  $("#hint").textContent =
    `${d.rows.length}${d.partial?"+ (showing first 80)":(q?" matching":"")} of ${d.total} sessions${scope}` +
    (q?` · searched ${what} in ${(d.ms/1000).toFixed(1)}s`:``) +
    ` · click a row to copy its resume command · double-click to read it`;
}

$("#list").addEventListener("click", e => {
  const go = e.target.closest(".go");
  if (go){ launch(go.dataset.id); e.stopPropagation(); return; }
  const fk = e.target.closest(".fork");
  if (fk){ launch(fk.dataset.id, true); e.stopPropagation(); return; }
  const idc = e.target.closest(".id");
  if (idc){ copy(idc.dataset.copy, "id"); e.stopPropagation(); return; }
  const row = e.target.closest(".row");
  if (row){ select([...document.querySelectorAll(".row")].indexOf(row));
            copy(row.dataset.cmd, "resume command"); }
});

async function launch(id, fork){
  toast(fork ? "forking…" : "opening terminal…");
  try {
    const d = await (await fetch("/api/launch?id=" + encodeURIComponent(id) +
                                 (fork ? "&fork=1" : ""))).json();
    toast(d.ok ? `${fork ? "forked" : "resumed"} in ${d.terminal}` : `couldn't launch: ${d.error}`);
  } catch(e){ toast("launch failed: " + e.message); }
}

// --- keyboard: j/k move, Enter read, y copy, o open terminal ---
let sel = -1;
function rows(){ return [...document.querySelectorAll(".row")]; }
function select(i){
  const r = rows(); if (!r.length) return;
  sel = Math.max(0, Math.min(i, r.length - 1));
  r.forEach(x => x.classList.remove("sel"));
  const el = r[sel]; el.classList.add("sel");
  const b = el.getBoundingClientRect();
  if (b.top < 90 || b.bottom > innerHeight) el.scrollIntoView({block:"center"});
}
$("#list").addEventListener("dblclick", e => {
  const row = e.target.closest(".row");
  if (row) open_session(row.dataset.id);
});

// Small markdown renderer — enough for transcripts, no library.
function md(src){
  const code = [];
  let t = esc(src).replace(/```(\w*)\n?([\s\S]*?)```/g, (m, lang, body) => {
    code.push(`<pre class="code"><code>${body.replace(/\n$/,"")}</code></pre>`);
    return `\u0000${code.length - 1}\u0000`;
  });

  const lines = t.split("\n"), out = [];
  let list = null, para = [], quote = [];
  const flushPara = () => { if (para.length){ out.push(`<p>${para.join("<br>")}</p>`); para = []; } };
  const flushList = () => { if (list){ out.push(`</${list}>`); list = null; } };
  const flushQuote = () => { if (quote.length){ out.push(`<blockquote>${quote.join("<br>")}</blockquote>`); quote = []; } };
  const flushAll = () => { flushPara(); flushList(); flushQuote(); };

  for (const raw of lines){
    const line = raw.replace(/\s+$/,"");
    let m;
    if (!line.trim()){ flushAll(); continue; }
    if (/^\u0000\d+\u0000$/.test(line.trim())){ flushAll(); out.push(line.trim()); continue; }
    if ((m = line.match(/^(#{1,6})\s+(.*)$/))){
      flushAll(); out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())){ flushAll(); out.push("<hr>"); continue; }
    if ((m = line.match(/^&gt;\s?(.*)$/))){ flushPara(); flushList(); quote.push(inline(m[1])); continue; }
    if (/^\s*\|.*\|\s*$/.test(line)){ flushAll(); out.push(row2cells(line)); continue; }
    if ((m = line.match(/^\s*[-*+]\s+(.*)$/))){
      flushPara(); flushQuote();
      if (list !== "ul"){ flushList(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(m[1])}</li>`); continue;
    }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))){
      flushPara(); flushQuote();
      if (list !== "ol"){ flushList(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${inline(m[1])}</li>`); continue;
    }
    flushList(); flushQuote(); para.push(inline(line));
  }
  flushAll();

  let html = out.join("\n")
    .replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, m => `<table>${m.replace(/\n/g,"")}</table>`)
    .replace(/\u0000(\d+)\u0000/g, (m, i) => code[+i]);
  return html;
}
function row2cells(line){
  const cells = line.trim().replace(/^\||\|$/g, "").split("|");
  if (cells.every(c => /^\s*:?-{2,}:?\s*$/.test(c))) return "";   // separator row
  const tag = /\*\*/.test(line) ? "td" : "td";
  return "<tr>" + cells.map(c => `<${tag}>${inline(c.trim())}</${tag}>`).join("") + "</tr>";
}
function inline(s){
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

let rawMode = false, showTools = false, current = null, currentId = null;

async function open_session(id){
  currentId = id;
  const r = await fetch("/api/session?id=" + encodeURIComponent(id) +
                        (showTools ? "&tools=1" : ""));
  const d = await r.json();
  current = d;
  const agent = d.src === "codex" ? "Codex" : "Claude";
  $("#phead").innerHTML = `<button id="close">← Back to list  (Esc)</button>
    <b>${esc(d.label)}</b>
    <span class="when">${esc(d.cwd)} · ${d.turns} messages · ${d.start} → ${d.end}</span>
    <span class="cmd" id="pcmd" title="Click to copy">${esc(d.cmd)} ⧉</span>
    <button id="praw">${rawMode ? "Rendered" : "Raw text"}</button>
    <button id="ptools" class="${showTools ? "on" : ""}">Tool calls</button>`;
  paint();
  $("#panel").classList.add("open");
  $("#pbody").scrollTop = 0;
  $("#close").onclick = closePanel;
  $("#pcmd").onclick = () => copy(d.cmd, "resume command");
  $("#praw").onclick = () => { rawMode = !rawMode;
    $("#praw").textContent = rawMode ? "Rendered" : "Raw text"; paint(); };
  $("#ptools").onclick = () => { showTools = !showTools; open_session(currentId); };
}

function paint(){
  const d = current, agent = d.src === "codex" ? "Codex" : "Claude";
  $("#pbody").innerHTML = d.turns_list.map(t =>
    `<div class="turn ${t[0]}"><b>${t[0]==="user"?"You":agent} · ${t[1]}</b>` +
    (rawMode ? `<pre>${esc(t[2])}</pre>` : `<div class="md">${md(t[2])}</div>`) +
    `</div>`).join("");
}

function closePanel(){ $("#panel").classList.remove("open");
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape"){ closePanel(); $("#q").blur(); return; }
  const typing = document.activeElement === $("#q");
  if (e.key === "/" && !typing){ e.preventDefault(); $("#q").focus(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if ($("#panel").classList.contains("open")) return;
  // arrows + Enter work even while the search box has focus (it autofocuses);
  // the letter shortcuts only when you are not typing
  const nav = ["ArrowDown", "ArrowUp", "Enter"].includes(e.key);
  if (typing && !nav) return;
  const r = rows();
  if (e.key === "j" || e.key === "ArrowDown"){ e.preventDefault(); select(sel + 1); }
  else if (e.key === "k" || e.key === "ArrowUp"){ e.preventDefault(); select(sel - 1); }
  else if (e.key === "g"){ select(0); }
  else if (e.key === "G"){ select(rows().length - 1); }
  else if (sel >= 0 && r[sel]){
    if (e.key === "Enter"){ e.preventDefault(); open_session(r[sel].dataset.id); }
    else if (e.key === "y"){ copy(r[sel].dataset.cmd, "resume command"); }
    else if (e.key === "o"){ launch(r[sel].dataset.id); }
  }
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

let todayOn = false;
function setMode(m){ mode = m;
  [["title","#mTitle"],["deep","#mDeep"],["global","#mGlob"],["prompts","#mPrompt"]]
    .forEach(([k,s]) => $(s).classList.toggle("on", k===m));
  save(); load(); }
$("#mTitle").onclick  = () => setMode("title");
$("#mDeep").onclick   = () => setMode("deep");
$("#mGlob").onclick   = () => setMode("global");
$("#mPrompt").onclick = () => setMode("prompts");
$("#today").onclick = () => { todayOn = !todayOn;
  $("#today").classList.toggle("on", todayOn); save(); load(); };
const persist = ["#src","#subs","#folder","#subdirs"];
persist.forEach(sel => { const el = $(sel); el.addEventListener("change", () => { save(); load(); }); });

function save(){
  try { localStorage.setItem("csx-prefs", JSON.stringify({
    mode, todayOn, src: $("#src").value, subs: $("#subs").checked,
    folder: $("#folder").value, subdirs: $("#subdirs").checked })); } catch(e){}
}
function restore(){
  let p = {};
  try { p = JSON.parse(localStorage.getItem("csx-prefs") || "{}"); } catch(e){}
  if (p.src) $("#src").value = p.src;
  $("#subs").checked = !!p.subs; $("#subdirs").checked = !!p.subdirs;
  todayOn = !!p.todayOn; $("#today").classList.toggle("on", todayOn);
  if (p.mode) { mode = p.mode;
    [["title","#mTitle"],["deep","#mDeep"],["global","#mGlob"],["prompts","#mPrompt"]]
      .forEach(([k,s]) => $(s).classList.toggle("on", k===mode)); }
  return p.folder || "";
}

// come back to the tab after a while -> refresh so the list is not stale
let hiddenAt = 0;
document.addEventListener("visibilitychange", () => {
  if (document.hidden) hiddenAt = Date.now();
  else if (hiddenAt && Date.now() - hiddenAt > 30000 &&
           !$("#panel").classList.contains("open")) load();
});

async function dayStrip(day){
  const el = $("#day");
  if (!day){ el.classList.remove("on"); return; }
  const d = await (await fetch("/api/day?day=" + day)).json();
  el.classList.add("on");
  el.innerHTML = d.count
    ? `<b>Today</b> — ${d.count} session${d.count==1?"":"s"}, ${d.msgs} messages · ${esc(d.span)}` +
      ` · ` + d.folders.map(f => `${esc(f[0])} <b>${f[1]}</b>`).join(" · ")
    : `<b>Today</b> — nothing yet`;
}

async function loadFolders(){
  const d = await (await fetch("/api/folders")).json();
  const sel = $("#folder");
  sel.innerHTML = `<option value="">All folders (${d.total} sessions)</option>` +
    d.folders.map(f => `<option value="${esc(f.path)}">${esc(f.short)} — ${f.own} session${f.own==1?"":"s"}</option>`).join("");
}
const wantFolder = restore();
loadFolders().then(() => { if (wantFolder) $("#folder").value = wantFolder; load(); });
$("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(load, mode==="title"?120:450); };
</script>
"""


def build(csx):
    """Return a request handler bound to the csx module (avoids a circular import)."""

    def rows_for(q, mode, src, subs, limit=5000, hitcap=80, folder="", subdirs=False, day=""):
        idx = [e for e in csx.load(quiet=True) if e.get("turns")]
        if day:
            idx = [e for e in idx if csx.day_of(e) == day]
        if folder:
            idx = [e for e in idx if csx.in_tree(e.get("cwd"), folder, subdirs)]
        if not subs and mode != "global":
            idx = [e for e in idx if e.get("kind") != "sub"]
        if src == "codex":
            idx = [e for e in idx if e.get("src") == "codex"]
        elif src == "claude":
            idx = [e for e in idx if e.get("src") != "codex"]

        try:
            terms = [t for t in shlex.split(q) if t]
        except ValueError:
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
            sel = []
            for e, hits in csx.search(idx, terms, ctx=100, meta=meta, per=3):
                sel.append(dict(e, _hits=[[("You" if r == "user" else
                                            ("Title" if r == "ttl" else
                                             ("Codex" if e.get("src") == "codex" else "Claude"))),
                                           ts, sn] for r, ts, sn in hits]))
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
                "when": when.strftime("%b %d, %I:%M %p").replace(" 0", " "),
                "full_when": when.strftime("%A %d %B %Y, %I:%M %p").replace(" 0", " ")
                             + f"  ({csx.ago(e['mtime'])} ago)",
                "turns": e["turns"],
                "proj": csx.proj(e),
                "branch": e.get("branch") or "",
                "cwd": e.get("cwd") or "",
                "title": e["title"],
                "cmd": csx.resume_cmd(e),
                "forkable": e.get("src") != "codex",
                "hits": e.get("_hits", []),
            })
        return out, len(sel)

    def prompt_rows(q):
        terms = [t for t in q.split() if t]
        hits = csx.prompt_log(terms) if terms else csx.prompt_log([], 200)
        by_id = {e["id"]: e for e in csx.load(quiet=True)}
        out = []
        for h in hits:
            e = by_id.get(h["session"])
            when = csx.dt.datetime.fromtimestamp((h["ts"] or 0) / 1000)
            out.append({
                "id": h["session"] or "-",
                "tag": "claude" if e else "gone",
                "label": "Claude" if e else "no session",
                "when": when.strftime("%b %d, %I:%M %p").replace(" 0", " "),
                "full_when": when.strftime("%A %d %B %Y, %I:%M %p").replace(" 0", " "),
                "turns": e["turns"] if e else 0,
                "proj": os.path.basename((h["project"] or "").rstrip("/")) or "?",
                "cwd": h["project"] or "",
                "title": h["text"],
                "cmd": csx.resume_cmd(e) if e else "",
                "hits": [],
            })
        return out, len(out)

    def day_summary(day):
        idx = [e for e in csx.load(quiet=True)
               if e.get("kind") != "sub" and csx.day_of(e) == day]
        if not idx:
            return {"count": 0}
        stamps = []
        for e in idx:
            for k in ("start", "end"):
                try:
                    stamps.append(csx.dt.datetime.fromisoformat(
                        e[k].replace("Z", "+00:00")).astimezone())
                except Exception:
                    pass
        folders = {}
        for e in idx:
            f = csx.proj(e)
            folders[f] = folders.get(f, 0) + 1
        today = csx.dt.datetime.now().strftime("%Y-%m-%d")
        stamps = [s for s in stamps if s.strftime("%Y-%m-%d") == day] or stamps
        span = ""
        if stamps:
            lo, hi = min(stamps), max(stamps)
            hrs = (hi - lo).total_seconds() / 3600
            span = (f"{lo.strftime('%I:%M %p').lstrip('0')} → "
                    f"{hi.strftime('%I:%M %p').lstrip('0')}  ({hrs:.1f}h span)")
        return {"count": len(idx), "span": span, "isToday": day == today,
                "msgs": sum(e["turns"] for e in idx),
                "folders": sorted(folders.items(), key=lambda kv: -kv[1])[:6]}

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
                mode = qs.get("mode", "title")
                if mode == "prompts":
                    rows, total = prompt_rows(qs.get("q", ""))
                    ms = int((csx.dt.datetime.now() - t0).total_seconds() * 1000)
                    return self._send(json.dumps({"rows": rows, "total": total,
                                                  "ms": ms, "partial": False}),
                                      "application/json")
                rows, total = rows_for(qs.get("q", ""), mode,
                                       qs.get("src", ""), qs.get("subs") == "1",
                                       folder=qs.get("folder", ""),
                                       subdirs=qs.get("subdirs", "0") == "1",
                                       day=qs.get("day", ""))
                partial = mode != "title" and total >= 80
                ms = int((csx.dt.datetime.now() - t0).total_seconds() * 1000)
                return self._send(json.dumps({"rows": rows, "total": total, "ms": ms,
                                              "partial": partial}),
                                  "application/json")
            if u.path == "/api/day":
                return self._send(json.dumps(day_summary(
                    qs.get("day") or csx.dt.datetime.now().strftime("%Y-%m-%d"))),
                    "application/json")

            if u.path == "/api/launch":
                import subprocess
                idx = csx.load(quiet=True)
                e = csx.pick(idx, qs.get("id", ""))[0]
                if e.get("kind") == "sub":
                    par = [x for x in idx if x["id"] == e["parent"]]
                    if par:
                        e = par[0]
                # built only from indexed values, never from page input
                fork = qs.get("fork") == "1" and e.get("src") != "codex"
                sh = (f"cd {shlex.quote(e.get('cwd') or os.path.expanduser('~'))} && "
                      f"exec {'codex resume' if e.get('src') == 'codex' else 'claude --resume'} "
                      f"{shlex.quote(e['id'])}" + (" --fork-session" if fork else ""))
                argv, term = csx.terminal_argv(sh)
                if qs.get("dry") == "1":          # inspect the command without running it
                    return self._send(json.dumps({"ok": True, "dry": True,
                                                  "terminal": term, "argv": argv}),
                                      "application/json")
                if not argv:
                    return self._send(json.dumps({"ok": False,
                                                  "error": "no terminal emulator found"}),
                                      "application/json")
                try:
                    subprocess.Popen(argv, start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as exc:
                    return self._send(json.dumps({"ok": False, "error": str(exc)}),
                                      "application/json")
                return self._send(json.dumps({"ok": True, "terminal": term,
                                              "id": e["id"]}), "application/json")

            if u.path == "/api/folders":
                idx = [e for e in csx.load(quiet=True) if e.get("kind") != "sub"]
                home = os.path.expanduser("~")
                fl = [{"path": c,
                       "short": ("~" + c[len(home):]) if c.startswith(home) else c,
                       "own": own, "deep": deep}
                      for c, own, deep in csx.folders(idx)]
                total = sum(f["own"] for f in fl)
                return self._send(json.dumps({"folders": fl, "total": total}),
                                  "application/json")

            if u.path == "/api/session":
                idx = csx.load(quiet=True)
                e = csx.pick(idx, qs.get("id", ""))[0]
                turns = []
                for role, ts, text in csx.msgs(e, qs.get("tools") == "1"):
                    if role == "user" and csx.is_noise(text):
                        continue
                    turns.append([role, csx.clock(ts), text[:20000]])
                agent = "Codex" if e.get("src") == "codex" else "Claude Code"
                if e.get("kind") == "sub":
                    agent += " subagent"
                return self._send(json.dumps({
                    "id": e["id"], "src": e.get("src", "claude"), "cwd": e.get("cwd") or "?",
                    "label": f"{agent} · {e['id'][:8]}",
                    "turns": e["turns"], "start": csx.clock(e["start"]), "end": csx.clock(e["end"]),
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
    csx.pool()          # fork workers before the server spawns threads
    url = f"http://127.0.0.1:{p}/"
    print(f"csx ui → {url}   (ctrl-c to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()
