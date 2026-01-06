import streamlit as st
from core_ui.layout import set_base_page_config, inject_base_css
from core_ui.auth import require_signed_in
from core_ui.dataset import get_sessions_for_culture
from core_ui.chat_view import render_chat

set_base_page_config()
inject_base_css()

def main():
    require_signed_in()

    culture = st.session_state.get("culture")
    if not culture:
        st.warning("Please select a dataset first.")
        st.switch_page("pages/01_culture_select.py")

    # sessions cache
    if st.session_state.get("_sessions_cache") is None:
        st.session_state["_sessions_cache"] = get_sessions_for_culture(culture)
    sessions = st.session_state["_sessions_cache"]

    idx = int(st.session_state.get("session_idx", 0))
    idx = max(0, min(idx, len(sessions) - 1))
    st.session_state["session_idx"] = idx
    session = sessions[idx]
    st.session_state["current_session"] = session

    st.markdown("## 02 — Rate")
    st.caption(f"Dataset: {culture} • Session {idx + 1}/{len(sessions)} • Session ID: {session.get('session_id')}")

    render_chat(session.get("turns", []))

    st.markdown("---")
    st.markdown("### Ratings (placeholder)")
    st.info("We will finalize the A/B perspective metrics later.")

    st.markdown("---")
    cols = st.columns([1, 1, 2, 2])
    with cols[0]:
        if st.button("← Previous", disabled=(idx <= 0), use_container_width=True):
            st.session_state["session_idx"] = idx - 1
            st.rerun()
    with cols[1]:
        if st.button("Next →", disabled=(idx >= len(sessions) - 1), use_container_width=True):
            st.session_state["session_idx"] = idx + 1
            st.rerun()
    with cols[2]:
        if st.button("Back to culture select", use_container_width=True):
            st.switch_page("pages/01_culture_select.py")
    with cols[3]:
        if st.button("Go to results →", use_container_width=True):
            st.switch_page("pages/03_results.py")


if __name__ == "__main__":
    main()
