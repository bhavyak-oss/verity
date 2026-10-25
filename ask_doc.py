"""ask_doc.py - "Try your own document" backend for Verity's /try page.

Stdlib only, Python 3.9 compatible. Reuses ask_api.py (BM25, prompt builder, model call).
The visitor's text is kept in memory for one request only: it is never written to disk.
Talks ONLY to the SGLang servers in config.json. Never calls Groq.
"""
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import ask_api

MAX_DOC_CHARS = 80000     # ~240 KB of Devanagari in JSON, under server.py's 300 KB POST cap
MIN_DOC_CHARS = 40
CHUNK_CHARS = 1700        # same size as the chunks the model was evaluated on (~1700)
DOC_ID = "your_document"
GLOBAL_PER_MINUTE = 30    # behind a tunnel every visitor looks like 127.0.0.1, so one shared limit

_stamps = deque()
_lock = threading.Lock()

STOP = set("what does is are was were the a an of in on to for and or by with from at as be been it "
           "this that which who whom how when where why do did can could shall should will would may "
           "might must i you we they he she not no any".split())

_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def _allowed():
    now = time.time()
    with _lock:
        while _stamps and now - _stamps[0] > 60:
            _stamps.popleft()
        if len(_stamps) >= GLOBAL_PER_MINUTE:
            return False
        _stamps.append(now)
        return True


def split_chunks(text, size=CHUNK_CHARS):
    """Pack sentences into chunks of at most ~size characters, repeating a short last sentence as overlap."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    units = []
    for u in _SPLIT.split(text):
        u = re.sub(r"[ \t]+", " ", u).strip()
        while len(u) > size:
            units.append(u[:size])
            u = u[size:]
        if u:
            units.append(u)
    chunks, cur, n = [], [], 0
    for u in units:
        if cur and n + len(u) + 1 > size:
            chunks.append(" ".join(cur))
            keep = cur[-1] if len(cur[-1]) <= 300 else ""
            cur, n = ([keep] if keep else []), len(keep)
        cur.append(u)
        n += len(u) + 1
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def pick(chunks, question, top_k, budget):
    """Returns (chosen_chunks, note). A short document is given whole, so retrieval cannot miss."""
    total = sum(len(c["text"]) for c in chunks)
    if total <= budget:
        return [dict(c, score=0) for c in chunks], "whole"
    q = " ".join(w for w in ask_api.tokenize(question) if w not in STOP) or question
    hits = ask_api.BM25(chunks).search(q, top_k)
    note = "bm25"
    if not hits:
        hits = [(c, 0.0) for c in chunks[:top_k]]
        note = "nomatch"
    chosen, used = [], 0
    for c, score in hits:
        text = c["text"]
        if used + len(text) > budget:
            if chosen:
                continue
            text = text[:budget]
        chosen.append({"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "text": text, "score": round(score, 3)})
        used += len(text)
    return chosen, note


def handle(params):
    q = (params.get("question") or "").strip()[:ask_api.MAX_QUESTION_CHARS]
    if not q:
        return {"ok": False, "error": "empty_question", "message": "Type a question first."}
    text = params.get("text")
    text = text.strip() if isinstance(text, str) else ""
    if len(text) < MIN_DOC_CHARS:
        return {"ok": False, "error": "empty_document", "message": "Paste or upload your document first."}
    if len(text) > MAX_DOC_CHARS:
        return {"ok": False, "error": "too_long",
                "message": "Document is too long (%d characters). The limit is %d." % (len(text), MAX_DOC_CHARS)}
    if not _allowed():
        return {"ok": False, "error": "busy", "message": "Too many requests right now. Try again in a minute."}

    cfg = ask_api.load_config()
    wanted = params.get("models")
    if not isinstance(wanted, list):
        wanted = ask_api.DEFAULT_MODELS
    wanted = [m for m in wanted if m in cfg["models"]] or [m for m in ask_api.DEFAULT_MODELS if m in cfg["models"]]

    pieces = split_chunks(text)
    chunks = [{"chunk_id": "%s_c%d" % (DOC_ID, i + 1), "doc_id": DOC_ID, "text": t} for i, t in enumerate(pieces)]
    chosen, note = pick(chunks, q, int(cfg["top_k"]), int(cfg["context_char_budget"]))
    messages = ask_api.build_messages(chosen, q, cfg)
    context_text = "\n".join(c["text"] for c in chosen)

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(wanted))) as ex:
        futs = {k: ex.submit(ask_api.ask_model, cfg["models"][k], messages, context_text) for k in wanted}
        for k, f in futs.items():
            try:
                results[k] = f.result()
            except Exception as e:
                results[k] = {"error": "request_failed", "message": str(e)[:200]}
    return {"ok": True, "doc_chars": len(text), "n_chunks": len(chunks), "read": note,
            "chunks": chosen, "results": results}
