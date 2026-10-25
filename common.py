"""
SHARED CONTRACT - dono log SAME file use karo. Hour 0-2 me freeze kar do, phir mat badlo.
(Sirf ek jagah badlega: B hour-2 pe AlignTune ka rendered prompt dekh ke build_prompt() match karega - dekho B ka doc.)
"""
import json

SYSTEM = (
    "You are a grounded assistant for government / organisation documents. "
    "Answer ONLY using the CONTEXT. Reply in the user's language (Hindi, Hinglish or regional). "
    "If the context does not contain the answer, return status 'not_found'. "
    "Return JSON with keys: status, answer, evidence_quote, source_id. "
    "evidence_quote must be an exact substring of the context."
)

# JSON schema (SGLang constrained decoding me yahi jayega)
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

NOT_FOUND_TEXT = {
    "hi": "दिए गए दस्तावेज़ों में इसकी जानकारी नहीं है।",
    "hinglish": "Diye gaye documents me iski jaankari nahi hai.",
    "en": "The provided documents do not contain this information.",
}


def format_context(chunks):
    """chunks = [{"chunk_id": "d3_c7", "text": "..."}]"""
    return "\n\n".join(f"[{c['chunk_id']}]\n{c['text']}" for c in chunks)


def build_prompt(chunks, question):
    """Single user-prompt string. Training aur inference DONO me same hona chahiye."""
    return f"{SYSTEM}\n\nCONTEXT:\n{format_context(chunks)}\n\nQUESTION: {question}"


def build_messages(chunks, question):
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "CONTEXT:\n" + format_context(chunks) + "\n\nQUESTION: " + question}]


def target_json(status, answer="", evidence_quote="", source_id=""):
    return json.dumps(
        {"status": status, "answer": answer,
         "evidence_quote": evidence_quote, "source_id": source_id},
        ensure_ascii=False,
    )


# ---------------- FILE FORMATS (A banata hai, B padhta hai) ----------------
# SFT (HF dataset, alpaca columns):  {"instruction": question, "input": context_text, "output": target_json(...)}
#     + extra cols (ignore ho jayenge): "lang", "qtype", "id"
# DPO (HF dataset):                  {"prompt": build_prompt(...), "chosen": target_json(...), "rejected": <hallucinated json>}
# TEST (jsonl, kabhi training me nahi):
#     {"id","lang","qtype": "answerable|unanswerable|adversarial","split": "A_seen_docs|B_unseen_docs|adv",
#      "chunks":[{"chunk_id","text"}], "question", "gold_answer", "gold_status"}
#
# HF Hub repos (naam team decide kare, private rakho):
#   <hfuser>/ps3-sft-raw, <hfuser>/ps3-sft-curated, <hfuser>/ps3-dpo-curated      (A -> B)
#   <hfuser>/ps3-model-base-pick, ps3-sft-raw, ps3-sft-curated, ps3-dpo           (B -> A, MERGED 16-bit models)
