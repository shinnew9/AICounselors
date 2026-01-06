import streamlit as st

from core_ui.layout import set_base_page_config, inject_base_css
from core_ui.auth import require_signed_in
from core_ui.dataset import get_sessions_for_culture, DATASET_FILES
from core.logs_assess import read_assess_rows, rated_session_ids, compute_progress

set_base_page_config()
inject_base_css()


def _find_next_unrated_index(sessions, rated_ids_set):
    for i, s in enumerate(sessions):
        sid = str(s.get("session_id", "")).strip()
        if sid and sid not in rated_ids_set:
            return i
    return None  # all rated


def _set_resume_pointer_and_go(culture: str):
    # lock the user's chosen culture
    st.session_state["selected_culture_lock"] = culture

    # load sessions once (cache to session_state to avoid reloads)
    sessions = get_sessions_for_culture(culture)
    st.session_state["_sessions_cache"] = sessions

    # compute next unrated by CSV
    rows = read_assess_rows()
    rater_id = (st.session_state.get("rater_id") or "").strip()
    rated_ids = rated_session_ids(rows, rater_id=rater_id, culture=culture)
    nxt = _find_next_unrated_index(sessions, rated_ids)

    if nxt is None:
        # All done at least once → send them to results or allow re-rate from 0
        st.session_state["session_idx"] = 0
        st.toast("All sessions already rated at least once. You can re-rate from the beginning.", icon="✅")
    else:
        st.session_state["session_idx"] = nxt

    st.switch_page("pages/02_Assess.py")


def _enter_assess(culture: str, start_mode: str):
    """
    start_mode: "resume" or "start"
    """
    # lock + required session state for Assess page
    st.session_state["selected_culture_lock"] = culture
    st.session_state["culture"] = culture

    # Load sessions NOW and cache (prevents assess page from bouncing back)
    sessions = get_sessions_for_culture(culture)
    st.session_state["_sessions_cache"] = sessions

    # Decide session_idx
    all_rows = read_assess_rows()
    rater_id = st.session_state.get("rater_id", "").strip()

    if start_mode == "start":
        st.session_state["session_idx"] = 0
    else:
        rated_ids_set = rated_session_ids(all_rows, rater_id=rater_id, culture=culture)
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

    # Show progress cards for each dataset
    rows = read_assess_rows()
    lock = st.session_state.get("selected_culture_lock")

    # Auto-restore lock after app restart (from CSV)
    if lock is None:
        from core.logs_assess import last_culture_for_rater
        inferred = last_culture_for_rater(rows, rater_id=rater_id)
        if inferred:
            st.session_state["selected_culture_lock"] = inferred
            lock = inferred

    # Lock UI
    if lock:
        st.info(f"Current dataset locked to: **{lock}** (based on your last activity).")

        # Allow change (for mistakes or exploration)
        if st.button("Change dataset (unlock)"):
            st.session_state.pop("selected_culture_lock", None)
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

            # Load session count (fast enough; if slow, we can cache per culture)
            sessions = get_sessions_for_culture(culture)
            total = len(sessions)

            done, _ = compute_progress(total, rows, rater_id=rater_id, culture=culture)
            frac = 0 if total == 0 else (done / total)

            st.progress(frac)
            st.caption(f"Progress: {done}/{total}")

            # Buttons
            lock = st.session_state.get("selected_culture_lock")
            is_locked_other = (lock is not None and culture != lock)
            
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Resume", key=f"resume_{culture}", use_container_width=True, disabled=is_locked_other):
                    _enter_assess(culture, start_mode="resume")
                    
                    try:
                        _set_resume_pointer_and_go(culture)
                    except Exception as e:
                        st.error("Resume failed while preparing sessions. See details below.")
                        st.exception(e)
                        st.stop()
                   
            with b2:
                if st.button("Start from 1", key=f"start_{culture}", use_container_width=True, disabled=is_locked_other):
                    _enter_assess(culture, start_mode="resume")
                    st.session_state["selected_culture_lock"] = culture
                    st.session_state["culture"] = culture
                    st.session_state["_sessions_cache"] = sessions
                    st.session_state["session_idx"] = 0
                    st.switch_page("pages/02_Assess.py")

    st.markdown("---")
    st.info("Tip: Use **Resume** to continue from the next unrated session automatically.")


if __name__ == "__main__":
    main()
