# pages/rate.py
import json
from pathlib import Path
from datetime import datetime
import streamlit as st

from core_ui.data import load_sessions_any, get_turns, session_id, qc_clean_turns

RATINGS_DIR = Path("data") / "ratings"   # 로컬 저장용 (repo에 커밋하지 말고 .gitignore 추천)

def _ratings_path(rater_id: str, culture: str) -> Path:
    safe_r = "".join(ch for ch in (rater_id or "unknown") if ch.isalnum() or ch in ("_", "-", "."))
    safe_c = (culture or "unknown").replace(" ", "_")
    return RATINGS_DIR / safe_r / f"{safe_c}.jsonl"

def _append_jsonl(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

def _next_unrated_index(existing_rows: list[dict]) -> int:
    # assume saved with "session_idx"
    done = sorted({int(r.get("session_idx", -1)) for r in existing_rows if str(r.get("session_idx","")).isdigit() or isinstance(r.get("session_idx"), int)})
    if not done:
        return 0
    # smallest missing
    i = 0
    done_set = set(done)
    while i in done_set:
        i += 1
    return i

def _render_transcript(turns_cleaned: list[dict]):
    # simple readable transcript
    for t in turns_cleaned:
        role = t.get("role")
        txt = t.get("text","")
        if role == "user":
            st.markdown(f"**Client:** {txt}")
        elif role == "assistant":
            st.markdown(f"**Counselor:** {txt}")
        else:
            st.markdown(f"<span style='opacity:0.65'>System: {txt}</span>", unsafe_allow_html=True)

def render():
    st.header("Rate session")

    rater_id = (st.session_state.get("rater_id") or "").strip()
    culture = st.session_state.get("culture")
    ds_file = st.session_state.get("ds_file")

    if not rater_id:
        st.error("Missing rater_id. Please set it in the sidebar.")
        return
    if not culture or not ds_file:
        st.info("Go to **Culture** tab first and select a dataset.")
        return

    # Load dataset
    max_rows = int(st.session_state.get("max_rows", 20000) or 20000)
    sessions = load_sessions_any(ds_file, max_rows=max_rows) or []
    if not sessions:
        st.error(f"No sessions loaded from: {ds_file}")
        return

    # Existing progress
    path = _ratings_path(rater_id, culture)
    existing = _load_existing(path)
    st.session_state.setdefault("session_idx", _next_unrated_index(existing))

    # Header/progress UI
    total = len(sessions)
    idx = int(st.session_state.get("session_idx", 0) or 0)
    idx = max(0, min(idx, total - 1))
    st.session_state["session_idx"] = idx

    left, right = st.columns([0.7, 0.3])
    with left:
        st.subheader(f"{culture} — Session {idx+1} / {total}")
        st.caption(f"Rater: **{rater_id}**   |   File: `{Path(ds_file).name}`")
    with right:
        # jump / resume control
        start_from = st.number_input("Jump to session #", min_value=1, max_value=total, value=idx+1, step=1)
        if st.button("Go", use_container_width=True):
            st.session_state["session_idx"] = int(start_from) - 1
            st.rerun()

    st.divider()

    # Show transcript
    sess = sessions[idx]
    sid = str(session_id(sess, fallback=str(idx)))
    turns_raw = get_turns(sess)
    turns_cleaned, qc = qc_clean_turns(turns_raw, remove_consecutive_dupes=True)

    with st.expander("Show full transcript", expanded=True):
        _render_transcript(turns_cleaned)

    st.divider()

    # Rating form (A/B)
    st.markdown("## Ratings")
    st.caption("A: As a student from this cultural group, does the CLIENT sound authentic?  B: Are the COUNSELOR responses effective/helpful?")

    with st.form("rating_form", clear_on_submit=False):
        st.markdown("### A) Patient perspective (authenticity)")
        a_auth = st.slider("Patient voice authenticity (1=not at all, 5=very authentic)", 1, 5, 3)
        a_note = st.text_area("Optional note (what felt authentic/inauthentic?)", height=90)

        st.markdown("### B) Counselor perspective (effectiveness)")
        b_eff = st.slider("Counselor response effectiveness (1=poor, 5=excellent)", 1, 5, 3)
        dims = st.multiselect(
            "Which aspects were present? (optional)",
            ["Empathy", "Cultural sensitivity", "Open questions", "Validation", "Actionable suggestions", "Coherent/clear"],
            default=[]
        )
        b_note = st.text_area("Optional note (what worked / what should change?)", height=90)

        submitted = st.form_submit_button("Save rating & Next", use_container_width=True)

    if submitted:
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "rater_email": st.session_state.get("rater_email"),
            "rater_id": rater_id,
            "culture": culture,
            "ds_file": str(ds_file),
            "session_idx": idx,
            "session_id": sid,
            "ratings": {
                "A_patient_authenticity": int(a_auth),
                "A_note": a_note.strip(),
                "B_counselor_effectiveness": int(b_eff),
                "B_dims": dims,
                "B_note": b_note.strip(),
            },
        }
        _append_jsonl(path, record)

        # advance
        st.session_state["session_idx"] = min(idx + 1, total - 1)
        st.success("Saved ✅ Moving to next session...")
        st.rerun()

    # Safety: allow user to download their current ratings file anytime
    st.divider()
    st.markdown("### Export")
    existing2 = _load_existing(path)
    st.download_button(
        "Download my ratings (JSONL)",
        data="\n".join(json.dumps(r, ensure_ascii=False) for r in existing2),
        file_name=f"ratings_{rater_id}_{culture.replace(' ','_')}.jsonl",
        mime="application/jsonl",
        use_container_width=True,
    )

    # Quick status
    st.caption(f"Saved ratings so far: {len(existing2)}  |  Local path: {path}")
