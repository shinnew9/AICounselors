# pages/chat.py
import re
import streamlit as st

from core_ui.data import (
    DATA_ROOT,
    list_data_files,
    load_sessions_any,
    # filter_sessions,
    # pick_random_session,
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

    st.session_state.setdefault("seq_idx_by_ds", {})   # {ds_file: next_index(int)}
    st.session_state.setdefault("current_session_no", None)  # 1-based display


    # # avoid repeating sessions    
    # st.session_state.setdefault("seen_session_ids", [])



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
    # 여기선 c, 밑에 함수에선 cursor
    c = int(st.session_state.get("cursor", 0))

    while c < len(turns) and turns[c].get("role") != "user":
        c += 1

    if c < len(turns):
        st.session_state["patient_msgs"].append(turns[c].get("text", ""))
        c += 1

    st.session_state["cursor"] = c


def _choose_dataset_file() -> str | None:
    files = list_data_files(DATA_ROOT) or []

    ds_file = st.session_state.get("ds_file")
    
    if ds_file and ds_file in files:
        return ds_file
    
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
    elif "chinese" in race:
        st.session_state["rewrite_target"] = "Chinese college student"
        want_hint = "chinese"
    else:
        st.session_state["rewrite_target"] = st.session_state.get("rewrite_target")
        want_hint = None

    # 힌트 기반 파일 선택
    if want_hint:
        for f in files:
            if want_hint in f.lower():
                return f
            
    ds_file = st.session_state.get("ds_file")
    if ds_file and ds_file in files:
        return ds_file

    return files[0]


def _load_random_session() -> bool:
    """
    Sequential loader:
    - ethnicity 선택에 맞는 ds_file을 고른 뒤
    - 그 파일 안에서 1,2,3... 순서대로 session을 로드
    - 현재 몇 번째인지 번호(current_session_no)도 기록
    """
    # 0) 파일 존재 확인
    files = list_data_files(DATA_ROOT)
    if not files:
        st.session_state["_load_err"] = f"No dataset files under {DATA_ROOT}"
        return False

    # 1) intake 기반 ds_file 선택
    ds_file = _choose_dataset_file()
    if not ds_file:
        st.session_state.setdefault("_load_err", "No dataset file chosen.")
        return False

    st.session_state["ds_file"] = ds_file
    st.session_state["session_ended"] = False

    # 2) 세션 로드
    max_rows = int(st.session_state.get("max_rows", 20000) or 20000)
    sessions = load_sessions_any(ds_file, max_rows=max_rows) or []

    if not sessions:
        st.session_state["_load_err"] = f"No sessions loaded. file={ds_file}"
        return False

    total = len(sessions)

    # 3) 파일별 next index 가져오기
    idx_map = st.session_state.get("seq_idx_by_ds") or {}
    idx = int(idx_map.get(ds_file, 0) or 0)

    # 끝까지 다 했으면 막기(또는 다시 0으로 리셋)
    if idx >= total:
        st.session_state["_load_err"] = f"All sessions completed for this dataset. ({total}/{total})"
        st.session_state["_load_warn"] = "No more sessions left. (Switch ethnicity/dataset or reset progress.)"
        return False

    # 4) 이번 session 선택 (순서대로)
    s = sessions[idx]

    # 5) QC/clean
    turns_raw = get_turns(s)
    turns_cleaned, qc = qc_clean_turns(
        turns_raw,
        remove_consecutive_dupes=bool(st.session_state.get("dedupe", True)),
    )

    # internal ids
    st.session_state["active_session_id"] = str(session_id(s, "session"))
    st.session_state["removed_dupes"] = int(qc.get("removed_dupes", 0))

    if bool(st.session_state.get("hide_system", False)):
        turns_display = [t for t in turns_cleaned if t.get("role") != "system"]
    else:
        turns_display = turns_cleaned

    # 6) per-session state reset
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

    # 7) numbering: 현재 몇 번째 세션인지(1-based)
    st.session_state["current_session_no"] = idx + 1
    st.session_state["current_session_total"] = total

    # 8) index advance (다음번엔 다음 세션)
    idx_map[ds_file] = idx + 1
    st.session_state["seq_idx_by_ds"] = idx_map

    # 9) play counter/log
    st.session_state["session_play_count"] = int(st.session_state.get("session_play_count", 0) or 0) + 1
    st.session_state.setdefault("session_play_log", [])
    st.session_state.setdefault("session_ended", False)
    st.session_state["session_play_log"].append(st.session_state.get("active_session_id"))
    st.session_state["session_play_log"] = st.session_state["session_play_log"][-10:]

    # 10) advance to first patient
    _advance_to_next_patient()

    if len(st.session_state.get("patient_msgs", [])) == 0:
        st.session_state["_load_err"] = "Loaded turns but could not display the first patient turn."
        return False

    return True


def _render_left_panel() -> None:
    st.markdown('<div class="sidepanel-card">', unsafe_allow_html=True)

    st.markdown("### Session")

    # NEW: sequential numbering display
    no = st.session_state.get("current_session_no")
    total = st.session_state.get("current_session_total")
    if no and total:
        st.markdown(f"**Session {int(no)} / {int(total)}**")

    prof = st.session_state.get("profile") or {}
    st.caption(f"Client profile: **{prof.get('race_ethnicity', 'Unknown')}**")

    rt = st.session_state.get("rewrite_target")
    if rt:
        st.caption(f"Dataset: **{rt}**")

    ds = st.session_state.get("ds_file")
    if ds:
        st.caption(f"DEBUG file: `{ds}`")

    lsid = st.session_state.get("active_session_id")
    if lsid:
        st.caption(f"DEBUG session_id: `{lsid}`")

    warn = st.session_state.get("_load_warn")
    if warn:
        st.warning(warn)

    st.divider()

    st.checkbox("Hide system turns", key="hide_system")
    st.checkbox("Remove consecutive duplicates", key="dedupe")
    st.checkbox("Compact system style", key="compact_system")

    if st.button("🎲 Load new session", use_container_width=True, key="btn_load_session"):
        ok = _load_random_session()
        st.session_state["_load_ok"] = bool(ok)
        st.rerun()

    if st.button("🔁 Reset dataset progress (start from Session 1)", use_container_width=True, key="btn_reset_progress"):
        ds = st.session_state.get("ds_file")
        if ds:
            m = st.session_state.get("seq_idx_by_ds") or {}
            m[ds] = 0
            st.session_state["seq_idx_by_ds"] = m
        st.session_state["current_session_no"] = None
        st.session_state["current_session_total"] = None
        reset_chat_state(keep_profile=True)
        st.rerun()

    # Instructor-only internal panel
    if bool(st.session_state.get("instructor_unlocked", False)):
        st.divider()
        with st.expander("Instructor tools", expanded=False):
            st.caption(f"Sessions played: {int(st.session_state.get('session_play_count', 0))}")
            st.caption("Recent internal session_ids (hidden from students):")
            st.write(st.session_state.get("session_play_log", []))
    
    if st.button("🧾 End session → Results", use_container_width=True, key="btn_end_session"):
        st.session_state["session_ended"] = True
        st.session_state["page"] = "Results"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _normalize_labs(labs: dict) -> dict:
    """
    Normalize LLM label output into DEFAULT_KEYS-compatible {key:0/1}.
    """
    if not isinstance(labs, dict):
        return {}

    alias = {
        # core
        "empathy": "empathy",
        "reflection": "reflection",
        "validation": "validation",
        "open_question": "open_question",
        "open questions": "open_question",
        "openquestions": "open_question",
        "openq": "open_question",

        "suggestion": "suggestion",
        "suggestions": "suggestion",
        "advice": "suggestion",

        # extensions
        "cultural_responsiveness": "cultural_responsiveness",
        "cultural responsiveness": "cultural_responsiveness",
        "culture": "cultural_responsiveness",

        "stereotype_risk": "stereotype_risk",
        "stereotype risk": "stereotype_risk",

        "goal_alignment": "goal_alignment",
        "goal alignment": "goal_alignment",

        "coherence": "coherence",

        "safety_response": "safety_response",
        "safety response": "safety_response",
    }

    out = {}
    for k, v in labs.items():
        kk = alias.get(str(k).strip().lower())
        if kk:
            out[kk] = int(bool(v))

    # IMPORTANT: make sure every DEFAULT_KEYS key exists (prevents missing keys)
    for kk in [
        "empathy","reflection","validation","open_question","suggestion",
        "cultural_responsiveness","stereotype_risk","goal_alignment","coherence","safety_response"
    ]:
        out.setdefault(kk, 0)

    return out


def _render_chat_area() -> None:
    st.subheader("Chat")

    # not loaded yet
    if not st.session_state.get("loaded_session"):
        err = st.session_state.get("_load_err")
        if err:
            st.error(err)
        st.info("Click **🎲 Load new session** on the left panel.")
        return

    # AUTO END GUARD (put right after "loaded_session" check)
    turns = st.session_state.get("turns_cleaned", []) or []
    cursor = int(st.session_state.get("cursor", 0) or 0)
    patient_msgs = st.session_state.get("patient_msgs", []) or []
    counselor_msgs = st.session_state.get("counselor_msgs", []) or []

    # end guard (REPLACE this whole block)
    if (
        turns
        and patient_msgs
        and cursor >= len(turns)
        and len(patient_msgs) == len(counselor_msgs)
    ):
        st.success("✅ End of scripted patient turns.")

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Go to Results", type="primary", key="btn_go_results"):
                st.session_state["page"] = "Results"
                st.rerun()

        with c2:
            if st.button("🎲 Start a new session", key="btn_new_session_after_end"):
                ok = _load_random_session()
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

    # NEW: give the LLM the most recent client turn as context
    client_prev = ""
    if st.session_state.get("patient_msgs"):
        client_prev = st.session_state["patient_msgs"][-1]

    raw = label_turn_with_llm(gcall, user_text, context={"client_prev": client_prev})
    st.session_state.setdefault("turn_labels_raw", []).append(raw)
    labs = _normalize_labs(raw)
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
