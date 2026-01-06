import re
import streamlit as st
from pathlib import Path

# 여기서는 st.session_state["ds_file"]에 파일명만 넣는 방식으로 처리.
DATA_DIR = Path("data/psydial4")

EMAIL_RE = re.compile(r"^[^@\s]+@lehigh\.edu$", re.I)

DATASET_MAP = {
    "Chinese": "student_only_100.jsonl",
    "Hispanic": "student_only_rewrite_hispanic_college_grad_100.jsonl",
    "African American": "student_only_rewrite_african_american_college_grad_100.jsonl",
    # "Others": (UI만) -> 실제 파일 연결은 나중에
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
          .muted { opacity: 0.70; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_rater():
    # ✅ 로그인 후에만 sidebar 표시
    if not st.session_state.get("logged_in"):
        return
    st.sidebar.markdown("### Rater")
    st.sidebar.caption(f"Email: `{st.session_state.get('rater_email','')}`")
    st.sidebar.text_input(
        "Rater ID (editable)",
        key="rater_id",
        value=st.session_state.get("rater_id", ""),
    )


def _login_screen():
    _center_css()
    st.markdown('<div class="center-wrap"><div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="title">Sign in (Lehigh email)</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub">Enter your Lehigh email. You can edit your Rater ID after signing in.</div>',
        unsafe_allow_html=True,
    )

    email = st.text_input("Lehigh email", placeholder="yourid@lehigh.edu", key="login_email")
    c1, c2 = st.columns([1, 3])
    with c1:
        clicked = st.button("Continue", type="primary", use_container_width=True)

    if clicked:
        email_norm = (email or "").strip().lower()
        if not EMAIL_RE.match(email_norm):
            st.error("❗ Please enter a valid Lehigh email ending with @lehigh.edu")
            st.stop()

        # rater_email / rater_id 세팅
        st.session_state["logged_in"] = True
        st.session_state["rater_email"] = email_norm
        st.session_state["rater_id"] = email_norm.split("@")[0]  # 기본: @ 앞부분
        st.session_state["page"] = "Culture"
        st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)


def _culture_screen():
    _sidebar_rater()

    st.markdown("## Cultural Counseling Session Rater")
    st.caption("Select which dataset you want to rate. Sessions will be shown sequentially, and your progress will be saved.")

    # Others 버튼 UI만 추가 (데이터 연결은 안 함)
    cols = st.columns(4)
    choices = ["Chinese", "Hispanic", "African American", "Others"]
    for i, name in enumerate(choices):
        with cols[i]:
            if name == "Others":
                st.button(name, use_container_width=True, disabled=True)
            else:
                if st.button(name, use_container_width=True, key=f"btn_{name}"):
                    st.session_state["culture"] = name
                    st.session_state["ds_file"] = str(DATA_DIR / DATASET_MAP[name])

                    # progress key: rater_id + culture 별로 "몇번째 session"인지 저장할 수 있게
                    st.session_state.setdefault("progress", {})
                    pkey = f"{st.session_state.get('rater_id','unknown')}::{name}"
                    st.session_state["progress"].setdefault(pkey, 1)  # 1부터 시작

                    st.session_state["page"] = "Rate"
                    st.rerun()

    st.divider()

    # Current Selection dict(st.json) 제거하고, 사람 읽기 쉬운 텍스트만
    cur = st.session_state.get("culture")
    if cur:
        st.markdown(f"**Current dataset:** {cur} <span class='pill'>selected</span>", unsafe_allow_html=True)
        st.caption(f"File: `{st.session_state.get('ds_file','')}`")
    else:
        st.caption("No dataset selected yet.")


def render():
    # 로그인 전에는 중앙 카드만 보이게
    if not st.session_state.get("logged_in"):
        _login_screen()
        return

    # 로그인 후에는 Sign in UI 없애고 바로 culture selection만 보이게
    _culture_screen()
