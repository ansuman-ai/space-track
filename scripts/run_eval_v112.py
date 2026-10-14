#!/usr/bin/env python3
"""Targeted live evaluation runner for v1.1.2.

Runs ONLY:
1. 15 Held-out questions (Q01 to Q15)
2. 7 Hallucination benchmark questions (H10 to H16)
Total: 22 questions live once.

Saves raw results to tests/eval_v112_results.json and prints formatted table.
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

    failures = []
    passed = True

    # 1. Run label check
    exp_label = spec.get("expected_run_label")
    if exp_label:
        norm_exp_label = normalize_text(exp_label)
        if norm_exp_label not in norm_ans:
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

    # 5. must_contain_any_sets checks
    for any_set in spec.get("must_contain_any_sets", []):
        found_set = any(normalize_text(it) in norm_ans for it in any_set)
        if not found_set:
            failures.append(f"Missing token from set: {any_set}")
            passed = False

    return {
        "passed": passed,
        "failures": failures,
    }


def main():
    print("=================================================================")
    print("RUNNING TARGETED 22 QUESTIONS (Q01-Q15 + H10-H16) LIVE ONCE")
    print("=================================================================")

    expected_facts_p = Path("tests/expected_facts.yaml")
    with open(expected_facts_p, "r", encoding="utf-8") as f:
        spec_data = yaml.safe_load(f)

    heldout_specs = {item["id"]: item for item in spec_data.get("heldout_questions", [])}
    hallucination_specs = {item["id"]: item for item in spec_data.get("hallucination_questions", [])}

    # 15 Held-out questions
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

    # H10 to H16
    hallucination_tests_p = Path("tests/hallucination_tests.yaml")
    with open(hallucination_tests_p, "r", encoding="utf-8") as f:
        h_data = yaml.safe_load(f)
    h_map = {item["id"]: item["query"] for item in h_data.get("questions", [])}
    
    target_h_ids = ["H10", "H11", "H12", "H13", "H14", "H15", "H16"]
    h_questions = [(hid, h_map[hid]) for hid in target_h_ids if hid in h_map]

    all_questions = [(qid, q, "15_heldout", heldout_specs.get(qid, {})) for qid, q in heldout_questions] + \
                    [(hid, q, "hallucination", hallucination_specs.get(hid, {})) for hid, q in h_questions]

    # Initialize SINGLE CopilotAgent session on primary run
    primary_store = FactStore("runs/test_A_cold_verify")
    agent = CopilotAgent(primary_store, provider="pool", strict_no_fallback=False)
    agent.key_pool.reload_from_env()
    for p, keys in agent.key_pool._keys_by_provider.items():
        for k in keys:
            k.exhausted = False
            k.cooldown_until = 0.0
            k.failure_count = 0

    print(f"Session initialized on Primary Run: {agent.primary_run_label}")
    print(f"Total questions: {len(all_questions)}\n")

    results = []
    for qid, query, cat, spec in all_questions:
        print(f"[{qid}] Asking: {query[:60]}...")
        t0 = time.time()
        resp = agent.ask(query)
        lat = round(time.time() - t0, 2)

        eval_res = evaluate_answer_correctness(resp.text, spec) if spec else {"passed": True, "failures": []}
        status = "PASS" if eval_res["passed"] else "FAIL"
        reason = "; ".join(eval_res["failures"]) if not eval_res["passed"] else ""

        ans_preview = resp.text.replace("\n", " ")[:90]
        rec = {
            "id": qid,
            "cat": cat,
            "query": query,
            "status": status,
            "reason": reason,
            "path": resp.answer_path,
            "provider": resp.provider,
            "model": resp.model,
            "lat": lat,
            "ans_preview": ans_preview,
        }
        results.append(rec)
        print(f"  -> {status} | path={resp.answer_path} | provider={resp.provider}/{resp.model} | lat={lat}s")
        if not eval_res["passed"]:
            print(f"     Reason: {reason}")
            print(f"     Answer: {ans_preview}")

    # Save to tests/eval_v112_results.json
    out_file = Path("tests/eval_v112_results.json")
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRaw results saved to {out_file}")

    # Print summary counts
    llm_count = sum(1 for r in results if r["path"] == "llm")
    offline_count = sum(1 for r in results if r["path"] in ["offline", "template_fallback"])
    rules_count = sum(1 for r in results if r["path"] in ["rules", "keyword_refusal"])
    pass_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)

    print("\n=================================================================")
    print(f"EVALUATION SUMMARY: {pass_count}/{total_count} PASSED")
    print(f"Path breakdown: {llm_count} LLM, {offline_count} Offline/Template, {rules_count} Rules/Keyword")
    print("=================================================================")


if __name__ == "__main__":
    main()
