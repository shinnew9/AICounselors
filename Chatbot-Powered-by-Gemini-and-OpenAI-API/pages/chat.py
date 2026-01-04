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
    # 여기선 c, 밑에 함수에선 cursor
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
    """
    Load one random session from the intake-matched dataset file.
    - student_only 데이터만 쓰는 전제라 _is_studentish_session 제거
    - rewrite_target 필터가 0개를 만들면 자동 fallback (필터 없이 진행)
    - concerns bias는 "히트가 있으면" 그 subset으로만 랜덤 추출
    """
    # 0) 기본값: 어떤 분기에서도 sessions가 미할당 되지 않게
    sessions: list[dict] = []

    # 1) 데이터 파일 존재 확인
    files = list_data_files(DATA_ROOT)
    if not files:
        st.session_state["_load_err"] = f"No dataset files under {DATA_ROOT}"
        return False

    # 2) intake 기반 dataset 선택 (네가 이미 만들어둔 함수)
    ds_file = _choose_dataset_file()
    if not ds_file:
        # _choose_dataset_file() 내부에서 _load_err 세팅하는 스타일이면 그대로 두면 됨
        st.session_state.setdefault("_load_err", "No dataset file chosen.")
        return False

    st.session_state["ds_file"] = ds_file
    st.session_state["session_ended"] = False

    # 3) 세션 로드
    max_rows = int(st.session_state.get("max_rows", 20000) or 20000)
    sessions = load_sessions_any(ds_file, max_rows=max_rows) or []

    if not sessions:
        st.session_state["_load_err"] = f"No sessions loaded. file={ds_file}"
        return False

    # 4) rewrite_target 필터 (0개면 자동 fallback)
    rt = st.session_state.get("rewrite_target")
    if rt:
        filtered = filter_sessions(sessions, rt) or []
        if filtered:
            sessions = filtered
        else:
            # 필터 문구 mismatch여도 앱이 멈추지 않게
            st.session_state["_load_warn"] = (
                "rewrite_target filter matched 0 sessions; falling back to unfiltered sessions.\n"
                f"rewrite_target={rt}"
            )

    # 5) Intake concerns bias (히트가 있으면 그 subset)
    prof = st.session_state.get("profile") or {}
    concerns = prof.get("concerns") or prof.get("concern_tags") or []
    concerns = [str(c).strip().lower() for c in concerns if str(c).strip()]

    if concerns:
        def _score(sess: dict) -> int:
            turns = get_turns(sess) or []
            blob = " ".join([(t.get("text") or "") for t in turns]).lower()
            return sum(1 for c in concerns if c in blob)

        scored = [(s, _score(s)) for s in sessions]
        hit = [s for (s, sc) in scored if sc > 0]
        if hit:
            sessions = hit

    # 6) 최종 방어
    if not sessions:
        st.session_state["_load_err"] = (
            "No sessions found after filtering.\n"
            f"file={ds_file}\n"
            f"rewrite_target={st.session_state.get('rewrite_target')}\n"
            f"max_rows={max_rows}"
        )
        return False

    # 7) 랜덤 선택 + 정리
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

    # 8) per-session state reset
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
    # 경고는 유지해도 되지만, 이전 경고가 남는 게 싫으면 다음 줄 uncomment
    # st.session_state.pop("_load_warn", None)

    # 9) play counter/log (internal)
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
