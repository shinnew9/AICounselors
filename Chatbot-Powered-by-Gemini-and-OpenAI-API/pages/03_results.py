import streamlit as st
from core_ui.layout import set_base_page_config, inject_base_css
from core_ui.auth import require_signed_in

set_base_page_config()
inject_base_css()

def main():
    require_signed_in()

    st.markdown("## 03 — Results")
    st.info("Results page placeholder. We'll add aggregated metrics/export later.")

    culture = st.session_state.get("culture")
    idx = st.session_state.get("session_idx", 0)
    st.write({"culture": culture, "session_idx": idx})

    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("← Back to Access", use_container_width=True):
            st.switch_page("pages/02_Assess.py")
    with cols[1]:
        if st.button("Back to cultural dataset select", use_container_width=True):
            st.switch_page("pages/01_Dataset.py")

if __name__ == "__main__":
    main()
