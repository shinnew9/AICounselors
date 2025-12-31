import json
import streamlit as st
from datetime import datetime

from core.llm import gcall
from core.prompts import OVERALL_FEEDBACK_SYSTEM, build_history
from core.metrics import parse_session_metrics



# Micro feedback (fallback)
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
"""


def _clean_json_block(text: str) -> dict:
    t = (text or "").strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e == -1:
        return {}
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        return {}


def gen_micro_feedback_fallback(counselor_text: str, labs: dict) -> dict:
    flags = {k: int(bool(labs.get(k, 0))) for k in
             ["empathy", "reflection", "validation", "open_question", "suggestion"]}

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


# Rubric (transparent heuristic)
def compute_rubric(metrics_summary: dict, labels: list):
    def clip01(x):
        try:
            return max(0.0, min(1.0, float(x)))
        except Exception:
            return 0.0

    emp = clip01(metrics_summary.get("Empathy", 0.0))
    ref = clip01(metrics_summary.get("Reflection", 0.0))
    oq = clip01(metrics_summary.get("Open Questions", 0.0))
    val = clip01(metrics_summary.get("Validation", 0.0))
    sug = clip01(metrics_summary.get("Suggestions", 0.0))

    def score_from_rate(x, good_lo, good_hi):
        # 0..5 with peak in [good_lo, good_hi]
        if x <= 0:
            return 0
        if x < good_lo:
            return int(round(5 * (x / good_lo)))
        if x <= good_hi:
            return 5
        # too high -> penalty
        over = min(1.0, (x - good_hi) / max(1e-6, (1.0 - good_hi)))
        return max(1, int(round(5 * (1.0 - 0.6 * over))))

    engagement = score_from_rate((oq + ref) / 2, 0.20, 0.55)
    empathic = score_from_rate((emp + val) / 2, 0.20, 0.60)
    guidance = score_from_rate(1.0 - sug, 0.55, 0.95)  # less suggestion is better
    consistency = 5 if (emp + ref + val + oq) > 0.6 else (3 if (emp + ref + val + oq) > 0.3 else 1)

    def note_eng():
        if engagement >= 4:
            return "Good balance of reflections and open questions to keep the client talking."
        if engagement == 3:
            return "Add a bit more reflection or one open question per turn."
        return "Try 1 reflection + 1 open question more consistently."

    def note_emp():
        if empathic >= 4:
            return "Empathy/validation are present and supportive."
        if empathic == 3:
            return "Add explicit validation when emotions show up."
        return "Name the emotion and validate before moving forward."

    def note_guid():
        if guidance >= 4:
            return "Advice is appropriately restrained; client-led pace is maintained."
        if guidance == 3:
            return "Reduce suggestions unless the client requests them."
        return "Pause advice-giving; focus on understanding and eliciting more detail."

    def note_cons():
        if consistency >= 4:
            return "Overall stance is consistent across turns."
        if consistency == 3:
            return "Try to keep each reply short and client-centered."
        return "Focus on one skill per reply to avoid scattered responses."

    return [
        {"dimension": "Engagement", "score": engagement, "note": note_eng()},
        {"dimension": "Empathic stance", "score": empathic, "note": note_emp()},
        {"dimension": "Guidance control", "score": guidance, "note": note_guid()},
        {"dimension": "Consistency", "score": consistency, "note": note_cons()},
    ]


# Rendering helpers
def _skill_badges(labs: dict) -> str:
    keys = [("empathy", "Empathy"), ("reflection", "Reflection"), ("validation", "Validation"),
            ("open_question", "OpenQ"), ("suggestion", "Suggestion")]
    on = [name for k, name in keys if int(bool(labs.get(k, 0))) == 1]
    if not on:
        return "`No skill detected`"
    return " ".join([f"`{x}`" for x in on])


def _render_quantitative(metrics_summary: dict):
    st.subheader("1) Quantitative skill breakdown")

    if not metrics_summary:
        st.info("No skill metrics yet (send at least one counselor reply).")
        return

    st.write(f"- Empathy: {metrics_summary.get('Empathy', 0):.2f}")
    st.write(f"- Reflection: {metrics_summary.get('Reflection', 0):.2f}")
    st.write(f"- Open Questions: {metrics_summary.get('Open Questions', 0):.2f}")
    st.write(f"- Validation: {metrics_summary.get('Validation', 0):.2f}")
    st.write(f"- Suggestions: {metrics_summary.get('Suggestions', 0):.2f}")

    st.caption("Tip: Keep Suggestions lower unless the client explicitly asks for advice.")


def _render_turn_coaching_cards(patient_msgs, counselor_msgs, labels):
    st.subheader("2) Turn-level coaching (micro feedback)")

    if not counselor_msgs:
        st.info("No counselor turns yet.")
        return

    for i, ctext in enumerate(counselor_msgs):
        ptext = patient_msgs[i] if i < len(patient_msgs) else ""
        labs = labels[i] if i < len(labels) else {}

        with st.expander(f"Turn {i + 1}: coaching", expanded=(i == len(counselor_msgs) - 1)):
            st.markdown("**Client said:**")
            st.write(ptext or "(missing)")
            st.markdown("**Counselor replied:**")
            st.write(ctext)

            st.markdown(f"**Detected skills:** {_skill_badges(labs)}")

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


def _render_rubric(metrics_summary: dict, labels: list):
    st.subheader("3) Rubric (paper-inspired)")

    rubric = compute_rubric(metrics_summary or {}, labels or [])
    cols = st.columns(4)
    for idx, item in enumerate(rubric):
        with cols[idx % 4]:
            st.metric(item["dimension"], f"{item['score']}/5")
            st.caption(item["note"])

    with st.expander("What this rubric means"):
        st.markdown(
            "- **Engagement**: Did you keep the client talking via reflections + open questions?\n"
            "- **Empathic stance**: Did you name emotions and validate the client?\n"
            "- **Guidance control**: Did you avoid premature advice-giving?\n"
            "- **Consistency**: Were your replies reliably brief and client-centered?\n"
        )


def _render_overall_feedback_section():
    st.markdown("### Session-level feedback (LLM)")

    # button key 꼭 주기 (중복 방지)
    if st.button("Generate session-level feedback (LLM)", key="btn_results_overall_llm"):
        history_text = build_history(
            st.session_state.get("patient_msgs", []),
            st.session_state.get("counselor_msgs", []),
        )
        overall_prompt = (
            f"{OVERALL_FEEDBACK_SYSTEM}\n\n"
            f"Conversation (chronological):\n{history_text}\n\n"
            "Evaluate the counselor's replies in aggregate."
        )
        with st.spinner("Generating feedback..."):
            fb_all, _ = gcall(overall_prompt, max_tokens=800, temperature=0.4)

        st.session_state["overall_feedback"] = fb_all
        st.session_state["session_metrics"] = parse_session_metrics(fb_all)
        st.rerun()

    if st.session_state.get("overall_feedback"):
        st.markdown(st.session_state["overall_feedback"])
    else:
        st.info("Generate feedback to see an overall summary and actionable advice.")


def _render_instructor_tools():
    payload = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "user_role": st.session_state.get("user_role"),
        "instructor_unlocked": st.session_state.get("instructor_unlocked", False),

        # session basics
        "profile": st.session_state.get("profile"),
        "dataset_file": st.session_state.get("ds_file"),

        # conversation
        "patient_msgs": st.session_state.get("patient_msgs", []),
        "counselor_msgs": st.session_state.get("counselor_msgs", []),

        # metrics
        "turn_labels": st.session_state.get("turn_labels", []),
        "metrics_summary": st.session_state.get("metrics_summary", {}),
        "overall_feedback": st.session_state.get("overall_feedback"),

        # internal tracking (hidden to students)
        "active_session_id": st.session_state.get("active_session_id"),
        "removed_dupes": st.session_state.get("removed_dupes", 0),
        "session_play_count": st.session_state.get("session_play_count", 0),
        "session_play_log": st.session_state.get("session_play_log", []),
    }

    with st.expander("Instructor tools (download / debug)", expanded=False):
        st.caption("Visible only when Instructor is unlocked.")
        st.download_button(
            "Download session JSON",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name="practice_session_export.json",
            mime="application/json",
            use_container_width=True,
        )
        st.json(payload.get("metrics_summary", {}))



# MAIN
def render():
    st.subheader("Results")

    # session loaded?
    if not st.session_state.get("loaded_session"):
        st.info("No session loaded yet. Go to **Chat** and click **Load new session**.")
        return

    metrics_summary = st.session_state.get("metrics_summary", {}) or {}
    labels = st.session_state.get("turn_labels", []) or []
    patient_msgs = st.session_state.get("patient_msgs", []) or []
    counselor_msgs = st.session_state.get("counselor_msgs", []) or []

    _render_quantitative(metrics_summary)
    st.divider()

    _render_turn_coaching_cards(patient_msgs, counselor_msgs, labels)
    st.divider()

    _render_rubric(metrics_summary, labels)
    st.divider()

    _render_overall_feedback_section()

    # Instructor-only tools
    if st.session_state.get("user_role") == "Instructor" and st.session_state.get("instructor_unlocked"):
        st.divider()
        _render_instructor_tools()