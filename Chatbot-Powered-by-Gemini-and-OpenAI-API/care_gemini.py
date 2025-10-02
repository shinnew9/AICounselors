# CARE-style counselor practice (Gemini) — refactored with main()
# Prereqs: pip install streamlit python-dotenv google-generativeai==0.3.2
# Run:     streamlit run care_gemini.py
# .env:    GOOGLE_API_KEY=AIza...

import os, re, uuid, csv
import streamlit as st
from datetime import datetime

from core.llm import gcall
from core.scenarios import SCENARIOS
from core.prompts import build_patient_system_prompt, OVERALL_FEEDBACK_SYSTEM, build_history
from core.metrics import label_turn_with_llm, compute_session_skill_rates, parse_session_metrics
from core.logs import log_turn, log_session_snapshot

RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)


# SESSION SETUP
def setup_session_defaults():
    st.session_state.setdefault("participant_id", str(uuid.uuid4()))
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("scenario", list(SCENARIOS.keys())[0])
    st.session_state.setdefault("phase", "pre")  # 'pre' | 'practice' | 'post'
    st.session_state.setdefault("mode", "Practice only")  # 'Practice only' | 'Practice + Feedback'

    st.session_state.setdefault("started", False)
    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])
    st.session_state.setdefault("overall_feedback", None)
    st.session_state.setdefault("session_metrics", {})   # e.g., gap words/T_GAP
    st.session_state.setdefault("metrics_summary", {})   # live aggregates
    st.session_state.setdefault("turn_labels", [])       # list of per-turn dicts
    st.session_state.setdefault("_pending_send", False)  # safe-send flag
    st.session_state.setdefault("reply_box", "")


def reset_session():
    # keep participant_id, scenario/phase/mode; reset the run
    keep = {
        "participant_id": st.session_state["participant_id"],
        "scenario": st.session_state["scenario"],
        "phase": st.session_state["phase"],
        "mode": st.session_state["mode"],
    }
    for k in ["started", "patient_msgs", "counselor_msgs", "overall_feedback",
              "session_metrics", "metrics_summary", "turn_labels", "_pending_send", "reply_box"]:
        st.session_state.pop(k, None)
    st.session_state.update(keep)
    st.session_state["started"] = True
    st.session_state["session_id"] = str(uuid.uuid4())


# UI BLOCKS
def render_sidebar():
    with st.sidebar:
        st.header("Session setup")

        st.selectbox("Patient Scenario", list(SCENARIOS.keys()), key="scenario")
        st.selectbox("Phase", ["pre", "practice", "post"], key="phase")
        st.radio("Mode", ["Practice only", "Practice + Feedback"], key="mode")

        if st.button("Session Start / Reset", type="primary", use_container_width=True):
            reset_session()
            st.success("Session started. First patient message will be generated.")
            st.rerun()


def render_header_badges():
    phase = st.session_state["phase"]
    mode = st.session_state["mode"]
    feedback_enabled = (phase == "practice" and mode == "Practice + Feedback")

    st.title("CARE-style Counselor Practice (Google Gemini AI)")
    st.markdown(
        f"**Phase:** `{phase}`  |  "
        f"**Mode:** `{mode}`  |  "
        f"**Feedback:** `{'ENABLED' if feedback_enabled else 'DISABLED'}`"
    )
    if phase in ("pre", "post"):
        st.caption("Measurement phase — feedback is disabled by design.")
    elif feedback_enabled:
        st.caption("Intervention phase — feedback is ENABLED (P+F).")
    else:
        st.caption("Intervention phase — Practice-only (no feedback).")


def ensure_first_patient():
    if not st.session_state["patient_msgs"]:
        p = f"{build_patient_system_prompt(st.session_state['scenario'])}\n" \
            f"Task: Start the conversation in 1–2 sentences about how you're feeling."
        with st.spinner("Generating the first patient message..."):
            first, _ = gcall(p, max_tokens=140, temperature=0.7)
        st.session_state["patient_msgs"].append(first)


def handle_pending_send():
    """Process a send event safely *before* drawing widgets to avoid key-collisions."""
    if not st.session_state.get("_pending_send"):
        return

    st.session_state["_pending_send"] = False
    text = (st.session_state.get("reply_box") or "").strip()
    if not text:
        st.warning("Please type a reply.")
        return

    if RISK_PAT.search(text):
        st.warning("⚠️ Crisis-related language detected. In real settings, use local crisis resources (US: 988).")

    # (1) store counselor turn
    st.session_state["counselor_msgs"].append(text)

    # (2) label/log/aggregate
    labs = label_turn_with_llm(gcall, text)
    st.session_state["turn_labels"].append(labs)
    try:
        log_turn(st, text, labs)  # core/logs.py (ensure it uses labels.get to avoid KeyError)
        st.session_state["metrics_summary"] = compute_session_skill_rates(st.session_state["turn_labels"])
        log_session_snapshot(st)
    except Exception as e:
        st.warning(f"(logging skipped) {e}")

    # (3) next patient turn
    nxt_prompt = (
        f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
        f"Context: Previous patient message: {st.session_state['patient_msgs'][-1]}\n"
        f"Counselor replied: {text}\n\n"
        "Task: Reply as the patient in 1–3 sentences, staying in character."
    )
    try:
        with st.spinner("Patient is responding..."):
            nxt, _ = gcall(nxt_prompt, max_tokens=200, temperature=0.7)
        st.session_state["patient_msgs"].append(nxt)
    except Exception as e:
        st.error(f"Patient generation failed: {e}")

    # clear input and rerun
    st.session_state["reply_box"] = ""
    st.rerun()


def render_chat_column():
    with st.container():
        st.subheader("Conversation")
        # history
        for i, pmsg in enumerate(st.session_state["patient_msgs"]):
            st.markdown(f"**Patient:** {pmsg}")
            if i < len(st.session_state["counselor_msgs"]):
                st.markdown(f"**You:** {st.session_state['counselor_msgs'][i]}")

        # single input box
        st.text_area("Your reply (1–5 sentences)", height=130, key="reply_box")

        def _trigger_send():
            st.session_state["_pending_send"] = True

        c1, c2 = st.columns([1, 1])
        c1.button("Send", type="primary", use_container_width=True, key="btn_send", on_click=_trigger_send)

        # Feedback button enabled ONLY in practice + P+F
        phase = st.session_state["phase"]
        mode = st.session_state["mode"]
        fb_enabled = (phase == "practice" and mode == "Practice + Feedback")
        fb_click = c2.button(
            "Feedback", use_container_width=True, key="btn_feedback",
            disabled=not fb_enabled,
            help="Enabled only during Practice phase in Practice + Feedback mode."
        )
        return fb_click


def render_feedback_column(fb_click):
    st.subheader("Feedback / Summary")

    phase = st.session_state["phase"]
    mode = st.session_state["mode"]
    feedback_enabled = (phase == "practice" and mode == "Practice + Feedback")

    if not feedback_enabled:
        st.info("Feedback is unavailable in this phase.")
        return

    # Generate on demand
    if fb_click:
        history_text = build_history(st.session_state["patient_msgs"], st.session_state["counselor_msgs"])
        overall_prompt = (
            f"{OVERALL_FEEDBACK_SYSTEM}\n\n"
            f"Conversation (chronological):\n{history_text}\n\n"
            "Evaluate the counselor's replies in aggregate."
        )
        with st.spinner("Generating session-level feedback..."):
            fb_all, _ = gcall(overall_prompt, max_tokens=800, temperature=0.4)
        st.session_state["overall_feedback"] = fb_all

        # parse for GAP/T_GAP
        st.session_state["session_metrics"] = parse_session_metrics(fb_all)
        st.rerun()

    if st.session_state.get("overall_feedback"):
        st.markdown(st.session_state["overall_feedback"])
    else:
        st.info("Write a reply, then click **Feedback** to get session-level feedback.")

    # Optional: live skill tallies (you may hide in pre/post to avoid bias)
    if st.session_state.get("metrics_summary"):
        st.divider()
        st.markdown("**Live skill usage in this session** (fraction of counselor turns):")
        ms = st.session_state["metrics_summary"]
        st.write(f"- Empathy: {ms.get('Empathy', 0):.2f}")
        st.write(f"- Reflection: {ms.get('Reflection', 0):.2f}")
        st.write(f"- Open Questions: {ms.get('Open Questions', 0):.2f}")
        st.write(f"- Validation: {ms.get('Validation', 0):.2f}")
        st.write(f"- Suggestions: {ms.get('Suggestions', 0):.2f}")


def render_self_efficacy_if_needed():
    phase = st.session_state["phase"]
    if phase not in ("pre", "post"):
        return

    with st.expander("Self-efficacy (0–8)", expanded=False):
        se_expl = st.slider("Exploration", 0, 8, 5, step=1, key=f"se_expl_{phase}")
        se_act  = st.slider("Action", 0, 8, 5, step=1, key=f"se_act_{phase}")
        se_mgmt = st.slider("Session Mgmt", 0, 8, 5, step=1, key=f"se_mgmt_{phase}")
        if st.button(f"Save self-efficacy ({phase})", use_container_width=True, key=f"se_save_{phase}"):
            os.makedirs("logs", exist_ok=True)
            path = os.path.join("logs", "seff.csv")
            row = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "participant_id": st.session_state["participant_id"],
                "session_id": st.session_state["session_id"],
                "phase": phase,
                "mode": st.session_state["mode"],
                "scenario": st.session_state["scenario"],
                "Exploration": se_expl, "Action": se_act, "SessionMgmt": se_mgmt,
            }
            new = not os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=row.keys())
                if new: w.writeheader()
                w.writerow(row)
            st.success(f"Saved self-efficacy for {phase}.")


# MAIN
def main():
    st.set_page_config(page_title="CARE-style Counselor Practice (Google Gemini AI)",
                       page_icon="🧠", layout="wide")

    setup_session_defaults()
    render_sidebar()

    if not st.session_state["started"]:
        st.info("Use the left sidebar to select a scenario and click **Session Start / Reset**.")
        return

    render_header_badges()
    ensure_first_patient()

    # Process a pending send (must run BEFORE drawing input widgets)
    handle_pending_send()

    # Layout
    left, right = st.columns([0.58, 0.42])
    with left:
        fb_click = render_chat_column()
    with right:
        render_feedback_column(fb_click)

    # Self-efficacy only in pre/post
    render_self_efficacy_if_needed()


if __name__ == "__main__":
    main()
