"""One-time patcher for Verity (v2). Usage: python3 apply_patch.py [path/to/verity-folder]
Safe to run several times: every change checks if it is already applied.

server.py : /api/ask + /api/info hook (local model), /api/groq hook (server-side Groq proxy),
            POST body cap 100 KB -> 300 KB, block source/config files from being downloaded,
            front page (/) shows the Govt Document Assistant; Verity landing stays at /index.html and /verity
app.html  : loads js/groq-shim.js before keys.js
index.html: "Ask documents" nav link
Original files are saved once as <name>.bak (never overwritten)."""
import os
import shutil
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

ANCHOR = "        if not valid_id(video_id):\n"
ASK_HOOK = '''        if route in ("/api/ask", "/api/info"):
            try:
                import ask_api
                return self.send_json(ask_api.handle(route, params))
            except Exception as e:
                return self.send_json({"ok": False, "error": "failed", "message": str(e)[:200]}, 500)
'''
GROQ_HOOK = '''        if route == "/api/groq":
            try:
                import groq_proxy
                status, obj, extra = groq_proxy.handle(params, self.headers, self.client_address[0])
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for hk, hv in (extra or {}).items():
                    self.send_header(hk, hv)
                self.end_headers()
                return self.wfile.write(body)
            except Exception:
                return self.send_json({"error": {"message": "AI proxy failed."}}, 500)
'''
CAP_OLD = 'int(self.headers.get("Content-Length") or 0), 100000)'
CAP_NEW = 'int(self.headers.get("Content-Length") or 0), 300000)'
GET_ANCHOR = "        # Clean URLs: /app opens app.html\n"
BLOCK = '''        # VERITY-BLOCK: never serve source / config / backup files
        _bp = self.path.split("?")[0].lower()
        if _bp.endswith((".py", ".bak", ".jsonl", ".command", ".bat")) or _bp == "/config.json":
            return self.send_error(404)
'''
SHIM_OLD = '<script src="js/keys.js"></script>'
SHIM_NEW = '<script src="js/groq-shim.js"></script>\n' + SHIM_OLD
ROOT_ASK = '''        # VERITY-ROOT: the grounded assistant is the front page; Verity's landing is /index.html or /verity
        _rp = self.path.split("?")[0].rstrip("/")
        if _rp == "":
            self.path = "/ask.html"
        elif _rp == "/verity":
            self.path = "/index.html"
'''
NAV_OLD = '    <a class="btn small" href="app.html">Open Verity</a>'
NAV_NEW = '    <a href="ask">Ask documents</a>\n' + NAV_OLD


def once(s, old, new, marker, label, before=True):
    if marker in s:
        print("  - " + label + ": already done")
        return s
    if s.count(old) != 1:
        sys.exit("ERROR: anchor for '" + label + "' not found exactly once, aborting (nothing written)")
    print("  + " + label)
    return s.replace(old, (new + old) if before else new)


def patch(name, fn):
    p = os.path.join(root, name)
    with open(p, "r", encoding="utf-8") as f:
        s = f.read()
    print(name)
    out = fn(s)
    if out == s:
        return
    if not os.path.exists(p + ".bak"):
        shutil.copyfile(p, p + ".bak")
    with open(p, "w", encoding="utf-8") as f:
        f.write(out)


def server(s):
    s = once(s, ANCHOR, ASK_HOOK, "import ask_api", "/api/ask hook")
    s = once(s, ANCHOR, GROQ_HOOK, "import groq_proxy", "/api/groq hook")
    if "300000" in s:
        print("  - POST cap: already done")
    else:
        if s.count(CAP_OLD) != 1:
            sys.exit("ERROR: POST cap line not found exactly once, aborting")
        print("  + POST cap 300 KB")
        s = s.replace(CAP_OLD, CAP_NEW)
    s = once(s, GET_ANCHOR, BLOCK, "VERITY-BLOCK", "block sensitive files")
    s = once(s, GET_ANCHOR, ROOT_ASK, "VERITY-ROOT", "front page = /ask")
    return s


def app(s):
    return once(s, SHIM_OLD, SHIM_NEW, "groq-shim.js", "groq shim", before=False)


def index(s):
    return once(s, NAV_OLD, NAV_NEW, 'href="ask"', "nav link", before=False)


patch("server.py", server)
patch("app.html", app)
patch("index.html", index)
print("done")
