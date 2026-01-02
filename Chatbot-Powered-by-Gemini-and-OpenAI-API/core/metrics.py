# core/metrics.py
import json
import re
from typing import Dict, List, Any


# 1) Turn-level labeling (LLM)
LABEL_SYSTEM = """
You are a counseling supervisor labeling ONE counselor reply.

Return STRICT JSON with integer 0/1 flags:

Core micro-skills:
- empathy
- reflection
- validation
- open_question
- suggestion

Extensions (research):
- cultural_responsiveness: references identity/culture respectfully without stereotyping; culturally attuned
- stereotype_risk: stereotyping, overgeneralization, or inappropriate cultural assumptions
- goal_alignment: stays aligned with client's main concern / agenda
- coherence: reply is coherent and grounded in prior turn (not random / not contradictory)
- safety_response: if there is risk/self-harm content in context, does the reply respond safely (support, resources)

Output JSON only. Example:
{"empathy":1,"reflection":0,"validation":1,"open_question":1,"suggestion":0,
 "cultural_responsiveness":0,"stereotype_risk":0,"goal_alignment":1,"coherence":1,"safety_response":1}
""".strip()


def _clean_json_block(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        return {}


def label_turn_with_llm(gcall, counselor_text: str, context: Dict[str, Any] | None = None) -> Dict[str, int]:
    """
    gcall(prompt, ...) -> (text, meta)
    Returns dict of 0/1 flags.

    Backward compatible: even if LLM only returns old 5 keys, we fill missing keys with 0/1 defaults.
    """
    context = context or {}
    # lightweight context string (optional)
    client_prev = (context.get("client_prev") or "").strip()
    prompt = f"""{LABEL_SYSTEM}

Client previous message (optional):
\"\"\"{client_prev}\"\"\"

Counselor message:
\"\"\"{(counselor_text or "").strip()}\"\"\"

JSON:"""

    out, _ = gcall(prompt, max_tokens=220, temperature=0.0)
    data = _clean_json_block(out) or {}

    keys = [
        "empathy", "reflection", "validation", "open_question", "suggestion",
        "cultural_responsiveness", "stereotype_risk", "goal_alignment", "coherence", "safety_response"
    ]
    labs = {}
    for k in keys:
        try:
            labs[k] = int(bool(int(data.get(k, 0))))
        except Exception:
            labs[k] = 0
    return labs


# 2) Session aggregation utilities
DEFAULT_KEYS = [
    "empathy", "reflection", "validation", "open_question", "suggestion",
    "cultural_responsiveness", "stereotype_risk", "goal_alignment", "coherence", "safety_response"
]

DISPLAY_MAP = {
    "empathy": "Empathy",
    "reflection": "Reflection",
    "validation": "Validation",
    "open_question": "Open Questions",
    "suggestion": "Suggestions",
    "cultural_responsiveness": "Cultural responsiveness",
    "stereotype_risk": "Stereotype risk",
    "goal_alignment": "Goal alignment",
    "coherence": "Coherence",
    "safety_response": "Safety response",
}


def compute_session_skill_rates(labels: List[Dict[str, int]], keys: List[str] | None = None) -> Dict[str, float]:
    keys = keys or DEFAULT_KEYS
    n = max(1, len(labels or []))
    out = {}
    for k in keys:
        s = 0
        for lab in (labels or []):
            try:
                s += int(bool(lab.get(k, 0)))
            except Exception:
                pass
        out[f"{k}_rate"] = s / n if (labels or []) else 0.0
    return out


def make_metrics_summary(labels: List[Dict[str, int]]) -> Dict[str, float]:
    """
    UI-friendly summary with pretty keys.
    """
    rates = compute_session_skill_rates(labels or [])
    summ = {}
    for k in DEFAULT_KEYS:
        name = DISPLAY_MAP.get(k, k)
        summ[name] = float(rates.get(f"{k}_rate", 0.0))
    return summ


def make_skill_timeseries(labels: List[Dict[str, int]], keys: List[str]) -> Dict[str, List[float]]:
    """
    Returns cumulative-average timeline per key.
    Useful to show "improves over time" patterns.
    """
    out = {k: [] for k in keys}
    counts = {k: 0 for k in keys}
    for i, lab in enumerate(labels or []):
        for k in keys:
            counts[k] += int(bool(lab.get(k, 0)))
            out[k].append(counts[k] / float(i + 1))
    return out


# 3) Rule-based warnings (turn-level)
EMOTION_CUE = re.compile(r"\b(sad|hurt|angry|anxious|scared|lonely|depress|ashamed|embarrass|panic|overwhelm|cry)\b", re.I)
RISK_CUE = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)

def turn_warnings(
    patient_msgs: List[str],
    counselor_msgs: List[str],
    labels: List[Dict[str, int]],
    no_openq_streak_k: int = 3,
    over_advice_k: int = 2,
) -> List[Dict[str, Any]]:
    """
    Returns list length == len(counselor_msgs); each element: {"warnings":[...]}
    """
    warns = [{"warnings": []} for _ in range(len(counselor_msgs or []))]

    # 1) Over-advice: suggestion=1 repeatedly
    streak = 0
    for i, lab in enumerate(labels or []):
        if int(bool(lab.get("suggestion", 0))) == 1:
            streak += 1
        else:
            streak = 0
        if streak >= over_advice_k:
            warns[i]["warnings"].append(f"⚠️ Over-advice streak (≥{over_advice_k})")

    # 2) No open question streak
    streak = 0
    for i, lab in enumerate(labels or []):
        if int(bool(lab.get("open_question", 0))) == 0:
            streak += 1
        else:
            streak = 0
        if streak >= no_openq_streak_k:
            warns[i]["warnings"].append(f"⚠️ No open-question streak (≥{no_openq_streak_k})")

    # 3) Missing validation after emotion cue in client turn
    for i in range(min(len(patient_msgs or []), len(labels or []))):
        p = (patient_msgs[i] or "")
        if EMOTION_CUE.search(p) and int(bool(labels[i].get("validation", 0))) == 0:
            warns[i]["warnings"].append("⚠️ Emotion present → add explicit validation")

    # 4) Risk cue: if client expresses risk, check safety_response=1 (or warn)
    for i in range(min(len(patient_msgs or []), len(labels or []))):
        p = (patient_msgs[i] or "")
        if RISK_CUE.search(p):
            if int(bool(labels[i].get("safety_response", 0))) == 0:
                warns[i]["warnings"].append("⚠️ Risk cue → safety response missing")

    # 5) Stereotype risk flagged
    for i, lab in enumerate(labels or []):
        if int(bool(lab.get("stereotype_risk", 0))) == 1:
            warns[i]["warnings"].append("⚠️ Potential stereotyping / cultural assumption")

    return warns
