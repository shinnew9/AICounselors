import json
import os
import random
import streamlit as st

st.set_page_config(
    page_title="Cultural Counseling Session Rater",
    page_icon="🧠",
    layout="wide",
)


from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # 프로젝트 루트
DATASET_FILES = {
    "Chinese": ROOT / "data" / "psydial4" / "student_only_100.jsonl",
    "Hispanic": ROOT / "data" / "psydial4" / "student_only_rewrite_hispanic_college_grad_100.jsonl",
    "African American": ROOT / "data" / "psydial4" / "student_only_rewrite_african_american_college_grad_100.jsonl",
    "Others": None  # UI only for no
}


# UI: Global CSS
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }

    /* Optional: hide default Streamlit menu/footer */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Make buttons look a bit more consistent */
    div.stButton > button {
        border-radius: 12px;
        padding: 0.55rem 0.85rem;
        font-weight: 700;
    }

    /* Headline spacing */
    .page-title {
        font-size: 42px;
        font-weight: 900;
        margin: 0.2rem 0 0.2rem 0;
    }
    .page-sub {
        opacity: 0.75;
        margin-bottom: 1.2rem;
    }

    /* Hide "Current selection dict" area is removed already */
    </style>
    """,
    unsafe_allow_html=True,
)


def sidebar_rater_panel():
    st.sidebar.markdown("## Rater")
    st.sidebar.caption("Email")
    st.sidebar.write(st.session_state.get("email",""))

    st.sidebar.caption("Rater ID (editable)")
    rid = st.sidebar.text_input(" ", value=st.session_state.get("rater_id",""), label_visibility="collapsed")
    st.session_state["rater_id"] = rid.strip()

    if st.sidebar.button("Sign out"):
        for k in ["email","rater_id","culture","ds_file","session_idx","current_session"]:
            st.session_state.pop(k, None)
        st.switch_page("app.py")


# Helpers: Auth
def require_signed_in():
    if not st.session_state.get("email"):
        st.error("You must sign in first. Please return to the home page.")
        st.stop()


# Helpers: Data loading
def load_jsonl(path: str):
    if not os.path.exists(path):
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


def parse_session(raw: dict):
    """
    Normalize a session into:
    {
      "session_id": str,
      "turns": [{"speaker": "client"/"counselor", "text": "..."} ...]
    }

    You MUST edit this function if your dataset schema differs.
    """
    # Common possibilities:
    # 1) {"session_id": "...", "turns":[{"speaker":"client","text":"..."}]}
    # 2) {"id": "...", "dialogue":[{"role":"user","content":"..."}]}
    sid = raw.get("session_id") or raw.get("id") or raw.get("sid") or str(raw.get("index", "")) or "unknown"

    turns = raw.get("turns") or raw.get("dialogue") or raw.get("messages") or []
    norm_turns = []

    for t in turns:
        speaker = (t.get("speaker") or t.get("role") or "").lower()
        text = t.get("text") or t.get("content") or t.get("utterance") or ""

        if speaker in ["client", "patient", "seeker", "user", "human"]:
            norm_turns.append({"speaker": "client", "text": text})
        else:
            # counselor/assistant/therapist/etc
            norm_turns.append({"speaker": "counselor", "text": text})

    return {"session_id": sid, "turns": norm_turns}


def get_sessions_for_culture(culture: str):
    path = DATASET_FILES.get(culture)
    if not path:
        st.error("This dataset is not configured yet.")
        st.stop()

    raw_rows = load_jsonl(path)
    sessions = [parse_session(r) for r in raw_rows]
    if not sessions:
        st.error("No sessions found in the dataset.")
        st.stop()
    return sessions


# Helpers: Chat rendering
def render_chat(turns):
    for t in turns:
        speaker = t.get("speaker", "")
        text = t.get("text", "")

        if speaker == "client":
            with st.chat_message("user", avatar="🧑‍💬"):
                st.markdown(text)
        else:
            with st.chat_message("assistant", avatar="🧑‍⚕️"):
                st.markdown(text)


# Main page
def main():
    require_signed_in()

    st.markdown('<div class="page-title">🧠 Cultural Counseling Session Rater</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="page-sub">Choose a dataset to rate. You will rate sessions sequentially and your progress can be saved.</div>',
        unsafe_allow_html=True,
    )

    # Dataset selection buttons (+ Others UI only)
    st.markdown("## Select dataset")
    cols = st.columns(4)
    options = ["Chinese", "Hispanic", "African American", "Others"]

    for i, opt in enumerate(options):
        with cols[i]:
            if opt == "Others":
                st.button(opt, disabled=True, use_container_width=True)
            else:
                if st.button(opt, use_container_width=True):
                    st.session_state["culture"] = opt
                    st.session_state["ds_file"] = DATASET_FILES.get(opt)
                    # reset session state when switching datasets
                    st.session_state["session_idx"] = 0
                    st.session_state["current_session"] = None
                    st.rerun()

    # Remove dict UI -> show a simple status line
    culture = st.session_state.get("culture")
    if not culture:
        st.info("No dataset selected yet.")
        st.stop()

    st.success(f"Current dataset: {culture}")

    # Load sessions (cached in session_state to avoid reloading every rerun)
    if st.session_state.get("current_session") is None:
        sessions = get_sessions_for_culture(culture)
        st.session_state["_sessions_cache"] = sessions
        st.session_state["current_session"] = sessions[st.session_state.get("session_idx", 0)]

    sessions = st.session_state.get("_sessions_cache") or get_sessions_for_culture(culture)
    session_idx = int(st.session_state.get("session_idx", 0))

    # Guard
    session_idx = max(0, min(session_idx, len(sessions) - 1))
    st.session_state["session_idx"] = session_idx
    session = sessions[session_idx]
    st.session_state["current_session"] = session

    # Session header
    st.markdown("---")
    st.subheader(f"Session {session_idx + 1} / {len(sessions)}")
    st.caption(f"Session ID: {session.get('session_id', 'unknown')}")

    # Render chat bubbles
    render_chat(session.get("turns", []))

    # Navigation
    st.markdown("---")
    nav_cols = st.columns([1, 1, 3])
    with nav_cols[0]:
        prev_disabled = session_idx <= 0
        if st.button("← Previous", disabled=prev_disabled, use_container_width=True):
            st.session_state["session_idx"] = session_idx - 1
            st.session_state["current_session"] = None
            st.rerun()

    with nav_cols[1]:
        next_disabled = session_idx >= len(sessions) - 1
        if st.button("Next →", disabled=next_disabled, use_container_width=True):
            st.session_state["session_idx"] = session_idx + 1
            st.session_state["current_session"] = None
            st.rerun()

    # Rating section: you said stop at (1)(2), so keep minimal placeholder
    st.markdown("## Ratings (placeholder)")
    st.info("We will finalize the A/B perspective metrics later. For now, the UI and chat rendering are updated.")


if __name__ == "__main__":
    main()
