import streamlit as st

CULTURE_BADGES = {
    "Chinese": "🀄",
    "Hispanic": "🪇",
    "African American": "🎤",
    "Others": "🌍",
}


def _inject_chat_css():
    st.markdown(
        """
        <style>
        .chat-wrap { display: flex; flex-direction: column; gap: 10px; }

        .msg-row { display: flex; width: 100%; }
        .msg-row.left  { justify-content: flex-start; }
        .msg-row.right { justify-content: flex-end; }

        .bubble {
            max-width: min(760px, 78%);
            padding: 10px 12px;
            border-radius: 16px;
            line-height: 1.35;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.06);
            word-wrap: break-word;
            white-space: pre-wrap;
        }

        .bubble.left  { border-top-left-radius: 8px; }
        .bubble.right { border-top-right-radius: 8px; }

        .meta {
            font-size: 12px;
            opacity: 0.70;
            margin-bottom: 4px;
            display:flex;
            gap:6px;
            align-items:center;
        }
        .meta .tag {
            font-weight: 700;
            opacity: 0.85;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_chat(turns, culture: str = "Others"):
    _inject_chat_css()
    badge = CULTURE_BADGES.get(culture, "🌍")

    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)

    for t in turns:
        speaker = (t.get("speaker") or "").lower()
        text = t.get("text") or ""

        if speaker == "client":
            who = f'{badge} Client'
            row_cls = "left"
            bubble_cls = "left"
        else:
            who = "🧑‍⚕️ Counselor"
            row_cls = "right"
            bubble_cls = "right"

        st.markdown(
            f"""
            <div class="msg-row {row_cls}">
              <div class="bubble {bubble_cls}">
                <div class="meta"><span class="tag">{who}</span></div>
                {text}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
