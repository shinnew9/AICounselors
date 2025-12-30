import re
import streamlit as st

from core_ui.data import (
    DATA_ROOT, list_data_files, load_sessions_any, filter_sessions,
    pick_random_session, get_turns, qc_clean_turns, session_id
)
from core_ui.state import reset_chat_state
from core_ui.ui import render_turn

from core.llm import gcall
from core.metrics import label_turn_with_llm, compute_session_skill_rates


def _ensure_ui_flags():
    st.session_state.setdefault("panel_open", True)


def _apply_chat_wide_css(panel_open: bool):
    # panel 닫으면 말풍선/컨테이너 폭을 최대한 넓게
    if not panel_open:
        st.markdown(
            """
            <style>
              /* main container a bit wider feeling */
              section.main > div { padding-left: 2rem; padding-right: 2rem; }

              /* make chat messages use more horizontal space */
              [data-testid="stChatMessage"] { width: 100% !important; }
              [data-testid="stChatMessageContent"] { width: 100% !important; max-width: 100% !important; }

              /* reduce max-width clamp inside markdown blocks */
              .stMarkdown, .stMarkdown p { max-width: 100% !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


RISK_PAT = re.compile(r"\b(suicide|kill myself|self[- ]harm|end it|overdose|hurt myself)\b", re.I)


def _update_metrics_summary():
    rates = compute_session_skill_rates(st.session_state.get("turn_labels", [])) or {}
    st.session_state["metrics_summary"] = {
        "Empathy": float(rates.get("empathy_rate", 0.0)),
        "Reflection": float(rates.get("reflection_rate", 0.0)),
        "Open Questions": float(rates.get("open_question_rate", 0.0)),
        "Validation": float(rates.get("validation_rate", 0.0)),
        "Suggestions": float(rates.get("suggestion_rate", 0.0)),
    }


def _advance_to_next_patient():
    turns = st.session_state.get("turns_cleaned", [])
    c = st.session_state.get("cursor", 0)

    while c < len(turns) and turns[c]["role"] != "user":
        c += 1
    if c < len(turns):
        st.session_state["patient_msgs"].append(turns[c]["text"])
        c += 1
    st.session_state["cursor"] = c


def _load_random_session() -> bool:
    files = list_data_files(DATA_ROOT)
    if not files:
        st.session_state["_load_err"] = f"No dataset files under {DATA_ROOT}"
        return False

    if not st.session_state.get("ds_file") or st.session_state["ds_file"] not in files:
        st.session_state["ds_file"] = files[0]

    sessions = load_sessions_any(st.session_state["ds_file"], max_rows=int(st.session_state["max_rows"]))
    sessions = filter_sessions(sessions, st.session_state.get("rewrite_target"))

    if not sessions:
        st.session_state["_load_err"] = (
            "No sessions found after filtering.\n"
            f"file={st.session_state['ds_file']}\n"
            f"rewrite_target={st.session_state.get('rewrite_target')}\n"
            f"max_rows={int(st.session_state['max_rows'])}"
        )
        return False

    s = pick_random_session(sessions)
    turns_raw = get_turns(s)
    turns_cleaned, qc = qc_clean_turns(turns_raw, remove_consecutive_dupes=st.session_state["dedupe"])

    # keep internal ids for metrics/logging
    st.session_state["active_session_id"] = str(session_id(s, "session"))
    st.session_state["removed_dupes"] = int(qc.get("removed_dupes", 0))

    if st.session_state["hide_system"]:
        turns_display = [t for t in turns_cleaned if t["role"] != "system"]
    else:
        turns_display = turns_cleaned

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

    _advance_to_next_patient()

    # debug snapshot
    st.session_state["_loaded_debug"] = {
        "n_turns_raw": len(turns_raw),
        "n_turns_cleaned": len(turns_display),
        "first_roles": [t["role"] for t in turns_display[:8]],
        "cursor_after_first": st.session_state["cursor"],
        "n_patient_msgs": len(st.session_state["patient_msgs"]),
    }

    # still no patient -> treat as failure
    if len(st.session_state["patient_msgs"]) == 0:
        st.session_state["_load_err"] = "Loaded turns but could not display the first patient turn."
        return False

    return True


def render():
    _ensure_ui_flags()
    _apply_chat_wide_css(st.session_state["panel_open"])

    # Top bar
    top_l, top_r = st.columns([0.08, 0.92])
    with top_l:
        if st.button("☰", help="Show/hide panel"):
            st.session_state["panel_open"] = not st.session_state["panel_open"]
            st.rerun()
    with top_r:
        st.title("🧠 AI Counselor Simulation")

    # Layout columns (panel + chat)
    if st.session_state["panel_open"]:
        panel, chatcol = st.columns([0.28, 0.72], gap="large")
    else:
        panel, chatcol = None, st.container()

    # -------------------------
    # LEFT PANEL (foldable)
    # -------------------------
    if panel is not None:
        with panel:
            st.markdown("### Session")

            prof = st.session_state.get("profile") or {}
            race = (prof.get("race_ethnicity") or "").lower()

            # Intake 기반 고정
            if "african" in race:
                st.session_state["rewrite_target"] = "African American student"
                want_hint = "african"
            elif "hispanic" in race:
                st.session_state["rewrite_target"] = "Hispanic college student"
                want_hint = "hispanic"
            else:
                st.session_state["rewrite_target"] = None
                want_hint = None

            # 내부 고정값
            st.session_state["max_rows"] = 20000

            files = list_data_files(DATA_ROOT)
            if not files:
                st.error(f"No data files found under: {DATA_ROOT}")
                st.stop()

            def pick_file_by_hint(files, hint):
                if not hint:
                    return files[0]
                for f in files:
                    if hint in f.lower():
                        return f
                return files[0]

            st.session_state["ds_file"] = pick_file_by_hint(files, want_hint)

            st.caption(f"Client profile: **{prof.get('race_ethnicity','Unknown')}**")
            if st.session_state["rewrite_target"]:
                st.caption(f"Dataset: **{st.session_state['rewrite_target']}**")

            st.divider()
            st.checkbox("Hide system turns", key="hide_system")
            st.checkbox("Remove consecutive duplicates", key="dedupe")
            st.checkbox("Compact system style", key="compact_system")

            if st.button("🎲 Load new session", use_container_width=True):
                ok = _load_random_session()
                if not ok:
                    st.session_state["_load_ok"] = False
                st.rerun()

            if st.button("Reset chat (keep profile)", use_container_width=True):
                reset_chat_state(keep_profile=True)
                st.rerun()

    # -------------------------
    # RIGHT: CHAT AREA
    # -------------------------
    with chatcol:
        st.subheader("Chat")

        # Not loaded yet
        if not st.session_state.get("loaded_session"):
            err = st.session_state.get("_load_err")
            if err:
                st.error(err)
            st.info("Click **🎲 Load new session** on the left panel.")
            return

        # End-of-session guard (only after at least 1 patient shown)
        turns = st.session_state.get("turns_cleaned", []) or []
        if turns and st.session_state.get("patient_msgs") and st.session_state.get("cursor", 0) >= len(turns) \
           and len(st.session_state.get("patient_msgs", [])) == len(st.session_state.get("counselor_msgs", [])):
            st.success("End of scripted patient turns. Go to Results.")
            if st.button("Go to Results", type="primary"):
                st.session_state["page"] = "Results"
                st.rerun()
            return

        # Render dialogue (left=patient, right=counselor)
        patient_msgs = st.session_state.get("patient_msgs", [])
        counselor_msgs = st.session_state.get("counselor_msgs", [])
        for i, pmsg in enumerate(patient_msgs):
            render_turn("patient", pmsg)
            if i < len(counselor_msgs):
                render_turn("counselor", counselor_msgs[i])

        # Input
        user_text = st.chat_input("Type your counselor reply (1–3 sentences)...")
        if user_text:
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
