# pages/results.py
import json
import streamlit as st
from datetime import datetime

from core.llm import gcall
from core.prompts import OVERALL_FEEDBACK_SYSTEM, build_history

from core.metrics import (
    make_metrics_summary,
    make_skill_timeseries,
    turn_warnings,
)



# Micro feedback (fallback)
def _clean_json_block(text: str) -> dict:
    t = (text or "").strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(t[s : e + 1])
    except Exception:
        return {}


MICRO_FEEDBACK_SYSTEM = """
You are a counseling supervisor. Given ONE counselor message and its micro-skill flags
(empathy, reflection, validation, open_question, suggestion: 0/1), produce very concise micro feedback.

Return STRICT JSON with fields:
{
  "strength_title": "Empathy|Reflection|Validation|Open Question|Listening",
  "strength_note": "one short sentence (<=18 words) praising the best thing",
  "feedback_title": "Questions|Validation|Empathy|Refocus|Suggesting",
  "feedback_note": "one short sentence (<=18 words) with a concrete improvement tip",
  "alt_response": "optional 1-2 sentences better rewrite; neutral tone"
}
Output JSON only.
""".strip()


def gen_micro_feedback_fallback(counselor_text: str, labs: dict) -> dict:
    flags = {k: int(bool(labs.get(k, 0))) for k in ["empathy", "reflection", "validation", "open_question", "suggestion"]}
    prompt = f"""{MICRO_FEEDBACK_SYSTEM}

Counselor message:
\"\"\"{(counselor_text or "").strip()}\"\"\"

Skill flags (0/1):
{json.dumps(flags)}

JSON:"""
    out, _ = gcall(prompt, max_tokens=220, temperature=0.3)
    data = _clean_json_block(out) or {}
    return {
        "strength_title": data.get("strength_title", "Strengths"),
        "strength_note": data.get("strength_note", "Good client-centered stance."),
        "feedback_title": data.get("feedback_title", "Feedback"),
        "feedback_note": data.get("feedback_note", "Try one gentle open question to invite more detail."),
        "alt_response": data.get("alt_response", ""),
    }


# UI helpers
def _apply_results_css():
    st.markdown(
        """
        <style>
          /* Centered content wrapper for transcript */
          .results-wrap { max-width: 980px; margin: 0 auto; }

          /* Bubble system (match chat feel) */
          .bubble-row { display: flex; margin: 0.35rem 0; }
          .bubble-row.left  { justify-content: flex-start; }
          .bubble-row.right { justify-content: flex-end; }

          .bubble {
            max-width: 72%;
            padding: 10px 12px;
            border-radius: 16px;
            line-height: 1.35;
            font-size: 0.95rem;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.04);
            color: rgba(255,255,255,0.92);
            white-space: pre-wrap;
            word-wrap: break-word;
          }
          hr {
            margin-top: 2.0rem !important;
            margin-bottom: 2.0rem !important;
            opacity: 0.25;
          }
          .bubble.user {
            background: rgba(0, 122, 255, 0.16);
            border-color: rgba(0, 122, 255, 0.26);
          }
          .bubble.assistant {
            background: rgba(255,255,255,0.04);
            border-color: rgba(255,255,255,0.10);
          }
          

          /* Give plots less vertical dominance */
          .small-plot-note { opacity: 0.75; font-size: 0.9rem; margin-top: -0.25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _skill_badges(labs: dict) -> str:
    keys = [
        ("empathy", "Empathy"),
        ("reflection", "Reflection"),
        ("validation", "Validation"),
        ("open_question", "OpenQ"),
        ("suggestion", "Suggestion"),
        ("cultural_responsiveness", "Culture+"),
        ("stereotype_risk", "StereoRisk"),
        ("goal_alignment", "GoalAlign"),
        ("coherence", "Coherence"),
        ("safety_response", "Safety"),
    ]
    on = [name for k, name in keys if int(bool(labs.get(k, 0))) == 1]
    if not on:
        return "`(none)`"
    return " ".join([f"`{x}`" for x in on])


def _has_any_signal(metrics_summary: dict) -> bool:
    if not metrics_summary:
        return False
    try:
        return any(float(v) > 0 for v in metrics_summary.values())
    except Exception:
        return False


# Plotters
def _plot_bar(metrics_summary: dict):
    """
    Returns fig or None (if empty/all-zero).
    """
    if not metrics_summary or not _has_any_signal(metrics_summary):
        return None

    import matplotlib.pyplot as plt

    labels = list(metrics_summary.keys())
    vals = [float(metrics_summary[k]) for k in labels]

    # smaller & tighter
    fig, ax = plt.subplots(figsize=(5.2, 2.2), dpi=140)
    ax.bar(labels, vals)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Rate (0–1)")

    ax.tick_params(axis="x", labelrotation=30, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)

    fig.tight_layout()
    return fig


def _plot_timeline(ts: dict):
    """
    Returns fig or None
    """
    if not ts:
        return None
    # if all series empty or all zeros, skip
    try:
        if not any(any(float(x) > 0 for x in series) for series in ts.values()):
            return None
    except Exception:
        pass

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.2, 2.4), dpi=140)
    for k, series in ts.items():
        ax.plot(list(range(1, len(series) + 1)), series, label=k)

    ax.set_ylim(0, 1)
    ax.set_xlabel("Counselor turn index")
    ax.set_ylabel("Cumulative avg rate")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


# Main sections
def _render_session_overview(metrics_summary: dict):
    st.subheader("1) Session overview")

    # Metric cards: core 5
    core = {
        "Empathy": metrics_summary.get("Empathy", 0.0),
        "Reflection": metrics_summary.get("Reflection", 0.0),
        "Open Questions": metrics_summary.get("Open Questions", 0.0),
        "Validation": metrics_summary.get("Validation", 0.0),
        "Suggestions": metrics_summary.get("Suggestions", 0.0),
    }
    cols = st.columns(5)
    for i, (k, v) in enumerate(core.items()):
        with cols[i]:
            st.metric(k, f"{v*100:.0f}%")

    st.caption("Tip: Suggestions are not always bad—but frequent advice can reduce client-led exploration.")
    st.divider()

    # Bar chart: core + extensions (if present)
    st.markdown("**Skill rates (core + extensions)**")
    st.markdown('<div class="small-plot-note">Plots are hidden when metrics are all-zero.</div>', unsafe_allow_html=True)

    fig = _plot_bar(metrics_summary)
    if fig is None:
        st.info("No detected skills yet for this session (all rates are 0).")
        return

    st.pyplot(fig, use_container_width=True, clear_figure=True)


def _render_transcript(patient_msgs, counselor_msgs):
    """
    4-1: Better transcript UI: centered wrapper + chat bubbles.
    """
    st.subheader("Session transcript")

    if not patient_msgs and not counselor_msgs:
        st.info("No transcript yet. Complete a chat session first.")
        return

    # Pairwise render: patient[i] then counselor[i]
    st.markdown('<div class="results-wrap">', unsafe_allow_html=True)

    n = max(len(patient_msgs), len(counselor_msgs))
    for i in range(n):
        if i < len(patient_msgs):
            p = patient_msgs[i] or ""
            st.markdown(
                f'<div class="bubble-row left"><div class="bubble assistant">{p}</div></div>',
                unsafe_allow_html=True,
            )
        if i < len(counselor_msgs):
            c = counselor_msgs[i] or ""
            st.markdown(
                f'<div class="bubble-row right"><div class="bubble user">{c}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def _render_timeline(labels: list[dict]):
    st.subheader("2) Skill timeline (cumulative average)")

    if not labels:
        st.info("No counselor turns labeled yet.")
        return

    keys = ["empathy", "reflection", "validation", "open_question", "suggestion"]
    ts = make_skill_timeseries(labels, keys)

    # pretty legend labels (short)
    pretty = {
        "empathy": "Empathy",
        "reflection": "Reflection",
        "validation": "Validation",
        "open_question": "OpenQ",
        "suggestion": "Suggestion",
    }
    ts2 = {pretty[k]: ts[k] for k in keys}

    fig = _plot_timeline(ts2)
    if fig is None:
        st.info("Timeline hidden (no signal yet).")
        return

    st.pyplot(fig, use_container_width=True, clear_figure=True)


def _render_turn_table(patient_msgs, counselor_msgs, labels):
    st.subheader("3) Turn-level summary (flags + warnings)")

    if not counselor_msgs:
        st.info("No counselor turns yet.")
        return

    warns = turn_warnings(patient_msgs, counselor_msgs, labels)

    rows = []
    for i, ctext in enumerate(counselor_msgs):
        ptext = patient_msgs[i] if i < len(patient_msgs) else ""
        lab = labels[i] if i < len(labels) else {}
        w = warns[i]["warnings"] if i < len(warns) else []
        rows.append(
            {
                "turn": i + 1,
                "client": (ptext[:80] + "…") if len(ptext) > 80 else ptext,
                "counselor": (ctext[:80] + "…") if len(ctext) > 80 else ctext,
                "skills": _skill_badges(lab),
                "warnings": " | ".join(w) if w else "",
            }
        )

    st.dataframe(rows, use_container_width=True)


def _render_turn_coaching_cards(patient_msgs, counselor_msgs, labels):
    st.subheader("4) Turn-level coaching (micro feedback)")

    if not counselor_msgs:
        st.info("No counselor turns yet.")
        return

    warns = turn_warnings(patient_msgs, counselor_msgs, labels)

    for i, ctext in enumerate(counselor_msgs):
        ptext = patient_msgs[i] if i < len(patient_msgs) else ""
        labs = labels[i] if i < len(labels) else {}
        w = warns[i]["warnings"] if i < len(warns) else []

        with st.expander(f"Turn {i+1}: coaching", expanded=(i == len(counselor_msgs) - 1)):
            st.markdown("**Client said:**")
            st.write(ptext or "(missing)")
            st.markdown("**Counselor replied:**")
            st.write(ctext)

            st.markdown(f"**Detected skills:** {_skill_badges(labs)}")
            if w:
                st.warning(" / ".join(w))

            # micro feedback
            try:
                micro = gen_micro_feedback_fallback(ctext, labs)
            except Exception:
                micro = {
                    "strength_title": "Strengths",
                    "strength_note": "Nice listening stance.",
                    "feedback_title": "Feedback",
                    "feedback_note": "Ask a gentle open question.",
                    "alt_response": "",
                }

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**✅ {micro['strength_title']}**")
                st.write(micro["strength_note"])
            with c2:
                st.markdown(f"**🛠️ {micro['feedback_title']}**")
                st.write(micro["feedback_note"])

            if micro.get("alt_response"):
                st.markdown("**Suggested rewrite**")
                st.write(micro["alt_response"])


def _render_overall_feedback():
    st.subheader("5) Session-level feedback (LLM)")

    if st.button("Generate session-level feedback (LLM)", key="btn_overall_feedback"):
        history_text = build_history(
            st.session_state.get("patient_msgs", []),
            st.session_state.get("counselor_msgs", []),
        )
        overall_prompt = (
            f"{OVERALL_FEEDBACK_SYSTEM}\n\n"
            f"Conversation (chronological):\n{history_text}\n\n"
            "Evaluate the counselor's replies in aggregate. Provide actionable feedback."
        )
        with st.spinner("Generating feedback..."):
            fb_all, _ = gcall(overall_prompt, max_tokens=800, temperature=0.4)

        st.session_state["overall_feedback"] = fb_all
        st.rerun()

    if st.session_state.get("overall_feedback"):
        st.markdown(st.session_state["overall_feedback"])
    else:
        st.info("Generate feedback to see an overall summary and actionable advice.")


def _render_instructor_tools():
    payload = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "profile": st.session_state.get("profile"),
        "dataset_file": st.session_state.get("ds_file"),
        "patient_msgs": st.session_state.get("patient_msgs", []),
        "counselor_msgs": st.session_state.get("counselor_msgs", []),
        "turn_labels": st.session_state.get("turn_labels", []),
        "metrics_summary": st.session_state.get("metrics_summary", {}),
        "overall_feedback": st.session_state.get("overall_feedback"),
        # internal id for logging only (not shown to student)
        "active_session_id": st.session_state.get("active_session_id"),
        "removed_dupes": st.session_state.get("removed_dupes", 0),
    }

    with st.expander("Instructor tools", expanded=False):
        st.download_button(
            "Download session JSON",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name="practice_session.json",
            mime="application/json",
            use_container_width=True,
        )
        st.json(payload["metrics_summary"])


def render():
    _apply_results_css()
    st.subheader("Results")

    if not st.session_state.get("loaded_session"):
        st.info("No session loaded yet. Go to **Chat** and click **Load new session**.")
        return

    labels = st.session_state.get("turn_labels", []) or []
    patient_msgs = st.session_state.get("patient_msgs", []) or []
    counselor_msgs = st.session_state.get("counselor_msgs", []) or []

    # DEBUG 유지
    st.caption(f"DEBUG: #labels={len(labels)} #counselor={len(counselor_msgs)}")

    # labels가 없으면: 결과 계산/그래프를 안 그림 (빈 plot 방지)
    if not labels:
        st.warning("No skill labels yet. Finish at least 1 counselor turn (or check labeling pipeline).")

        with st.expander("Show transcript", expanded=True):
            _render_transcript(patient_msgs, counselor_msgs)
        return

    # metrics
    metrics_summary = make_metrics_summary(labels)
    st.session_state["metrics_summary"] = metrics_summary

    _render_session_overview(metrics_summary)
    st.divider()

    with st.expander("Show transcript", expanded=False):
        _render_transcript(patient_msgs, counselor_msgs)
    st.divider()

    _render_timeline(labels)
    st.divider()

    _render_turn_table(patient_msgs, counselor_msgs, labels)
    st.divider()

    _render_turn_coaching_cards(patient_msgs, counselor_msgs, labels)
    st.divider()

    _render_overall_feedback()

    if st.session_state.get("user_role") == "Instructor" and st.session_state.get("instructor_unlocked"):
        st.divider()
        _render_instructor_tools()

