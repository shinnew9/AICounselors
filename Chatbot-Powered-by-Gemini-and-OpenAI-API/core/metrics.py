import re, json
REWRITE_HDR = re.compile(r"##\s*Exemplars", re.I)

SKILL_LABEL_SYSTEM = """
You are rating counseling micro-skills on a single counselor message.
Return STRICT JSON with 0/1 flags (no prose).
Fields: empathy, reflection, validation, open_question, suggestion.
Output ONLY: {"empathy":0,"reflection":1,"validation":0,"open_question":1,"suggestion":0}
"""


def estimate_gap_exposure(md: str) -> int:
    capture, words = False, 0
    for ln in md.splitlines():
        if REWRITE_HDR.search(ln):
            capture = True
            continue
        if ln.startswith("## ") and capture:
            break
        if capture: 
            words += len(ln.split())
    return words


def parse_session_metrics(md: str) -> dict:
    out = {
        "Empathy": {"check": None, "score": None},
        "Reflection":{"check": None,"score": None},
        "Open Questions":{"check": None,"score": None},
        "Validation":{"check": None,"score": None},
        "Advice Timing":{"ok": None,"score": None},
        "gap_words": estimate_gap_exposure(md),
    }
    for raw in md.splitlines():
        s = raw.strip()
        m = re.match(r"^-?\s*(Empathy|Reflection|Open Questions|Validation\s*/\s*Non-judgment)\s*\((✔|✖)(?:\s*,\s*([0-5]))?", s, re.I)
        if m:
            name = m.group(1)
            key = "Validation" if name.lower().startswith("validation") else name
            out[key]["check"] = 1 if m.group(2) == "✔" else 0
            if m.group(3) is not None:
                out[key]["score"] = int(m.group(3))
            continue
        m2 = re.match(r"^-?\s*Advice\s*Timing\s*\((OK|Too\s*early)(?:\s*,\s*([0-5]))?", s, re.I)
        if m2:
            out["Advice Timing"]["ok"] = 1 if m2.group(1).lower().startswith("ok") else 0
            if m2.group(2) is not None:
                out["Advice Timing"]["score"] = int(m2.group(2))
    return out


def clean_json_block(text: str) -> str:
    t = text.strip().strip(" ")
    s, e = t.find("{"), t.rfind("}")
    return t[s:e+1] if s != -1 and e != -1 else "{}"


def label_turn_with_llm(gcall, counselor_text: str) -> dict:
    prompt = f"""{SKILL_LABEL_SYSTEM}

Counselor: {counselor_text}
JSON:"""
    out, _ = gcall(prompt, max_tokens=120, temperature=0.1)
    try:
        data = json.loads(clean_json_block(out))
    except Exception:
        data = {}
    keys = ["empathy", "reflection", "validation", "open_question", "suggestion"]
    norm = {}
    
    for k in keys:
        v = data.get(k, 0)
        if isinstance(v, bool):
            norm[k] = 1 if v else 0
        elif isinstance(v, (int, float)):
            norm[k] = 1 if v >= 1 else 0
        else:
            norm[k] = 1 if str(v).strip().lower() in {"1","true","yes"} else 0
    return norm


def compute_session_skill_rates(labels: list[dict]) -> dict:
    n = max(1, len(labels))
    sums = {"Empathy": 0, "Reflection": 0, "Validation":0, "Open Questions": 0, "Suggestion":0}
    for d in labels:
        sums["Empathy"] += d.get("empathy", 0)
        sums["Reflection"] += d.get("reflection", 0)
        sums["Validation"] += d.get("validation", 0)
        sums["Open Questions"] += d.get("open_question",0)
        sums.setdefault("Suggestion", 0)
        sums["Suggestion"] += d.get("suggestion",0)

    return {k: round(v / n, 4) for k, v in sums.items()}