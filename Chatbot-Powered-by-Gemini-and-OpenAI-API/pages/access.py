import streamlit as st

PIN = "1234"

def render():
    st.title("🧠 AI Counselor Simulation")
    st.caption("Choose your access type to begin.")

    st.markdown("### Access")
    role = st.radio("View as", ["Student", "Instructor"], horizontal=True, key="access_role")

    if role == "Student":
        if st.button("Continue as Student", type="primary", use_container_width=True, key="btn_student"):
            st.session_state["user_role"] = "Student"
            st.session_state["instructor_unlocked"] = False
            st.session_state["page"] = "Intake"
            st.rerun()
        return

    # Instructor
    st.info("Instructor mode requires a PIN.")
    pin = st.text_input("Instructor PIN", type="password", key="access_pin")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Unlock & Continue", type="primary", use_container_width=True, key="btn_instructor"):
            ok = (pin == PIN)
            st.session_state["user_role"] = "Instructor"
            st.session_state["instructor_unlocked"] = bool(ok)
            if ok:
                st.session_state["page"] = "Results"   # 원하면 "Intake"로 바꿔도 됨
                st.rerun()
            else:
                st.error("Wrong PIN. Please try again.")
    with col2:
        if st.button("Back", use_container_width=True, key="btn_back"):
            st.session_state["access_role"] = "Student"
            st.session_state["access_pin"] = ""
            st.rerun()
