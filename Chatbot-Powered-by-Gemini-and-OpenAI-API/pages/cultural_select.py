# pages/culture_select.py
import streamlit as st
from core_ui.data import DATA_ROOT, list_data_files

def _pick_file_for_culture(culture: str, files: list[str]) -> str | None:
    c = (culture or "").lower()
    hints = []
    if c == "hispanic":
        hints = ["hispanic"]
    elif c in ("african_american", "african american"):
        hints = ["african", "african_american"]
    elif c == "chinese":
        hints = ["chinese", "china"]
    else:
        hints = [c]

    for h in hints:
        for f in files:
            if h in f.lower():
                return f
    return files[0] if files else None

def render():
    st.header("Select dataset")
    st.caption("Choose which cultural dataset you want to rate. You will rate sessions sequentially and your progress will be saved.")

    files = list_data_files(DATA_ROOT) or []
    if not files:
        st.error(f"No dataset files found under {DATA_ROOT}")
        return

    c1, c2, c3 = st.columns(3)

    def _choose(culture_label: str):
        ds = _pick_file_for_culture(culture_label, files)
        st.session_state["culture"] = culture_label
        st.session_state["ds_file"] = ds
        st.session_state.setdefault("session_idx", 0)
        # move to Rate
        st.session_state["page"] = "Rate"
        st.rerun()

    with c1:
        if st.button("Chinese", use_container_width=True):
            _choose("Chinese")
    with c2:
        if st.button("Hispanic", use_container_width=True):
            _choose("Hispanic")
    with c3:
        if st.button("African American", use_container_width=True):
            _choose("African American")

    st.divider()
    st.markdown("#### Current selection")
    st.write({
        "rater_id": st.session_state.get("rater_id"),
        "culture": st.session_state.get("culture"),
        "ds_file": st.session_state.get("ds_file"),
    })
