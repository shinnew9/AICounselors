import re
import streamlit as st

LEHIGH_DOMAIN = "@lehigh.edu"
LEHIGH_ID_PATTERN = re.compile(r"^[a-z]{3}\d{3}@lehigh\.edu$")


def lehigh_email_valid(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    return bool(LEHIGH_ID_PATTERN.match(email))


def render_signin_gate() -> bool:
    if st.session_state.get("email"):
        return True

    # 가운데 정렬 + 폭 제한 (HTML div 쓰지 말고 columns로!)
    left, mid, right = st.columns([1.2, 2.2, 1.2])
    with mid:
        # Two spacers 
        st.write("")
        st.write("")
        st.write("")
        
        st.markdown("## Welcome")
        st.caption("Sign in with your Lehigh email to continue.")

        with st.form("signin_form", clear_on_submit=False):
            email_raw = st.text_input(
                "Lehigh email",
                placeholder="abc123@lehigh.edu",
                help="Format must be exactly: 3 lowercase letters + 3 digits + @lehigh.edu (e.g., abc123@lehigh.edu)",
            )

            submitted = st.form_submit_button("Continue")

            if submitted:
                email = (email_raw or "").strip()

                # 대문자 입력도 실패시키고 싶으면 이 줄 유지 (원치 않으면 삭제)
                if email != email.lower():
                    st.error("Use lowercase only (e.g., abc123@lehigh.edu).")
                    return False

                if not lehigh_email_valid(email):
                    st.error("Invalid email. Use exactly: abc123@lehigh.edu (3 lowercase letters + 3 digits).")
                    return False

                st.session_state["email"] = email
                st.session_state["rater_id"] = st.session_state.get("rater_id") or email.split("@")[0]
                st.session_state["signed_in"] = True
                st.rerun()

    return False


def require_signed_in():
    if not st.session_state.get("email"):
        st.error("You must sign in first. Please return to the home page.")
        st.stop()


def sign_out_to_home():
    for k in ["email", "rater_id", "signed_in", "culture", "ds_file", "session_idx", "current_session", "_sessions_cache"]:
        st.session_state.pop(k, None)
    st.switch_page("Home.py")
