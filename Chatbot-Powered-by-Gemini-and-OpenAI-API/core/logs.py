import os, csv
from datetime import datetime
os.makedirs("logs", exist_ok=True)

def log_trun(st, counselor_text: str, labels: dict):
    path = os.path.join("logs", "turns.csv")
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session_id": st.session_state["session_id"],
        "mode": st.session_state["mode"],
        "scenario": st.session_state["scenario"],
        "turn_idx": len(st.session_state["counselor_msgs"]),
        "text": counselor_text.replace("\n", " ").strip(),
        "empathy": labels["empathy"],
        "reflection": labels["reflection"],
        "validation": labels["validation"],
        "open_question": labels["open_question"],
        "suggestion": labels["suggestion"],
    }

    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames = row.keys())
        if new:
            w.writeheader()
        w.writerow(row)


def log_session_snapshot(st):
    path = os.path.join("logs", "sessions.csv")
    ms = st.session_state.get("metrics_summary", {})
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session_id": st.session_state["session_id"],
        "mode": st.session_state["mode"],
        "scenario": st.session_state["scenario"],
        "turn_idx": len(st.session_state["counselor_msgs"]),
        "Empathy": ms.get("Empathy",0),
        "Reflection": ms.get("Reflection",0),
        "OpenQuestions": ms.get("Open Questions",0),
        "Validation": ms.get("Validation",0),
        "Suggestions": ms.get("Suggestions",0),
        "GAP_words": st.session_state.get("session_metrics",{}).get("gap_words", 0),
    }
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if new: w.writeheader()
        w.writerow(row)