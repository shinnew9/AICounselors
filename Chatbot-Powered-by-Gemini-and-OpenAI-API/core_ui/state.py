import uuid
import streamlit as st
# from core_ui.state import ensure_global_ui_state

def ensure_global_ui_state():
    st.session_state.setdefault("panel_open", True)

def toggle_panel():
    st.session_state["panel_open"] = not st.session_state.get("panel_open", True)


def init_state():
    st.session_state.setdefault("page", "Intake")
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("user_role", "Student")   # Student | Instructor
    st.session_state.setdefault("instructor_unlocked", False)
    
    # dataset controls
    st.session_state.setdefault("ds_file", None)
    st.session_state.setdefault("rewrite_target", "Hispanic college student")
    st.session_state.setdefault("max_rows", 20000)

    # session/chat state
    st.session_state.setdefault("loaded_session", None)
    st.session_state.setdefault("turns_cleaned", [])
    st.session_state.setdefault("qc", {})
    st.session_state.setdefault("cursor", 0)
    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])

    # metrics / feedback
    st.session_state.setdefault("turn_labels", [])
    st.session_state.setdefault("metrics_summary", {})
    st.session_state.setdefault("overall_feedback", None)

    # run id
    st.session_state.setdefault("session_id", str(uuid.uuid4()))

    # display options
    st.session_state.setdefault("hide_system", True)
    st.session_state.setdefault("dedupe", True)
    st.session_state.setdefault("compact_system", True)


def reset_chat_state(keep_profile: bool = True):
    prof = st.session_state.get("profile") if keep_profile else None

    st.session_state["loaded_session"] = None
    st.session_state["turns_cleaned"] = []
    st.session_state["qc"] = {}
    st.session_state["cursor"] = 0
    st.session_state["patient_msgs"] = []
    st.session_state["counselor_msgs"] = []
    st.session_state["turn_labels"] = []
    st.session_state["metrics_summary"] = {}
    st.session_state["overall_feedback"] = None

    st.session_state["session_id"] = str(uuid.uuid4())

    if keep_profile:
        st.session_state["profile"] = prof
