import os

import streamlit as st
from datetime import datetime
from core_ui.state import reset_chat_state


DATASET_BY_RACE = {
    "African American": "data/psydial4/student_only_rewrite_african_american_college_grad_100.jsonl",
    "Hispanic": "data/psydial4/student_only_rewrite_hispanic_college_grad_100.jsonl",
}


def render():
    st.write("INTAKE FILE:", os.path.abspath(__file__))
    st.subheader("Intake Survey (Create a client profile)")
    st.caption("Fill this out once, then start chatting using this profile.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        race = st.selectbox("Race / Ethnicity", ["African American", "Hispanic", "Asian", "White", "Other"], index=0)
    with col2:
        gender = st.selectbox("Gender", ["Female", "Male", "Non-binary", "Other"], index=0)
    with col3:
        academic = st.selectbox("Academic level", ["Undergraduate", "Graduate", "Other"], index=0)
    with col4:
        major = st.selectbox("Major", ["Engineering", "Computer Science", "Business", "Arts", "Other"], index=1)

    concerns = st.multiselect(
        "What are you most concerned about? (multi-select)",
        ["academics", "stress/anxiety", "family", "relationships", "loneliness", "identity", "finances", "other"],
        default=["academics", "stress/anxiety"],
    )

    # 요구사항: 기본값 최대치
    c5, c6, c7 = st.columns([1, 1, 1.2])
    with c5:
        mood = st.slider("Mood (0–1)", 0.0, 1.0, 1.0, step=0.01)
    with c6:
        openness = st.slider("Openness (0–1)", 0.0, 1.0, 1.0, step=0.01)
    with c7:
        topic = st.text_input("Topic (optional)", value=(concerns[0] if concerns else ""))

    if st.button("Create profile & Start chat", type="primary", key="btn_create_profile"):
        st.session_state["profile"] = {
            "race_ethnicity": race,
            "gender": gender,
            "academic_level": academic,
            "major": major,
            "concerns": concerns,
            "mood": float(mood),
            "openness": float(openness),
            "topic": topic.strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        # auto set rewrite_target based on intake
        if race == "African American":
            st.session_state["rewrite_target"] = "African American student"
        elif race == "Hispanic":
            st.session_state["rewrite_target"] = "Hispanic college student"
        else:
            st.session_state["rewrite_target"] = None

        st.session_state["ds_file"] = None
        st.session_state["loaded_session"] = None

        reset_chat_state(keep_profile=True)
        st.session_state["page"] = "Chat"
        st.rerun()
