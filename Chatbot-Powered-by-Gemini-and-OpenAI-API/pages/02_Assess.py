import streamlit as st

from core_ui.layout import set_base_page_config, inject_base_css, render_top_right_signout
from core_ui.auth import require_signed_in
from core_ui.dataset import get_sessions_for_culture, DATASET_FILES
from core_ui.chat_view import render_chat

from core.logs_assess import (
    append_assessment_row,
    read_assess_rows,
    rated_session_ids,
    compute_progress,
    latest_rows_per_session,
    METRIC_FIELDS,
)

set_base_page_config()
inject_base_css()


def scroll_to_top():
    st.components.v1.html(
        """
        <script>
        function goTop() {
          const el = window.parent.document.getElementById("TOP");
          if (el) { el.scrollIntoView({behavior: "instant", block: "start"}); }
          else { window.parent.scrollTo(0, 0); }
        }
        goTop();
        setTimeout(goTop, 50);
        </script>
        """,
        height=0,
    )


def _get_sessions(culture: str):
    # 1) session_state cache 우선 사용
    cached = st.session_state.get("_sessions_cache")
    if cached and isinstance(cached, list) and len(cached) > 0:
        return cached

    # 2) 없으면 로드하고 cache 저장
    sessions = get_sessions_for_culture(culture)  # core_ui.dataset에서 불러오는 함수
    st.session_state["_sessions_cache"] = sessions
    return sessions


def _find_next_unrated_index(sessions, rated_ids_set):
    for i, s in enumerate(sessions):
        sid = str(s.get("session_id", "")).strip()
        if sid and sid not in rated_ids_set:
            return i
    return None


def _ensure_resume_pointer(sessions, rater_id: str, culture: str):
    rows = read_assess_rows()
    rated_ids_set = rated_session_ids(rows, rater_id=rater_id, culture=culture)

    # If session_idx not set or points to already-rated session, move to next unrated
    cur_idx = st.session_state.get("session_idx", None)
    if cur_idx is None:
        nxt = _find_next_unrated_index(sessions, rated_ids_set)
        st.session_state["session_idx"] = nxt if nxt is not None else 0
        return

    try:
        cur_idx = int(cur_idx)
    except Exception:
        cur_idx = 0

    cur_idx = max(0, min(cur_idx, len(sessions) - 1))
    cur_sid = str(sessions[cur_idx].get("session_id", "")).strip()
    if cur_sid and cur_sid in rated_ids_set:
        nxt = _find_next_unrated_index(sessions, rated_ids_set)
        st.session_state["session_idx"] = nxt if nxt is not None else cur_idx


def main():
    require_signed_in()
    render_top_right_signout(key="signout_assess")

    st.markdown('<div id="TOP"></div>', unsafe_allow_html=True)

    # consume scroll flag exactly once per render
    if st.session_state.pop("_scroll_top", False):
        scroll_to_top()

    culture = st.session_state.get("culture")
    if not culture:
        st.warning("Please select a dataset first.")
        st.switch_page("pages/01_Dataset.py")
        st.stop()

    rater_id = st.session_state.get("rater_id", "").strip()
    email = st.session_state.get("email", "").strip()
    ds_file = str(DATASET_FILES.get(culture) or "")

    sessions = _get_sessions(culture)
    total = len(sessions)

    # Resume logic (based on CSV)
    _ensure_resume_pointer(sessions, rater_id=rater_id, culture=culture)

    # Progress UI
    all_rows = read_assess_rows()
    done, total = compute_progress(total, all_rows, rater_id=rater_id, culture=culture)

    st.markdown("## Conversation Assess")
    st.caption(f"Dataset: {culture} • Progress: {done}/{total} completed")

    # Controls: Resume / Start Over
    ctrl = st.columns([1.2, 1.2, 3])
    with ctrl[0]:
        if st.button("Resume next unrated", use_container_width=True):
            rated_ids_set = rated_session_ids(all_rows, rater_id=rater_id, culture=culture)
            nxt = _find_next_unrated_index(sessions, rated_ids_set)
            if nxt is not None:
                st.session_state["_scroll_top"] = True
                st.session_state["session_idx"] = nxt
                st.rerun()
            else:
                st.toast("All sessions have been rated at least once.", icon="✅")
    with ctrl[1]:
        if st.button("Start from first", use_container_width=True):
            st.session_state["_scroll_top"] = True
            st.session_state["session_idx"] = 0
            st.rerun()

    # Current session
    idx = int(st.session_state.get("session_idx", 0) or 0)
    idx = max(0, min(idx, len(sessions) - 1))
    st.session_state["session_idx"] = idx
    session = sessions[idx]
    sid = str(session.get("session_id", "")).strip()

    st.markdown("---")
    st.subheader(f"Session {idx + 1} / {len(sessions)}")
    st.caption(f"Session ID: {sid}")

    # Chat (left/right bubbles)
    render_chat(session.get("turns", []), culture=culture)

    st.markdown("---")

    # If already rated, show info + last rating preview (latest row)
    filtered = [
        r for r in all_rows
        if r.get("rater_id", "").strip() == rater_id and r.get("culture", "").strip() == culture
    ]
    latest_map = latest_rows_per_session(filtered)
    already = sid in latest_map
    if already:
        st.info("This session has been rated before (history is preserved). You can rate again; a new row will be appended.")
        last = latest_map[sid]
        with st.expander("Show latest saved rating for this session"):
            st.write({k: last.get(k, "") for k in ["timestamp_utc", *METRIC_FIELDS, "comment"]})

    # Rating form
    st.markdown("### Rate this conversation (1–5)")
    st.caption("1 = Poor / 3 = Acceptable / 5 = Excellent")

    with st.form("rating_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            empathy = st.slider("Empathy / Warmth", 1, 5, 3)
            clarity = st.slider("Clarity / Helpfulness", 1, 5, 3)
            safety = st.slider("Safety / Non-judgment", 1, 5, 3)
        with c2:
            cultural_fit = st.slider("Cultural Appropriateness", 1, 5, 3)
            specificity = st.slider("Specificity (not stereotypical)", 1, 5, 3)
            meaning = st.slider("Maintains Original Meaning", 1, 5, 3)

        comment = st.text_area("Optional comment (what felt authentic / what felt off)", height=90)
        submit = st.form_submit_button("Save rating")

    if submit:
        row = {
            "timestamp_utc": "",
            "email": email,
            "rater_id": rater_id,
            "culture": culture,
            "dataset_file": ds_file,
            "session_id": sid,
            "session_idx": str(idx),
            "empathy_warmth": str(empathy),
            "clarity_helpfulness": str(clarity),
            "safety_nonjudgment": str(safety),
            "cultural_appropriateness": str(cultural_fit),
            "specificity_nostereotype": str(specificity),
            "meaning_preserve": str(meaning),
            "comment": comment.strip(),
        }
        append_assessment_row(row)

        # After saving, jump to next unrated session
        all_rows = read_assess_rows()
        rated_ids_set = rated_session_ids(all_rows, rater_id=rater_id, culture=culture)
        nxt = _find_next_unrated_index(sessions, rated_ids_set)

        # request scroll-to-top on next render
        st.session_state["_scroll_top"] = True

        if nxt is None:
            st.toast("Saved! All sessions rated at least once.", icon="✅")
            st.session_state["session_idx"] = idx
        else:
            st.toast("Saved! Moving to next unrated session…", icon="✅")
            st.session_state["session_idx"] = nxt

        st.rerun()

    # Navigation (manual)
    st.markdown("---")
    nav = st.columns([1, 1, 2, 2])
    with nav[0]:
        if st.button("← Previous", disabled=(idx <= 0), use_container_width=True):
            st.session_state["_scroll_top"] = True
            st.session_state["session_idx"] = idx - 1
            st.rerun()
    with nav[1]:
        if st.button("Next →", disabled=(idx >= len(sessions) - 1), use_container_width=True):
            st.session_state["_scroll_top"] = True
            st.session_state["session_idx"] = idx + 1
            st.rerun()
    with nav[2]:
        if st.button("Back to dataset select", use_container_width=True):
            st.switch_page("pages/01_Dataset.py")
    with nav[3]:
        if st.button("Go to results →", use_container_width=True):
            st.switch_page("pages/03_Results.py")



if __name__ == "__main__":
    main()
