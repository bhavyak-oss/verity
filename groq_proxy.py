"""groq_proxy.py - server-side Groq proxy so real API keys never reach the browser.

Stdlib only, Python 3.9 compatible.
Keys come from environment variables only (same names server.py already uses):
  GROQ_API_KEYS (comma separated), GROQ_API_KEY, GROQ_API_KEY_2 ... GROQ_API_KEY_9
It deliberately does NOT read js/keys.js (that file is public).

Abuse limits (all configurable by env):
  VERITY_PROXY_IP_PER_MIN  default 20   requests per client IP per minute
  VERITY_PROXY_HOURLY      default 600  requests per hour, all clients together
  VERITY_GROQ_BASE         default https://api.groq.com (only change for tests)
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("VERITY_GROQ_BASE", "https://api.groq.com").rstrip("/") + "/openai/v1/chat/completions"
IP_PER_MIN = int(os.environ.get("VERITY_PROXY_IP_PER_MIN", "20"))
HOURLY_CAP = int(os.environ.get("VERITY_PROXY_HOURLY", "600"))
TIMEOUT_S = 90
MAX_TOKENS_CAP = 8192
PLACEHOLDER = "gsk_proxy_placeholder"
ALLOWED = ("model", "messages", "temperature", "max_tokens", "max_completion_tokens",
           "response_format", "tools", "tool_choice", "top_p", "stop", "seed")

_lock = threading.Lock()
_ip_hits = {}     # ip -> [timestamps]
_hour_hits = []   # timestamps
_cooldown = {}    # key -> unix time until which it is skipped
_rr = [0]         # round-robin start index


def _err(status, message, extra=None):
    return status, {"error": {"message": message}}, (extra or {})


def _keys():
    raw = [os.environ.get("GROQ_API_KEYS", ""), os.environ.get("GROQ_API_KEY", "")]
    raw += [os.environ.get("GROQ_API_KEY_%d" % i, "") for i in range(2, 10)]
    out = []
    for chunk in raw:
        for k in chunk.split(","):
            k = k.strip()
            if k and k != PLACEHOLDER and k not in out:
                out.append(k)
    return out


def _client_ip(headers, fallback):
    ip = ""
    try:
        ip = (headers.get("CF-Connecting-IP") or "").strip()
        if not ip:
            ip = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    except Exception:
        pass
    return ip or fallback or "?"


def _rate_ok(ip):
    now = time.time()
    with _lock:
        hits = [t for t in _ip_hits.get(ip, []) if now - t < 60]
        if len(hits) >= IP_PER_MIN:
            _ip_hits[ip] = hits
            return False, "Too many requests from your connection. Wait a minute and try again."
        global _hour_hits
        _hour_hits = [t for t in _hour_hits if now - t < 3600]
        if HOURLY_CAP and len(_hour_hits) >= HOURLY_CAP:
            return False, "The demo's hourly AI limit was reached. Try again later."
        hits.append(now)
        _ip_hits[ip] = hits
        _hour_hits.append(now)
        if len(_ip_hits) > 2000:   # keep memory bounded
            for k in list(_ip_hits)[:1000]:
                _ip_hits.pop(k, None)
    return True, ""


def _post(key, body_bytes):
    req = urllib.request.Request(
        UPSTREAM, data=body_bytes, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key,
                 "User-Agent": "Mozilla/5.0 (verity-proxy)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8"))


def handle(params, headers, client_ip):
    """Returns (http_status, json_obj, extra_headers)."""
    if not isinstance(params, dict) or not isinstance(params.get("messages"), list) or not params["messages"]:
        return _err(400, "Bad request: messages missing.")
    if not isinstance(params.get("model"), str) or not params["model"]:
        return _err(400, "Bad request: model missing.")
    ok, why = _rate_ok(_client_ip(headers, client_ip))
    if not ok:
        return _err(429, why, {"Retry-After": "60"})
    keys = _keys()
    if not keys:
        return _err(503, "The server has no Groq key configured.")

    body = {k: params[k] for k in ALLOWED if k in params}
    body["stream"] = False
    for f in ("max_tokens", "max_completion_tokens"):
        if isinstance(body.get(f), int) and body[f] > MAX_TOKENS_CAP:
            body[f] = MAX_TOKENS_CAP
    body_bytes = json.dumps(body).encode("utf-8")

    now = time.time()
    with _lock:
        start = _rr[0] % len(keys)
        _rr[0] += 1
        order = [keys[(start + i) % len(keys)] for i in range(len(keys))]
        fresh = [k for k in order if _cooldown.get(k, 0) <= now]
        rested = sorted([k for k in order if _cooldown.get(k, 0) > now], key=lambda k: _cooldown[k])
    for key in fresh + rested[:1]:
        try:
            return 200, _post(key, body_bytes), {}
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode("utf-8"))
            except Exception:
                data = None
            if e.code in (429, 401, 403):
                try:
                    wait = float(e.headers.get("retry-after") or 60)
                except Exception:
                    wait = 60.0
                with _lock:
                    _cooldown[key] = time.time() + (min(wait, 600) if e.code == 429 else 600)
                continue
            msg = ""
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                msg = str(data["error"].get("message") or "")
            return _err(e.code, msg[:300] or ("Groq request failed (HTTP %d)." % e.code))
        except Exception:
            return _err(502, "Could not reach Groq from the server.")
    with _lock:
        wait = max(1, int(min(_cooldown.get(k, 0) for k in keys) - time.time()))
    return _err(429, "AI rate limit reached on the server. Try again shortly.", {"Retry-After": str(min(wait, 120))})
