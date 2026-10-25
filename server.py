#!/usr/bin/env python3
"""Verity server: static files, YouTube helpers and live store prices in one file.

Uses only Python's standard library (the YouTube tools need: pip install youtube-transcript-api).

Usage:
    python3 server.py            serve on port 8000
    python3 server.py 80         serve on port 80 (URL has no port; may need sudo)

Sections of this file (they used to be three files):
    1. YouTube helpers   transcript + title relevance        (was verity_yt.py)
    2. Price lookup      Sourcing advisor store prices        (was verity_prices.py)
    3. Web server        static files and the /api/* routes   (was server.py)
"""
import functools
import http.server
import json
import os
import re
import socket
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ROOT = os.path.dirname(os.path.abspath(__file__))


# ============================================================================
# 1. YouTube helpers (was verity_yt.py)
# YouTube helpers for Verity (transcript + title-relevance), used by server.py.
#
# Based on the transcript.py and relevance.py scripts. Both libraries are imported lazily so the
# rest of Verity works without them:
#     pip install youtube-transcript-api           (needed for transcripts, relevance and fact-check)
#     pip install sentence-transformers            (optional: embedding-based relevance; large download)
# ============================================================================

ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
LANGS = ["en", "en-US", "en-GB", "hi"]

_cache = {}          # video id -> {"segments": [...], "title": str}
_cache_lock = threading.Lock()
_model = None
_model_lock = threading.Lock()


class MissingDependency(Exception):
    def __init__(self, package):
        super().__init__(package)
        self.package = package


def valid_id(video_id):
    return bool(video_id and ID_RE.match(video_id))


def fetch_title(video_id):
    """Title via YouTube's oEmbed endpoint (no API key). Returns '' on failure."""
    url = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
        {"url": "https://www.youtube.com/watch?v=" + video_id, "format": "json"})
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return str(json.load(resp).get("title", "")).strip()
    except Exception:
        return ""


def _segments_from(fetched):
    out = []
    for s in fetched:
        if isinstance(s, dict):
            text, start = s.get("text", ""), s.get("start", 0)
        else:
            text, start = s.text, s.start
        text = re.sub(r"\s+", " ", str(text).replace("\n", " ")).strip()
        if text:
            out.append({"t": round(float(start), 1), "s": text})
    return out


def get_transcript(video_id):
    """Returns {"segments": [{"t": seconds, "s": text}], "title": str}. Raises MissingDependency."""
    with _cache_lock:
        if video_id in _cache:
            return _cache[video_id]
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise MissingDependency("youtube-transcript-api")
    try:
        api = YouTubeTranscriptApi()
    except TypeError:
        api = None
    if api is not None and hasattr(api, "fetch"):                       # library v1.x
        try:
            fetched = api.fetch(video_id, languages=LANGS)
        except Exception as first:
            # No transcript in the preferred languages: take whatever the video has.
            try:
                fetched = next(iter(api.list(video_id))).fetch()
            except Exception:
                raise first
    else:                                                               # older versions
        fetched = YouTubeTranscriptApi.get_transcript(video_id, languages=LANGS)
    result = {"segments": _segments_from(fetched), "title": fetch_title(video_id)}
    if not result["segments"]:
        raise ValueError("This video has an empty transcript.")
    with _cache_lock:
        if len(_cache) > 40:
            _cache.clear()
        _cache[video_id] = result
    return result


def relevance(video_id, title):
    """Cosine similarity between the title and 200-word transcript chunks (all-MiniLM-L6-v2)."""
    global _model
    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError:
        raise MissingDependency("sentence-transformers")
    data = get_transcript(video_id)
    words = " ".join(s["s"] for s in data["segments"]).split()
    chunks = [" ".join(words[i:i + 200]) for i in range(0, len(words), 200)]
    with _model_lock:
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        model = _model
        title_emb = model.encode(title, convert_to_tensor=True)
        chunk_emb = model.encode(chunks, convert_to_tensor=True)
        scores = [float(x) for x in util.cos_sim(title_emb, chunk_emb)[0]]
    return {"mean": sum(scores) / len(scores), "max": max(scores), "scores": scores, "chunks": len(chunks)}


def friendly_error(exc):
    """The transcript library's messages are long; keep the useful first line."""
    msg = str(exc).strip()
    lines = [l.strip() for l in msg.splitlines() if l.strip()]
    first = lines[0] if lines else type(exc).__name__
    low = msg.lower()
    if "disabled" in low:
        return "Subtitles are turned off for this video, so there is no transcript."
    if "no transcript" in low or "could not retrieve" in low and "transcript" in low and "not available" in low:
        return "This video has no transcript available."
    if "blocked" in low or "ip" in low and "cloud" in low:
        return "YouTube blocked the transcript request from this network. Try again later or from another connection."
    if "unavailable" in low or "private" in low:
        return "This video is unavailable or private."
    return (type(exc).__name__ + ": " + first)[:300]


# ============================================================================
# 2. Price lookup for the Sourcing advisor (was verity_prices.py)
# Real vendor prices for Verity's Sourcing advisor (standard library only).
#
# Ported from the Flask app.py price check, so Verity no longer needs any demo sellers.
# Where prices come from (nothing is simulated, no made-up suppliers):
#   1. Free public storefront APIs of Indian electronics shops (Robu.in, Robocraze, ThinkRobotics,
#      Quartz Components, Probots). No key needed.
#   2. SERPER_API_KEY set  -> Google Shopping India listings (seller, price, link).
#   3. Otherwise, if a Groq key exists and a part still has fewer than 3 vendors -> Groq's built-in
#      web-search model (groq/compound-mini) reads live store pages.
# A part with no live listing returns no offers, and the app then shows an AI estimate, clearly labelled.
#
# Groq keys are read from the environment (GROQ_API_KEY, GROQ_API_KEYS, GROQ_API_KEY_2 ...) or from js/keys.js.
# ============================================================================

SERPER_KEY = os.environ.get("SERPER_API_KEY", "").strip()
SEARCH_MODEL = os.environ.get("SEARCH_MODEL", "groq/compound-mini")
CACHE_TTL = 3600
MAX_PARTS = 25
WEB_SEARCH_PARTS = int(os.environ.get("VERITY_WEB_PARTS", "6"))       # only the first N parts may use the (slower, rate-limited) web-search model
GROQ_HOURLY_CAP = int(os.environ.get("VERITY_GROQ_HOURLY", "40"))     # max Groq web-search requests per hour, all users (0 = unlimited)
GROQ_WEB_ENABLED = os.environ.get("VERITY_GROQ_WEB", "1") != "0"      # set VERITY_GROQ_WEB=0 to never use Groq for prices
CATEGORIES = ["electronics", "mechanical", "plastics", "raw_material", "fasteners", "textiles", "packaging", "other"]

_cache, _lock = {}, threading.Lock()
_cool = {}                  # Groq key -> unix time until which it is skipped
_stamps = []                # times of recent Groq web-search requests (for the hourly cap)

# (display name, kind, base url)
STORE_APIS = [
    ("Robu.in", "woo", "https://robu.in"),
    ("Robocraze", "shopify", "https://robocraze.com"),
    ("ThinkRobotics", "shopify", "https://thinkrobotics.com"),
    ("Quartz Components", "shopify", "https://quartzcomponents.com"),
    ("Probots", "shopify", "https://probots.co.in"),
]
UA = {"User-Agent": "Mozilla/5.0 (compatible; VerityPriceCheck/1.0)", "Accept": "application/json"}
STOP = {"and", "with", "the", "for", "pack", "set", "of", "kit", "pcs", "pc", "a", "in", "to"}


# ---------------------------------------------------------------- helpers
def parse_price(p):
    if p is None or isinstance(p, bool):
        return None
    if isinstance(p, (int, float)):
        return float(p) if p > 0 else None
    if any(x in str(p) for x in "$€£"):
        return None
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", str(p))
    try:
        v = float(m.group(1).replace(",", "")) if m else None
    except ValueError:
        v = None
    return v if v and v > 0 else None


def parse_json(t):
    idx = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if not idx:
        raise ValueError("no JSON in reply")
    t = t[min(idx):max(t.rfind("}"), t.rfind("]")) + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:   # repair common model slips: trailing commas, // comments
        t = re.sub(r"//[^\n]*", "", t)
        return json.loads(re.sub(r",\s*([}\]])", r"\1", t))


def host(u):
    try:
        h = urllib.parse.urlparse(u).netloc.lower()
    except Exception:
        return ""
    return h[4:] if h.startswith("www.") else h


def _get_json(url, timeout=8):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def toks(s):
    return [t for t in re.findall(r"[a-z0-9]+", str(s).lower()) if t not in STOP and (len(t) > 1 or t.isdigit())]


def _cached(key, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (time.time(), val)
    return val


# ---------------------------------------------------------------- Groq keys (for the web-search tier)
def groq_keys():
    raw = [os.environ.get("GROQ_API_KEYS", ""), os.environ.get("GROQ_API_KEY", "")]
    raw += [os.environ.get("GROQ_API_KEY_%d" % i, "") for i in range(2, 10)]
    keys = []
    for chunk in raw:
        for k in chunk.split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    try:
        with open(os.path.join(ROOT, "js", "keys.js"), encoding="utf-8") as f:
            txt = f.read()
        txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)     # ignore the example keys inside comments
        txt = re.sub(r"//[^\n]*", "", txt)
        for k in re.findall(r"gsk_[A-Za-z0-9_]+", txt):
            if k not in keys:
                keys.append(k)
    except OSError:
        pass
    return keys


def _budget_ok():
    if not GROQ_HOURLY_CAP:
        return True
    now = time.time()
    with _lock:
        _stamps[:] = [t for t in _stamps if now - t < 3600]
        if len(_stamps) >= GROQ_HOURLY_CAP:
            return False
        _stamps.append(now)
        return True


def groq_chat(messages):
    keys = groq_keys()
    if not keys:
        raise RuntimeError("no Groq key")
    if not _budget_ok():
        raise RuntimeError("Hourly limit for Groq web search reached (%d). Store prices still work; try again later." % GROQ_HOURLY_CAP)
    last = None
    for k in keys:
        if _cool.get(k, 0) > time.time():
            continue
        body = json.dumps({"model": SEARCH_MODEL, "temperature": 0, "messages": messages}).encode()
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                                     headers={"Authorization": "Bearer " + k, "Content-Type": "application/json",
                                              "User-Agent": UA["User-Agent"]})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403):
                _cool[k] = time.time() + 3600
            elif e.code == 429:
                _cool[k] = time.time() + 60
            else:
                raise
    raise last or RuntimeError("all Groq keys are cooling down")


# ---------------------------------------------------------------- price sources
def store_query(store, q):
    name, kind, base = store
    out = []
    if kind == "woo":     # WooCommerce Store API
        d = _get_json("%s/wp-json/wc/store/v1/products?per_page=12&search=%s" % (base, urllib.parse.quote_plus(q)))
        for it in d or []:
            pr = it.get("prices") or {}
            try:
                price = float(pr.get("price")) / (10 ** int(pr.get("currency_minor_unit", 2)))
            except (TypeError, ValueError):
                price = None
            out.append({"seller": name, "price": price if price and price > 0 else None,
                        "link": it.get("permalink") or "",
                        "title": re.sub(r"<[^>]+>|&amp;", " ", str(it.get("name") or "")).strip(),
                        "stock": it.get("is_in_stock")})
    else:                 # Shopify predictive search
        d = _get_json("%s/search/suggest.json?q=%s&resources%%5Btype%%5D=product&resources%%5Blimit%%5D=10"
                      % (base, urllib.parse.quote_plus(q)))
        for it in (((d or {}).get("resources") or {}).get("results") or {}).get("products", []) or []:
            out.append({"seller": name, "price": parse_price(it.get("price")),
                        "link": base + (it.get("url") or ""), "title": str(it.get("title") or ""),
                        "stock": it.get("available")})
    return out


def best_match(rows, c):
    """From one store's results keep only the listing that really matches the part (name words + spec words)."""
    nt, st = set(toks(c["name"])), set(toks(c["spec"]))
    best, bs = None, 0
    for r in rows:
        if not r.get("price"):
            continue
        tt = set(toks(r["title"]))
        nm = len(nt & tt) / max(len(nt), 1)
        if nm < 0.6:
            continue
        sc = nm + 0.6 * (len(st & tt) / max(len(st), 1))
        if sc > bs + 0.05 or (abs(sc - bs) <= 0.05 and best and r["price"] < best["price"]):
            best, bs = r, sc
    return best


def store_rows(c):
    """One best-matching real listing from each free store that carries this part."""
    q = c["name"][:80]

    def one(store):
        try:
            return _cached(("st" + store[0] + q).lower(), lambda: store_query(store, q))
        except Exception as e:
            print("  [store] %s failed for '%s': %s" % (store[0], q, str(e)[:80]))
            return []
    with ThreadPoolExecutor(max_workers=len(STORE_APIS)) as ex:
        res = list(ex.map(one, STORE_APIS))
    return [m for m in (best_match(r, c) for r in res) if m]


def serper_search(q):
    req = urllib.request.Request("https://google.serper.dev/shopping",
                                 data=json.dumps({"q": q, "gl": "in", "hl": "en", "num": 20}).encode(),
                                 headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        res = json.load(r).get("shopping", []) or []
    return [{"seller": it.get("source"), "price": parse_price(it.get("price")), "link": it.get("link") or "",
             "title": it.get("title") or ""} for it in res]


WSYS = ("You find CURRENT retail prices in India. Search the web and open real product pages. "
        "Reply with ONLY a JSON array (max 6 items). Each item: {\"vendor\": store or seller name, \"price_inr\": number for ONE unit, "
        "\"url\": the exact product page where you saw that price, \"title\": listing title}. "
        "Use different vendors (Amazon.in, Flipkart, Robu.in, Robocraze, Moglix, IndiaMART, manufacturer sites...). "
        "Only include a vendor if you actually saw its price on a page. Never guess or invent. If you find nothing, reply [].")


def web_search(q):
    txt = groq_chat([{"role": "system", "content": WSYS}, {"role": "user", "content": "Product: " + q}])
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S)
    if "[" not in txt:
        return []
    res = parse_json(txt)
    out = []
    for it in (res if isinstance(res, list) else []):
        if isinstance(it, dict):
            out.append({"seller": it.get("vendor"), "price": parse_price(it.get("price_inr")),
                        "link": it.get("url") or "", "title": it.get("title") or ""})
    return out


def search_rows(q):
    return _cached(("s" if SERPER_KEY else "w") + q.lower(), lambda: serper_search(q) if SERPER_KEY else web_search(q))


def offers_for(c, allow_web=True):
    """(offers, error) for one part. Top 4 vendors: in-stock first, then lowest real price."""
    q = ("%s %s" % (c["name"], c["spec"])).strip()[:90]
    rows, err = [], ""
    try:
        rows += store_rows(c)
    except Exception as e:
        err = str(e)[:160]
    if SERPER_KEY:
        try:
            rows += search_rows(q)
        except Exception as e:
            err = str(e)[:160]
    elif allow_web and groq_keys() and len({str(r["seller"]).lower() for r in rows if r.get("price")}) < 3:
        try:
            rows += search_rows(q)
        except Exception as e:
            err = str(e)[:160]
            print("  [live] web search failed for '%s': %s" % (q, err))
    est = c["price"]
    rows = [r for r in rows if r.get("price") and str(r.get("link", "")).startswith("http") and r.get("seller")
            and 0.1 * est <= r["price"] <= 10 * est]        # sanity check against the AI estimate
    if len(rows) >= 4:                                      # drop multi-packs / accessories / mismatches
        med = statistics.median(r["price"] for r in rows)
        rows = [r for r in rows if 0.3 * med <= r["price"] <= 3 * med] or rows
    best = {}
    for r in rows:
        k = str(r["seller"]).strip().lower()
        if k not in best or r["price"] < best[k]["price"]:
            best[k] = r
    out = []
    for r in sorted(best.values(), key=lambda r: (r.get("stock") is False, r["price"]))[:4]:
        out.append({"name": str(r["seller"]).strip()[:40], "price": round(r["price"], 2), "url": r["link"],
                    "source": host(r["link"]), "stock": r.get("stock"), "listing": str(r.get("title") or "")[:90]})
    return out, err


# ---------------------------------------------------------------- API entry points
def _clean_part(p):
    p = p if isinstance(p, dict) else {}
    try:
        price = float(p.get("price"))
    except (TypeError, ValueError):
        price = 0
    cat = p.get("category")
    return {"name": str(p.get("name") or "Part")[:80], "spec": str(p.get("spec") or "")[:160],
            "category": cat if cat in CATEGORIES else "other", "price": price if price > 0 else 1.0}


def lookup(parts, allow_web=True):
    """Real offers for every part. Returns the JSON object sent to the browser."""
    parts = [_clean_part(p) for p in (parts if isinstance(parts, list) else [])][:MAX_PARTS]
    if not parts:
        return {"ok": False, "error": "no_parts", "message": "No parts were sent."}
    allow_web = bool(allow_web) and GROQ_WEB_ENABLED
    jobs = [(c, allow_web and i < WEB_SEARCH_PARTS) for i, c in enumerate(parts)]
    with ThreadPoolExecutor(max_workers=6 if SERPER_KEY else 3) as ex:
        results = list(ex.map(lambda j: offers_for(j[0], j[1]), jobs))
    found = sum(1 for o, _ in results if o)
    src = "store websites" + (" + Google Shopping" if SERPER_KEY else (" + live web search" if groq_keys() and allow_web else ""))
    err = next((e for o, e in results if e), "")
    note = "" if found else ("No live vendor prices could be fetched" + (" (%s)" % err if err else "") + ".")
    return {"ok": True, "parts": [{"offers": o} for o, _ in results], "found": found, "source": src, "note": note}


def storetest(q):
    """/api/storetest?q=brushless motor : shows which free stores answer from YOUR network."""
    out = {}
    for s in STORE_APIS:
        try:
            r = store_query(s, q)
            out[s[0]] = {"ok": True, "results": len(r), "first": (r[0]["title"], r[0]["price"]) if r else None}
        except Exception as e:
            out[s[0]] = {"ok": False, "error": str(e)[:120]}
    return {"ok": True, "stores": out, "serper": bool(SERPER_KEY), "groq_web_search": bool(groq_keys())}


# ============================================================================
# 3. Web server (was server.py)
# Serves the site and the JSON API used by the YouTube tools and the Sourcing advisor.
# ============================================================================



class Handler(http.server.SimpleHTTPRequestHandler):
    # ---- JSON API used by the YouTube tools (transcript, relevance) ----
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def api(self, params):
        route = self.path.split("?")[0]
        video_id = (params.get("id") or "").strip()
        if route == "/api/status":
            return self.send_json({"ok": True})
        # ---- Sourcing advisor: real vendor prices (see py) ----
        if route == "/api/offers":
            try:
                return self.send_json(lookup(params.get("parts"), params.get("web") is not False))
            except Exception as e:
                return self.send_json({"ok": False, "error": "failed", "message": str(e)[:200]}, 500)
        if route == "/api/storetest":
            return self.send_json(storetest((params.get("q") or "arduino uno").strip()[:80]))
        if route == "/api/ask_doc":  # VERITY-TRY
            try:
                import ask_doc
                return self.send_json(ask_doc.handle(params))
            except Exception as e:
                return self.send_json({"ok": False, "error": "failed", "message": str(e)[:200]}, 500)
        if route in ("/api/ask", "/api/info"):
            try:
                import ask_api
                return self.send_json(ask_api.handle(route, params))
            except Exception as e:
                return self.send_json({"ok": False, "error": "failed", "message": str(e)[:200]}, 500)
        if route == "/api/groq":
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
        if not valid_id(video_id):
            return self.send_json({"ok": False, "error": "bad_id", "message": "Not a valid YouTube video ID."}, 400)
        try:
            if route == "/api/transcript":
                data = get_transcript(video_id)
                return self.send_json({"ok": True, "title": data["title"], "segments": data["segments"]})
            if route == "/api/relevance":
                title = (params.get("title") or "").strip() or get_transcript(video_id)["title"]
                if not title:
                    return self.send_json({"ok": False, "error": "no_title", "message": "Could not find the video title."})
                return self.send_json(dict(ok=True, title=title, **relevance(video_id, title)))
        except MissingDependency as e:
            return self.send_json({"ok": False, "error": "missing_dep", "package": e.package,
                                   "message": "Install it with: pip install " + e.package})
        except Exception as e:
            return self.send_json({"ok": False, "error": "failed", "message": friendly_error(e)})
        self.send_json({"ok": False, "error": "not_found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/api/"):
            return self.send_error(404)
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 300000)
            params = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send_json({"ok": False, "error": "bad_request"}, 400)
        self.api(params if isinstance(params, dict) else {})

    def do_GET(self):
        if self.path.startswith("/api/"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self.api({k: v[0] for k, v in q.items()})
        # VERITY-BLOCK: never serve source / config / backup files
        _bp = self.path.split("?")[0].lower()
        if _bp.endswith((".py", ".bak", ".jsonl", ".command", ".bat")) or _bp == "/config.json":
            return self.send_error(404)
        # VERITY-ROOT: Verity is the front page; the grounded govt assistant is /local
        _rp = self.path.split("?")[0].rstrip("/")
        if _rp == "" or _rp == "/verity":
            self.path = "/index.html"
        elif _rp == "/local":
            self.path = "/local.html"
        # Clean URLs: /app opens app.html
        path = self.path.split("?")[0].rstrip("/")
        if path and "." not in os.path.basename(path) and os.path.exists(os.path.join(ROOT, path.lstrip("/") + ".html")):
            self.path = path + ".html"
        super().do_GET()

    def end_headers(self):
        # Always serve the latest files (the browser used to keep old css/js after an update)
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("  " + fmt % args)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no data is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    handler = functools.partial(Handler, directory=ROOT)
    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    except PermissionError:
        sys.exit(f"Port {PORT} needs administrator rights. Run: sudo python3 server.py {PORT}")
    except OSError as e:
        sys.exit(f"Could not use port {PORT}: {e}. Try another port, for example: python3 server.py 8080")
    suffix = "" if PORT == 80 else f":{PORT}"
    print("\nVerity is running.\n")
    print(f"  On this computer:      http://localhost{suffix}")
    print(f"  On your Wi-Fi network: http://{lan_ip()}{suffix}")
    print("\nPress Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
