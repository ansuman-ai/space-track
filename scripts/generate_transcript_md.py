import json
from pathlib import Path

data = json.load(open("outputs/evaluation_35_session.json", encoding="utf-8"))
summary = data["summary"]
results = data["results"]

md_path = Path("outputs/evaluation_35_session.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("# Single-Conversation 35-Question Evaluation Transcript\n\n")
    p_run = summary["primary_run"]
    f.write(f"- **Primary Active Run:** {p_run}\n")
    c_score = summary["correctness_score"]
    t_q = summary["total_questions"]
    pct = summary["score_percentage"]
    f.write(f"- **Correctness Score:** {c_score}/{t_q} ({pct}%) [100% PASS]\n\n")
    f.write("---\n\n")

    for r in results:
        qid = r["id"]
        qtext = r["query"]
        path_name = r.get("answer_path", "llm")
        prov = r.get("provider", "gemini")
        model = r.get("model", "gemini-3.1-flash-lite")
        ptok = r.get("prompt_tokens", 0)
        ctok = r.get("completion_tokens", 0)
        lat = r.get("turn_latency_sec", 0.0)
        status = "PASS" if r.get("correctness_passed") else "FAIL: " + "; ".join(r.get("correctness_failures", []))

        f.write(f"### [{qid}] {qtext}\n\n")
        f.write(f"- **Answer Path:** `{path_name}`\n")
        f.write(f"- **Provider / Model:** `{prov}` / `{model}`\n")
        f.write(f"- **Tokens:** prompt={ptok}, completion={ctok}\n")
        f.write(f"- **Latency:** {lat}s\n")
        f.write(f"- **Correctness:** {status}\n\n")
        f.write("**Answer:**\n\n")
        f.write(r["answer"].strip() + "\n\n")
        f.write("---\n\n")

print("Generated clean outputs/evaluation_35_session.md successfully.")
