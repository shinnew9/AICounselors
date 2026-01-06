import streamlit as st
from core_ui.auth import sign_out_to_home

def sidebar_rater_panel():
    ### culture_select에서만 호출, rater_id는 로그인 후 culture select 화면에서만 보여야 함
    st.sidebar.markdown("## Rater")

    st.sidebar.caption("Email")
    st.sidebar.write(st.session_state.get("email", ""))

    st.sidebar.caption("Rater ID (editable)")
    rid = st.sidebar.text_input(" ", value=st.session_state.get("rater_id", ""), label_visibility="collapsed")
    st.session_state["rater_id"] = (rid or "").strip()

    if st.sidebar.button("Sign out"):
        sign_out_to_home()
