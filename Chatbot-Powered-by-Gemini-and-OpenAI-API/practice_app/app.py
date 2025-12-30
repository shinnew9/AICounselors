import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))



import streamlit as st

from core_ui.state import init_state
from core_ui.ui import nav

from pages import intake, chat, results

INSTRUCTOR_PIN = "411"  # 원하면 환경변수로 빼도 됨


def role_selector():
    with st.sidebar:
        st.header("Access")
        st.session_state["user_role"] = st.radio(
            "View as",
            ["Student", "Instructor"],
            index=0 if st.session_state.get("user_role","Student") == "Student" else 1,
            help="Student view hides instructor tools. Instructor view can unlock admin tools in Results."
        )

        if st.session_state["user_role"] == "Instructor":
            pin = st.text_input("Instructor PIN (optional)", type="password")
            st.session_state["instructor_unlocked"] = (pin == INSTRUCTOR_PIN) if INSTRUCTOR_PIN else True
            if not st.session_state["instructor_unlocked"]:
                st.caption("Enter PIN to unlock instructor tools.")
        else:
            st.session_state["instructor_unlocked"] = False


def main():
    st.set_page_config(page_title="AI Counselor Simulation", page_icon="🧠", layout="wide")
    init_state()

    st.title("🧠 AI Counselor Simulation")
    nav()
    st.divider()

    page = st.session_state.get("page", "Intake")
    if page == "Intake":
        intake.render()
    elif page == "Chat":
        chat.render()
    else:
        results.render()


if __name__ == "__main__":
    main()
