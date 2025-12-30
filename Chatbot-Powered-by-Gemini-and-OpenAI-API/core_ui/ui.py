import streamlit as st

def nav():
    # 3 tabs only
    tabs = ["Intake", "Chat", "Results"]
    idx = tabs.index(st.session_state["page"]) if st.session_state["page"] in tabs else 0
    picked = st.radio("Navigation", tabs, index=idx, horizontal=True, label_visibility="collapsed")
    st.session_state["page"] = picked

def render_turn(role: str, text: str):
    """
    Our app semantics:
    - 'patient' should appear on LEFT  -> chat_message("assistant")
    - 'counselor' should appear on RIGHT -> chat_message("user")
    """
    if role == "patient":
        with st.chat_message("assistant"):
            st.write(text)
    elif role == "counselor":
        with st.chat_message("user"):
            st.write(text)
    else:
        # system
        with st.chat_message("assistant"):
            if st.session_state.get("compact_system", True):
                st.markdown(f"*{text}*")
            else:
                st.write(text)
