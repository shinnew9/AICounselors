import json, random
from pathlib import Path
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data" / "psydial4"

@st.cache_data(show_spinner=False)
def list_data_files(root: Path = DATA_ROOT):
    if not root.exists():
        return []
    files = []
    files += [str(p) for p in root.rglob("*.json")]
    files += [str(p) for p in root.rglob("*.jsonl")]
    return sorted(files)

@st.cache_data(show_spinner=True)
def load_sessions_any(path: str, max_rows: int = 20000):
    p = Path(path)
    if p.suffix.lower() == ".json":
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "sessions" in data:
            data = data["sessions"]
        return data if isinstance(data, list) else []

    # jsonl
    rows = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
            if len(rows) >= max_rows:
                break
    return rows


def _normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r in {"user", "patient", "client", "seeker"}:
        return "user"
    if r in {"assistant", "counselor", "therapist"}:
        return "assistant"
    if r == "system":
        return "system"
    return "system"


def qc_clean_turns(turns: list[dict], remove_consecutive_dupes=True):
    cleaned = []
    removed_dupes = 0
    prev_key = None

    for t in (turns or []):
        role = _normalize_role(t.get("role"))
        text = (t.get("text") or "").strip()
        if not text:
            continue
        key = (role, text)
        if remove_consecutive_dupes and prev_key == key:
            removed_dupes += 1
            continue
        prev_key = key
        cleaned.append({"role": role, "text": text})

    non_system = [t for t in cleaned if t["role"] in {"user", "assistant"}]
    issues = []
    for i in range(1, len(non_system)):
        if non_system[i]["role"] == non_system[i - 1]["role"]:
            issues.append({
                "idx": i,
                "role": non_system[i]["role"],
                "prev": non_system[i - 1]["text"][:120],
                "curr": non_system[i]["text"][:120],
            })

    counts = {"user": 0, "assistant": 0, "system": 0}
    for t in cleaned:
        counts[t["role"]] += 1

    return cleaned, {"removed_dupes": removed_dupes, "alternation_issues": issues, "role_counts": counts}


def get_turns(sess: dict):
    if isinstance(sess, dict) and isinstance(sess.get("turns"), list):
        return sess["turns"]
    for k in ["dialogue", "messages", "utterances", "conversation", "log"]:
        if isinstance(sess.get(k), list):
            return sess[k]
    return []


def session_id(sess: dict, fallback: str = "session"):
    return str(sess.get("session_id") or sess.get("id") or sess.get("dialogue_id") or fallback)


def filter_sessions(sessions: list[dict], rewrite_target: str | None):
    if not rewrite_target:
        return sessions
    rt = rewrite_target.lower()
    out = []
    for s in sessions:
        v = str(s.get("rewrite_target") or "").lower()
        if rt in v:
            out.append(s)
    return out


def pick_random_session(sessions: list[dict]) -> dict:
    return random.choice(sessions)
