"""ask_api.py - local grounded-QA backend for Verity's /ask page.

Stdlib only, Python 3.9 compatible.
Exposes handle(route, params) for /api/info and /api/ask.
Talks ONLY to the SGLang servers listed in config.json. Never calls Groq.
"""
import json
import math
import os
import re
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "config.json")
CHUNK_FILES = ["demo_chunks.jsonl", "sample_chunks.jsonl"]

MAX_QUESTION_CHARS = 1000
MODEL_TIMEOUT_S = 120
USER_DOC_MAX_CHARS = 250000      # pasted / uploaded document text (chars <= 250 KB)
USER_DOC_CHUNK_CHARS = 1400      # target chunk size for user documents
DEFAULT_MODELS = ["curated", "base"]

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["answered", "not_found"]},
        "answer": {"type": "string"},
        "evidence_quote": {"type": "string"},
        "source_id": {"type": "string"},
    },
    "required": ["status", "answer", "evidence_quote", "source_id"],
    "additionalProperties": False,
}

# FALLBACK ONLY. The real system prompt must be the one used in training.
# Best fix: copy common.py (from teammate A) next to this file; it is used first.
# Or put the exact training prompt in config.json under "system_prompt".
FALLBACK_SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided CONTEXT. "
    "Reply with a JSON object with keys status, answer, evidence_quote, source_id. "
    "If the context does not contain the answer, use status \"not_found\" and empty "
    "evidence_quote and source_id. Otherwise status \"answered\", answer in the "
    "user's language, evidence_quote = an exact substring of the context, "
    "source_id = the chunk id."
)

# ---------------------------------------------------------------- config

def load_config():
    """Re-read config.json on every call so tunnel URLs can be edited without restart."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("models", {})
    cfg.setdefault("top_k", 3)
    cfg.setdefault("context_char_budget", 3500)
    cfg.setdefault("held_out_prefixes", ["RTI"])
    return cfg

# ---------------------------------------------------------------- chunks + BM25

_TOKEN_RE = re.compile(r"[\w\u0900-\u0963\u0966-\u097F]+", re.UNICODE)  # keeps matras, drops danda


def tokenize(text):
    return _TOKEN_RE.findall((text or "").lower())


class BM25(object):
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.tf = []
        self.dl = []
        df = {}
        for c in chunks:
            toks = tokenize(c["text"])
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            self.dl.append(len(toks))
            for t in counts:
                df[t] = df.get(t, 0) + 1
        n = len(chunks)
        self.avgdl = (sum(self.dl) / n) if n else 0.0
        self.idf = {t: math.log(1.0 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query, k):
        q = tokenize(query)
        scored = []
        for i, counts in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = counts.get(t)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avgdl or 1.0))
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: -x[0])
        return [(self.chunks[i], s) for s, i in scored[:k]]


_lock = threading.Lock()
_state = {"file": None, "mtime": None, "chunks": [], "indexes": {}}


def _chunk_path():
    for name in CHUNK_FILES:
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            return p
    return None


def _ensure_chunks():
    p = _chunk_path()
    if p is None:
        return None
    mtime = os.path.getmtime(p)
    with _lock:
        if _state["file"] != p or _state["mtime"] != mtime:
            chunks = []
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    if o.get("chunk_id") and o.get("text"):
                        chunks.append({"chunk_id": str(o["chunk_id"]),
                                       "doc_id": str(o.get("doc_id", "")),
                                       "text": o["text"]})
            _state.update(file=p, mtime=mtime, chunks=chunks, indexes={})
    return p


def index_for(doc_id):
    key = doc_id or "ALL"
    with _lock:
        idx = _state["indexes"].get(key)
        if idx is None:
            pool = _state["chunks"] if key == "ALL" else [c for c in _state["chunks"] if c["doc_id"] == key]
            idx = BM25(pool)
            _state["indexes"][key] = idx
        return idx


def retrieve(question, doc_id, top_k, char_budget):
    return _pick(index_for(doc_id).search(question, top_k), char_budget)


_SENT_RE = re.compile(r"(?<=[.!?\u0964])\s+")


def chunk_text(text, target=USER_DOC_CHUNK_CHARS, hard=1900):
    """Split a user document into passages of roughly `target` chars (paragraph/sentence aware)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    pieces = []
    for p in paras:
        if not p:
            continue
        if len(p) <= hard:
            pieces.append(p)
            continue
        cur = ""
        for sent in _SENT_RE.split(p):
            while len(sent) > hard:          # no punctuation at all: hard split
                if cur:
                    pieces.append(cur)
                    cur = ""
                pieces.append(sent[:hard])
                sent = sent[hard:]
            if cur and len(cur) + 1 + len(sent) > target:
                pieces.append(cur)
                cur = sent
            else:
                cur = (cur + " " + sent).strip()
        if cur:
            pieces.append(cur)
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 2 + len(p) > target:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def retrieve_user_doc(question, text, top_k, char_budget):
    pieces = chunk_text(text)
    pool = [{"chunk_id": "your_doc_c%d" % (i + 1), "doc_id": "your_document", "text": t}
            for i, t in enumerate(pieces)]
    return _pick(BM25(pool).search(question, top_k), char_budget), len(pool)


def _pick(hits, char_budget):
    chosen, used = [], 0
    for c, score in hits:
        text = c["text"]
        if used + len(text) > char_budget:
            if chosen:
                continue          # skip chunks that do not fit
            text = text[:char_budget]  # always keep the best chunk, truncated if needed
        chosen.append({"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "text": text,
                       "score": round(score, 3)})
        used += len(text)
    return chosen

# ---------------------------------------------------------------- prompt + model

def format_context(chunks):
    return "\n\n".join("[%s]\n%s" % (c["chunk_id"], c["text"]) for c in chunks)


def build_messages(chunks, question, cfg):
    try:
        import common  # teammate A's file: exact training prompt
        msgs = common.build_messages(chunks, question)
        if isinstance(msgs, list) and msgs:
            return msgs
    except Exception:
        pass
    system = cfg.get("system_prompt") or FALLBACK_SYSTEM_PROMPT
    user = "CONTEXT:\n" + format_context(chunks) + "\n\nQUESTION: " + question
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def ask_model(spec, messages, context_text):
    url = (spec.get("url") or "").strip().rstrip("/")
    if not url:
        return {"error": "not_connected", "message": "Model URL is empty in config.json."}
    payload = {
        "model": spec.get("model", ""),
        "messages": messages,
        "temperature": 0,
        "repetition_penalty": 1.0,
        "max_tokens": 400,
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "grounded_answer", "schema": SCHEMA, "strict": True}},
    }
    try:
        req = urllib.request.Request(
            url + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     # Cloudflare tunnels may reject the default Python-urllib agent
                     "User-Agent": "Mozilla/5.0 (verity-ask)"},
            method="POST")
        with urllib.request.urlopen(req, timeout=MODEL_TIMEOUT_S) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        return {"error": "request_failed", "message": str(e)[:200]}
    try:
        out = json.loads(content)
        if not isinstance(out, dict):
            raise ValueError("not an object")
    except ValueError:
        return {"error": "bad_json", "message": "Model did not return valid JSON.", "raw": str(content)[:400]}
    quote = out.get("evidence_quote") or ""
    return {
        "status": out.get("status", ""),
        "answer": out.get("answer", ""),
        "evidence_quote": quote,
        "source_id": out.get("source_id", ""),
        "quote_valid": bool(quote) and quote in context_text,
    }

# ---------------------------------------------------------------- public entry

def _docs(cfg):
    counts = {}
    for c in _state["chunks"]:
        counts[c["doc_id"]] = counts.get(c["doc_id"], 0) + 1
    prefixes = tuple(cfg.get("held_out_prefixes") or [])
    return [{"doc_id": d, "chunks": n, "held_out": bool(prefixes) and d.startswith(prefixes)}
            for d, n in sorted(counts.items())]


def handle(route, params):
    cfg = load_config()
    path = _ensure_chunks()
    models = {k: {"label": v.get("label", k), "ready": bool((v.get("url") or "").strip())}
              for k, v in cfg["models"].items()}
    if route == "/api/info":
        return {"ok": True, "docs": _docs(cfg), "models": models,
                "chunk_file": os.path.basename(path) if path else None}

    # route == "/api/ask"
    q = (params.get("question") or "").strip()
    if not q:
        return {"ok": False, "error": "empty_question"}
    q = q[:MAX_QUESTION_CHARS]
    user_text = params.get("doc_text")
    user_doc = isinstance(user_text, str) and bool(user_text.strip())
    if user_doc and len(user_text) > USER_DOC_MAX_CHARS:
        return {"ok": False, "error": "doc_too_long",
                "message": "Document is too long (limit %d characters)." % USER_DOC_MAX_CHARS}
    if path is None and not user_doc:
        return {"ok": False, "error": "no_chunks", "message": "demo_chunks.jsonl not found."}
    doc_id = (params.get("doc_id") or "ALL").strip() or "ALL"
    known = set(d["doc_id"] for d in _docs(cfg))
    if not user_doc and doc_id != "ALL" and doc_id not in known:
        return {"ok": False, "error": "unknown_doc"}
    wanted = params.get("models")
    if not isinstance(wanted, list):
        wanted = DEFAULT_MODELS
    wanted = [m for m in wanted if m in cfg["models"]] or [m for m in DEFAULT_MODELS if m in cfg["models"]]

    n_doc_chunks = None
    if user_doc:
        chunks, n_doc_chunks = retrieve_user_doc(q, user_text, int(cfg["top_k"]), int(cfg["context_char_budget"]))
    else:
        chunks = retrieve(q, doc_id, int(cfg["top_k"]), int(cfg["context_char_budget"]))
    messages = build_messages(chunks, q, cfg)
    context_text = "\n".join(c["text"] for c in chunks)

    results = {}
    if chunks:
        with ThreadPoolExecutor(max_workers=max(1, len(wanted))) as ex:
            futs = {k: ex.submit(ask_model, cfg["models"][k], messages, context_text) for k in wanted}
            for k, f in futs.items():
                try:
                    results[k] = f.result()
                except Exception as e:
                    results[k] = {"error": "request_failed", "message": str(e)[:200]}
    else:
        for k in wanted:
            results[k] = {"error": "no_passages", "message": "No matching passage found for this question."}
    return {"ok": True, "user_doc": user_doc, "doc_chunks": n_doc_chunks, "chunks": chunks, "prompt_format": messages[-1]["content"][:300],
            "results": results}
