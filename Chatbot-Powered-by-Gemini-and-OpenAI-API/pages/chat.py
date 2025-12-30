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
    st.subheader("Chat")

    if not st.session_state.get("profile"):
        st.info("Please complete **Intake** first.")
        return

    with st.sidebar:
        st.header("Dataset / Session")

        files = list_data_files(DATA_ROOT)
        if files:
            cur = st.session_state.get("ds_file")
            st.session_state["ds_file"] = st.selectbox(
                "Dataset file",
                files,
                index=files.index(cur) if cur in files else 0
            )

        st.session_state["max_rows"] = st.number_input("Max rows (perf)", 1000, 200000, int(st.session_state["max_rows"]), step=1000)

        options = ["(no filter)", "African American student", "Hispanic college student"]

        cur_rt = st.session_state.get("rewrite_target")
        if cur_rt in options:
            default_idx = options.index(cur_rt)
        elif cur_rt is None:
            default_idx = 0
        else:
            default_idx = 0

        rt = st.selectbox(
            "Rewrite target filter",
            options,
            index=default_idx,
        )
        st.session_state["rewrite_target"] = None if rt == "(no filter)" else rt

        st.divider()
        st.checkbox("Hide system turns", key="hide_system")
        st.checkbox("Remove consecutive duplicates", key="dedupe")
        st.checkbox("Compact system style", key="compact_system")

        if st.button("🎲 Load random session", use_container_width=True):
            ok = _load_random_session()
            st.session_state["_load_ok"] = ok
            st.rerun()

        if st.button("Reset chat (keep profile)", use_container_width=True):
            reset_chat_state(keep_profile=True)
            st.rerun()

    if not st.session_state.get("loaded_session"):
        err = st.session_state.get("_load_err")
        if err:
            st.error(err)
        st.info("Use the sidebar to **Load random session**.")
        # 입력창은 로드 전엔 못 쓰니까 여기서 return은 맞음
        return

    sid = session_id(st.session_state["loaded_session"], "session")
    qc = st.session_state.get("qc", {})
    st.caption(f"session_id: {sid} | removed_dupes: {qc.get('removed_dupes', 0)}")

    if qc.get("alternation_issues"):
        st.warning(f"⚠️ Alternation issues detected: {len(qc['alternation_issues'])}")
        with st.expander("Show alternation issues"):
            st.json(qc["alternation_issues"][:20])

    # render conversation so far
    for i, pmsg in enumerate(st.session_state["patient_msgs"]):
        render_turn("user", pmsg)
        if i < len(st.session_state["counselor_msgs"]):
            render_turn("assistant", st.session_state["counselor_msgs"][i])

    turns = st.session_state.get("turns_cleaned", [])
    # END 판단은 최소 1개 patient가 있고, cursor가 끝이고, patient==counselor일 때만
    if turns and st.session_state["patient_msgs"] and st.session_state["cursor"] >= len(turns) and len(st.session_state["patient_msgs"]) == len(st.session_state["counselor_msgs"]):
        st.success("End of scripted patient turns. Go to Results.")
        if st.button("Go to Results", type="primary"):
            st.session_state["page"] = "Results"
            st.rerun()
        return

    reply = st.chat_input("Type your counselor reply (1–3 sentences)…")
    if reply:
        reply = reply.strip()
        if not reply:
            return

        if RISK_PAT.search(reply):
            st.warning("⚠️ Crisis-related language detected. In real settings, US: 988.")

        st.session_state["counselor_msgs"].append(reply)

        labs = label_turn_with_llm(gcall, reply)
        st.session_state["turn_labels"].append(labs)
        _update_metrics_summary()

        _advance_to_next_patient()
        st.rerun()
