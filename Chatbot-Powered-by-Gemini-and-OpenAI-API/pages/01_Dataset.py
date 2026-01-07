import streamlit as st

from core_ui.layout import set_base_page_config, inject_base_css
from core_ui.auth import require_signed_in
from core_ui.dataset import get_sessions_for_culture, DATASET_FILES
from core.logs_assess import (
    read_assess_rows,
    rated_session_ids,
    compute_progress,
    last_culture_for_rater,
)

set_base_page_config()
inject_base_css()


def _find_next_unrated_index(sessions, rated_ids_set):
    for i, s in enumerate(sessions):
        sid = str(s.get("session_id", "")).strip()
        if sid and sid not in rated_ids_set:
            return i
    return None  # all rated


def _go_assess(culture: str, start_mode: str):
    """
    start_mode: "resume" or "start"
    - resume: next unrated session (based on assess_sessions.csv)
    - start : session 0
    """
    # lock + required session state for Assess page
    st.session_state["selected_culture_lock"] = culture
    st.session_state["culture"] = culture

    # Load sessions NOW and cache (prevents assess page from bouncing / reloading)
    sessions = get_sessions_for_culture(culture)
    st.session_state["_sessions_cache"] = sessions

    # Decide session_idx
    rows = read_assess_rows()
    rater_id = (st.session_state.get("rater_id") or "").strip()

    if start_mode == "start":
        st.session_state["session_idx"] = 0
    else:
        rated_ids_set = rated_session_ids(rows, rater_id=rater_id, culture=culture)
        nxt = _find_next_unrated_index(sessions, rated_ids_set)
        st.session_state["session_idx"] = int(nxt) if nxt is not None else 0

    st.toast("Opening Assess…", icon="🚀")
    st.switch_page("pages/02_Assess.py")
    st.stop()


def main():
    require_signed_in()

    st.markdown("## Dataset")
    st.caption("Select a dataset. You can resume from the next unrated session based on assess_sessions.csv.")

    rater_id = (st.session_state.get("rater_id") or "").strip()
    if not rater_id:
        st.warning("Please enter your Rater ID in the sidebar first.")
        st.stop()

    rows = read_assess_rows()

    # -----------------------------
    # Lock handling (Policy you wanted)
    # -----------------------------
    lock = st.session_state.get("selected_culture_lock")

    # ✅ 핵심 변경:
    # 예전엔 'CSV 기반으로 자동 lock 복원'을 매번 강하게 해버려서
    # "처음 들어왔는데도 특정 문화가 자동으로 잡히는 느낌"이 생김.
    #
    # 이제는:
    # - 자동 복원은 "세션 상태에 lock이 없을 때만" '소프트하게' 한 번만 세팅
    # - 그리고 사용자에게 unlock 버튼 제공
    if lock is None:
        inferred = last_culture_for_rater(rows, rater_id=rater_id)
        if inferred:
            st.session_state["selected_culture_lock"] = inferred
            lock = inferred

    if lock:
        st.info(f"Current dataset locked to: **{lock}** (based on your last activity).")
        if st.button("Change dataset (unlock)"):
            st.session_state.pop("selected_culture_lock", None)
            st.session_state.pop("culture", None)
            st.session_state.pop("_sessions_cache", None)
            st.session_state.pop("session_idx", None)
            st.toast("Unlocked. You can choose another dataset now.", icon="🔓")
            st.rerun()

    cultures = ["Chinese", "Hispanic", "African American", "Others"]
    cols = st.columns(4)

    for i, culture in enumerate(cultures):
        with cols[i]:
            st.markdown(f"### {culture}")

            if culture == "Others" or DATASET_FILES.get(culture) is None:
                st.button("Not configured", disabled=True, use_container_width=True)
                continue

            sessions = get_sessions_for_culture(culture)
            total = len(sessions)

            done, _ = compute_progress(total, rows, rater_id=rater_id, culture=culture)
            frac = 0 if total == 0 else (done / total)

            st.progress(frac)
            st.caption(f"Progress: {done}/{total}")

            # If locked to another culture, disable
            current_lock = st.session_state.get("selected_culture_lock")
            disabled = (current_lock is not None and culture != current_lock)

            b1, b2 = st.columns(2)
            with b1:
                if st.button("Resume", key=f"resume_{culture}", use_container_width=True, disabled=disabled):
                    _go_assess(culture, start_mode="resume")

            with b2:
                if st.button("Start from 1", key=f"start_{culture}", use_container_width=True, disabled=disabled):
                    _go_assess(culture, start_mode="start")

    st.markdown("---")
    st.info("Tip: Use **Resume** to continue from the next unrated session automatically.")


if __name__ == "__main__":
    main()
