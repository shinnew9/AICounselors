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



# Configs
PHASE_ORDER = ["pre", "practice", "post"]
PHASE_LIMITS = {"pre":6, "practice": 10, "post": 6}   # counselor turns per phase

PHASE_SCENARIO = {
    "pre": "Alex (35, holiday loneliness)",
    "practice": "Veteran father (35, reunification barriers)",
    "post": "Jane (young adult, low mood & self-esteem, family issues)"
}

RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)



# Session Defaults
def setup_session_defaults():
    st.session_state.setdefault("participant_id", str(uuid.uuid4()))
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    
    
    # Phased flow state
    st.session_state.setdefault("phase", "pre")  # 'pre' | 'practice' | 'post'
    st.session_state.setdefault("turn_counts", {"pre":0, "practice":0, "post": 0})
    st.session_state.setdefault("completed", {"pre": False, "practice": False, "post": False})
    st.session_state.setdefault("scenario", list(SCENARIOS.keys())[0])
    
    # Mode can only matter in "practice"
    st.session_state.setdefault("mode", "Practice only")  # 'Practice only' | 'Practice + Feedback'

    # Run state
    st.session_state.setdefault("started", False)
    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])
    st.session_state.setdefault("overall_feedback", None)
    st.session_state.setdefault("session_metrics", {})   # e.g., gap words/T_GAP
    st.session_state.setdefault("metrics_summary", {})   # live aggregates
    st.session_state.setdefault("turn_labels", [])       # list of per-turn dicts
    st.session_state.setdefault("_pending_send", False)  # safe-send flag
    st.session_state.setdefault("reply_box", "")


def reset_run_state():
    """Clear the chat/runtime (keeps scenario/phase/mode/ids)."""
    for k in ["patient_msgs", "counselor_msgs", "overall_feedback",
              "session_metrics", "metrics_summary", "turn_labels",
               "_pending_send", "reply_box"]:
        st.session_state.pop(k, None)

    st.session_state["patient_msgs"]     = []
    st.session_state["counselor_msgs"]   = []
    st.session_state["overall_feedback"] = None
    st.session_state["session_metrics"]  = {}
    st.session_state["metrics_summary"]  = {}
    st.session_state["turn_labels"]      = []
    st.session_state["_pending_send"]    = False
    st.session_state["reply_box"]        = ""


def force_phase_scenario():
    """Keep scenario in sync with current phase."""
    ph = st.session_state["phase"]
    want = PHASE_SCENARIO[ph]
    if st.session_state.get("scenario") != want:
        st.session_state["scenario"] = want


def reset_all_and_start():
    """Start full protocol from PRE, clearing counts & runtime."""
    st.session_state["phase"]       = "pre"
    st.session_state["turn_couts"]  = {"pre":0, "practice": 0, "post": 0}
    st.session_state["completed"]   = {"pre": False, "practice": False, "post": False}
    st.session_state["session_id"]  = str(uuid.uuid4())
    st.session_state["started"]     = True
    # when phase is pre/post, the mode sticks to 'Practice only'
    st.session_state["mode"]        = "Practice only"
    force_phase_scenario()
    reset_run_state()


def start_next_phase():
    """Advance to next phase in PHASE_ORDER, resetting runtime."""
    cur = st.session_state["phase"]
    idx = PHASE_ORDER.index(cur)
    if idx < len(PHASE_ORDER) - 1:
        st.session_state["phase"] = PHASE_ORDER[idx+1]
        # practice 
        if st.session_state["phase"] != "practice":
            st.session_state["mode"] = "Practice only"
        reset_run_state()
        st.session_state["session_id"] = str(uuid.uuid4())
        st.rerun()


# Helpers
def _update_metrics_summary_from_labels():
    """ core.metrics.compute_session_skill_rates() 가 snake_case 키를 반환하는 걸"""
    rates = compute_session_skill_rates(st.session_state.get("turn_labels", [])) or {}
    st.session_state["metrics_summary"] = {
        "Empathy":          float(rates.get("empathy_rate", 0.0)),
        "Reflection":       float(rates.get("reflection_rate", 0.0)),
        "Open Questions":   float(rates.get("open_question_rate", 0.0)),
        "Validation":       float(rates.get("validation_rate", 0.0)),
        "Suggestion":       float(rates.get("suggestion_rate", 0.0)),
    }


# UI Helpers: Sidebar
def render_sidebar():
    with st.sidebar:
        st.header("Session setup")

        # Choosing the scenario
        st.selectbox("Patient Scenario", list(SCENARIOS.keys()), key="scenario")
        
        # Phase is not freely selectable - show a read-only stepper instead
        cur = st.session_state["phase"]
        st.markdown("**Phase (locked order)**")
        for p in PHASE_ORDER:
            mark = "▶️" if p == cur else ("✅" if st.session_state["completed"].get(p) else "⏳")
            st.write(f"{mark} '{p}' - {st.session_state['turn_counts'][p]}/{PHASE_LIMITS[p]} turns")
            

        # Mode is available ONLY in practice
        disabled = (st.session_state["phase"] != "practice")
        st.radio(
            "Mode (only available in Practice)",
            ["Practice only", "Practice + Feedback"],
            key = "mode",
            disabled = disabled,
            help = "Feedback is only available in Practice phase."
        )
        if disabled:
            st.caption("Mode is locked outside Practice.")

        # Start / Reset protocol
        if st.button("Session Start / Reset", type="primary", use_container_width=True):
            reset_all_and_start()
            st.success("Session started at PRE. First patient message will be geerated.")
            st.rerun() 

        # Advance button appears once current phase is complete
        if st.session_state["completed"].get(cur) and cur != "post":
            nxt = PHASE_ORDER[PHASE_ORDER.index(cur) +1]
            if st.button(f"Continue to **(nxt)**", use_container_width=True):
                start_next_phase()
        
        
# UI: Header badges
def render_header_badges():
    phase = st.session_state["phase"]
    mode = st.session_state["mode"]
    fb_on = (phase == "practice" and mode == "Practice + Feedback")
    turns = st.session_state["turn_counts"][phase]
    cap = PHASE_LIMITS[phase]


    # 상태 라벨
    if phase in ("pre", "post"):
        mode_label = ":gray[Practice only(locked)]"
        fb_label = ":red[NOT AVAIALABLE]"
        phase_hint = "Measurement phase - feedback is disabled by design."
    else:
        if mode == "Practice + Feedback":
            mode_label = ":blue[Practice only(locked)]"
            fb_label = ":green[ENABLED]"
            phase_hint = "Intervention phase - Practice + Feedback (feedback is ENABLED)."
        else:
            mode_label = ":gray[Practice only]"
            fb_label = ":gray[ENABLED]"
            phase_hint = "Intervention phase - Practice-only (no feedback)."


    st.title("CARE-style Counselor Practice (Google Gemini AI)")
    st.markdown(
        f"**Phase:** `{phase}`  |  "
        f"**Mode:** `{'Practice only (locked)' if phase!='practice' else mode}`  |  "
        f"**Feedback:** `{'ENABLED' if fb_on else 'DISABLED'}`  |  "
        f"**Turns:** {st.session_state['turn_counts'][phase]}/{PHASE_LIMITS[phase]}"
    )
    st.caption("Measurement phase - feedback is disabled by design." if phase in ("pre", "post")
                else ("Intervention phase - P+F (feedback is ENABLEd)." if fb_on 
                      else "Intervention phase - Practice-only (no feedback)."))



# LLM: first patient message
def ensure_first_patient():
    if not st.session_state["patient_msgs"]:
        p = (
            f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
            "Task: Start the conversation in 1–2 sentences about how you're feeling."
        )
        with st.spinner("Generating the first patient message..."):
            first, _ = gcall(p, max_tokens=140, temperature=0.7)
        st.session_state["patient_msgs"].append(first)


# Send handling (run BEFORE drawing inputs)
def handle_pending_send():
    """Process a send event safely *before* drawing widgets to avoid key-collisions."""
    if not st.session_state.get("_pending_send"):
        return

    st.session_state["_pending_send"] = False

    # turn cap check
    ph = st.session_state["phase"]
    cap = PHASE_LIMITS[ph]
    if st.session_state["turn_counts"][ph] >= cap:
        st.warning(f"{ph.upper()} phase is complete. Please procedd to the next phase form the sidebar.")
        return

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
        # be safe inside log_turn
        log_turn(st, text, labs)  # core/logs.py (ensure it uses labels.get to avoid KeyError)
        _update_metrics_summary_from_labels()
        # st.session_state["metrics_summary"] = compute_session_skill_rates(st.session_state["turn_labels"])
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

    # (4) increment turn & phase complete check
    st.session_state["turn_counts"][ph] += 1
    if st.session_state["turn_counts"][ph] >= cap:
        st.session_state["completed"][ph] = True
        st.success(f"{ph.upper()} phase complete. Use the sidebar to continue.")

    # clear input and rerun
    st.session_state["reply_box"] = ""
    st.rerun()


# UI: Left Column (chat)
def render_chat_column():
    st.subheader("Conversation")

    # history
    for i, pmsg in enumerate(st.session_state["patient_msgs"]):
        st.markdown(f"**Patient:** {pmsg}")
        if i < len(st.session_state["counselor_msgs"]):
            st.markdown(f"**You:** {st.session_state['counselor_msgs'][i]}")

    # input + buttons
    st.text_area("Your reply (1–5 sentences)", height=130, key="reply_box")

    phase = st.session_state["phase"]
    cap = PHASE_LIMITS[phase]
    sent = st.session_state["turn_counts"][phase]
    send_disabled = (sent >= cap)


    def _trigger_send():
        st.session_state["_pending_send"] = True

    c1, c2 = st.columns([1, 1])
    c1.button("Send", type="primary", use_container_width=True, 
              key="btn_send", on_click=_trigger_send, disabled=send_disabled)

    # Feedback button enabled ONLY in practice + P+F
    mode        = st.session_state["mode"]
    fb_enabled  = (phase == "practice" and mode == "Practice + Feedback")
    fb_click    = c2.button(
        "Feedback", use_container_width=True, key="btn_feedback",
        disabled=not fb_enabled,
        help="Enabled only during Practice phase in Practice + Feedback mode."
    )
    return fb_click


# UI: Right Column (Feedback)
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


# UI: Self-efficacy (pre/post only) 
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
                "session_id":     st.session_state["session_id"],
                "phase":          phase,
                "mode":           st.session_state["mode"],
                "scenario":       st.session_state["scenario"],
                "Exploration":    se_expl, 
                "Action":         se_act, 
                "SessionMgmt":    se_mgmt,
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
    force_phase_scenario()
    render_sidebar()

    if not st.session_state["started"]:
        st.info("Use the left sidebar to start at **pre**.")
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

