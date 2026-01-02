# practice_app/app.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st

from core_ui.ui import nav
from core_ui.state import ensure_global_ui_state, init_state
from pages import intake, chat, results


def access_screen():
    st.markdown(
        """
        <style>
          .access-wrap { max-width: 900px; margin: 3.5rem auto 0 auto; }
          .access-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; }
          .access-sub { opacity: 0.75; margin-bottom: 1.5rem; }

          /* Card-like buttons */
          div[data-testid="stButton"] > button.access-card {
            width: 100%;
            height: 140px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.04);
            color: white;
            font-size: 1.25rem;
            font-weight: 700;
            transition: transform .08s ease, background .15s ease, border-color .15s ease;
          }
          div[data-testid="stButton"] > button.access-card:hover {
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.22);
            transform: translateY(-2px);
          }
          /* Instructor hover tint */
          div[data-testid="stButton"] > button.access-card.instructor:hover {
            background: rgba(255, 69, 96, 0.12);
            border-color: rgba(255, 69, 96, 0.35);
          }
          /* Student hover tint */
          div[data-testid="stButton"] > button.access-card.student:hover {
            background: rgba(0, 122, 255, 0.12);
            border-color: rgba(0, 122, 255, 0.35);
          }

          .access-hint { font-size: 0.95rem; opacity: 0.7; margin-top: 0.35rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="access-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="access-title">Access</div>', unsafe_allow_html=True)
    st.markdown('<div class="access-sub">Choose how you want to use this app.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="large")

    with c1:
        # "access-card student" 클래스를 button에 먹이기 위해 label을 HTML로 넣는 꼼수 사용
        if st.button("Student", key="access_student"):
            st.session_state["user_role"] = "Student"
            st.session_state["instructor_unlocked"] = False
            st.session_state["access_done"] = True
            st.session_state["page"] = "Intake"
            st.rerun()

        # 버튼 클래스 주입 (Streamlit 기본 버튼에 class를 직접 못 주니, 아래 JS 없이 가장 안정적인 방식은
        # "버튼을 만든 다음 CSS로 nth-of-type을 잡는 방법"인데 페이지 구조가 바뀌면 깨질 수 있음.
        # 그래서 여기서는 'st.button'을 그대로 쓰고, 아래에서 간단히 카드 느낌만 적용.
        st.caption("Create a client profile and practice counseling.")
    with c2:
        if st.button("Instructor", key="access_instructor"):
            st.session_state["user_role"] = "Instructor"
            st.session_state["access_done"] = True
            st.session_state["page"] = "Instructor PIN"
            st.rerun()
        st.caption("Unlock instructor tools and downloads (PIN required).")

    st.markdown("</div>", unsafe_allow_html=True)


def instructor_pin_screen():
    st.subheader("Instructor Access")
    pin = st.text_input("Enter PIN", type="password")
    if st.button("Continue", type="primary"):
        st.session_state["instructor_unlocked"] = (pin == "1234")
        if not st.session_state["instructor_unlocked"]:
            st.error("Wrong PIN.")
            return
        st.session_state["page"] = "Results"
        st.rerun()


def render_top_nav():
    st.markdown("## 🧠 AI Counselor Simulation")
    tabs = st.radio(
        "",
        ["Intake", "Chat", "Results"],
        horizontal=True,
        index=["Intake","Chat","Results"].index(st.session_state.get("page", "Intake"))
        if st.session_state.get("page") in ("Intake","Chat","Results") else 0,
        key="top_nav_radio",
    )
    st.session_state["page"] = tabs


PIN = 1234
def render_access_page():
    st.subheader("Access")
    st.caption("Choose how you want to use this app.")

    choice = st.radio("View as", ["Student", "Instructor"], horizontal=True)

    if choice == "Student":
        st.session_state["user_role"] = "Student"
        st.session_state["instructor_unlocked"] = False
        if st.button("Continue", type="primary", use_container_width=True):
            st.session_state["page"] = "Intake"
            st.rerun()

    else:
        st.session_state["user_role"] = "Instructor"
        pin = st.text_input("Instructor PIN", type="password", placeholder="Enter PIN (1234)")
        ok = (pin == PIN)
        st.session_state["instructor_unlocked"] = ok

        if ok:
            st.success("Unlocked.")
            if st.button("Continue to Results", type="primary", use_container_width=True):
                st.session_state["page"] = "Results"
                st.rerun()
        else:
            st.info("Enter PIN to unlock instructor tools.")


def main():
    st.set_page_config(page_title="AI Counselor Simulation", page_icon="🧠", layout="wide")
    init_state()
    ensure_global_ui_state()

    # 0) Access gate
    if not st.session_state.get("access_done"):
        access_screen()
        return

    page = st.session_state.get("page", "Intake")

    # 1) Instructor PIN page
    if page == "Instructor PIN":
        instructor_pin_screen()
        return

    # 2) Student flow: show nav only AFTER access gate (and only for students)
    if st.session_state.get("user_role") == "Student":
        st.title("🧠 AI Counselor Simulation")
        nav()   # <- 여기서 page가 갱신됨
        st.divider()
        page = st.session_state.get("page", "Intake")

        if page == "Intake":
            intake.render()
            return

        if page == "Chat":
            # profile guard
            if not st.session_state.get("profile"):
                st.warning("Please complete Intake first.")
                st.session_state["page"] = "Intake"
                st.rerun()
            chat.render()
            return

        # Results
        results.render()
        return

    # 3) Instructor flow (unlocked only)
    if st.session_state.get("user_role") == "Instructor":
        if not st.session_state.get("instructor_unlocked"):
            st.session_state["page"] = "Instructor PIN"
            st.rerun()
        results.render()


if __name__ == "__main__":
    main()
