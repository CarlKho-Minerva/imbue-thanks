#!/usr/bin/env python3
"""imbue-thanks - a farewell wall for the Imbue office, self-hosted on Carl's
OpenHost zone (cloud in a bottle). Read-only: there is not a single write
endpoint in this file, which is what lets the whole app be public.

Content lives OUTSIDE this repo, in the app's data dir:
    $OPENHOST_APP_DATA_DIR/people.json     one entry per person
    $OPENHOST_APP_DATA_DIR/media/*.mp4     optional self-hosted clips
Copy them in with `oh app ssh` (never over HTTP - there is no upload route).
"""
import html
import json
import mimetypes
import os
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("OPENHOST_APP_DATA_DIR", os.path.join(HERE, "sample_data"))
PORT = int(os.environ.get("PORT", "8080"))
FONT_DIR = os.path.join(HERE, "fonts")
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")

# ---------------------------------------------------------------- content

def load():
    """Read people.json fresh on every request so edits land without a reload."""
    for path in (os.path.join(DATA, "people.json"),
                 os.path.join(HERE, "sample_data", "people.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            doc.setdefault("people", [])
            return doc
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as exc:            # loud, never silent
            return {"error": f"people.json is not valid JSON: {exc}", "people": []}
    return {"error": f"no people.json found under {DATA}", "people": []}


def find(doc, slug):
    for p in doc.get("people", []):
        if p.get("slug") == slug:
            return p
    return None

# ---------------------------------------------------------------- render

CSS = """
@font-face{font-family:Geist;src:url(/fonts/geist.woff2)format('woff2-variations');
 font-weight:100 900;font-display:swap}
@font-face{font-family:'Geist Mono';src:url(/fonts/geist-mono.woff2)format('woff2-variations');
 font-weight:100 900;font-display:swap}
/* Imbue's own tokens, read off imbue.com. Their palette is named after feelings. */
:root{
 --web-white:#faf8f2;   /* page */
 --clarity:#fcefd4;     /* warm card */
 --comfort:#f5d6a0;     /* warm accent block */
 --confusion:#0b292b;   /* ink, a very dark teal */
 --confidence:#f50d00;  /* the one red */
 --inspiration:#e9ecd9; /* pale green */
 --peace:#8eafcb;       /* blue */
 --respect:#d26645;     /* terracotta */
 --strength:#cfc7b3;    /* hairline */
 --body:#3d5254;
 --mute:#7d8b8a;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--web-white);color:var(--confusion);
 font-family:Geist,Inter,system-ui,-apple-system,sans-serif;font-size:17px;line-height:1.6}
.wrap{max-width:680px;margin:0 auto;padding:72px 24px 110px}
.eyebrow{font-family:'Geist Mono',ui-monospace,Menlo,monospace;font-size:12px;
 line-height:16px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 20px}
h1{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
 font-size:52px;line-height:1.05;font-weight:400;letter-spacing:-.5px;margin:0 0 20px}
h2{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
 font-size:28px;line-height:1.2;font-weight:400;margin:56px 0 14px}
h3{font-size:19px;line-height:1.3;font-weight:600;margin:0 0 8px;letter-spacing:-.2px}
p{color:var(--body);margin:0 0 18px}
p.lead{color:var(--confusion);font-size:21px;line-height:1.5;
 font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
a{color:var(--confusion);text-decoration:underline;text-underline-offset:3px;
 text-decoration-color:var(--confidence);text-decoration-thickness:2px}
a:hover{color:var(--confidence)}
.card{background:#fff;border:1px solid var(--strength);border-radius:4px;
 padding:26px;margin:26px 0}
.card.warm{background:var(--clarity);border-color:#e8d5aa}
.pill{display:inline-block;font-family:'Geist Mono',ui-monospace,monospace;font-size:11px;
 line-height:16px;letter-spacing:.08em;text-transform:uppercase;padding:5px 11px;
 border-radius:999px;background:var(--inspiration);color:#40513f}
video,iframe{width:100%;border:1px solid var(--strength);border-radius:4px;background:#000;
 aspect-ratio:16/9;display:block}
.note{white-space:pre-wrap;color:var(--confusion);font-size:18px}
ul{color:var(--body);padding-left:20px;margin:0}
li{margin-bottom:9px}
.rule{height:1px;background:var(--strength);border:0;margin:56px 0 0}
.foot{margin-top:22px;font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;
 line-height:1.7;color:var(--mute)}
.missing{border:1px dashed var(--strength);border-radius:4px;padding:26px;color:var(--mute);
 font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;background:#fff}
.tape{display:inline-block;background:var(--comfort);padding:2px 10px;transform:rotate(-1.2deg);
 font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;letter-spacing:.06em;
 text-transform:uppercase;color:#4b3a10}
@media(max-width:600px){h1{font-size:36px}.wrap{padding:44px 20px 72px}body{font-size:16px}}
"""


def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><div class="wrap">{body}</div></body></html>"""


def player(person):
    """A Cap link renders as an iframe, a local file as a <video>, neither as a stub."""
    cap = (person.get("cap_url") or "").strip()
    local = (person.get("video") or "").strip()
    if cap:
        src = cap if "/embed/" in cap else cap.replace("/s/", "/embed/")
        return (f'<iframe src="{html.escape(src)}" allow="fullscreen" '
                f'title="clip" loading="lazy"></iframe>'
                f'<p style="margin-top:8px"><a href="{html.escape(cap)}">'
                f'open on my Cap instead</a></p>')
    if local and SLUG_RE.match(os.path.splitext(local)[0]):
        return (f'<video controls preload="metadata" playsinline '
                f'src="/media/{html.escape(local)}"></video>')
    return ('<div class="missing">clip not uploaded yet. carl records these one at a '
            'time, so it lands here shortly.</div>')


def map_block(doc):
    """The labelled office map, clickable straight into the Gather space."""
    m = doc.get("meta", {})
    img = (m.get("map_image") or "").strip()
    gather = (m.get("gather_url") or "").strip()
    if not img:
        return ('<div class="missing">the labelled office map goes here '
                '(app_data/thanks/media/office-map.png)</div>')
    tag = (f'<img src="/media/{html.escape(img)}" alt="the Imbue office, rebuilt, '
           f'with everyone\'s desk labelled" style="width:100%;border:1px solid '
           f'var(--strength);border-radius:4px;display:block">')
    if gather:
        tag = f'<a href="{html.escape(gather)}" style="text-decoration:none">{tag}</a>'
    return tag


def landing(doc):
    m = doc.get("meta", {})
    gather = (m.get("gather_url") or "").strip()
    gather_block = (
        f'<p><a href="{html.escape(gather)}">Walk into the office replica</a></p>'
        if gather else
        '<div class="missing">gather.town link goes here once the replica is done</div>')
    err = (f'<div class="missing">{html.escape(doc["error"])}</div>'
           if doc.get("error") else "")
    return page(m.get("title", "Thank you, Imbue"), f"""
{err}
<p class="eyebrow">{html.escape(m.get('eyebrow','292 ivy / last day of coworking'))}</p>
<h1>{html.escape(m.get('title','Thank you, Imbue.'))}</h1>
<p class="lead">{html.escape(m.get('lead',''))}</p>
{player(m)}
<h2>The office, rebuilt</h2>
<p>{html.escape(m.get('gather_blurb',''))}</p>
{map_block(doc)}
<p style="margin-top:14px">{gather_block}</p>
<div class="card warm"><h3>One thing before you join</h3>
<p style="margin:0">{html.escape(m.get('gather_note',''))}</p></div>
<h2>Your clip</h2>
<p>{html.escape(m.get('clip_blurb',''))}</p>
<h2>One ask, one offer</h2>
<div class="card"><h3>{html.escape(m.get('ask_title',''))}</h3>
<p>{html.escape(m.get('ask_body',''))}</p></div>
<div class="card"><h3>{html.escape(m.get('offer_title',''))}</h3>
<p>{html.escape(m.get('offer_body',''))}</p></div>
<div class="foot">{html.escape(m.get('footer',''))}</div>""")


def bench_block(doc, heading_level="h2"):
    b = doc.get("meta", {}).get("bench") or {}
    if not b:
        return ""
    return (f'<{heading_level}>{html.escape(b.get("title",""))}</{heading_level}>'
            f'<p class="eyebrow">{html.escape(b.get("sub",""))}</p>'
            f'<div class="card"><h3>Methods</h3><p>{html.escape(b.get("methods",""))}</p></div>'
            f'<div class="card"><h3>Results</h3><p>{html.escape(b.get("results",""))}</p></div>')


def bench_page(doc):
    m = doc.get("meta", {})
    return page(m.get("bench", {}).get("title", "benchmark"), f"""
<p class="eyebrow">local model bench / carl kho</p>
<h1>{html.escape(m.get("bench", {}).get("title", ""))}</h1>
<p class="lead">{html.escape(m.get("bench", {}).get("sub", ""))}</p>
{bench_block(doc)}
<div class="foot">{html.escape(m.get('footer',''))}</div>""")


def person_page(doc, person):
    m = doc.get("meta", {})
    gather = (m.get("gather_url") or "").strip()
    return page(f"For {person.get('first','you')}", f"""
<p class="eyebrow">a message for one person</p>
<h1>{html.escape(person.get('name',''))}</h1>
<p class="eyebrow" style="margin:28px 0 8px">Start here, the one for everybody</p>
{player(m)}
<p class="eyebrow" style="margin:28px 0 8px">Then yours</p>
{player(person)}
{bench_block(doc) if person.get("bench") else ''}
<h2>The replica</h2>
<p>{html.escape(m.get('gather_blurb',''))}</p>
{map_block(doc)}
{f'<p style="margin-top:14px"><a href="{html.escape(gather)}">Open the office in Gather</a></p>' if gather else ''}
<div class="card warm"><h3>One thing before you join</h3>
<p style="margin:0">{html.escape(m.get('gather_note',''))}</p></div>
<div class="foot">{html.escape(m.get('footer',''))}
<span class="pill">this page is unlisted</span></div>""")


TELEPROMPTER = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="robots" content="noindex,nofollow"><title>Teleprompter</title><style>
@font-face{font-family:Geist;src:url(/fonts/geist.woff2)format('woff2-variations');font-weight:100 900;font-display:swap}
@font-face{font-family:'Geist Mono';src:url(/fonts/geist-mono.woff2)format('woff2-variations');font-weight:100 900;font-display:swap}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;background:#0a0a0a;color:#ededed;
 font-family:Geist,Inter,system-ui,-apple-system,sans-serif;overscroll-behavior:none}
body{display:flex;flex-direction:column}
header{flex:0 0 auto;padding:12px 16px;border-bottom:1px solid #262626;display:flex;
 align-items:center;gap:10px;font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;color:#7a7a7a}
header .who{color:#ededed;font-family:Geist,system-ui,sans-serif;font-size:15px;font-weight:600;
 letter-spacing:-.3px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
main{flex:1 1 auto;overflow-y:auto;padding:20px 20px 8px;-webkit-overflow-scrolling:touch}
#script{font-size:26px;line-height:1.45;letter-spacing:-.4px;white-space:pre-wrap;margin:0 0 24px}
#head{font-size:13px;line-height:18px;color:#7a7a7a;margin:0 0 14px;
 font-family:'Geist Mono',ui-monospace,monospace}
.dim{color:#52a8ff}
nav{flex:0 0 auto;display:flex;gap:8px;padding:10px 12px 22px;border-top:1px solid #262626;background:#0a0a0a}
button{flex:1;appearance:none;border:1px solid #262626;background:#111;color:#ededed;
 border-radius:12px;padding:16px 10px;font:inherit;font-size:15px;font-weight:600;letter-spacing:-.3px}
button:active{background:#1b1b1b}
button.go{background:#ededed;color:#0a0a0a;border-color:#ededed;flex:2}
button.small{flex:0 0 62px;font-family:'Geist Mono',ui-monospace,monospace;font-size:13px;font-weight:400}
.done{color:#52a8ff}
</style></head><body>
<header>
  <span id="count">00 / 00</span>
  <span class="who" id="who">.</span>
  <span id="secs"></span>
  <button class="small" id="size" style="padding:6px 8px;border-radius:8px">Aa</button>
</header>
<main><p id="head"></p><p id="script">loading</p></main>
<nav>
  <button id="prev">Back</button>
  <button class="go" id="next">Recorded, next</button>
  <button class="small" id="skip">Skip</button>
</nav>
<script>
var DATA = __DATA__;
var KEY = 'prompt-' + DATA.token;
var i = 0, size = 26;
try { var s = JSON.parse(localStorage.getItem(KEY) || '{}'); i = s.i || 0; size = s.size || 26; } catch(e){}
function save(){ try { localStorage.setItem(KEY, JSON.stringify({i:i, size:size})); } catch(e){} }
function render(){
  if (i < 0) i = 0;
  if (i > DATA.clips.length - 1) i = DATA.clips.length - 1;
  var c = DATA.clips[i];
  document.getElementById('count').textContent = (i+1 < 10 ? '0' : '') + (i+1) + ' / ' + DATA.clips.length;
  document.getElementById('who').textContent = c.who;
  document.getElementById('secs').textContent = c.secs ? '~' + c.secs + 's' : '';
  document.getElementById('head').textContent = c.head || '';
  var el = document.getElementById('script');
  el.textContent = c.text;
  el.style.fontSize = size + 'px';
  document.querySelector('main').scrollTop = 0;
  document.getElementById('next').textContent = (i === DATA.clips.length - 1) ? 'Done' : 'Recorded, next';
  save();
}
document.getElementById('next').onclick = function(){ i++; render(); };
document.getElementById('prev').onclick = function(){ i--; render(); };
document.getElementById('skip').onclick = function(){ i++; render(); };
document.getElementById('size').onclick = function(){ size = size >= 34 ? 20 : size + 4; render(); };
document.addEventListener('keydown', function(e){
  if (e.key === 'ArrowRight' || e.key === ' ') { i++; render(); }
  if (e.key === 'ArrowLeft') { i--; render(); }
});
render();
</script></body></html>"""


def teleprompter(doc):
    """Phone-sized reader for the clips. Reached only by the secret token."""
    clips = [{"who": "Opening clip, everyone sees this",
              "head": "hold up the office pan, then to camera",
              "secs": 0, "text": (doc.get("meta", {}).get("opening") or "").strip()}]
    for p in doc.get("people", []):
        tag = "" if p.get("named_in_recording", True) else "  (not on the seating plan)"
        clips.append({"who": p.get("name", "") + tag,
                      "head": (p.get("role", "") + " / " + p.get("headline", "")).strip(" /"),
                      "secs": p.get("secs", 0),
                      "text": (p.get("script") or "").strip()})
    clips.append({"who": "Closing clip, leave this at the empty desk",
                  "head": "to camera", "secs": 0,
                  "text": (doc.get("meta", {}).get("closing") or "").strip()})
    payload = json.dumps({"clips": clips, "token": doc.get("meta", {}).get("prompt_token", "x")})
    return TELEPROMPTER.replace("__DATA__", payload)


REVIEW_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Review</title><style>
@font-face{font-family:Geist;src:url(/fonts/geist.woff2)format('woff2-variations');font-weight:100 900;font-display:swap}
@font-face{font-family:'Geist Mono';src:url(/fonts/geist-mono.woff2)format('woff2-variations');font-weight:100 900;font-display:swap}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#faf8f2;color:#0b292b;font-family:Geist,system-ui,-apple-system,sans-serif;font-size:16px}
header{position:sticky;top:0;z-index:9;background:#faf8f2;border-bottom:1px solid #cfc7b3;
 padding:12px 16px;display:flex;gap:10px;align-items:center}
header b{font-size:15px;font-weight:600}
header .count{font-family:'Geist Mono',monospace;font-size:12px;color:#7d8b8a;margin-left:auto}
main{padding:12px 14px 120px;max-width:720px;margin:0 auto}
.card{background:#fff;border:1px solid #cfc7b3;border-radius:6px;padding:16px;margin:0 0 16px}
.card.ok{border-color:#8eafcb;background:#f4f8fb}
.card.bad{border-color:#f50d00;background:#fff4f3}
.who{font-size:19px;font-weight:600;margin:0 0 2px}
.to{font-family:'Geist Mono',monospace;font-size:12px;color:#7d8b8a;margin:0 0 10px}
.subj{font-size:14px;font-weight:600;margin:0 0 10px}
pre{white-space:pre-wrap;word-break:break-word;font-family:Geist,system-ui,sans-serif;
 font-size:14.5px;line-height:1.6;color:#3d5254;margin:0 0 12px;background:#faf8f2;
 border:1px solid #ece6d8;border-radius:4px;padding:12px}
.spoken{font-size:13px;line-height:1.55;color:#5b6f70;border-left:3px solid #f5d6a0;
 padding:2px 0 2px 10px;margin:0 0 12px}
img.poster{width:100%;border:1px solid #cfc7b3;border-radius:4px;display:block;margin:0 0 10px}
.row{display:flex;gap:8px}
button{flex:1;appearance:none;border:1px solid #cfc7b3;background:#fff;color:#0b292b;
 border-radius:8px;padding:12px;font:inherit;font-size:14px;font-weight:600}
button.y[aria-pressed=true]{background:#0b292b;color:#faf8f2;border-color:#0b292b}
button.n[aria-pressed=true]{background:#f50d00;color:#fff;border-color:#f50d00}
a{color:#0b292b}
.bar{position:fixed;left:0;right:0;bottom:0;background:#0b292b;color:#faf8f2;padding:12px 16px;
 display:flex;gap:10px;align-items:center;font-family:'Geist Mono',monospace;font-size:12px}
.bar button{flex:0 0 auto;background:#faf8f2;color:#0b292b;border:0;padding:10px 14px}
textarea{position:fixed;left:-9999px}
</style></head><body>
<header><b>Review before sending</b><span class="count" id="count"></span></header>
<main id="list"></main>
<div class="bar"><span id="summary">.</span><button id="copy">Copy flags</button></div>
<textarea id="clip"></textarea>
<script>
var D = __DATA__;
var KEY = 'review-' + D.token;
var state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){}
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(state)); }catch(e){} paint(); }
function paint(){
  var ok=0, bad=0;
  D.items.forEach(function(p){ if(state[p.to]==='ok') ok++; if(state[p.to]==='bad') bad++; });
  document.getElementById('count').textContent = ok+'/'+D.items.length+' ok, '+bad+' flagged';
  document.getElementById('summary').textContent = bad ? bad+' flagged' : 'nothing flagged';
  D.items.forEach(function(p, i){
    var c = document.getElementById('c'+i);
    c.className = 'card' + (state[p.to]==='ok' ? ' ok' : state[p.to]==='bad' ? ' bad' : '');
    c.querySelector('.y').setAttribute('aria-pressed', state[p.to]==='ok');
    c.querySelector('.n').setAttribute('aria-pressed', state[p.to]==='bad');
  });
}
var list = document.getElementById('list');
list.innerHTML = '<div class="card"><p class="who">The one everybody gets</p>'
  + '<p class="to">3 min, top of every email</p>'
  + '<p><a href="'+D.main+'">open the main video</a> &middot; <a href="'+D.gather+'">open Gather</a></p></div>';
D.items.forEach(function(p, i){
  var d = document.createElement('div');
  d.className = 'card'; d.id = 'c'+i;
  d.innerHTML =
    '<p class="who">'+p.name+'</p><p class="to">'+p.to+'</p>'
    + '<p class="subj">'+p.subject+'</p>'
    + '<a href="'+p.clip+'"><img class="poster" loading="lazy" src="/media/'+p.poster+'" alt=""></a>'
    + '<p class="spoken">what you actually say: '+p.spoken+'</p>'
    + '<pre>'+p.body+'</pre>'
    + '<div class="row"><button class="y">Good</button><button class="n">Flag</button></div>';
  d.querySelector('.y').onclick = function(){ state[p.to] = state[p.to]==='ok'?null:'ok'; save(); };
  d.querySelector('.n').onclick = function(){ state[p.to] = state[p.to]==='bad'?null:'bad'; save(); };
  list.appendChild(d);
});
document.getElementById('copy').onclick = function(){
  var out = D.items.filter(function(p){ return state[p.to]==='bad'; })
                   .map(function(p){ return 'FLAG '+p.name; }).join('\\n') || 'nothing flagged';
  var t = document.getElementById('clip'); t.value = out; t.select();
  try{ document.execCommand('copy'); }catch(e){}
  this.textContent = 'Copied';
  var b=this; setTimeout(function(){ b.textContent='Copy flags'; }, 1200);
};
paint();
</script></body></html>"""


def review_page(doc):
    """Everything that is about to go out, in one scroll, on a phone."""
    for it in doc.get("items", []):
        it["poster"] = it.get("poster") or ""
    return REVIEW_PAGE.replace("__DATA__", json.dumps(doc))

# ---------------------------------------------------------------- serve

class Handler(BaseHTTPRequestHandler):
    server_version = "imbue-thanks"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # one tidy line per request
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _send(self, code, body, ctype="text/html; charset=utf-8", cache="no-store"):
        blob = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(blob)

    def _file(self, root, name, cache="public, max-age=3600"):
        if not name or "/" in name or ".." in name:
            return self._send(404, page("not found", "<h1>404</h1>"))
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            return self._send(404, page("not found", "<h1>404</h1>"))
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            self._send(200, fh.read(), ctype, cache)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, "ok", "text/plain; charset=utf-8")
        if path.startswith("/fonts/"):
            return self._file(FONT_DIR, path[len("/fonts/"):], "public, max-age=604800")
        if path.startswith("/media/"):
            return self._file(os.path.join(DATA, "media"), path[len("/media/"):])
        doc = load()
        if path == "/":
            return self._send(200, landing(doc))
        if path == "/bench":
            return self._send(200, bench_page(doc))
        if path.startswith("/r/"):
            token = path[len("/r/"):]
            try:
                rev = json.load(open(os.path.join(DATA, "review.json")))
            except Exception as exc:
                return self._send(500, page("review", f"<h1>no review.json</h1><p>{exc}</p>"))
            want = rev.get("token") or ""
            if not want or not SLUG_RE.match(token or "") or not secrets.compare_digest(token, want):
                return self._send(404, page("not found", "<h1>404</h1>"))
            return self._send(200, review_page(rev))
        if path.startswith("/t/"):
            token = path[len("/t/"):]
            want = doc.get("meta", {}).get("prompt_token") or ""
            if not want or not SLUG_RE.match(token or "") or not secrets.compare_digest(token, want):
                return self._send(404, page("not found", "<h1>404</h1>"))
            return self._send(200, teleprompter(doc))
        if path.startswith("/p/"):
            slug = path[len("/p/"):]
            person = find(doc, slug) if SLUG_RE.match(slug or "") else None
            if not person:
                return self._send(404, page("not found",
                    "<h1>404</h1><p>That link does not match anyone. Check the URL "
                    "from the email, or reply and Carl will resend it.</p>"))
            return self._send(200, person_page(doc, person))
        return self._send(404, page("not found", "<h1>404</h1>"))


if __name__ == "__main__":
    print(f"imbue-thanks on :{PORT}, content from {DATA}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
