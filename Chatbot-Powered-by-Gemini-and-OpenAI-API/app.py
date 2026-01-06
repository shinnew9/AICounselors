import streamlit as st

st.set_page_config(
    page_title="Dataset Assessment Simulation made by LLM",
    page_icon="✨",
    layout="wide",
)

# Global CSS (optional)
st.markdown(
    """
    <style>
    /* Reduce empty top padding a bit */
    .block-container { padding-top: 1.8rem; }

    /* Optional: hide default Streamlit menu/footer */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Center card wrapper */
    .center-wrap{
        min-height: 70vh;
        display:flex;
        align-items:center;
        justify-content:center;
    }
    .signin-card{
        width:min(560px, 92vw);
        background: rgba(18, 18, 18, 0.70);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 18px;
        padding: 28px 28px 18px 28px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.35);
        backdrop-filter: blur(10px);
    }
    .signin-title{
        font-size: 32px;
        font-weight: 900;
        margin-bottom: 6px;
    }
    .signin-sub{
        opacity: 0.80;
        margin-bottom: 18px;
        font-size: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

LEHIGH_DOMAIN = "@lehigh.edu"


def lehigh_email_valid(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    return email.endswith(LEHIGH_DOMAIN) and ("@" in email) and (" " not in email)


def render_signin_gate() -> bool:
    """
    Renders a centered sign-in card if not signed in.
    Returns True if signed in, else False (and stops downstream rendering).
    """
    if st.session_state.get("email"):
        return True

    # Centered card
    st.markdown('<div class="center-wrap"><div class="signin-card">', unsafe_allow_html=True)
    st.markdown('<div class="signin-title">Welcome</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="signin-sub">Sign in with your Lehigh email to continue.</div>',
        unsafe_allow_html=True,
    )

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


def sidebar_profile():
    """
    Simple sidebar profile panel after sign in.
    """
    st.sidebar.markdown("## Rater")
    email = st.session_state.get("email", "")
    st.sidebar.caption("Email")
    st.sidebar.write(email)

    st.sidebar.caption("Rater ID (editable)")
    rid = st.sidebar.text_input(" ", value=st.session_state.get("rater_id", ""), label_visibility="collapsed")
    st.session_state["rater_id"] = rid.strip() if rid else ""

    if st.sidebar.button("Sign out"):
        for k in ["email", "rater_id", "signed_in", "culture", "ds_file", "session_idx", "current_session"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


def sidebar_rater_panel():
    st.sidebar.markdown("## Rater")
    st.sidebar.caption("Email")
    st.sidebar.write(st.session_state.get("email",""))

    st.sidebar.caption("Rater ID (editable)")
    rid = st.sidebar.text_input(" ", value=st.session_state.get("rater_id",""), label_visibility="collapsed")
    st.session_state["rater_id"] = rid.strip()

    if st.sidebar.button("Sign out"):
        for k in ["email","rater_id","culture","ds_file","session_idx","current_session"]:
            st.session_state.pop(k, None)
        st.switch_page("app.py")


def main():
    # Gate: Sign-in first
    if not render_signin_gate():
        st.stop()

    sidebar_profile()

    # After sign-in, send them to the dataset selection page
    # Streamlit multipage apps will show pages on the left menu automatically.
    st.title("Dataset Assessment Simulation made by LLM")
    st.caption("A culturally adaptive companion for your mental wellness journey.")
    st.info("Use the left sidebar to navigate to **Cultural Counseling Session Rater** and start rating.")
    # 로그인 완료 후 (email이 세션에 들어온 직후)
    if st.session_state.get("email"):
        st.switch_page("../pages/culture_select.py")


if __name__ == "__main__":
    main()