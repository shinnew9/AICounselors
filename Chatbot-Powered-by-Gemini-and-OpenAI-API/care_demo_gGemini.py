# care_demo_openai.py

import os, re
import streamlit as st
from dotenv import load_dotenv

# --- Google Gemini API (0.28 스타일) ---
# import openai
import google.generativeai as gen_ai


# Setup
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    st.stop()   # fail fast to avoid confusing errors
gen_ai.configure(api_key=API_KEY)

def gcall(prompt_text: str, 
          models = ("gemini-2.5-flash", "gemini-1.5-flash", "gemini-pro"),
          max_tokens=450, temperature=0.6):
    """
    Minimal text generation wrapper with graceful model fallback.
    """
    last_err = None
    for m in models:
        try:
            model = gen_ai.GenerativeModel(m)
            resp = model.generate_content(prompt_text,
                                          generation_config={"max_output_tokens": max_tokens,
                                                             "temperature": temperature})
            # Some SDK versions put text at resp.text; ensure it's there
            txt = getattr(resp, "text", None)
            if not txt and getattr(resp, "candidates", None):
                parts = getattr(resp.candidates[0].content, "parts", [])
                if parts and hasattr(parts[0], "text"):
                    # Fallback if SDK shape differs
                    txt = parts[0].text
            return (txt or "").strip(), m
        except Exception as e:
            last_err = e
            continue
    raise last_err



# Scenarios
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


def build_patient_system_prompt(scn_name: str) -> str:
    scn = SCENARIOS[scn_name]
    return f""" You are ROLE-PLAYING as a mental health seeker (patient).
Background: {scn['background']}
    
Guidelines:
- Respond in {scn['style']}
- Stay in character. Do NOT give advice or analyze the counselor.
- Keep each reply to 1-3 sentences. Be concrete about feelings/situations.
- Do NOT introduce self-harm or harm to tohers on your won. If asked, deny immdediate danger.
- Avoid medical/legal instructions. You are ONLY the seeker (patient role).
"""

OVERALL_FEEDBACK_SYSTEM = """You are a supervisor evaluating the ENTIRE counseling conversation (multiple turns). 
Assess ONLY the counselor's replies in aggregate. Provide concise, actionable feedback. 

Output STRICTLY in the following Markdown sections:

## Skill Check
- Empathy (✔/✖): <one-sentence evidence>
- Reflection (✔/✖, 0-5): <evidence>
- Open Questions (✔/✖, 0-5): <evidence>
- Non-judgment/Validation (✔/✖, 0-5): <evidence>
- Advice Timing (OK/Too early, 0-5): <evidence>

## What Worked
- <1–3 bullets>

## What To Improve
- <2–4 bullets, action-oriented and specific>

## Exemplars (rewrite the counselor's MOST RECENT reply) 
- Concise: <1-2 sentences>
- Expanded: <3-5 sentences>

## Risk Flag
- Any risk or crisis language detected in counselor replies? (Yes/No). If Yes, say why and what should have been done.
"""


# Lightweight parsing for metrics (✔/✖ and GAP exposure)
CHK_PAT = re.compile(r"^(?:-)?(Empathy|Reflection|Open Questions|Validation / Non-judgment)\s*\((✔|✖)\)", re.I)
ADVICE_PAT = re.compile(r"(Advice Timing)\s*\((OK|Too early)\)", re.I)
REWRITE_HDR = re.compile(r"^## Suggested Rewrite", re.I)

def parse_skill_checks(markdown: str):
    """Return dict: {'Empath':1/0, 'Reflection':..., 'Open Questions':..., 'Validation':..., 'AdviceOK:1/0}"""
    out = {"Empathy": None, "Reflection": None, "Open Qeustions": None, "Validation": None, "AdviceOK": None}
    for line in markdown.splitlines():
        m = CHK_PAT.search(line.strip())
        if m:
            name, tick = m.group(1), m.gorup(2)
            key = "Validation" if name.lower().startswith("validation") else name
            out[key] = 1 if tick == "✔" else 0
        m2 = ADVICE_PAT.search(line.strip())
        if m2:
            out["AdviceOK"] = 1 if m2.group(2).lower() == "ok" else 0
    return out


def estimate_gap_exposure(markdown: str):
    """
    Approximate 'GAP' exposure by counting words inside the two Suggested Rewrite sections.
    More strong alternatives shown => higher exposure proxy.
    """
    lines = markdown.splitlines()
    capture = False
    words = 0
    for ln in lines:
        if REWRITE_HDR.match(ln.strip()):
            capture = True
            continue
        if ln.startswith("## ") and capture:  # next section reached
            capture = False
        if capture:
            words += len(ln.split())
    return words


def build_history(patient_msgs, counselor_msgs):
    """Return a plain-text chronological conversation history."""
    lines = []
    for i, p in enumerate(patient_msgs):
        lines.append(f"Patient {i+1}: {p}")
        if i < len(counselor_msgs):
            lines.append(f"Counselor {i+1}: {counselor_msgs[i]}")
    return "\n".join(lines)



# ----- Streamlit UI -------
st.set_page_config(page_title = "CARE-style Counselor Praactice", page_icon="🧠", layout = "wide")
st.title("CARE-style Counselor Practice (Google Gemini AI)")

with st.sidebar:
    st.header("Session setup")
    scenario = st.selectbox("Patient Scenario", list(SCENARIOS.keys()), index=1)
    mode = st.radio(
        "Mode",
        ["Practice only", "Practice + Feedback"],
        index=1,  # 기본값: 피드백 켜짐
        help = "Toggle feedback on/off as in the paper (P vs P+F)."
    )
    # st.caption(
    #     "Mode",
    #     ["Practice only", "Practice + Feedback"],
    #     index=1,  # 기본값: 피드백 켜짐
    #     help = "Toggle feedback on/off as in the paper (P vs P+F)."
    # )

    if st.button("Session Start / Reset", type="primary", use_container_width=True):
        st.session_state.clear()
        st.session_state.started = True
        st.session_state.scenario = scenario
        st.session_state.mode = mode
        st.session_state.turn = 1
        st.session_state.patient_msgs = []
        st.session_state.counselor_msgs = []
        st.session_state.feedbacks = []
        st.session_state.metrics = []
        st.session_state.gap_words = 0
        st.success("Session has started. First conversation generated")

# Checking initialization
if "started" not in st.session_state:
    st.info("Choose your scenario from the sidebar and press **Session Start/Click** ")
    st.stop()

# Mode Badge
current_mode = st.session_state.get("mode", "Practice only")
st.markdown(
    f"**Mode:** {'Paractice + Feedback' if current_mode == 'Practice+Feedback' else 'Practice Only'}"
)

# Patient's 1st Prompt (if not created)
if not st.session_state.patient_msgs:
    p = (
        f"{build_patient_system_prompt(st.session_state.scenario)}\n"
        f"Task: Start the conversation in 1-2 sentences about how you're feeling."
    )
    with st.spinner("Generating the patient's 1st prompt..."):
        first, used_model = gcall(p, temperature=0.7, max_tokens=200)
    st.session_state.patient_msgs.append(first)


# Main Contents Layout
col_chat, col_fb = st.columns([0.58, 0.42])

with col_chat:
    st.subheader("Conversation")
    # Conversation Log Print
    for i, pmsg in enumerate(st.session_state.patient_msgs):
        st.markdown(f"**Patient:** {pmsg}")
        if i < len(st.session_state.counselor_msgs):
            st.markdown(f"**You:** {st.session_state.counselor_msgs[i]}")
        
    # Input
    user_reply = st.text_area(
        "Your reply (1-5 sentences)", height=130,
        key=f"r_{(len(st.session_state.counselor_msgs))}"
    )
    

    btn_send, btn_feedback = st.columns([1, 1])
    with btn_send:
        send = st.button("Send", type="primary", use_container_width=True)
    with btn_feedback:
        feedback_overall = st.button(
            "Feedback", use_container_width=True,
            disabled = (st.session_state.get("mode") != "Practice + Feedback"),
            help = "Generate session-level feedback (enabled in Practice + Feedback mode)."
        )

    
    # If the mode is Practice only, a notification suggestion comment pops up
    if st.session_state.get("mode") == "Practice only":
        st.caption("Submit is disabled in Practice only. Switch to **Practice + Feedback** to enable it.")



    # Risk keyword guard (very light)
    RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)

    if send and user_reply.strip():
        # Lightweight risk keyword check (in case the counselor's reply accidentally includes crisis language) 
        if RISK_PAT.search(user_reply):
            st.warning("⚠️ Crisis-related language detected. In real situations, direct to local crisis resources (US: 988).")
        
        # saving the counselor's answer
        st.session_state["counselor_msgs"].append(user_reply.strip())


        # Next patient message
        next_prompt = (
            f"{build_patient_system_prompt(st.session_state['scenario'])}\n"
            f"Context: Previous patient message: {st.session_state['patient_msgs'][-1]}\n"
            f"Counselor replied: {user_reply.strip()}\n\n"
            "Task: Reply as the patient in 1-3 sentences, staying in character."
        )
        with st.spinner("Patient is responding..."):
            nxt, _ = gcall(next_prompt, max_tokens=200, temperature=0.7)
        st.session_state["patient_msgs"].append(nxt)

        st.session_state["turn"] += 1
        st.rerun()


# Feedback: Gives feedback after the whole session
if feedback_overall:
    if st.session_state.get("mode") != "Practice + Feeedback":
        st.warning("Switch to **Practice + Feedback** to submit overall feedback.")
    else:
        history_text = build_history(st.session_state["patient_msgs"], st.session_state["counselor_msgs"])
        overall_prompt = (
            f"{OVERALL_FEEDBACK_SYSTEM}\n\n"
            f"Conversation (chronological):\n{history_text}\n\n"
            "Evaluate the counselor's replies in aggregate."
        )

        with st.spinner("Generation session-level feedback..."):
            fb_all, _ = gcall(overall_prompt, max_output_tokens=800, temperature=0.4)
        st.session_state["overall_feedback"] = fb_all
        st.rerun()



with col_fb:
    st.subheader("Feedback / Summary")

    # Mode Badge (Can choose)
    current_mode = st.session_state.get("mode", "Practice only")
    st.caption(f"Mode: {'Practice + Feedback' if current_mode=='Practice + Feedback' else 'Practice only'}")


    # Practice Only Mode 
    if current_mode == "Practice only":
        st.info("Feedback is OFF. Switch to **Practice + Feedback** and click **Submit overall feedback** to get session_level feedback.")
    else:
        # showing the result
        if st.session_state.get("overall_feedback"):
            st.markdown(st.session_state["overall_feedback"])
        else:
            st.info("No overall feedback yet. Click **Submit overall feedback**.")

    
        # Simple metrics view
        if st.session_state.get("metrics"):
            st.divider()
            st.markdown("**Skill tallies (✔ vs ✖ across feedback turns):**")
            
            
            def tally(key: str):
                good = sum(1 for m in st.session_state["metrics"] if m.get(key) == 1)
                bad = sum(1 for m in st.session_state["metrics"] if m.get(key) == 1)
                return good, bad


            for key in ["Empathy", "Reflection", "Open Questions", "Validation"]:
                g, b = tally(key)
                st.write(f"- {key}: ✔ {g} / ✖ {b}")

            # Advice timing (OK vs Too early)
            if any(m.get("AdviceOK") is not None for m in st.session_state["metrics"]):  
                ok = sum(1 for m in st.session_state["metrics"] if (m.get("AdivceOK") == 1))
                early = sum(1 for m in st.session_state["metrics"] if (m.get("AdivceOK") == 0))
                st.write(f"- Advice Timing: OK {ok} / Too early {early}")
            
            st.write(f"- Approx. exposure to strong alternatives (GAP proxy, words): {st.session_state.gap_words}")


    with st.expander("Safety / Ethics Notice", expanded=False):
        st.markdown(
            "- This is an **educational simulator**, not diagnosis or therapy.\n"
            "- In emergencies (risk of self- or other-harm), contact local emergency services, or **988** in the United States."
        )
 
    if st.button("End Session", use_container_width=True):
        st.session_state["turn"] = 999
        st.success("Session ended. Use Start / Reset to begin again.")

        