import streamlit as st

LEHIGH_DOMAIN = "@lehigh.edu"


def lehigh_email_valid(email: str) -> bool:
    """Only require @lehigh.edu (no strict id format)."""
    if not email:
        return False
    email = email.strip().lower()
    return email.endswith(LEHIGH_DOMAIN) and len(email) > len(LEHIGH_DOMAIN)


def render_signin_gate() -> bool:
    # already signed in
    if st.session_state.get("email") and st.session_state.get("signed_in"):
        return True

    # Centered layout (no raw HTML)
    left, mid, right = st.columns([1.2, 2.2, 1.2])
    with mid:
        st.write("")
        st.write("")
        st.write("")

        st.markdown("## Welcome")
        st.caption("Sign in with your Lehigh email to continue.")

        with st.form("signin_form", clear_on_submit=False):
            email = st.text_input(
                "Lehigh email",
                placeholder="yourid@lehigh.edu",
                key="lehigh_email",
            ).strip()

            submitted = st.form_submit_button("Continue")

        if submitted:
            email_norm = email.strip().lower()

            if not lehigh_email_valid(email_norm):
                st.error("Please use your Lehigh email (ending with @lehigh.edu).")
                return False

            # Store normalized email + rater_id = part before @
            st.session_state["email"] = email_norm
            st.session_state["rater_id"] = email_norm.split("@")[0]
            st.session_state["signed_in"] = True

            st.rerun()

    return False


def require_signed_in():
    if not st.session_state.get("email") or not st.session_state.get("signed_in"):
        st.error("You must sign in first. Please return to the home page.")
        st.stop()


def sign_out_to_home():
    # Clear everything auth/session-related
    for k in [
        "email",
        "rater_id",
        "signed_in",
        "culture",
        "ds_file",
        "session_idx",
        "current_session",
        "_sessions_cache",
        "selected_culture_lock",
    ]:
        st.session_state.pop(k, None)

    st.switch_page("Home.py")
