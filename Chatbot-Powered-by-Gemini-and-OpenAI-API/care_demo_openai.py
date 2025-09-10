# care_demo_openai.py

import os, re, time
import streamlit as st
from dotenv import load_dotenv

# --- OpenAI (0.28 스타일) ---
import openai

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def oai(messages, model_list = ("gpt-4o-mini", "gpt-4o", "gpt-5-turbo"),
        temperature=0.6, max_tokens = 600):
    last_err = None
    for m in model_list:
        try:
            resp = openai.ChatCompletion.create(
                model=m, messages = messages,
                temperature = temperature, max_tokens = max_tokens,
            )
            return resp["choices"][0]["message"]["content"], m
        except Exception as e:
            last_err = e
            continue
    raise last_err



# ------- Scenarios (Persona) --------- #
SCENARIOS = {
    "Alex (35, holiday loneliness / estranged parents)": {
        "background": """You are a 35 - year - old American male . You are feeling abandoned and alone after the holidays . Everyone had been with family but you are not talking to your parents. 
        You feel the injustice of being abandoned and have no interest in an olive branch to work on things .""",
        "style": "Reply in 1–3 sentences in natural, conversational American English. Convey hurt/resentment and loneliness; do not ask for advice; occasionally ask short questions about connection/meaning.",
    },
}


# ------- System Prompts ------- #
def build_patient_system_prompt(scn_name):
    scn = SCENARIOS[scn_name]
    return f"""
You are ROLE-PLAYING as a mental health seeker. {scn['background']}
Guidelines:
- Respond in {scn['style']}
- Stay in character. Do NOT give advice or analyze the counselor.
- Keep each reply to 1-3 sentences. Be concrete about feelings/situations.
- Do NOT introduce self-harm or harm to tohers on your won. If asked, deny immdediate danger.
- Avoid medical/legal instructions. You are ONLY the seeker (patient role).
"""


FEEDBACK_SYSTEM = """
You are a supervisor giving structured feedback to a novice counselor's single reply.
Evaluate ONLY the counselor's reply to the seeker's latest message.

Output STRICTLY in the following Markdown sections:

## Skill Check
- Empathy (✔/✖): <one-sentence evidence>
- Reflection (✔/✖): <evidence>
- Open Questions (✔/✖): <evidence>
- Non-judgment/Validation (✔/✖): <evidence>
- Advice Timing (OK/Too early): <evidence>

## What Worked
- <1–2 bullets>

## What To Improve
- <2–3 bullets, action-oriented and specific>

## Suggested Rewrite (concise)
<1–2 sentences revised counselor reply>

## Suggested Rewrite (expanded)
<3–5 sentences revised counselor reply>

## Risk Flag
- Any risk or crisis language detected in counselor reply? (Yes/No). If Yes, say why.
"""


RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|hurt myself|end it|overdose)\b", re.I)




# ----- Streamlit UI -------
st.set_page_config(page_title = "CARE-style Counselor Praactice", layout = "wide")
st.title("CARE-style Counselor Practice (OpenAI)")

with st.sidebar:
    st.header("Session setup")
    scenario = st.selectbox("Patien Scenario", list(SCENARIOS.keys()))
    mode = st.radio("Pracice Mode", ["Practice only", "Practice + Feedback"], index=1)
    max_turns = st.slider("Maximum Number of Turns", 2, 10, 6, 1)

    if st.button("Session Start/Reset", type="primary", use_container_width=True):
        st.session_state.clear()
        st.session_state["started"] = True
        st.session_state["scenario"] = scenario
        st.session_state["mode"] = mode
        st.session_state["turn"] = 1
        st.session_state["patient_msgs"] = []
        st.session_state["counselor_msgs"] = []
        st.session_state["feedbacks"] = []
        st.success("Session has started. First conversation generated")

# Checking initialization
if "started" not in st.session_state:
    st.info("Choose your scenario from the sidebar and press **Session Start/Click** ")
    st.stop()

# Patient's 1st Prompt (if not created)
if len(st.session_state["patient_msgs"]) == 0:
    sys_prompt = build_patient_system_prompt(st.session_state["scenario"])
    msg = [
        {"role": "system", "content": sys_prompt},
        {"role":"user", "content":"오늘 어떠세요? 요즘 어떤일이 가장 힘들게 하나요? (start the conversation)"},
    ]
    with st.spinner("Generationg the patient's 1st prompt..."):
        p_text, used_model = oai(msg, temperature=0.7, max_tokens=200)
    st.session_state["patient_msgs"].append(p_text)

# Main Contents Layout
col_chat, col_fb = st.columns([0.58, 0.42])

with col_chat:
    st.subheader("Conversaion")
    # Conversation Log Print
    for i, p in enumerate(st.session_state["patient_msgs"]):
        st.markdown(f"**Patient:** {p}")
        if i <len(st.session_state["counselor_msgs"]):
            st.markdown(f"**Me (Counselor):** {st.session_state['counselor_msgs'][i]}")
        
    # Input
    if st.session_state["turn"] <= max_turns:
        user_reply = st.text_area("Write your answers here. (1-5 sentences)", height=140, key=f"reply_{st.session_state['turn']}")
        submit = st.button("Submit", type="primary")

    else:
        user_reply= None
        submit = False
        st.sucess("Session has terminated. You can check the summary of feedback on the right side.")

    if submit and user_reply.strip():
        # Lightweight risk keyword check (in case the counselor's reply accidentally includes crisis language) 
        if RISK_PAT.search(user_reply):
            st.warning("Crisis-related language detected. In real situations, direct to local crisis resources (US: 988).")
        st.session_state["counselor_msgs"].append(user_reply)


    # Feedback generation (optional)
    feedback_md = None
    if st.session_state["mode"] == "Practice + Feedback":
        fb_msgs = [
            {"role": "system", "content": FEEDBACK_SYSTEM},
            {"role": "user", "content": f"Seeker said: {st.session_state['patient_msgs'][-1]}"},
            {"role": "user", "content": f"Counselor replied: {user_reply}"},
        ]
        with st.spinner("Generating feedback..."):
            feedback_md, used_model = oai(fb_msgs, temperature=0.4, max_tokens=600)
        st.session_state["feedbacks"].append(feedback_md)

    # Next patient message
    convo = [{"role": "system", "content": build_patient_system_prompt(st.session_state["scenario"])}]
    # Provide alternating history of patient and counselor turns
    for p, c in zip(st.session_state["patient_msgs"], st.session_state["counselor_msgs"]):
        convo += [{"role": "assistant", "content": p}]  # patient (LLM)
        convo += [{"role": "user", "content": c}]       # counselor (user)
    with st.spinner("Generating the next patient message..."):
        next_p, used_model = oai(convo, temperature=0.7, max_tokens=220)
    st.session_state["patient_msgs"].append(next_p)

    st.session_state["turn"] += 1
    st.experimental_rerun()

with col_fb:
    st.subheader("Feedback / Summary")
    if st.session_state["mode"] == "Practice only":
        st.info("You're in **Practice only** mode. Switch to **Practice + Feedback** in the sidebar to see feedback.")
    else:
        if len(st.session_state["feedbacks"]) == 0:
            st.info("No feedback yet. Submit your first reply to receive feedback.")
        else:
            # Show the most recent feedback
            st.markdown(st.session_state["feedbacks"][-1])

    with st.expander("Session Safety / Ethics Notice", expanded=False):
        st.markdown(
            "- This tool is an **educational simulator**, not diagnosis or therapy.\n"
            "- In emergencies (risk of self- or other-harm), contact local emergency services, or **988** in the United States."
        )

    if st.button("End Session", use_container_width=True):
        st.session_state["turn"] = 999
        st.success("Session ended. Use the button at the top-left to reset and start again.")




