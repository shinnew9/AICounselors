# CARE-style counselor practice (Gemini) — single-file clean version
# Prereqs: pip install streamlit python-dotenv google-generativeai==0.3.2
# Run:     streamlit run care_app_full_gemini.py
# .env:    GOOGLE_API_KEY=AIza...

import os, re, json, uuid
import streamlit as st
from datetime import datetime

from core.llm import gcall
from core.scenarios import SCENARIOS
from core.prompts import build_patient_system_prompt, OVERALL_FEEDBACK_SYSTEM, build_history
from core.metrics import label_turn_with_llm, compute_session_skill_rates, parse_session_metrics
from core.logs import log_turn, log_session_snapshot

# Page 
st.set_page_config(page_title="CARE-style Counselor Practice (Google Gemini AI)",
                   page_icon="🧠", layout="wide")


# Session defaults
st.session_state.setdefault("mode", "Practice only")
st.session_state.setdefault("scenario", list(SCENARIOS.keys())[0])
st.session_state.setdefault("phase", "practice")
st.session_state.setdefault("started", False)
st.session_state.setdefault("turn", 1)
st.session_state.setdefault("patient_msgs", [])
st.session_state.setdefault("counselor_msgs", [])
st.session_state.setdefault("overall_feedback", None)
st.session_state.setdefault("session_metrics", {})
st.session_state.setdefault("metrics_summary", {})
st.session_state.setdefault("turn_labels", [])
st.session_state.setdefault("session_id", str(uuid.uuid4()))

def reset_session(preserve=True):
    # 위젯이 가진 상태는 유지
    keep = {
        "mode":   st.session_state.get("mode", "Practice only"),
        "scenario": st.session_state.get("scenario", list(SCENARIOS.keys())[0]),
        "phase":  st.session_state.get("phase", "practice"),
    }

    # 위젯 키는 건드리지 않고, 우리 앱 내부 키만 초기화
    for k in ["started","turn","patient_msgs","counselor_msgs",
              "overall_feedback","session_metrics","metrics_summary",
              "turn_labels","session_id"]:
        if k in st.session_state:
            del st.session_state[k]

    st.session_state["started"] = True
    st.session_state["turn"] = 1
    st.session_state["patient_msgs"] = []
    st.session_state["counselor_msgs"] = []
    st.session_state["overall_feedback"] = None
    st.session_state["session_metrics"] = {}
    st.session_state["metrics_summary"] = {}
    st.session_state["turn_labels"] = []
    import uuid
    st.session_state["session_id"] = str(uuid.uuid4())

# Sidebar (directly bound to session keys)
with st.sidebar:
    st.header("Session setup")
    st.selectbox(
        "Patient Scenario", list(SCENARIOS.keys()), key="scenario",
    )
    st.selectbox("Phase", ["pre","practice","post"], key="phase")
    st.radio("Mode", ["Practice only", "Practice + Feedback"], key="mode")  # ← single source of truth)
    if st.button("Session Start / Reset", type="primary", use_container_width=True):
        reset_session()
        st.success("Session has started. First conversation will be generated.")
        st.rerun()


# Guard
if not st.session_state["started"]:
    st.info("Use the left sidebar to select a scenario and click **Session Start / Reset**.")
    st.stop()
# Header / live badge
st.title("CARE-style Counselor Practice (Google Gemini AI)")
st.caption(f"Mode: {'Practice + Feedback' if st.session_state['mode']=='Practice + Feedback' else 'Practice only'}")


# First patient message
if len(st.session_state["patient_msgs"]) == 0:
    p = f"{build_patient_system_prompt(st.session_state['scenario'])}\nTask: Start the conversation in 1–2 sentences about how you're feeling."
    with st.spinner("Generating the first patient message..."):
        first, _ = gcall(p, max_tokens=140, temperature=0.7)
    st.session_state["patient_msgs"].append(first)

# Layout
col_chat, col_fb = st.columns([0.58, 0.42])

with col_chat:
    st.subheader("Conversation")

    # Render history
    for i, pmsg in enumerate(st.session_state["patient_msgs"]):
        st.markdown(f"**Patient:** {pmsg}")
        if i < len(st.session_state["counselor_msgs"]):
            st.markdown(f"**You:** {st.session_state['counselor_msgs'][i]}")

    # Input
    reply_key = f"reply_{len(st.session_state['counselor_msgs'])}"
    user_reply = st.text_area("Your reply (1–5 sentences)", height=130, key=reply_key)

    c1, c2 = st.columns([1, 1])
    send_click = c1.button("Send", type="primary", use_container_width=True, key="btn_send")
    fb_click   = c2.button(
        "Feedback", use_container_width=True, key="btn_feedback",
        disabled=(st.session_state["mode"] != "Practice + Feedback"),
        help="Generate session-level feedback (enabled in Practice + Feedback mode).",
    )

    # Send → advance conversation only
    RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)
    if send_click and user_reply.strip():
        if RISK_PAT.search(user_reply):
            st.warning("⚠️ Crisis-related language detected. In real settings, use local crisis resources (US: 988).")
        
        # store reply
        st.session_state["counselor_msgs"].append(user_reply.strip())



        # (A) turn labeling + log
        labs = label_turn_with_llm(gcall, user_reply.strip())
        st.session_state["turn_labels"].append(labs)
        try:
            log_turn(st, user_reply.strip(), labs)
            st.session_state["metrics_summary"] = compute_session_skill_rates(st.session_state["turn_labels"])
            log_session_snapshot(st)
        except Exception as e:
            st.warning(f"(logging skipped) {e}")


        # next patient turn
        nxt_prompt = (
            f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
            f"Context: Previous patient message: {st.session_state['patient_msgs'][-1]}\n"
            f"Counselor replied: {user_reply.strip()}\n\n"
            "Task: Reply as the patient in 1–3 sentences, staying in character."
        )
        with st.spinner("Patient is responding..."):
            nxt, _ = gcall(nxt_prompt, max_tokens=200, temperature=0.7)
        st.session_state["patient_msgs"].append(nxt)

        st.session_state["turn"] += 1
        st.rerun()

    # Feedback → session-level feedback on demand
    if fb_click:
        if st.session_state["mode"] != "Practice + Feedback":
            st.warning("Switch to **Practice + Feedback** to generate feedback.")
        else:
            history_text = build_history(st.session_state["patient_msgs"], st.session_state["counselor_msgs"])
            overall_prompt = (
                f"{OVERALL_FEEDBACK_SYSTEM}\n\n"
                f"Conversation (chronological):\n{history_text}\n\n"
                "Evaluate the counselor's replies in aggregate."
            )
            with st.spinner("Generating session-level feedback..."):
                fb_all, _ = gcall(overall_prompt, max_tokens=800, temperature=0.4)
            st.session_state["overall_feedback"] = fb_all

            # parse session_level metrics (incl. GAP words)
            st.session_state["session_metrics"] = parse_session_metrics(fb_all)
            st.rerun()

with col_fb:
    st.subheader("Feedback / Summary")
    st.caption(f"Mode: {'Practice + Feedback' if st.session_state['mode']=='Practice + Feedback' else 'Practice only'}")

    if st.session_state["mode"] == "Practice only":
        st.info("Feedback is OFF. Switch to **Practice + Feedback**, then click **Feedback** (next to Send).")
    else:
        if st.session_state.get("overall_feedback"):
            st.markdown(st.session_state["overall_feedback"])
        else:
            st.info("No overall feedback yet. Write a reply and click **Feedback** (next to Send).")

    # live session skill usage
    if st.session_state.get("metrics_summary"):
        st.divider()
        st.markdown("**Live skill usage in this session** (fraction of counselor turns):")
        ms = st.session_state["metrics_summary"]
        st.write(f"- Empathy: {ms.get('Empathy',0):.2f}")
        st.write(f"- Reflection: {ms.get('Reflection',0):.2f}")
        st.write(f"- Open Questions: {ms.get('Open Questions',0):.2f}")
        st.write(f"- Validation: {ms.get('Validation',0):.2f}")
        st.write(f"- Suggestions: {ms.get('Suggestions',0):.2f}")


with st.expander("Self-efficacy (0–100)", expanded=False):
    se_expl = st.slider("Exploration", 0, 100, 50, key="se_expl")
    se_act  = st.slider("Action", 0, 100, 50, key="se_act")
    se_mgmt = st.slider("Session Mgmt", 0, 100, 50, key="se_mgmt")
    if st.button("Save self-efficacy", use_container_width=True):
        import os, csv
        os.makedirs("logs", exist_ok=True)
        path = os.path.join("logs","seff.csv")
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": st.session_state["session_id"],
            "phase": st.session_state.get("phase","practice"),
            "mode": st.session_state["mode"],
            "scenario": st.session_state["scenario"],
            "Exploration": se_expl, "Action": se_act, "SessionMgmt": se_mgmt,
        }
        new = not os.path.exists(path)
        with open(path,"a",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=row.keys())
            if new: w.writeheader()
            w.writerow(row)
        st.success("Saved.")