"""add_switcher.py - puts the same LLM/Freshers track switch on Verity's landing page (index.html).
Usage: python3 add_switcher.py [verity-folder]. Safe to run twice. Backup: index.html.bak3"""
import os, shutil, sys
root = sys.argv[1] if len(sys.argv) > 1 else "."
p = os.path.join(root, "index.html")
s = open(p, encoding="utf-8").read()
if "TRACKSWITCH" in s:
    print("already done"); sys.exit(0)
if s.count("</body>") != 1:
    sys.exit("ERROR: </body> not found exactly once, nothing written")
SNIP = """<!-- TRACKSWITCH -->
<style>
.trk{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:9999;display:flex;width:min(560px,calc(100% - 24px));border:1px solid #243047;border-radius:16px;background:#111826;overflow:hidden;box-shadow:0 12px 34px rgba(0,0,0,.45);font-family:"Public Sans",system-ui,sans-serif}
.trk a{flex:1;display:flex;flex-direction:column;gap:2px;padding:10px 16px;text-decoration:none;color:#9aa7bf;font-size:15px;font-weight:700;line-height:1.2}
.trk a small{font-size:11.5px;font-weight:600;letter-spacing:.4px;text-transform:uppercase;opacity:.85}
.trk a+a{border-left:1px solid #243047;text-align:right;align-items:flex-end}
.trk a.on{color:#07101c;background:linear-gradient(90deg,#86e0b3,#8fb0ff);cursor:default}
.trk a:not(.on):hover{color:#eef2fa;background:rgba(122,162,255,.1)}
@media(max-width:480px){.trk a{padding:9px 12px;font-size:14px}}
</style>
<nav class="trk" aria-label="Project tracks"><a href="/"><small>LLM Track</small>&larr; Govt Document Assistant</a><a class="on" href="verity" aria-current="page"><small>Freshers Track</small>Verity</a></nav>
"""
if not os.path.exists(p + ".bak3"):
    shutil.copyfile(p, p + ".bak3")
open(p, "w", encoding="utf-8").write(s.replace("</body>", SNIP + "</body>"))
print("+ track switch added to index.html")
