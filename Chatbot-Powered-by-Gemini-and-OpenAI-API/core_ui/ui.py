import streamlit as st
import html

def nav():
    # 3 tabs only
    tabs = ["Intake", "Chat", "Results"]
    idx = tabs.index(st.session_state["page"]) if st.session_state["page"] in tabs else 0
    picked = st.radio("Navigation", tabs, index=idx, horizontal=True, label_visibility="collapsed")
    st.session_state["page"] = picked


def _bubble_css_once():
    if st.session_state.get("_bubble_css_loaded"):
        return
    st.session_state["_bubble_css_loaded"] = True
    st.markdown("""
    <style>
      .bubble-wrap { width: 100%; margin: 0.25rem 0; display: flex; }
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

      /* Left (AI patient) */
      .bubble.patient {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.08);
      }

      /* Right (Counselor) */
      .bubble.counselor {
        background: rgba(0, 122, 255, 0.18);
        border: 1px solid rgba(0, 122, 255, 0.28);
      }

      /* small role tag */
      .role-tag {
        font-size: 0.78rem;
        opacity: 0.70;
        margin: 0 0.6rem;
        align-self: flex-end;
      }
    </style>
    """, unsafe_allow_html=True)          


def render_turn(role: str, text: str):
    _bubble_css_once()
    safe = html.escape(text)

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
        # system (optional)
        if st.session_state.get("hide_system"):
            return
        st.markdown(f"<div class='role-tag'>system</div><div class='bubble patient'><i>{safe}</i></div>",
                    unsafe_allow_html=True)
