import streamlit as st

PIN = "1234"


def _apply_access_css():
    st.markdown(
        """
        <style>
        /* page vertical position: move content up a bit */
        .access-wrap { margin-top: -40px; }

        /* big clickable card */
        .access-card {
            position: relative;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 22px 18px;
            text-align: center;
            width: 100%;
        }
        .access-title {
            font-weight: 650;
            font-size: 16px;
            margin-bottom: 6px;
        }
        .access-desc {
            opacity: 0.75;
            font-size: 13px;
        }

        /* overlay streamlit button to capture click */
        div[data-testid="stButton"] > button.access-overlay {
            position: absolute !important;
            inset: 0 !important;
            width: 100% !important;
            height: 100% !important;
            opacity: 0 !important;
            border: 0 !important;
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render():
    _apply_access_css()

    st.markdown('<div class="access-wrap">', unsafe_allow_html=True)
    st.title("Access")
    st.caption("Choose how you want to use this app.")
    st.write("")

    # centered + stacked
    col = st.columns([0.18, 0.64, 0.18])[1]

    with col:
        # Student card
        c1 = st.container()
        with c1:
            st.markdown(
                """
                <div class="access-card">
                    <div class="access-title">Student</div>
                    <div class="access-desc">Create a client profile and practice counseling.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("\u200b", key="btn_student_card", help="Student", type="secondary"):
                st.session_state["user_role"] = "Student"
                st.session_state["page"] = "Intake"
                st.rerun()
            # make the button overlay this card
            st.markdown(
                """
                <script>
                const b = window.parent.document.querySelector('button[kind="secondary"][data-testid="baseButton-secondary"]:last-child');
                if (b) b.classList.add("access-overlay");
                </script>
                """,
                unsafe_allow_html=True,
            )

        st.write("")

        # --- Instructor card ---
        c2 = st.container()
        with c2:
            st.markdown(
                """
                <div class="access-card">
                    <div class="access-title">Instructor</div>
                    <div class="access-desc">Unlock instructor tools and downloads (PIN required).</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("\u200b", key="btn_instructor_card", help="Instructor", type="secondary"):
                st.session_state["user_role"] = "Instructor"
                st.session_state["page"] = "Intake"   # 또는 Instructor gate page가 있으면 거기로
                st.rerun()
            st.markdown(
                """
                <script>
                const buttons = window.parent.document.querySelectorAll('button[kind="secondary"][data-testid="baseButton-secondary"]');
                if (buttons.length) buttons[buttons.length-1].classList.add("access-overlay");
                </script>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)
