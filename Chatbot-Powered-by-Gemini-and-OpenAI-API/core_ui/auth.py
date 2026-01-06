import streamlit as st

LEHIGH_DOMAIN = "@lehigh.edu"


def lehigh_email_valid(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    # 가장 안전한 규칙: @lehigh.edu 끝 + 공백 없음 + @ 포함
    return email.endswith(LEHIGH_DOMAIN) and ("@" in email) and (" " not in email)


def render_signin_gate() -> bool:
    """
    로그인 안 되어 있으면 중앙 카드 렌더링 후 False 반환.
    로그인 완료 상태면 True 반환.
    """
    if st.session_state.get("email"):
        return True

    st.markdown('<div class="center-wrap"><div class="signin-card">', unsafe_allow_html=True)
    st.markdown('<div class="signin-title">Welcome</div>', unsafe_allow_html=True)
    st.markdown('<div class="signin-sub">Sign in with your Lehigh email to continue.</div>', unsafe_allow_html=True)

    with st.form("signin_form", clear_on_submit=False):
        email = st.text_input("Lehigh email", placeholder=f"yourid{LEHIGH_DOMAIN}")
        submitted = st.form_submit_button("Continue")

        if submitted:
            if not lehigh_email_valid(email):
                msg = f"Please enter a valid Lehigh email ending with {LEHIGH_DOMAIN}"
                st.error(msg)
                st.sidebar.error(msg)
                st.markdown("</div></div>", unsafe_allow_html=True)
                return False

            email = email.strip().lower()
            st.session_state["email"] = email
            st.session_state["rater_id"] = st.session_state.get("rater_id") or email.split("@")[0]
            st.session_state["signed_in"] = True
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)
    return False


def require_signed_in():
    if not st.session_state.get("email"):
        st.error("You must sign in first. Please return to the home page.")
        st.stop()


def sign_out_to_home():
    for k in ["email", "rater_id", "signed_in", "culture", "ds_file", "session_idx", "current_session", "_sessions_cache"]:
        st.session_state.pop(k, None)
    st.switch_page("Home.py")
