import streamlit as st


def ensure_global_ui_state() -> None:
    """Global UI flags that should exist regardless of page."""
    st.session_state.setdefault("panel_open", True)
    st.session_state.setdefault("_bubble_css_loaded", False)


def init_state() -> None:
    """
    IMPORTANT:
    - Must be safe to call on every rerun.
    - Only set defaults (setdefault), never overwrite existing values.
    """
    # access gate / roles
    st.session_state.setdefault("access_done", False)
    st.session_state.setdefault("user_role", None)  # "Student" | "Instructor"
    st.session_state.setdefault("instructor_unlocked", False)

    # navigation
    st.session_state.setdefault("page", "Intake")  # Intake | Chat | Results | Instructor PIN

    # intake/profile
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("rewrite_target", None)

    # dataset
    st.session_state.setdefault("ds_file", None)
    st.session_state.setdefault("max_rows", 20000)

    # chat toggles
    st.session_state.setdefault("hide_system", False)
    st.session_state.setdefault("dedupe", True)
    st.session_state.setdefault("compact_system", True)

    # chat runtime (DO NOT overwrite!)
    st.session_state.setdefault("loaded_session", None)
    st.session_state.setdefault("turns_cleaned", [])
    st.session_state.setdefault("qc", {})
    st.session_state.setdefault("cursor", 0)

    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])
    st.session_state.setdefault("turn_labels", [])

    st.session_state.setdefault("metrics_summary", {})
    st.session_state.setdefault("overall_feedback", None)

    # internal logging (instructor only)
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("removed_dupes", 0)
    st.session_state.setdefault("session_play_count", 0)
    st.session_state.setdefault("session_play_log", [])
    st.session_state.setdefault("_load_err", None)


def reset_chat_state(keep_profile: bool = True) -> None:
    """Clear only chat/session-specific state."""
    # keep profile & rewrite_target if requested
    profile = st.session_state.get("profile") if keep_profile else None
    rewrite_target = st.session_state.get("rewrite_target") if keep_profile else None

    # clear chat runtime
    st.session_state["loaded_session"] = None
    st.session_state["turns_cleaned"] = []
    st.session_state["qc"] = {}
    st.session_state["cursor"] = 0
    st.session_state["patient_msgs"] = []
    st.session_state["counselor_msgs"] = []
    st.session_state["turn_labels"] = []
    st.session_state["metrics_summary"] = {}
    st.session_state["overall_feedback"] = None

    # internal ids/log (keep play counter/log optional; 난 유지하는 쪽이 디버깅에 좋아서 유지)
    st.session_state["active_session_id"] = None
    st.session_state["removed_dupes"] = 0
    st.session_state["_load_err"] = None

    # restore profile if needed
    st.session_state["profile"] = profile
    st.session_state["rewrite_target"] = rewrite_target


def toggle_panel() -> None:
    st.session_state["panel_open"] = not bool(st.session_state.get("panel_open", True))
