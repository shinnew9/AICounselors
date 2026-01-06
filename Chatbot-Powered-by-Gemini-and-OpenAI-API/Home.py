import streamlit as st
from core_ui.layout import set_base_page_config, inject_base_css, render_app_header
from core_ui.auth import render_signin_gate

set_base_page_config()
inject_base_css()

def main():
    render_app_header()

    # Sign-in gate
    if not render_signin_gate():
        st.stop()

    # 로그인 성공하면 바로 01_Dataset.py로 이동
    st.switch_page("pages/01_Dataset.py")

if __name__ == "__main__":
    main()
