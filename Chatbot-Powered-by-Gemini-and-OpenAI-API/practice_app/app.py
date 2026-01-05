import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st

from core_ui.state import init_state, ensure_global_ui_state
from pages import culture_select, rate  # ✅ 새로 만들 페이지 2개


def require_lehigh_login():
    if not st.user.is_logged_in:
        st.markdown("## Sign in")
        st.caption("Lehigh Google 계정으로 로그인해주세요.")
        st.button("Log in with Lehigh Google", on_click=st.login)
        st.stop()

    email = (getattr(st.user, "email", "") or "").lower()
    if not email.endswith("@lehigh.edu"):
        st.error("Lehigh 계정(@lehigh.edu)으로만 접근 가능합니다.")
        st.button("Log out", on_click=st.logout)
        st.stop()

    st.session_state["rater_email"] = email

def _ensure_rater_id():
    email = (st.session_state.get("rater_email") or "")
    default_id = email.split("@")[0] if "@" in email else ""
    st.session_state.setdefault("rater_id", default_id)

def main():
    st.set_page_config(page_title="Cultural Session Rater", page_icon="🧠", layout="wide")

    init_state()
    ensure_global_ui_state()

    # IMPORTANT: 함수 호출!
    require_lehigh_login()
    _ensure_rater_id()

    # Sidebar: rater id
    with st.sidebar:
        st.markdown("### Rater")
        st.caption(f"Email: `{st.session_state.get('rater_email','')}`")
        st.session_state["rater_id"] = st.text_input(
            "Rater ID",
            value=st.session_state.get("rater_id", ""),
            help="Default is your Lehigh id (email before @). You can edit if needed.",
        ).strip()

        st.divider()
        if st.button("Log out", use_container_width=True):
            st.logout()

    # Simple top nav
    st.session_state.setdefault("page", "Culture")

    tabs = st.radio("", ["Culture", "Rate"], horizontal=True,
                    index=0 if st.session_state["page"] == "Culture" else 1)
    st.session_state["page"] = tabs

    if tabs == "Culture":
        culture_select.render()
    else:
        rate.render()


if __name__ == "__main__":
    main()
