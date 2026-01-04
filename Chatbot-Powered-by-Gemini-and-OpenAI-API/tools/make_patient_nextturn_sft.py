import json
from pathlib import Path
from core_ui.data import load_sessions_any, get_turns, qc_clean_turns

OUT = Path("data/finetune/patient_nextturn.jsonl")
OUT.parent.mkdir(parents=True, exist_ok=True)


def build_history(turns, up_to_idx, max_chars=1800):
    # turns: cleaned list of {"role","text"}
    # up_to_idx: include turns[0:up_to_idx] as context
    chunks = []
    for t in turns[:up_to_idx]:
        if t["role"] == "user":
            chunks.append(f"CLIENT: {t['text']}")
        elif t["role"] == "assistant":
            chunks.append(f"COUNSELOR: {t['text']}")
    txt = "\n".join(chunks)
    return txt[-max_chars:]  # keep tail


def main(ds_path: str):
    sessions = load_sessions_any(ds_path)
    n_written = 0

    with OUT.open("w", encoding="utf-8") as w:
        for sess in sessions:
            raw_turns = get_turns(sess)
            cleaned, qc = qc_clean_turns(raw_turns, remove_consecutive_dupes=True)

            # keep only user/assistant turns
            ua = [t for t in cleaned if t["role"] in {"user","assistant"}]
            if len(ua) < 4:
                continue

            # make examples where target = next CLIENT turn
            # pattern: ... COUNSELOR -> CLIENT(target)
            for i in range(1, len(ua)):
                if ua[i]["role"] != "user":
                    continue
                if ua[i-1]["role"] != "assistant":
                    continue

                history = build_history(ua, up_to_idx=i)  # includes counselor turn i-1
                target = ua[i]["text"]

                # you can optionally add profile/rewrite_target here if present
                profile = sess.get("profile") or {}
                rewrite_target = sess.get("rewrite_target") or ""

                record = {
                    "profile": profile,
                    "rewrite_target": rewrite_target,
                    "input": (
                        "You are simulating a counseling client.\n"
                        f"Client profile: {json.dumps(profile, ensure_ascii=False)}\n"
                        f"Rewrite target: {rewrite_target}\n"
                        "Conversation so far:\n"
                        f"{history}\n\n"
                        "Write the NEXT CLIENT message (1-3 sentences)."
                    ),
                    "output": target
                }
                w.write(json.dumps(record, ensure_ascii=False) + "\n")
                n_written += 1

    print(f"wrote {n_written} examples to {OUT}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python tools/make_patient_nextturn_sft.py <path_to_json_or_jsonl>")
        raise SystemExit(1)
    main(sys.argv[1])
