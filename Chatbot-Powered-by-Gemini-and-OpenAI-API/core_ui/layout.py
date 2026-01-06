import streamlit as st


def set_base_page_config():
    # 각 페이지에서 한 번만 호출되도록 설계했지만, Streamlit 특성상 페이지마다 호출해도 크게 문제는 없음.
    st.set_page_config(
        page_title="Dataset Assessment Simulation made by LLM",
        layout="wide",
    )


def inject_base_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.6rem; }

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
            margin: 0.2rem 0 0.25rem 0;
        }
        .page-sub {
            opacity: 0.80;
            margin-bottom: 1.2rem;
        }

        /* Center card wrapper (for sign-in) */
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

def render_app_header():
    st.markdown('<div class="page-title">Dataset Assessment Simulation made by LLM</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">A culturally adaptive companion for your mental wellness journey.</div>', unsafe_allow_html=True)
