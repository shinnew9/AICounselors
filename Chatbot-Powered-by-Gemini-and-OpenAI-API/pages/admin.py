import json
import streamlit as st
from datetime import datetime
from core_ui.data import session_id

def render():
    st.subheader("Admin")

    payload = {
        "session_id": st.session_state.get("session_id"),
        "profile": st.session_state.get("profile"),
        "dataset_file": st.session_state.get("ds_file"),
        "loaded_session_id": session_id(st.session_state.get("loaded_session") or {}, ""),
        "patient_msgs": st.session_state.get("patient_msgs", []),
        "counselor_msgs": st.session_state.get("counselor_msgs", []),
        "turn_labels": st.session_state.get("turn_labels", []),
        "metrics_summary": st.session_state.get("metrics_summary", {}),
        "overall_feedback": st.session_state.get("overall_feedback"),
        "ts": datetime.now().isoformat(timespec="seconds"),
    }

    st.download_button(
        "Download session JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name=f"practice_session_{payload['session_id']}.json",
        mime="application/json",
        use_container_width=True,
    )
