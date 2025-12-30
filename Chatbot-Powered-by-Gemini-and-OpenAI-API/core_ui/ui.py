import streamlit as st

def nav():
    # 3 tabs only
    tabs = ["Intake", "Chat", "Results"]
    idx = tabs.index(st.session_state["page"]) if st.session_state["page"] in tabs else 0
    picked = st.radio("Navigation", tabs, index=idx, horizontal=True, label_visibility="collapsed")
    st.session_state["page"] = picked

def render_turn(role: str, text: str):
    if role == "user":
        with st.chat_message("user"):
            st.write(text)
    elif role == "assistant":
        with st.chat_message("assistant"):
            st.write(text)
    else:
        with st.chat_message("assistant"):
            if st.session_state.get("compact_system", True):
                st.markdown(f"*{text}*")
            else:
                st.write(text)
