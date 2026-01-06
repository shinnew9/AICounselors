import streamlit as st
from core_ui.dataset import load_sessions_any, get_turns  # 너 프로젝트에 이미 있는 유틸 사용


def _bubble_css():
    st.markdown(
        """
        <style>
          .bubble-row { display: flex; width: 100%; margin: 6px 0; }
          .bubble-left { justify-content: flex-start; }
          .bubble-right { justify-content: flex-end; }

          .bubble {
            max-width: 72%;
            padding: 10px 12px;
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.06);
            line-height: 1.35;
            white-space: pre-wrap;
          }
          .patient { border-top-left-radius: 6px; }
          .counselor { border-top-right-radius: 6px; background: rgba(0, 122, 255, 0.10); }
          .meta { opacity: 0.70; font-size: 0.9rem; margin-bottom: 6px; }
          .card {
            border-radius: 18px;
            padding: 16px 14px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.10);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_bubble(role: str, text: str):
    role = (role or "").lower()
    if role in ("user", "patient", "seeker"):
        align = "bubble-left"
        klass = "patient"
    else:
        align = "bubble-right"
        klass = "counselor"

    st.markdown(
        f"<div class='bubble-row {align}'><div class='bubble {klass}'>{st.escape(text)}</div></div>",
        unsafe_allow_html=True,
    )


def _get_progress_key():
    rid = st.session_state.get("rater_id", "unknown")
    culture = st.session_state.get("culture", "unknown")
    return f"{rid}::{culture}"


def render():
    _bubble_css()

    # guard: culture_select에서 ds_file 세팅되어 있어야 함
    ds_file = st.session_state.get("ds_file")
    culture = st.session_state.get("culture")
    if not ds_file or not culture:
        st.error("No dataset selected. Go back and choose a dataset.")
        if st.button("Back to dataset selection"):
            st.session_state["page"] = "Culture"
            st.rerun()
        return

    # progress: "몇 번째 session"인지 (1-index)
    st.session_state.setdefault("progress", {})
    pkey = _get_progress_key()
    cur_idx = int(st.session_state["progress"].get(pkey, 1))

    # 세션 로드
    sessions = load_sessions_any(ds_file, max_rows=20000) or []
    if not sessions:
        st.error(f"No sessions loaded from: {ds_file}")
        return

    total = len(sessions)
    cur_idx = max(1, min(cur_idx, total))
    sess = sessions[cur_idx - 1]  # 0-index

    # 상단 정보 (signin UI는 여기서 절대 안 보여줌)
    st.markdown("## Rate sessions")
    st.caption(f"Rater: `{st.session_state.get('rater_id','')}`  |  Dataset: **{culture}**")
    st.markdown(f"**Session:** {cur_idx} / {total}")

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Transcript")
    turns = get_turns(sess) or []
    for t in turns:
        _render_bubble(t.get("role"), t.get("text") or "")
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # (3번은 나중) 일단 UI 자리만: A/B perspective 3개씩
    st.markdown("### Ratings (draft)")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**A) Patient perspective**")
        st.slider("Feels like a typical student from this culture", 1, 5, 3, key=f"a1_{pkey}_{cur_idx}")
        st.slider("Language & concerns feel authentic", 1, 5, 3, key=f"a2_{pkey}_{cur_idx}")
        st.slider("Overall relatability", 1, 5, 3, key=f"a3_{pkey}_{cur_idx}")
    with c2:
        st.markdown("**B) Counselor perspective**")
        st.slider("Response is culturally appropriate", 1, 5, 3, key=f"b1_{pkey}_{cur_idx}")
        st.slider("Shows empathy/understanding", 1, 5, 3, key=f"b2_{pkey}_{cur_idx}")
        st.slider("Provides helpful direction", 1, 5, 3, key=f"b3_{pkey}_{cur_idx}")

    st.text_area("Optional comments", key=f"comment_{pkey}_{cur_idx}")

    # 저장/이동 버튼 (저장은 다음 단계에서 파일/DB로 붙이면 됨)
    b1, b2, b3 = st.columns([1, 1, 2])
    with b1:
        if st.button("← Prev", use_container_width=True, disabled=(cur_idx <= 1)):
            st.session_state["progress"][pkey] = cur_idx - 1
            st.rerun()
    with b2:
        if st.button("Next →", type="primary", use_container_width=True, disabled=(cur_idx >= total)):
            st.session_state["progress"][pkey] = cur_idx + 1
            st.rerun()
    with b3:
        if st.button("Back to dataset selection", use_container_width=True):
            st.session_state["page"] = "Culture"
            st.rerun()
