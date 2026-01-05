# import json
# from pathlib import Path
# from datetime import datetime
# import streamlit as st

# from core_ui.data import load_sessions_any, get_turns, session_id, qc_clean_turns

# RATINGS_DIR = Path("data") / "ratings"   # 로컬 저장용 (repo에 커밋하지 말고 .gitignore 추천)


# def _ratings_path(rater_id: str, culture: str) -> Path:
#     safe_r = "".join(ch for ch in (rater_id or "unknown") if ch.isalnum() or ch in ("_", "-", "."))
#     safe_c = (culture or "unknown").replace(" ", "_")
#     return RATINGS_DIR / safe_r / f"{safe_c}.jsonl"


# def _append_jsonl(path: Path, obj: dict):
#     path.parent.mkdir(parents=True, exist_ok=True)
#     with open(path, "a", encoding="utf-8") as f:
#         f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# def _load_existing(path: Path) -> list[dict]:
#     if not path.exists():
#         return []
#     rows = []
#     with open(path, "r", encoding="utf-8") as f:
#         for line in f:
#             line = line.strip()
#             if not line:
#                 continue
#             try:
#                 rows.append(json.loads(line))
#             except Exception:
#                 pass
#     return rows


# def _next_unrated_index(existing_rows: list[dict]) -> int:
#     # assume saved with "session_idx"
#     done = sorted({int(r.get("session_idx", -1)) for r in existing_rows if str(r.get("session_idx","")).isdigit() or isinstance(r.get("session_idx"), int)})
#     if not done:
#         return 0
#     # smallest missing
#     i = 0
#     done_set = set(done)
#     while i in done_set:
#         i += 1
#     return i


# def _render_transcript(turns_cleaned: list[dict]):
#     # simple readable transcript
#     for t in turns_cleaned:
#         role = t.get("role")
#         txt = t.get("text","")
#         if role == "user":
#             st.markdown(f"**Client:** {txt}")
#         elif role == "assistant":
#             st.markdown(f"**Counselor:** {txt}")
#         else:
#             st.markdown(f"<span style='opacity:0.65'>System: {txt}</span>", unsafe_allow_html=True)


# def render():
#     st.header("Rate session")

#     rater_id = (st.session_state.get("rater_id") or "").strip()
#     culture = st.session_state.get("culture")
#     ds_file = st.session_state.get("ds_file")

#     if not rater_id:
#         st.error("Missing rater_id. Please set it in the sidebar.")
#         return
#     if not culture or not ds_file:
#         st.info("Go to **Culture** tab first and select a dataset.")
#         return

#     # Load dataset
#     max_rows = int(st.session_state.get("max_rows", 20000) or 20000)
#     sessions = load_sessions_any(ds_file, max_rows=max_rows) or []
#     if not sessions:
#         st.error(f"No sessions loaded from: {ds_file}")
#         return

#     # Existing progress
#     path = _ratings_path(rater_id, culture)
#     existing = _load_existing(path)
#     st.session_state.setdefault("session_idx", _next_unrated_index(existing))

#     # Header/progress UI
#     total = len(sessions)
#     idx = int(st.session_state.get("session_idx", 0) or 0)
#     idx = max(0, min(idx, total - 1))
#     st.session_state["session_idx"] = idx

#     left, right = st.columns([0.7, 0.3])
#     with left:
#         st.subheader(f"{culture} — Session {idx+1} / {total}")
#         st.caption(f"Rater: **{rater_id}**   |   File: `{Path(ds_file).name}`")
#     with right:
#         # jump / resume control
#         start_from = st.number_input("Jump to session #", min_value=1, max_value=total, value=idx+1, step=1)
#         if st.button("Go", use_container_width=True):
#             st.session_state["session_idx"] = int(start_from) - 1
#             st.rerun()

#     st.divider()

#     # Show transcript
#     sess = sessions[idx]
#     sid = str(session_id(sess, fallback=str(idx)))
#     turns_raw = get_turns(sess)
#     turns_cleaned, qc = qc_clean_turns(turns_raw, remove_consecutive_dupes=True)

#     with st.expander("Show full transcript", expanded=True):
#         _render_transcript(turns_cleaned)

#     st.divider()

#     # Rating form (A/B)
#     st.markdown("## Ratings")
#     st.caption("A: As a student from this cultural group, does the CLIENT sound authentic?  B: Are the COUNSELOR responses effective/helpful?")

#     with st.form("rating_form", clear_on_submit=False):
#         st.markdown("### A) Patient perspective (authenticity)")
#         a_auth = st.slider("Patient voice authenticity (1=not at all, 5=very authentic)", 1, 5, 3)
#         a_note = st.text_area("Optional note (what felt authentic/inauthentic?)", height=90)

#         st.markdown("### B) Counselor perspective (effectiveness)")
#         b_eff = st.slider("Counselor response effectiveness (1=poor, 5=excellent)", 1, 5, 3)
#         dims = st.multiselect(
#             "Which aspects were present? (optional)",
#             ["Empathy", "Cultural sensitivity", "Open questions", "Validation", "Actionable suggestions", "Coherent/clear"],
#             default=[]
#         )
#         b_note = st.text_area("Optional note (what worked / what should change?)", height=90)

#         submitted = st.form_submit_button("Save rating & Next", use_container_width=True)

#     if submitted:
#         record = {
#             "ts": datetime.now().isoformat(timespec="seconds"),
#             "rater_email": st.session_state.get("rater_email"),
#             "rater_id": rater_id,
#             "culture": culture,
#             "ds_file": str(ds_file),
#             "session_idx": idx,
#             "session_id": sid,
#             "ratings": {
#                 "A_patient_authenticity": int(a_auth),
#                 "A_note": a_note.strip(),
#                 "B_counselor_effectiveness": int(b_eff),
#                 "B_dims": dims,
#                 "B_note": b_note.strip(),
#             },
#         }
#         _append_jsonl(path, record)

#         # advance
#         st.session_state["session_idx"] = min(idx + 1, total - 1)
#         st.success("Saved ✅ Moving to next session...")
#         st.rerun()

#     # Safety: allow user to download their current ratings file anytime
#     st.divider()
#     st.markdown("### Export")
#     existing2 = _load_existing(path)
#     st.download_button(
#         "Download my ratings (JSONL)",
#         data="\n".join(json.dumps(r, ensure_ascii=False) for r in existing2),
#         file_name=f"ratings_{rater_id}_{culture.replace(' ','_')}.jsonl",
#         mime="application/jsonl",
#         use_container_width=True,
#     )

#     # Quick status
#     st.caption(f"Saved ratings so far: {len(existing2)}  |  Local path: {path}")



import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from core_ui.data import (
    DATA_ROOT,
    load_sessions_any,
    get_turns,
    qc_clean_turns,
    session_id,
)

SAVE_DIR = Path(__file__).resolve().parents[1] / "data" / "ratings"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

LIKERT = [1, 2, 3, 4, 5]

PATIENT_QS = [
    ("patient_cultural_voice", "If I were this student, the patient's wording feels culturally authentic."),
    ("patient_situation_realism", "The patient's concerns feel realistic for a college/graduate student."),
    ("patient_emotion_fit", "The patient's emotions feel believable and consistent throughout the session."),
]

COUNSELOR_QS = [
    ("counselor_cultural_fit", "The counselor responds in a culturally appropriate way for this student."),
    ("counselor_empathy", "The counselor demonstrates empathy and understanding."),
    ("counselor_helpfulness", "The counselor responses are helpful/actionable without being pushy."),
]


def _ratings_path(rater_id: str, culture: str) -> Path:
    safe_r = "".join([c for c in (rater_id or "unknown") if c.isalnum() or c in ("_", "-")])[:50]
    safe_c = (culture or "unknown").replace(" ", "_").lower()
    return SAVE_DIR / f"ratings_{safe_r}_{safe_c}.jsonl"


def _count_completed_sessions(path: Path) -> int:
    if not path.exists():
        return 0
    done = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                done.add(int(obj.get("session_idx", -1)))
            except Exception:
                continue
    return len(done)


def _append_rating(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _render_transcript(turns_cleaned: list[dict]):
    st.markdown("### Transcript")
    for t in turns_cleaned:
        role = t.get("role")
        text = (t.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            st.markdown(f"**Patient:** {text}")
        elif role == "assistant":
            st.markdown(f"**Counselor:** {text}")
        else:
            # system
            st.markdown(f"<span style='opacity:.65'>System: {text}</span>", unsafe_allow_html=True)


def render():
    st.subheader("Rate a Session")

    # culture / dataset guard
    culture = st.session_state.get("culture")
    ds_file = st.session_state.get("ds_file")
    if not culture or not ds_file:
        st.warning("Please select a culture dataset first.")
        st.session_state["page"] = "Culture"
        st.rerun()

    # rater guard
    rid = st.session_state.get("rater_id", "unknown")
    email = st.session_state.get("rater_email", "")
    save_path = _ratings_path(rid, culture)

    # load sessions
    sessions = load_sessions_any(ds_file, max_rows=20000) or []
    if not sessions:
        st.error(f"No sessions loaded from `{ds_file}`.")
        return

    completed = _count_completed_sessions(save_path)
    total = len(sessions)
    next_idx = min(completed, total - 1)

    st.info(f"Rater: **{rid}**  |  Culture: **{culture}**")
    st.caption(f"Progress: **{completed}/{total}** sessions completed")
    st.caption(f"Dataset: `{ds_file}`")

    st.divider()

    # resume control (professor request)
    start_from = st.number_input(
        "Start from session number (1-based)",
        min_value=1,
        max_value=total,
        value=int(next_idx + 1),
        step=1,
    )
    session_idx = int(start_from - 1)
    sess = sessions[session_idx]

    # prepare turns
    turns_raw = get_turns(sess)
    turns_cleaned, qc = qc_clean_turns(turns_raw, remove_consecutive_dupes=True)

    # Show numbering + session id
    sid = str(session_id(sess, fallback=str(session_idx)))
    st.markdown(f"## Session **{session_idx + 1}** / {total}")
    st.caption(f"Internal session_id: `{sid}` (for debugging)")

    # transcript expander (recommended)
    with st.expander("Show full transcript", expanded=True):
        _render_transcript(turns_cleaned)

    st.divider()

    # --- Rating form
    st.markdown("### A) Patient perspective")
    patient_scores = {}
    for key, q in PATIENT_QS:
        patient_scores[key] = st.radio(q, LIKERT, horizontal=True, key=f"pat_{session_idx}_{key}")

    st.markdown("### B) Counselor perspective")
    counselor_scores = {}
    for key, q in COUNSELOR_QS:
        counselor_scores[key] = st.radio(q, LIKERT, horizontal=True, key=f"coun_{session_idx}_{key}")

    st.markdown("### Comments (optional)")
    comment = st.text_area(
        "Anything that felt especially authentic/inauthentic or helpful/unhelpful?",
        key=f"comment_{session_idx}",
        height=120,
    )

    c1, c2, c3 = st.columns([1, 1, 1.2])
    with c1:
        if st.button("💾 Save rating", type="primary", use_container_width=True):
            record = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "rater_id": rid,
                "rater_email": email,
                "culture": culture,
                "dataset_file": ds_file,
                "session_idx": session_idx,
                "session_id": sid,
                "patient_scores": patient_scores,
                "counselor_scores": counselor_scores,
                "comment": (comment or "").strip(),
                "qc": qc,
            }
            _append_rating(save_path, record)
            st.success("Saved!")

            # 자동으로 다음 session으로 (가능하면)
            if session_idx + 1 < total:
                st.session_state["_auto_next"] = session_idx + 2  # 1-based
            else:
                st.session_state["_auto_next"] = None
            st.rerun()

    with c2:
        if st.button("Next session →", use_container_width=True):
            nxt = min(session_idx + 2, total)  # 1-based
            st.session_state["_auto_next"] = nxt
            st.rerun()

    with c3:
        if st.button("← Back to culture selection", use_container_width=True):
            st.session_state["page"] = "Culture"
            st.rerun()

    # auto-next apply
    auto = st.session_state.get("_auto_next")
    if auto:
        st.session_state["_auto_next"] = None
        st.session_state["page"] = "Rate"
        # 다음 번호로 UI를 유도하기 위해 rerun 시 number_input value가 바뀌게 하려면
        # start_from default가 completed 기반이라 저장 후 completed가 증가하면 자동으로 다음으로 감.
        st.rerun()

    # download current rater file
    st.divider()
    with st.expander("Download my ratings (JSONL)", expanded=False):
        if save_path.exists():
            st.download_button(
                "Download ratings JSONL",
                data=save_path.read_text(encoding="utf-8"),
                file_name=save_path.name,
                mime="application/jsonl",
                use_container_width=True,
            )
        else:
            st.info("No ratings saved yet.")
