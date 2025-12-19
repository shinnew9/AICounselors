import streamlit as st

PHASE_PRACTICE = "Practice"

def effective_mode_from_state() -> str:
    phase = st.session_state.get("phase", PHASE_PRACTICE)
    if phase != PHASE_PRACTICE:
        return "Practice only"
    return (
        st.session_state.get("mode")
        or st.session_state.get("mode_radio")
        or "Practice only"
    )

def ensure_mode_consistency() -> None:
    phase = st.session_state.get("phase", PHASE_PRACTICE)
    if phase == PHASE_PRACTICE:
        st.session_state["mode"] = st.session_state.get("mode_radio", "Practice only")
    else:
        st.session_state["mode"] = "Practice only"

def feedback_enabled() -> bool:
    return (
        st.session_state.get("phase") == PHASE_PRACTICE
        and effective_mode_from_state() == "Practice + Feedback"
    )
