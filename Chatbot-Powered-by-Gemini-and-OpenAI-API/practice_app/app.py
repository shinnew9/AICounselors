import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import streamlit as st

# init_state가 session_state를 덮어쓸 가능성이 높아서,
# 로그인/진행상태 루프를 막기 위해 여기서는 "최소한만" 씀.
# 꼭 필요하면 ensure_global_ui_state만 유지.
from core_ui.state import ensure_global_ui_state

from pages import culture_select, rate


def _ensure_defaults():
    st.session_state.setdefault("page", "Culture")   # Culture -> Rate
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("rater_email", "")
    st.session_state.setdefault("rater_id", "")
    st.session_state.setdefault("culture", None)
    st.session_state.setdefault("ds_file", None)
    st.session_state.setdefault("progress", {})      # { "rater::culture": session_idx }


def main():
    st.set_page_config(page_title="Cultural Session Rater", page_icon="🧠", layout="wide")

    _ensure_defaults()
    ensure_global_ui_state()

    page = st.session_state.get("page", "Culture")

    if page == "Culture":
        culture_select.render()
        return

    if page == "Rate":
        rate.render()
        return

    # fallback
    st.session_state["page"] = "Culture"
    st.rerun()


if __name__ == "__main__":
    main()
