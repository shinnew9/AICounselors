import streamlit as st
import html

def nav():
    tabs = ["Intake", "Chat", "Results"]
    idx = tabs.index(st.session_state["page"]) if st.session_state.get("page") in tabs else 0
    picked = st.radio("Navigation", tabs, index=idx, horizontal=True, label_visibility="collapsed")
    st.session_state["page"] = picked


def _bubble_css():
    # IMPORTANT: Streamlit reruns the script on every interaction.
    # So we MUST inject CSS every run (do NOT gate with session_state).
    st.markdown("""
    <style>
      .bubble-wrap { width: 100%; margin: 0.35rem 0; display: flex; }
      .bubble-left { justify-content: flex-start; }
      .bubble-right { justify-content: flex-end; }

      .bubble {
        max-width: 72%;
        padding: 10px 12px;
        border-radius: 18px;
        line-height: 1.35;
        font-size: 0.98rem;
        word-wrap: break-word;
        white-space: pre-wrap;
      }

      /* Left (Patient) */
      .bubble.patient {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.10);
      }

      /* Right (Counselor) */
      .bubble.counselor {
        background: rgba(0, 122, 255, 0.18);
        border: 1px solid rgba(0, 122, 255, 0.30);
      }

      /* Optional: make the chat area breathe a bit */
      .chat-area-title { margin-top: 0.2rem; }

    </style>
    """, unsafe_allow_html=True)


def render_turn(role: str, text: str):
    _bubble_css()
    safe = html.escape(text or "")

    if role == "patient":
        st.markdown(
            f"""
            <div class="bubble-wrap bubble-left">
              <div class="bubble patient">{safe}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif role == "counselor":
        st.markdown(
            f"""
            <div class="bubble-wrap bubble-right">
              <div class="bubble counselor">{safe}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # system
        if st.session_state.get("hide_system"):
            return
        st.markdown(
            f"""
            <div class="bubble-wrap bubble-left">
              <div class="bubble patient"><i>{safe}</i></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
