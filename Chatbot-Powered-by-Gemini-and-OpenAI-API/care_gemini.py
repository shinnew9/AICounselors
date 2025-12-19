# CARE-style counselor practice (Gemini)
# Run: streamlit run care_gemini.py

import os, re, uuid, csv, json
import streamlit as st
from datetime import datetime

from core.llm import gcall
from core.prompts import (
    build_patient_system_prompt,
    OVERALL_FEEDBACK_SYSTEM,
    build_history,
)
from core.metrics import (
    label_turn_with_llm,
    compute_session_skill_rates,
    parse_session_metrics,
)
from core.state_utils import (
    effective_mode_from_state,   # <- no-arg
    ensure_mode_consistency,     # <- no-arg
    feedback_enabled,            # <- no-arg
)
from core.logs import log_turn, log_session_snapshot


# Config
PHASE_ORDER = ["Pre", "Practice", "Post"]
PHASE_LIMITS = {"Pre": 6, "Practice": 10, "Post": 6}

PHASE_SCENARIO = {
    "Pre": "Alex (35, holiday loneliness)",
    "Practice": "Veteran father (35, reunification barriers)",
    "Post": "Jane (young adult, low mood & self-esteem, family issues)",
}

RISK_PAT = re.compile(
    r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I
)

MICRO_FEEDBACK_SYSTEM = """
You are a counseling supervisor. Given ONE counselor message and its micro-skill flags
(empathy, reflection, validation, open_question, suggestion: 0/1), produce very concise micro feedback.

Return STRICT JSON with fields:
{
  "strength_title": "Empathy|Reflection|Validation|Open Question|Listening",
  "strength_note": "one short sentence (<=18 words) praising the best thing",
  "feedback_title": "Questions|Validation|Empathy|Refocus|Suggesting",
  "feedback_note": "one short sentence (<=18 words) with a concrete improvement tip",
  "alt_response": "optional 1-2 sentences better rewrite; neutral tone"
}
Output JSON only.
"""


# Small helpers
def _clean_json_block(text: str) -> dict:
    t = text.strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        return {}

def gen_micro_feedback(gcall_fn, counselor_text: str, labs: dict) -> dict:
    flags = {
        k: int(bool(labs.get(k, 0)))
        for k in ["empathy", "reflection", "validation", "open_question", "suggestion"]
    }
    prompt = f"""{MICRO_FEEDBACK_SYSTEM}

Counselor message:
\"\"\"{counselor_text.strip()}\"\"\"

Skill flags (0/1):
{json.dumps(flags)}

JSON:"""
    out, _ = gcall_fn(prompt, max_tokens=220, temperature=0.3)
    data = _clean_json_block(out) or {}
    return {
        "strength_title": data.get("strength_title", "Strengths"),
        "strength_note": data.get("strength_note", "Good use of client-centered skill."),
        "feedback_title": data.get("feedback_title", "Feedback"),
        "feedback_note": data.get("feedback_note", "Try an open question to invite more detail."),
        "alt_response": data.get("alt_response", ""),
    }

def _update_metrics_summary_from_labels():
    rates = compute_session_skill_rates(st.session_state.get("turn_labels", [])) or {}
    st.session_state["metrics_summary"] = {
        "Empathy": float(rates.get("empathy_rate", 0.0)),
        "Reflection": float(rates.get("reflection_rate", 0.0)),
        "Open Questions": float(rates.get("open_question_rate", 0.0)),
        "Validation": float(rates.get("validation_rate", 0.0)),
        "Suggestions": float(rates.get("suggestion_rate", 0.0)),
    }

def build_input_hint() -> str:
    phase = st.session_state.get("phase", "Practice")
    mode = effective_mode_from_state()
    if phase == "Pre":
        return "Reply in 1–3 short sentences. Prioritize empathy or a reflection; ask ONE open question; avoid advice."
    if phase == "Practice":
        if mode == "Practice + Feedback":
            return "Practice empathy/reflection/open questions. Hold suggestions unless explicitly asked."
        return "Practice listening: use empathy or an open question. Keep it brief (1–3 sentences)."
    return "Final assessment: 1–3 short sentences. Show active listening; one open question max; avoid advice."


# Session state
def setup_session_defaults():
    st.session_state.setdefault("participant_id", str(uuid.uuid4()))
    st.session_state.setdefault("session_id", str(uuid.uuid4()))

    st.session_state.setdefault("phase", "Pre")
    st.session_state.setdefault("turn_counts", {"Pre": 0, "Practice": 0, "Post": 0})
    st.session_state.setdefault("completed", {"Pre": False, "Practice": False, "Post": False})
    st.session_state.setdefault("scenario", PHASE_SCENARIO["Pre"])

    st.session_state.setdefault("mode_radio", "Practice only")

    st.session_state.setdefault("started", False)
    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])
    st.session_state.setdefault("micro_fb", [])
    st.session_state.setdefault("overall_feedback", None)
    st.session_state.setdefault("session_metrics", {})
    st.session_state.setdefault("metrics_summary", {})
    st.session_state.setdefault("turn_labels", [])
    st.session_state.setdefault("_pending_send", False)
    st.session_state.setdefault("reply_box", "")

def reset_run_state():
    for k in [
        "patient_msgs", "counselor_msgs", "overall_feedback", "session_metrics",
        "metrics_summary", "turn_labels", "_pending_send", "reply_box", "micro_fb"
    ]:
        st.session_state.pop(k, None)

    st.session_state["patient_msgs"] = []
    st.session_state["counselor_msgs"] = []
    st.session_state["overall_feedback"] = None
    st.session_state["session_metrics"] = {}
    st.session_state["metrics_summary"] = {}
    st.session_state["turn_labels"] = []
    st.session_state["_pending_send"] = False
    st.session_state["reply_box"] = ""
    st.session_state["micro_fb"] = []

def force_phase_scenario():
    ph = st.session_state["phase"]
    want = PHASE_SCENARIO[ph]
    if st.session_state.get("scenario") != want:
        st.session_state["scenario"] = want

def reset_all_and_start():
    st.session_state["phase"] = "Pre"
    st.session_state["turn_counts"] = {"Pre": 0, "Practice": 0, "Post": 0}
    st.session_state["completed"] = {"Pre": False, "Practice": False, "Post": False}
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["started"] = True
    force_phase_scenario()
    reset_run_state()

def start_next_phase():
    cur = st.session_state["phase"]
    idx = PHASE_ORDER.index(cur)
    if idx < len(PHASE_ORDER) - 1:
        st.session_state["phase"] = PHASE_ORDER[idx + 1]
        force_phase_scenario()
        reset_run_state()
        st.session_state["session_id"] = str(uuid.uuid4())
        st.rerun()

# -----------------------------
# UI – Sidebar
# -----------------------------
def render_sidebar():
    with st.sidebar:
        st.header("Session setup")
        st.markdown(f"**Scenario (auto):** {st.session_state['scenario']}")

        cur = st.session_state["phase"]
        st.markdown("**Phase (locked order)**")
        for p in PHASE_ORDER:
            mark = "▶️" if p == cur else ("✅" if st.session_state["completed"].get(p) else "⏳")
            st.write(f"{mark} '{p}' — {st.session_state['turn_counts'][p]}/{PHASE_LIMITS[p]} turns")

        disabled = (st.session_state["phase"] != "Practice")
        st.radio(
            "Mode (only available in Practice)",
            ["Practice only", "Practice + Feedback"],
            key="mode_radio",
            disabled=disabled,
            help="Feedback is only available in Practice phase.",
        )
        ensure_mode_consistency()  # <- keep 'mode' in sync
        if disabled:
            st.caption("Mode is locked outside Practice.")

        if st.button("Session Start / Reset", type="primary", use_container_width=True):
            reset_all_and_start()
            st.success("Session started at PRE. First patient message will be generated.")
            st.rerun()

        if st.session_state["completed"].get(cur) and cur != "Post":
            nxt = PHASE_ORDER[PHASE_ORDER.index(cur) + 1]
            if st.button(f"Continue to **{nxt}**", use_container_width=True):
                start_next_phase()


# UI – Header badges
def render_header_badges():
    phase = st.session_state["phase"]
    mode = effective_mode_from_state()
    fb_on = feedback_enabled()

    fb_badge = ":green[ENABLED]" if fb_on else ":red[DISABLED]"
    mode_label = (f"`{mode}`" if phase == "Practice" else ":gray[Practice only (locked)]")

    st.title("CARE-style Counselor Practice (Google Gemini AI)")
    st.markdown(
        f"**Phase:** `{phase}`  |  "
        f"**Mode:** {mode_label}  |  "
        f"**Feedback:** {fb_badge}  |  "
        f"**Turns:** {st.session_state['turn_counts'][phase]}/{PHASE_LIMITS[phase]}"
    )
    st.caption(
        "Measurement phase — feedback is disabled by design."
        if phase in ("Pre", "Post")
        else ("Intervention phase — P+F (feedback is ENABLED)." if fb_on
              else "Intervention phase — Practice-only (no feedback).")
    )


# LLM – first patient message
def ensure_first_patient():
    if not st.session_state["patient_msgs"]:
        p = (
            f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
            "Task: Start the conversation in 1–2 sentences about how you're feeling."
        )
        with st.spinner("Generating the first patient message..."):
            first, _ = gcall(p, max_tokens=140, temperature=0.7)
        st.session_state["patient_msgs"].append(first)


# Send handling
def handle_pending_send():
    if not st.session_state.get("_pending_send"):
        return
    st.session_state["_pending_send"] = False

    ph = st.session_state["phase"]
    cap = PHASE_LIMITS[ph]
    if st.session_state["turn_counts"][ph] >= cap:
        st.warning(f"{ph.upper()} phase is complete. Please proceed to the next phase from the sidebar.")
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

    # micro feedback only in Practice
    if st.session_state["phase"] == "Practice":
        try:
            micro = gen_micro_feedback(gcall, text, labs)
        except Exception:
            micro = {
                "strength_title": "Strengths",
                "strength_note": "Nice listening stance.",
                "feedback_title": "Feedback",
                "feedback_note": "Ask a gentle open question.",
                "alt_response": "",
            }
        st.session_state["micro_fb"].append(micro)
    else:
        st.session_state["micro_fb"].append({})

    try:
        log_turn(st, text, labs)
        _update_metrics_summary_from_labels()
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

    st.session_state["reply_box"] = ""
    st.rerun()


# UI – Left column (chat)
def render_chat_column():
    st.subheader("Conversation")

    patient = st.session_state["patient_msgs"]
    counselor = st.session_state["counselor_msgs"]
    phase = st.session_state["phase"]

    # Turn-by-turn history
    for i, pmsg in enumerate(patient):
        if i > 0:
            st.divider()
        st.markdown(f"**Turn {i + 1}**")
        st.markdown(f"**Patient:** {pmsg}")
        if i < len(counselor):
            st.markdown(f"**You:** {counselor[i]}")
        else:
            st.caption("Write your reply below to complete this turn.")

    # Input + buttons
    st.text_area(
        "Your reply (1–3 sentences)",
        height=130,
        key="reply_box",
        placeholder=build_input_hint(),
    )

    cap = PHASE_LIMITS[phase]
    sent = st.session_state["turn_counts"][phase]
    send_disabled = (sent >= cap)

    def _trigger_send():
        st.session_state["_pending_send"] = True

    c1, c2 = st.columns([1, 1])
    c1.button(
        "Send",
        type="primary",
        use_container_width=True,
        key="btn_send",
        on_click=_trigger_send,
        disabled=send_disabled,
    )

    fb_click = c2.button(
        "Feedback",
        use_container_width=True,
        key="btn_feedback",
        disabled=not feedback_enabled(),  # <- no-arg
        help="Enabled only during Practice phase in Practice + Feedback mode.",
    )
    return fb_click


# UI – Right column (feedback)
def render_feedback_column(fb_click):
    st.subheader("Feedback / Summary")

    if not feedback_enabled():  # <- no-arg
        st.info("Feedback is unavailable in this phase.")
        return

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
        st.session_state["session_metrics"] = parse_session_metrics(fb_all)
        st.rerun()

    if st.session_state.get("overall_feedback"):
        st.markdown(st.session_state["overall_feedback"])
    else:
        st.info("Write a reply, then click **Feedback** to get session-level feedback.")

    if st.session_state.get("metrics_summary"):
        st.divider()
        st.markdown("**Live skill usage in this session** (fraction of counselor turns):")
        ms = st.session_state["metrics_summary"]
        st.write(f"- Empathy: {ms.get('Empathy', 0):.2f}")
        st.write(f"- Reflection: {ms.get('Reflection', 0):.2f}")
        st.write(f"- Open Questions: {ms.get('Open Questions', 0):.2f}")
        st.write(f"- Validation: {ms.get('Validation', 0):.2f}")
        st.write(f"- Suggestions: {ms.get('Suggestions', 0):.2f}")


# UI – Self-efficacy (Pre/Post)
def render_self_efficacy_if_needed():
    phase = st.session_state["phase"]
    if phase not in ("Pre", "Post"):
        return

    with st.expander("Self-efficacy (0–7)", expanded=False):
        se_expl = st.slider("Exploration", 0, 7, 4, step=1, key=f"se_expl_{phase}")
        se_act = st.slider("Action", 0, 7, 4, step=1, key=f"se_act_{phase}")
        se_mgmt = st.slider("Session Mgmt", 0, 7, 4, step=1, key=f"se_mgmt_{phase}")
        if st.button(f"Save self-efficacy ({phase})", use_container_width=True, key=f"se_save_{phase}"):
            os.makedirs("logs", exist_ok=True)
            path = os.path.join("logs", "seff.csv")
            row = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "participant_id": st.session_state["participant_id"],
                "session_id": st.session_state["session_id"],
                "phase": phase,
                "mode": effective_mode_from_state(),
                "scenario": st.session_state["scenario"],
                "Exploration": se_expl,
                "Action": se_act,
                "SessionMgmt": se_mgmt,
            }
            new = not os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=row.keys())
                if new:
                    w.writeheader()
                w.writerow(row)
            st.success(f"Saved self-efficacy for {phase}.")

            if phase == "Pre" and st.session_state["completed"].get("Pre"):
                start_next_phase()
                st.rerun()

# -----------------------------
# MAIN
# -----------------------------
def main():
    st.set_page_config(
        page_title="CARE-style Counselor Practice (Google Gemini AI)",
        page_icon="🧠",
        layout="wide",
    )

    setup_session_defaults()
    force_phase_scenario()
    render_sidebar()

    if not st.session_state["started"]:
        st.info("Use the left sidebar to start at **Pre**.")
        return

    render_header_badges()
    ensure_first_patient()
    handle_pending_send()

    left, right = st.columns([0.58, 0.42])
    with left:
        fb_click = render_chat_column()
    with right:
        render_feedback_column(fb_click)

    render_self_efficacy_if_needed()

if __name__ == "__main__":
    main()
