# pages/chat.py
import re
import streamlit as st

from core_ui.data import (
    DATA_ROOT,
    list_data_files,
    load_sessions_any,
    filter_sessions,
    pick_random_session,
    get_turns,
    qc_clean_turns,
    session_id,
)
from core_ui.state import reset_chat_state
from core_ui.ui import render_turn

from core.llm import gcall
from core.metrics import label_turn_with_llm, compute_session_skill_rates


RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)


def _ensure_chat_state_defaults() -> None:
    # UI flags
    st.session_state.setdefault("panel_open", True)
    st.session_state.setdefault("hide_system", False)
    st.session_state.setdefault("dedupe", True)
    st.session_state.setdefault("compact_system", True)

    # dataset controls
    st.session_state.setdefault("max_rows", 20000)
    st.session_state.setdefault("ds_file", None)
    st.session_state.setdefault("rewrite_target", st.session_state.get("rewrite_target"))

    # chat runtime
    st.session_state.setdefault("loaded_session", None)
    st.session_state.setdefault("turns_cleaned", [])
    st.session_state.setdefault("qc", {})
    st.session_state.setdefault("cursor", 0)
    st.session_state.setdefault("patient_msgs", [])
    st.session_state.setdefault("counselor_msgs", [])
    st.session_state.setdefault("turn_labels", [])
    st.session_state.setdefault("metrics_summary", {})
    st.session_state.setdefault("overall_feedback", None)

    # internal metrics/log
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("removed_dupes", 0)
    st.session_state.setdefault("session_play_count", 0)
    st.session_state.setdefault("session_play_log", [])


def _apply_chat_css(panel_open: bool) -> None:
    # bubble CSS는 core_ui/ui.py에서 로드되지만, 레이아웃/패널만 여기서 조정
    st.markdown(
        """
        <style>
          .sidepanel-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 16px 14px;
          }

          /* panel 닫으면 main을 조금 더 넓게 체감 */
          section.main > div { padding-left: 2rem; padding-right: 2rem; }

          /* chat area가 너무 좁아지지 않게 */
          .block-container { padding-top: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # panel 닫힌 경우 말풍선 최대폭 늘리는 느낌
    if not panel_open:
        st.markdown(
            """
            <style>
              .bubble { max-width: 86% !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def _update_metrics_summary() -> None:
    rates = compute_session_skill_rates(st.session_state.get("turn_labels", [])) or {}
    st.session_state["metrics_summary"] = {
        "Empathy": float(rates.get("empathy_rate", 0.0)),
        "Reflection": float(rates.get("reflection_rate", 0.0)),
        "Open Questions": float(rates.get("open_question_rate", 0.0)),
        "Validation": float(rates.get("validation_rate", 0.0)),
        "Suggestions": float(rates.get("suggestion_rate", 0.0)),
    }


def _advance_to_next_patient() -> None:
    turns = st.session_state.get("turns_cleaned", []) or []
    c = int(st.session_state.get("cursor", 0))

    while c < len(turns) and turns[c].get("role") != "user":
        c += 1

    if c < len(turns):
        st.session_state["patient_msgs"].append(turns[c].get("text", ""))
        c += 1

    st.session_state["cursor"] = c


def _choose_dataset_file() -> str | None:
    files = list_data_files(DATA_ROOT)
    if not files:
        st.session_state["_load_err"] = f"No dataset files under {DATA_ROOT}"
        return None

    prof = st.session_state.get("profile") or {}
    race = (prof.get("race_ethnicity") or "").lower()

    want_hint = None
    if "african" in race:
        st.session_state["rewrite_target"] = "African American student"
        want_hint = "african"
    elif "hispanic" in race:
        st.session_state["rewrite_target"] = "Hispanic college student"
        want_hint = "hispanic"
    else:
        st.session_state["rewrite_target"] = st.session_state.get("rewrite_target")
        want_hint = None

    # 힌트 기반 파일 선택
    if want_hint:
        for f in files:
            if want_hint in f.lower():
                return f

    return files[0]


def _load_random_session() -> bool:
    ds_file = _choose_dataset_file()
    if not ds_file:
        return False

    st.session_state["ds_file"] = ds_file

    sessions = load_sessions_any(ds_file, max_rows=int(st.session_state.get("max_rows", 20000)))
    sessions = filter_sessions(sessions, st.session_state.get("rewrite_target"))

    if not sessions:
        st.session_state["_load_err"] = (
            "No sessions found after filtering.\n"
            f"file={ds_file}\n"
            f"rewrite_target={st.session_state.get('rewrite_target')}\n"
            f"max_rows={int(st.session_state.get('max_rows', 20000))}"
        )
        return False

    s = pick_random_session(sessions)
    turns_raw = get_turns(s)
    turns_cleaned, qc = qc_clean_turns(
        turns_raw,
        remove_consecutive_dupes=bool(st.session_state.get("dedupe", True)),
    )

    # internal ids (student에게 숨김)
    st.session_state["active_session_id"] = str(session_id(s, "session"))
    st.session_state["removed_dupes"] = int(qc.get("removed_dupes", 0))

    if bool(st.session_state.get("hide_system", False)):
        turns_display = [t for t in turns_cleaned if t.get("role") != "system"]
    else:
        turns_display = turns_cleaned

    # reset per-session state
    st.session_state["loaded_session"] = s
    st.session_state["turns_cleaned"] = turns_display
    st.session_state["qc"] = qc
    st.session_state["cursor"] = 0
    st.session_state["patient_msgs"] = []
    st.session_state["counselor_msgs"] = []
    st.session_state["turn_labels"] = []
    st.session_state["metrics_summary"] = {}
    st.session_state["overall_feedback"] = None
    st.session_state.pop("_load_err", None)

    # play counter/log (internal)
    st.session_state["session_play_count"] = int(st.session_state.get("session_play_count", 0)) + 1
    st.session_state.setdefault("session_play_log", [])
    st.session_state["session_play_log"].append(st.session_state.get("active_session_id"))
    st.session_state["session_play_log"] = st.session_state["session_play_log"][-10:]

    # advance to first patient
    _advance_to_next_patient()

    if len(st.session_state.get("patient_msgs", [])) == 0:
        st.session_state["_load_err"] = "Loaded turns but could not display the first patient turn."
        return False

    return True


def _render_left_panel() -> None:
    st.markdown('<div class="sidepanel-card">', unsafe_allow_html=True)

    st.markdown("### Session")

    prof = st.session_state.get("profile") or {}
    st.caption(f"Client profile: **{prof.get('race_ethnicity', 'Unknown')}**")

    rt = st.session_state.get("rewrite_target")
    if rt:
        st.caption(f"Dataset: **{rt}**")

    st.divider()

    st.checkbox("Hide system turns", key="hide_system")
    st.checkbox("Remove consecutive duplicates", key="dedupe")
    st.checkbox("Compact system style", key="compact_system")

    if st.button("🎲 Load new session", use_container_width=True, key="btn_load_session"):
        ok = _load_random_session()
        st.session_state["_load_ok"] = bool(ok)
        st.rerun()

    if st.button("Reset chat (keep profile)", use_container_width=True, key="btn_reset_chat"):
        reset_chat_state(keep_profile=True)
        st.rerun()

    # Instructor-only internal panel
    if bool(st.session_state.get("instructor_unlocked", False)):
        st.divider()
        with st.expander("Instructor tools", expanded=False):
            st.caption(f"Sessions played: {int(st.session_state.get('session_play_count', 0))}")
            st.caption("Recent internal session_ids (hidden from students):")
            st.write(st.session_state.get("session_play_log", []))

    st.markdown("</div>", unsafe_allow_html=True)


def _render_chat_area() -> None:
    st.subheader("Chat")

    # not loaded yet
    if not st.session_state.get("loaded_session"):
        err = st.session_state.get("_load_err")
        if err:
            st.error(err)
        st.info("Click **🎲 Load new session** on the left panel.")
        return

    turns = st.session_state.get("turns_cleaned", []) or []
    patient_msgs = st.session_state.get("patient_msgs", []) or []
    counselor_msgs = st.session_state.get("counselor_msgs", []) or []

    # end guard
    if (
        turns
        and patient_msgs
        and int(st.session_state.get("cursor", 0)) >= len(turns)
        and len(patient_msgs) == len(counselor_msgs)
    ):
        st.success("End of scripted patient turns. Go to Results.")
        if st.button("Go to Results", type="primary", key="btn_go_results"):
            st.session_state["page"] = "Results"
            st.rerun()
        return

    # render bubbles
    for i, pmsg in enumerate(patient_msgs):
        render_turn("patient", pmsg)
        if i < len(counselor_msgs):
            render_turn("counselor", counselor_msgs[i])

    # input
    user_text = st.chat_input("Type your counselor reply (1–3 sentences)...")
    if not user_text:
        return

    user_text = user_text.strip()
    if not user_text:
        return

    if RISK_PAT.search(user_text):
        st.warning("⚠️ Crisis-related language detected. In real settings, US: 988.")

    st.session_state["counselor_msgs"].append(user_text)

    labs = label_turn_with_llm(gcall, user_text)
    st.session_state.setdefault("turn_labels", []).append(labs)

    _update_metrics_summary()
    _advance_to_next_patient()

    st.rerun()


def render() -> None:
    _ensure_chat_state_defaults()
    _apply_chat_css(bool(st.session_state.get("panel_open", True)))

    # top bar: toggle panel
    top_l, top_r = st.columns([0.06, 0.94])
    with top_l:
        if st.button("☰", help="Show/hide panel", key="toggle_panel_chat"):
            st.session_state["panel_open"] = not bool(st.session_state.get("panel_open", True))
            st.rerun()
    with top_r:
        st.title("Chat")

    if bool(st.session_state.get("panel_open", True)):
        panel, chatcol = st.columns([0.30, 0.70], gap="large")
        with panel:
            _render_left_panel()
        with chatcol:
            _render_chat_area()
    else:
        _render_chat_area()
