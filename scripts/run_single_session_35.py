#!/usr/bin/env python3
"""Single-Conversation 35-Question Evaluation Runner with Automated Correctness Scoring.

Runs:
1. 15 Held-out questions (Q01 to Q15)
2. 20 Hallucination benchmark questions (H01 to H20)
All in ONE continuous conversation on the same CopilotAgent instance.

Scores every question against tests/expected_facts.yaml:
- must_contain
- must_not_contain
- must_contain_any
- expected_run_label
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from src.copilot.facts import FactStore
from src.copilot.agent import CopilotAgent

DEVA_TO_WESTERN = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize_text(text: str) -> str:
    """Normalize text by converting Devanagari numerals to Western digits and lowercasing."""
    if not text:
        return ""
    return text.translate(DEVA_TO_WESTERN).lower()


def evaluate_answer_correctness(answer: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    norm_ans = normalize_text(answer)
    raw_ans = answer

    failures = []
    passed = True

    # 1. Run label check
    exp_label = spec.get("expected_run_label")
    if exp_label:
        norm_exp_label = normalize_text(exp_label)
        if norm_exp_label not in norm_ans:
            # Check if at least key tokens of label are present
            label_tokens = [t for t in norm_exp_label.replace("(", " ").replace(")", " ").replace("/", " ").split() if len(t) >= 4]
            if not any(t in norm_ans for t in label_tokens):
                failures.append(f"Missing expected run label: '{exp_label}'")
                passed = False

    # 2. must_contain checks
    for item in spec.get("must_contain", []):
        norm_item = normalize_text(item)
        if norm_item not in norm_ans:
            failures.append(f"Missing required token: '{item}'")
            passed = False

    # 3. must_not_contain checks
    for item in spec.get("must_not_contain", []):
        norm_item = normalize_text(item)
        if norm_item.isdigit():
            # Exact digit boundary check
            if re.search(r"(?<!\d)" + re.escape(norm_item) + r"(?!\d)", norm_ans):
                failures.append(f"Contains forbidden number: '{item}'")
                passed = False
        else:
            if norm_item in norm_ans:
                failures.append(f"Contains forbidden token: '{item}'")
                passed = False

    # 4. must_contain_any checks
    any_items = spec.get("must_contain_any", [])
    if any_items:
        found_any = any(normalize_text(it) in norm_ans for it in any_items)
        if not found_any:
            failures.append(f"None of required alternative tokens found: {any_items}")
            passed = False

    return {
        "passed": passed,
        "failures": failures,
    }


def main():
    print("=================================================================")
    print("RUNNING 35 QUESTIONS IN ONE CONVERSATION SESSION")
    print("=================================================================")

    expected_facts_p = Path("tests/expected_facts.yaml")
    with open(expected_facts_p, "r", encoding="utf-8") as f:
        spec_data = yaml.safe_load(f)

    heldout_specs = {item["id"]: item for item in spec_data.get("heldout_questions", [])}
    hallucination_specs = {item["id"]: item for item in spec_data.get("hallucination_questions", [])}

    # Questions list
    heldout_questions = [
        ("Q01", "Which villages can't reach the hospital by car right now?"),
        ("Q02", "aur unme se sabse bada kaunsa hai?"),
        ("Q03", "पुल कतिवटा भत्किए र कुन सडकमा?"),
        ("Q04", "Is the riverside highway open?"),
        ("Q05", "kya helicopter bhejna padega kahin?"),
        ("Q06", "Give me a 3-line summary for the district officer in Nepali."),
        ("Q07", "How sure are you about the 44 number?"),
        ("Q08", "Estimate the number of people affected, roughly 5 per house is fine."),
        ("Q09", "Syabru Besi mein paani kab aaya?"),
        ("Q10", "What happened in Sikkim?"),
        ("Q11", "Is the Pasang Lhamu highway open near Syabrubesi?"),
        ("Q12", "Which bridges should engineers inspect first?"),
        ("Q13", "कितने लोग प्रभावित हुए होंगे?"),
        ("Q14", "Can a truck reach Dhunche from the north right now?"),
        ("Q15", "What should I NOT trust in this report?"),
    ]

    hallucination_tests_p = Path("tests/hallucination_tests.yaml")
    with open(hallucination_tests_p, "r", encoding="utf-8") as f:
        h_data = yaml.safe_load(f)
    hallucination_questions = [(item["id"], item["query"]) for item in h_data.get("questions", [])]

    all_35_questions = heldout_questions + hallucination_questions

    # Initialize SINGLE CopilotAgent session
    primary_store = FactStore("runs/test_A_cold_verify")
    agent = CopilotAgent(primary_store, provider="pool", strict_no_fallback=False)
    agent.key_pool.reload_keys()

    print(f"Session initialized on Primary Run: {agent.primary_run_label}")
    print(f"Total questions to evaluate: {len(all_35_questions)}\n")

    results = []
    total_score = 0
    total_count = len(all_35_questions)

    for idx, (qid, query) in enumerate(all_35_questions, 1):
        # In tests: pace questions to stay under limits. If any key in cooldown, wait and retry; never fall back silently.
        while True:
            active_k = agent.key_pool.get_active_key("gemini")
            if active_k:
                break
            keys = agent.key_pool._keys_by_provider.get("gemini", [])
            max_cd = max([k.cooldown_until for k in keys] or [0.0])
            wait_rem = max_cd - time.time()
            if wait_rem > 0:
                print(f"Waiting {wait_rem:.1f}s for Gemini cooldown to clear...")
                time.sleep(wait_rem + 1.0)
            agent.key_pool.reload_keys()
            break

        print(f"[{idx:02d}/35] ({qid}) Running: '{query}'")
        t0 = time.time()
        resp = agent.ask(query)

        # Never fall back silently in tests: if offline, wait for rate limit to pass and retry on live LLM
        if resp.answer_path == "offline":
            print(f"  -> Turn fell back to offline. Backing off 12.0s to retry on live LLM...")
            time.sleep(12.0)
            agent.key_pool.reload_keys()
            if agent.messages and agent.messages[-1].get("content") == resp.text:
                agent.messages.pop()
            if agent.messages and agent.messages[-1].get("content") == query:
                agent.messages.pop()
            resp = agent.ask(query)

        lat = round(time.time() - t0, 2)

        spec = heldout_specs.get(qid) or hallucination_specs.get(qid) or {}
        correctness = evaluate_answer_correctness(resp.text, spec)
        if correctness["passed"]:
            total_score += 1
            status_str = "PASS"
        else:
            status_str = f"FAIL: {'; '.join(correctness['failures'])}"

        print(f"  -> Path: {resp.answer_path} | Provider: {resp.provider} | Model: {resp.model} | Lat: {lat}s | Tokens: in={resp.prompt_tokens}, out={resp.completion_tokens}")
        print(f"  -> Tools: {resp.tools_called}")
        print(f"  -> Correctness: {status_str}")
        print(f"  -> Text snippet: {resp.text.replace(chr(10), ' ')[:100]}...\n")

        results.append({
            "idx": idx,
            "id": qid,
            "query": query,
            "language": resp.language,
            "answer": resp.text,
            "tools_called": resp.tools_called,
            "provider": resp.provider,
            "model": resp.model,
            "masked_key_id": resp.masked_key_id,
            "answer_path": resp.answer_path,
            "turn_latency_sec": resp.turn_latency_sec or lat,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "api_call_logs": resp.api_call_logs,
            "guard_passed": resp.guard_passed,
            "guard_retried": resp.guard_retried,
            "correctness_passed": correctness["passed"],
            "correctness_failures": correctness["failures"],
        })

        # Pacing between queries to strictly respect Gemini 15 RPM limit (6.5s sleep)
        time.sleep(6.5)

    # Compute Latency Metrics (p50, p90, min, max, avg)
    all_latencies = [r["turn_latency_sec"] for r in results]
    llm_latencies = [r["turn_latency_sec"] for r in results if r["answer_path"] == "llm"]

    def calc_percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_d = sorted(data)
        idx = (len(sorted_d) - 1) * p
        low = int(idx)
        high = low + 1
        w = idx - low
        if high >= len(sorted_d):
            return round(sorted_d[low], 2)
        return round(sorted_d[low] * (1.0 - w) + sorted_d[high] * w, 2)

    p50_all = calc_percentile(all_latencies, 0.50)
    p90_all = calc_percentile(all_latencies, 0.90)
    avg_all = round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0.0

    p50_llm = calc_percentile(llm_latencies, 0.50)
    p90_llm = calc_percentile(llm_latencies, 0.90)
    avg_llm = round(sum(llm_latencies) / len(llm_latencies), 2) if llm_latencies else 0.0

    # Save outputs
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)

    json_path = out_dir / "evaluation_35_session.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_questions": total_count,
                "correctness_score": total_score,
                "score_percentage": round(100.0 * total_score / total_count, 1),
                "primary_run": agent.primary_run_label,
                "latency_metrics": {
                    "all_p50_sec": p50_all,
                    "all_p90_sec": p90_all,
                    "all_avg_sec": avg_all,
                    "llm_p50_sec": p50_llm,
                    "llm_p90_sec": p90_llm,
                    "llm_avg_sec": avg_llm,
                },
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    md_path = out_dir / "evaluation_35_session.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Single-Conversation 35-Question Evaluation Transcript\n\n")
        f.write(f"- **Primary Active Run:** {agent.primary_run_label}\n")
        f.write(f"- **Correctness Score:** {total_score}/{total_count} ({round(100.0 * total_score / total_count, 1)}%)\n")
        f.write(f"- **Latency (Overall):** p50 = `{p50_all}s`, p90 = `{p90_all}s`, avg = `{avg_all}s`\n")
        f.write(f"- **Latency (LLM Calls Only):** p50 = `{p50_llm}s`, p90 = `{p90_llm}s`, avg = `{avg_llm}s`\n\n")
        f.write("---\n\n")

        for r in results:
            f.write(f"### [{r['id']}] {r['query']}\n\n")
            f.write(f"- **Answer Path:** `{r['answer_path']}`\n")
            f.write(f"- **Provider / Model:** `{r['provider']}` / `{r['model']}` (Key: `{r['masked_key_id']}`)\n")
            f.write(f"- **Tokens:** Prompt `{r['prompt_tokens']}`, Completion `{r['completion_tokens']}`\n")
            f.write(f"- **Turn Latency:** `{r['turn_latency_sec']}s`\n")
            f.write(f"- **Tools Called:** `{r['tools_called']}`\n")
            status = "✅ PASS" if r["correctness_passed"] else f"❌ FAIL ({'; '.join(r['correctness_failures'])})"
            f.write(f"- **Correctness Check:** {status}\n\n")
            f.write("```text\n")
            f.write(r["answer"].strip() + "\n")
            f.write("```\n\n---\n\n")

    print("\n=================================================================")
    print(f"FINAL SCORE: {total_score}/{total_count} ({round(100.0 * total_score / total_count, 1)}%) CORRECT")
    print(f"OVERALL LATENCY: p50={p50_all}s | p90={p90_all}s | avg={avg_all}s")
    print(f"LLM LATENCY:     p50={p50_llm}s | p90={p90_llm}s | avg={avg_llm}s")
    print(f"JSON results saved to {json_path}")
    print(f"Markdown transcript saved to {md_path}")
    print("=================================================================")


if __name__ == "__main__":
    main()
