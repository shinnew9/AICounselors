import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]

DATASET_FILES = {
    "Chinese": ROOT / "data" / "psydial4" / "student_only_100.jsonl",
    "Hispanic": ROOT / "data" / "psydial4" / "student_only_rewrite_hispanic_college_grad_100.jsonl",
    "African American": ROOT / "data" / "psydial4" / "student_only_rewrite_african_american_college_grad_100.jsonl",
    "Others": None,  # UI only for now
}


def load_jsonl(path: Path):
    if not path or not Path(path).exists():
        st.error(f"Dataset file not found: {path}")
        st.stop()

    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_session_psydial(raw: dict):
    """
    Confirmed schema from student_only_100.jsonl:
    {
      "session_id": int,
      "turns": [{"role": "system|user|assistant", "text": "..."} ...]
    }

    Normalize to:
    {
      "session_id": str,
      "turns": [{"speaker": "client|counselor", "text": "..."} ...]
    }
    """
    sid = str(raw.get("session_id", raw.get("id", "unknown")))
    turns = raw.get("turns", [])
    norm = []

    for t in turns:
        role = (t.get("role") or "").lower().strip()
        text = t.get("text") or ""
        if not text:
            continue

        # system turns are often long prompts; hide them in UI
        if role == "system":
            continue
        if role in ["user", "client", "patient", "seeker", "human"]:
            norm.append({"speaker": "client", "text": text})
        else:
            # assistant/therapist/counselor
            norm.append({"speaker": "counselor", "text": text})

    return {"session_id": sid, "turns": norm}


def get_sessions_for_culture(culture: str):
    path = DATASET_FILES.get(culture)
    if not path:
        st.error("This dataset is not configured yet.")
        st.stop()

    raw_rows = load_jsonl(path)
    sessions = [parse_session_psydial(r) for r in raw_rows]
    sessions = [s for s in sessions if s.get("turns")]  # empty guard

    if not sessions:
        st.error("No sessions found in the dataset.")
        st.stop()

    return sessions
