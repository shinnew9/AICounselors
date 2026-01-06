# pages/culture_select.py
import re
import streamlit as st
from pathlib import Path

# data 위치: <repo_root>/data/psydial4
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "psydial4"

EMAIL_RE = re.compile(r"^[^@\s]+@lehigh\.edu$", re.I)

DATASET_MAP = {
    "Chinese": "student_only_100.jsonl",
    "Hispanic": "student_only_rewrite_hispanic_college_grad_100.jsonl",
    "African American": "student_only_rewrite_african_american_college_grad_100.jsonl",
    # "Others": UI만 (나중에 파일 연결)
}


def _center_css():
    st.markdown(
        """
        <style>
          .center-wrap {
            min-height: 72vh;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .card {
            width: 100%;
            max-width: 720px;
            padding: 28px 26px;
            border-radius: 20px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.10);
          }
          .title {
            font-size: 2.0rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
          }
          .sub {
            opacity: 0.75;
            margin-bottom: 1.2rem;
          }
          .btnrow > div { padding-top: 0.25rem; }
          .pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.85rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.10);
            margin-left: 8px;
            opacity: 0.9;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_rater():
    # bugfix: signed_in -> logged_in
    if not st.session_state.get("logged_in"):
        return

    email = st.session_state.get("rater_email", "")
    st.sidebar.markdown("### Rater")
    st.sidebar.caption(f"Email: `{email}`")

    default_id = email.split("@")[0] if "@" in email else ""
    st.session_state.setdefault("rater_id", default_id)

    rid = st.sidebar.text_input(
        "Rater ID (editable)",
        value=st.session_state.get("rater_id", default_id),
        key="sidebar_rater_id",
    )
    st.session_state["rater_id"] = (rid or default_id).strip()


def _login_screen():
    _center_css()

    st.markdown('<div class="center-wrap"><div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="title">Sign in (Lehigh email)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub">Enter your Lehigh email. You can edit your Rater ID after signing in.</div>',
        unsafe_allow_html=True,
    )

    email = st.text_input("Lehigh email", placeholder="yourid@lehigh.edu", key="login_email").strip().lower()

    # @lehigh.edu 없으면 패널(화면)에 경고
    if email and not email.endswith("@lehigh.edu"):
        st.warning("Email must end with **@lehigh.edu**.")

    clicked = st.button("Continue", type="primary", use_container_width=False)

    if clicked:
        if not EMAIL_RE.match(email or ""):
            st.error("❗ Please enter a valid Lehigh email ending with @lehigh.edu")
            st.stop()

        st.session_state["logged_in"] = True
        st.session_state["rater_email"] = email
        st.session_state["rater_id"] = email.split("@")[0]
        st.session_state["page"] = "Culture"
        st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)


def _culture_screen():
    _sidebar_rater()

    st.markdown("## Cultural Counseling Session Rater")
    st.caption(
        "Select which dataset you want to rate. Sessions will be shown sequentially, and your progress will be saved."
    )

    cols = st.columns(4)
    choices = ["Chinese", "Hispanic", "African American", "Others"]

    for i, name in enumerate(choices):
        with cols[i]:
            if name == "Others":
                st.button(name, use_container_width=True, disabled=True)
                continue

            if st.button(name, use_container_width=True, key=f"btn_{name}"):
                st.session_state["culture"] = name

                # path safe join
                ds_path = DATA_DIR / DATASET_MAP[name]
                st.session_state["ds_file"] = str(ds_path)

                # progress: rater_id + culture 별 session index 저장
                rid = st.session_state.get("rater_id", "unknown")
                st.session_state.setdefault("progress", {})
                pkey = f"{rid}::{name}"
                st.session_state["progress"].setdefault(pkey, 1)  # 1부터 시작

                st.session_state["page"] = "Rate"
                st.rerun()

    st.divider()

    # Current Selection dict(st.json) 제거 → 텍스트만
    cur = st.session_state.get("culture")
    if cur:
        st.markdown(f"**Current dataset:** {cur} <span class='pill'>selected</span>", unsafe_allow_html=True)
        st.caption(f"File: `{st.session_state.get('ds_file','')}`")
    else:
        st.caption("No dataset selected yet.")


def render():
    # # 로그인 전: 중앙 카드만
    # if not st.session_state.get("logged_in"):
    #     _login_screen()
    #     return

    # 로그인 후: sign-in UI 없음, culture selection만
    _culture_screen()
