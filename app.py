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
:root{--page:#0a0a0a;--card:#111;--line:#262626;--ink:#ededed;--body:#a1a1a1;
 --mute:#7a7a7a;--accent:#52a8ff;--accent-bg:#0d2440}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);
 font-family:Geist,Inter,system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.5}
.wrap{max-width:720px;margin:0 auto;padding:64px 24px 96px}
.eyebrow{font-family:'Geist Mono',ui-monospace,Menlo,monospace;font-size:12px;
 line-height:16px;text-transform:uppercase;color:var(--mute);margin:0 0 16px}
h1{font-size:48px;line-height:48px;font-weight:600;letter-spacing:-2.4px;margin:0 0 16px}
h2{font-size:24px;line-height:32px;font-weight:600;letter-spacing:-.96px;margin:48px 0 16px}
p{color:var(--body);margin:0 0 16px}
p.lead{color:var(--ink);font-size:20px;line-height:28px;letter-spacing:-.6px}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
 padding:24px;margin:24px 0}
.card h3{margin:0 0 8px;font-size:20px;line-height:28px;font-weight:600;letter-spacing:-.6px}
.pill{display:inline-block;font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;
 line-height:16px;padding:4px 10px;border-radius:9999px;background:var(--accent-bg);
 color:var(--accent)}
video,iframe{width:100%;border:1px solid var(--line);border-radius:8px;background:#000;
 aspect-ratio:16/9;display:block}
.note{white-space:pre-wrap;color:var(--ink)}
ul{color:var(--body);padding-left:20px}
li{margin-bottom:8px}
.foot{margin-top:64px;padding-top:24px;border-top:1px solid var(--line);
 font-family:'Geist Mono',ui-monospace,monospace;font-size:12px;color:var(--mute)}
.missing{border:1px dashed var(--line);border-radius:8px;padding:24px;color:var(--mute);
 font-family:'Geist Mono',ui-monospace,monospace;font-size:12px}
@media(max-width:600px){h1{font-size:32px;line-height:40px;letter-spacing:-1.28px}
 .wrap{padding:40px 20px 64px}}
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
{gather_block}
<h2>Your clip</h2>
<p>{html.escape(m.get('clip_blurb',''))}</p>
<h2>One ask, one offer</h2>
<div class="card"><h3>{html.escape(m.get('ask_title',''))}</h3>
<p>{html.escape(m.get('ask_body',''))}</p></div>
<div class="card"><h3>{html.escape(m.get('offer_title',''))}</h3>
<p>{html.escape(m.get('offer_body',''))}</p></div>
<div class="foot">{html.escape(m.get('footer',''))}</div>""")


def person_page(doc, person):
    m = doc.get("meta", {})
    gather = (m.get("gather_url") or "").strip()
    asks = "".join(f"<li>{html.escape(a)}</li>" for a in person.get("asks", []))
    return page(f"For {person.get('first','you')}", f"""
<p class="eyebrow">a message for one person</p>
<h1>{html.escape(person.get('name',''))}</h1>
<p class="lead">{html.escape(person.get('headline',''))}</p>
{player(person)}
<div class="card"><p class="note">{html.escape(person.get('note',''))}</p></div>
{f'<h2>If you have ten minutes</h2><ul>{asks}</ul>' if asks else ''}
<h2>The replica</h2>
<p>{html.escape(m.get('gather_blurb',''))}</p>
{f'<p><a href="{html.escape(gather)}">Open the office in Gather</a></p>' if gather else ''}
<div class="foot">{html.escape(m.get('footer',''))}
<span class="pill">this page is unlisted</span></div>""")

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
