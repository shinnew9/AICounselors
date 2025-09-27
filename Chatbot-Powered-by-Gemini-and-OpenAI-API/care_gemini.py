# CARE-style counselor practice (Gemini) — single-file clean version
# Prereqs: pip install streamlit python-dotenv google-generativeai==0.3.2
# Run:     streamlit run care_app_full_gemini.py
# .env:    GOOGLE_API_KEY=AIza...

import os, re
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# ---------- Page / Setup ----------
st.set_page_config(page_title="CARE-style Counselor Practice (Google Gemini AI)",
                   page_icon="🧠", layout="wide")
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.error("GOOGLE_API_KEY not found. Put it in your .env (no quotes).")
    st.stop()
genai.configure(api_key=API_KEY)

def gcall(prompt_text: str,
          models=("gemini-2.5-flash-preview-09-2025", "gemini-2.5-flash-lite-preview-09-2025"),  # "gemini-pro"
          max_tokens=450, temperature=0.6):
    """Minimal Gemini call with graceful fallback."""
    last_err = None
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            resp = model.generate_content(
                prompt_text,
                generation_config={"max_output_tokens": max_tokens, "temperature": temperature}
            )
            txt = getattr(resp, "text", None)
            if not txt and getattr(resp, "candidates", None):
                parts = getattr(resp.candidates[0].content, "parts", [])
                if parts and hasattr(parts[0], "text"):
                    txt = parts[0].text
            return (txt or "").strip(), m
        except Exception as e:
            last_err = e
            continue
    raise last_err

# ---------- Scenarios ----------
SCENARIOS = {
    "Minji (25, grad school stress / insomnia)": {
        "background": (
            "You are Minji, a 25-year-old international graduate student. "
            "For the past 3 weeks you've had poor sleep (about 3–4 hours), low appetite, "
            "heavy deadline pressure, and you feel isolated in a new environment."
        ),
        "style": "natural English in 1–3 sentences; share concrete feelings and situations."
    },
    "Alex (35, holiday loneliness / estranged parents)": {
        "background": (
            "You are a 35-year-old American male. You are feeling abandoned and alone after the holidays. "
            "Everyone was with family, but you are not talking to your parents. "
            "You feel the injustice of being abandoned and have no interest in an olive branch to work on things."
        ),
        "style": "1–3 short sentences of natural American English; convey hurt/resentment and loneliness."
    },
    "Veteran father (35, reconnecting with children / legal barriers)": {
        "background": (
            "You are a 35-year-old U.S. military veteran and father. "
            "You want to reconnect with your children but face legal barriers and parental gatekeeping from your ex-partner. "
            "You feel shut out and frustrated, worried about losing the relationship, yet trying to stay hopeful and respectful of boundaries."
        ),
        "style": "1–3 short sentences of natural American English; convey longing to reconnect, frustration with barriers, and concern for your kids."
    },
}

# ---------- Prompts ----------
def build_patient_system_prompt(scn_name: str) -> str:
    scn = SCENARIOS[scn_name]
    return f"""You are ROLE-PLAYING as a mental health seeker (patient).
Background: {scn['background']}

Guidelines:
- Respond in {scn['style']}
- Stay in character. Do NOT give advice, diagnoses, or analyze the counselor.
- Keep each reply to 1–3 sentences. Be concrete about feelings and situations.
- Do NOT introduce self-harm or harm to others on your own. If asked, deny immediate danger.
- Avoid medical/legal instructions. You are ONLY the seeker (patient role).
"""

OVERALL_FEEDBACK_SYSTEM = """
You are a supervisor evaluating the ENTIRE counseling conversation (multiple turns).
Assess ONLY the counselor’s replies in aggregate. Provide concise, actionable feedback.

Output STRICTLY in Markdown with these sections:

## Skill Ratings (session-level)
- Empathy (✔/✖, 0–5): <one-sentence evidence>
- Reflection (✔/✖, 0–5): <evidence>
- Open Questions (✔/✖, 0–5): <evidence>
- Validation / Non-judgment (✔/✖, 0–5): <evidence>
- Advice Timing (OK/Too early, 0–5): <evidence>

## What Worked
- <1–3 bullets>

## What To Improve
- <2–4 bullets, action-oriented and specific>

## Exemplars (rewrite the counselor’s MOST RECENT reply)
- Concise: <1–2 sentences>
- Expanded: <3–5 sentences>

## Risk Flag
- Any risk/crisis language in the counselor’s replies? (Yes/No). If Yes, why and what should have been done.
"""

def build_history(patient_msgs, counselor_msgs):
    lines = []
    for i, p in enumerate(patient_msgs):
        lines.append(f"Patient {i+1}: {p}")
        if i < len(counselor_msgs):
            lines.append(f"Counselor {i+1}: {counselor_msgs[i]}")
    return "\n".join(lines)

# ---------- Session defaults ----------
if "mode" not in st.session_state:
    st.session_state["mode"] = "Practice only"
if "scenario" not in st.session_state:
    st.session_state["scenario"] = list(SCENARIOS.keys())[0]
for k, v in {
    "started": False,
    "turn": 1,
    "patient_msgs": [],
    "counselor_msgs": [],
    "overall_feedback": None,
}.items():
    st.session_state.setdefault(k, v)

def reset_session():
    """Reset conversation while preserving mode & scenario."""
    st.session_state.update({
        "started": True,
        "turn": 1,
        "patient_msgs": [],
        "counselor_msgs": [],
        "overall_feedback": None,
    })

# ---------- Sidebar (directly bound to session keys) ----------
with st.sidebar:
    st.header("Session setup")

    st.selectbox(
        "Patient Scenario",
        list(SCENARIOS.keys()),
        index=list(SCENARIOS.keys()).index(st.session_state["scenario"]),
        key="scenario",
    )

    st.radio(
        "Mode",
        ["Practice only", "Practice + Feedback"],
        index=(0 if st.session_state["mode"] == "Practice only" else 1),
        key="mode",  # ← single source of truth
    )

    if st.button("Session Start / Reset", type="primary", use_container_width=True, key="btn_reset"):
        reset_session()
        st.success("Session has started. First conversation will be generated.")
        st.rerun()

# ---------- Guard ----------
if not st.session_state["started"]:
    st.info("Use the left sidebar to select a scenario and click **Session Start / Reset**.")
    st.stop()

# ---------- Header / live badge ----------
st.title("CARE-style Counselor Practice (Google Gemini AI)")
st.caption(f"Mode: {'Practice + Feedback' if st.session_state['mode']=='Practice + Feedback' else 'Practice only'}")

# ---------- First patient message ----------
if len(st.session_state["patient_msgs"]) == 0:
    p = (
        f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
        "Task: Start the conversation in 1–2 sentences about how you're feeling."
    )
    with st.spinner("Generating the first patient message..."):
        first, _ = gcall(p, max_tokens=140, temperature=0.7)
    st.session_state["patient_msgs"].append(first)

# ---------- Layout ----------
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

        st.session_state["counselor_msgs"].append(user_reply.strip())

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

    with st.expander("Safety / Ethics Notice", expanded=False):
        st.markdown(
            "- This is an **educational simulator**, not diagnosis or therapy.\n"
            "- In emergencies (risk of self- or other-harm), contact local emergency services, or **988** in the United States."
        )

    if st.button("End Session", use_container_width=True, key="btn_end"):
        st.session_state["started"] = False
        st.success("Session ended. Use Start / Reset to begin again.")
        st.rerun()
