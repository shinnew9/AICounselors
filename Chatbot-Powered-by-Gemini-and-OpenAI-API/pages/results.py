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
        return json.loads(t[s:e + 1])
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
def _skill_badges(labs: dict) -> str:
    keys = [
        ("empathy","Empathy"), ("reflection","Reflection"), ("validation","Validation"),
        ("open_question","OpenQ"), ("suggestion","Suggestion"),
        ("cultural_responsiveness","Culture+"), ("stereotype_risk","StereoRisk"),
        ("goal_alignment","GoalAlign"), ("coherence","Coherence"), ("safety_response","Safety"),
    ]
    on = [name for k, name in keys if int(bool(labs.get(k, 0))) == 1]
    if not on:
        return "`(none)`"
    return " ".join([f"`{x}`" for x in on])


def _plot_bar(metrics_summary: dict):
    import matplotlib.pyplot as plt

    labels = list(metrics_summary.keys())
    vals = [float(metrics_summary[k]) for k in labels]

    fig, ax = plt.subplots(figsize=(6.0, 2.6), dpi=140)
    ax.bar(labels, vals)

    ax.set_ylim(0, 1)
    ax.set_ylabel("Rate (0-1)")
    ax.set_params(axis="x", labelrotation=30, labelsize=8)
    ax.set_params(axis="x", labelsize=8)
    fig.tight_layout()

    return fig


def _plot_timeline(ts: dict):
    import matplotlib.pyplot as plt
    fig = plt.figure()
    for k, series in ts.items():
        plt.plot(list(range(1, len(series)+1)), series, label=k)

    plt.ylim(0, 1)
    plt.xlabel("Counselor turn index")
    plt.ylabel("Cumulative avg rate")
    plt.legend()
    st.pyplot(fig, clear_figure=True)


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
    fig = _plot_bar(metrics_summary)
    st.pyplot(fig, use_container_width=False)


def _render_timeline(labels: list[dict]):
    st.subheader("2) Skill timeline (cumulative average)")
    if not labels:
        st.info("No counselor turns yet.")
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
    _plot_timeline(ts2)


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
        rows.append({
            "turn": i + 1,
            "client": (ptext[:80] + "…") if len(ptext) > 80 else ptext,
            "counselor": (ctext[:80] + "…") if len(ctext) > 80 else ctext,
            "skills": _skill_badges(lab),
            "warnings": " | ".join(w) if w else "",
        })

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
            st.session_state.get("counselor_msgs", [])
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
    st.subheader("Results")

    if not st.session_state.get("loaded_session"):
        st.info("No session loaded yet. Go to **Chat** and click **Load new session**.")
        return

    labels = st.session_state.get("turn_labels", []) or []
    patient_msgs = st.session_state.get("patient_msgs", []) or []
    counselor_msgs = st.session_state.get("counselor_msgs", []) or []

    # Build/refresh metrics_summary from labels (more reliable than stale state)
    metrics_summary = make_metrics_summary(labels)
    st.session_state["metrics_summary"] = metrics_summary  # keep for downloads

    _render_session_overview(metrics_summary)
    st.divider()

    _render_timeline(labels)
    st.divider()

    _render_turn_table(patient_msgs, counselor_msgs, labels)
    st.divider()

    _render_turn_coaching_cards(patient_msgs, counselor_msgs, labels)
    st.divider()

    _render_overall_feedback()

    # Instructor-only
    if st.session_state.get("user_role") == "Instructor" and st.session_state.get("instructor_unlocked"):
        st.divider()
        _render_instructor_tools()
