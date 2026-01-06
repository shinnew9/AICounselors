import streamlit as st
from core_ui.layout import set_base_page_config, inject_base_css
from core_ui.auth import require_signed_in
from core_ui.sidebar import sidebar_rater_panel
from core_ui.dataset import get_sessions_for_culture, DATASET_FILES
from core_ui.chat_view import render_chat

set_base_page_config()
inject_base_css()

def main():
    require_signed_in()
    sidebar_rater_panel()

    st.markdown("## Cultural Counseling Session Rater")
    st.caption("Choose a dataset to rate. You will rate sessions sequentially and your progress can be saved.")

    # Dataset selection buttons (+ Others UI only)
    st.markdown("### Select dataset")
    cols = st.columns(4)
    options = ["Chinese", "Hispanic", "African American", "Others"]

    for i, opt in enumerate(options):
        with cols[i]:
            if opt == "Others":
                st.button(opt, disabled=True, use_container_width=True)
            else:
                if st.button(opt, use_container_width=True):
                    st.session_state["culture"] = opt
                    st.session_state["ds_file"] = str(DATASET_FILES.get(opt))  # optional
                    st.session_state["session_idx"] = 0
                    st.session_state["current_session"] = None
                    st.session_state.pop("_sessions_cache", None)
                    st.rerun()

    culture = st.session_state.get("culture", "Others")
    render_chat(session.get("turns", []), culture=culture)
    if not culture:
        st.info("No dataset selected yet.")
        st.stop()

    st.success(f"Current dataset: {culture}")

    # Load sessions cache
    if st.session_state.get("_sessions_cache") is None:
        st.session_state["_sessions_cache"] = get_sessions_for_culture(culture)

    sessions = st.session_state["_sessions_cache"]
    session_idx = int(st.session_state.get("session_idx", 0))
    session_idx = max(0, min(session_idx, len(sessions) - 1))
    st.session_state["session_idx"] = session_idx

    session = sessions[session_idx]
    st.session_state["current_session"] = session

    st.markdown("---")
    st.subheader(f"Session {session_idx + 1} / {len(sessions)}")
    st.caption(f"Session ID: {session.get('session_id', 'unknown')}")

    render_chat(session.get("turns", []))

    st.markdown("---")
    nav_cols = st.columns([1, 1, 2, 2])
    with nav_cols[0]:
        if st.button("← Previous", disabled=(session_idx <= 0), use_container_width=True):
            st.session_state["session_idx"] = session_idx - 1
            st.rerun()
    with nav_cols[1]:
        if st.button("Next →", disabled=(session_idx >= len(sessions) - 1), use_container_width=True):
            st.session_state["session_idx"] = session_idx + 1
            st.rerun()
    with nav_cols[2]:
        if st.button("Start rating →", use_container_width=True):
            st.switch_page("pages/02_Assess.py")

if __name__ == "__main__":
    main()
