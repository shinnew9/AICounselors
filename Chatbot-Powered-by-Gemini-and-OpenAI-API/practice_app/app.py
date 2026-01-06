import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st
from datetime import datetime

from core_ui.state import init_state, ensure_global_ui_state
from pages import culture_select, rate


def require_lehigh_login():
    """
    1) Streamlit OIDC 인증이 설정되어 있으면 st.login / st.experimental_user(or st.user) 사용
    2) 아니면 (fallback) 이메일 직접 입력으로 간이 로그인
    """
    # 0) 어떤 user 객체가 있나 확인
    u = getattr(st, "experimental_user", None) or getattr(st, "user", None)

    # 1) OIDC/SSO가 켜져 있는 환경이면 (is_logged_in 속성이 존재)
    if u is not None and hasattr(u, "is_logged_in") and hasattr(st, "login"):
        if not u.is_logged_in:
            st.markdown("## Sign in")
            st.caption("Lehigh Google 계정으로 로그인해주세요.")
            st.button("Log in with Lehigh Google", on_click=st.login)
            st.stop()

        email = (getattr(u, "email", "") or "").lower()
        if not email.endswith("@lehigh.edu"):
            st.error("Lehigh 계정(@lehigh.edu)으로만 접근 가능합니다.")
            if hasattr(st, "logout"):
                st.button("Log out", on_click=st.logout)
            st.stop()

        st.session_state["rater_email"] = email

    else:
        # 2) fallback: 이메일 직접 입력 (Streamlit Cloud에서 auth 설정 없을 때)
        st.markdown("## Sign in (Lehigh email)")
        st.caption("현재 배포 환경에서 Streamlit OIDC 로그인 기능이 비활성화되어 있어, 이메일 입력 방식으로 진행합니다.")
        email = st.text_input("Lehigh email", placeholder="yourid@lehigh.edu").strip().lower()
        if st.button("Continue", type="primary"):
            if not email.endswith("@lehigh.edu"):
                st.error("Lehigh 계정(@lehigh.edu) 이메일만 가능합니다.")
                st.stop()
            st.session_state["rater_email"] = email
            st.session_state["logged_in_at"] = datetime.now().isoformat(timespec="seconds")
            st.rerun()

        # 아직 입력/확정 전이면 stop
        if not st.session_state.get("rater_email"):
            st.stop()

    # 3) rater_id: 이메일 @ 앞부분을 기본값으로 + 사용자가 수정 가능
    email = st.session_state.get("rater_email", "")
    default_id = (email.split("@")[0] if "@" in email else "")
    st.session_state.setdefault("rater_id", default_id)

    with st.sidebar:
        st.markdown("### Rater")
        st.caption(f"Email: `{email}`")
        rid = st.text_input("Rater ID (editable)", value=st.session_state.get("rater_id", default_id))
        st.session_state["rater_id"] = rid.strip() if rid else default_id


def _ensure_rater_id():
    email = (st.session_state.get("rater_email") or "")
    default_id = email.split("@")[0] if "@" in email else ""
    st.session_state.setdefault("rater_id", default_id)


def main():
    st.set_page_config(page_title="Cultural Session Rater", page_icon="🧠", layout="wide")

    init_state()
    ensure_global_ui_state()

    require_lehigh_login()
    st.title("🧠 Cultural Counseling Session Rater")

    page = st.session_state.get("page", "Culture")

    if page == "Culture":
        culture_select.render()
        return

    elif page == "Rate":
        rate.render()
        return
    else:
        st.session_state["page"] = "Culture"
        st.rerun()
    
    # fallback
    st.session_state["page"] = "Culture"
    st.rerun()

if __name__ == "__main__":
    main()
