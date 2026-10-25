#!/usr/bin/env python3
"""add_try.py - adds the "Try your own document" feature to the Verity folder.

Usage (inside the Verity folder):   python3 add_try.py .
It changes two files, after saving a backup of each (only if no backup exists yet):
  server.py   -> new route /api/ask_doc (calls ask_doc.py)
  local.html  -> small link "Try your own document" under "Ask your own question"
Running it twice does nothing the second time. Python 3.9 compatible.
"""
import os
import shutil
import sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")

ROUTE = '''        if route == "/api/ask_doc":  # VERITY-TRY
            try:
                import ask_doc
                return self.send_json(ask_doc.handle(params))
            except Exception as e:
                return self.send_json({"ok": False, "error": "failed", "message": str(e)[:200]}, 500)
'''
ANCHOR_SERVER = '        if route in ("/api/ask", "/api/info"):\n'

LINK = '''    <p class="fine" style="text-align:center;margin:14px 0 0"><!-- VERITY-TRY-LINK --><a href="/try" style="color:var(--blue);text-decoration:none;font-size:14px">Try your own document &rarr;</a></p>

'''
ANCHOR_HTML = '    <details id="passBox" hidden>\n'


def need(path):
    p = os.path.join(root, path)
    if not os.path.exists(p):
        sys.exit("Missing file: %s (run this inside the Verity folder)" % p)
    return p


def backup(p, suffix):
    b = p + suffix
    if not os.path.exists(b):
        shutil.copy2(p, b)


def patch(path, marker, anchor, add, before, suffix):
    p = need(path)
    s = open(p, encoding="utf-8").read()
    if marker in s:
        print("  - %s: already done" % path)
        return
    if s.count(anchor) != 1:
        sys.exit("%s: expected spot not found (%d matches). Nothing changed; send me this message." % (path, s.count(anchor)))
    backup(p, suffix)
    s = s.replace(anchor, add + anchor if before else anchor + add)
    open(p, "w", encoding="utf-8").write(s)
    print("  + %s: patched (backup %s%s)" % (path, path, suffix))


need("ask_api.py")
need("ask_doc.py")
need("try.html")
patch("server.py", "VERITY-TRY", ANCHOR_SERVER, ROUTE, True, ".bak4")
patch("local.html", "VERITY-TRY-LINK", ANCHOR_HTML, LINK, True, ".bak4")
print("done. Restart go_public.py (server.py changed), then open /try")
