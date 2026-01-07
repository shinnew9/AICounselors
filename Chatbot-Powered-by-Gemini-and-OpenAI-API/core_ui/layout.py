import streamlit as st


def set_base_page_config():
    st.set_page_config(
        page_title="Dataset Assessment Simulation made by LLM",
        layout="wide",
    )


def inject_base_css():
    st.markdown(
        """
        <style>
        /* 전체 상단 여백 약간 줄여서 Home에서 스크롤 생기는 확률 낮춤 */
        .block-container { padding-top: 1.4rem; }

        /* Optional: hide Streamlit default menu/footer */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        /* Buttons */
        div.stButton > button {
            border-radius: 12px;
            padding: 0.55rem 0.85rem;
            font-weight: 700;
        }

        /* Headline spacing */
        .page-title {
            font-size: 44px;
            font-weight: 900;
            margin: 0.6rem 0 0.25rem 0;
        }
        .page-sub {
            opacity: 0.80;
            margin-bottom: 0.9rem;
        }

        /* Center card wrapper (for sign-in)
           기존 min-height:70vh + align-items:center 때문에 카드가 아래로 밀리며 스크롤이 생김
           -> 위쪽에서 바로 보이도록 변경
        */
        .center-wrap{
            display:flex;
            justify-content:center;
            align-items:flex-start;
            padding-top: 1.0rem;
            padding-bottom: 1.0rem;
        }

        .signin-card{
            width:min(560px, 92vw);
            background: rgba(18, 18, 18, 0.70);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px;
            padding: 24px 28px 18px 28px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.35);
            backdrop-filter: blur(10px);
        }
        .signin-title{
            font-size: 30px;
            font-weight: 900;
            margin-bottom: 6px;
        }
        .signin-sub{
            opacity: 0.80;
            margin-bottom: 14px;
            font-size: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_header():
    st.markdown(
        '<div class="page-title">Dataset Assessment Simulation made by LLM</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-sub">A culturally adaptive companion for your mental wellness journey.</div>',
        unsafe_allow_html=True,
    )


def render_top_right_signout(key: str = "signout_top"):
    """
    Top-right sign out button (shows only when signed in).
    Place this near the top of each page (Dataset/Assess/Results).
    """
    if not st.session_state.get("email"):
        return  # not signed in -> don't show

    # Right-aligned row
    _, col = st.columns([8, 1])
    with col:
        # Slightly compact button
        if st.button("Sign out", key=key, use_container_width=True):
            # lazy import to avoid circular imports
            from core_ui.auth import sign_out_to_home
            sign_out_to_home()