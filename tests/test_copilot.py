"""Automated Evaluation Runner for Situation-Report Copilot.

Loads tests/copilot_questions.yaml and benchmarks:
- Tool-selection accuracy
- Answer correctness
- Number-guard violations
- Correct language matching
- Correct 'not available' behavior for data gaps
- Ambiguity resolution handling

Can run across multiple providers (e.g. offline, gemini, openai, anthropic).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.copilot.agent import CopilotAgent, detect_query_language
from src.copilot.facts import FactStore
from src.copilot.guard import NumberGuard

logger = logging.getLogger("copilot.eval")


def run_evaluation(
    questions_path: Path | str,
    runs_dir: Path | str,
    provider: str = "offline",
) -> Dict[str, Any]:
    """Run full evaluation suite from copilot_questions.yaml."""
    q_path = Path(questions_path).resolve()
    with open(q_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    questions = data.get("questions", [])
    runs_root = Path(runs_dir).resolve()

    # Preload stores
    fact_stores: Dict[str, FactStore] = {}
    agents: Dict[str, CopilotAgent] = {}

    run_aliases = {
        "test_A_trishuli": runs_root / "test_A_cold_verify",
        "test_B_melamchi": runs_root / "test_B_cold_verify",
    }

    for run_name in ["test_A_trishuli", "test_B_melamchi"]:
        run_path = run_aliases.get(run_name, runs_root / run_name)
        if run_path.exists():
            fs = FactStore(run_path)
            fact_stores[run_name] = fs
            agents[run_name] = CopilotAgent(fs, provider=provider)

    guard = NumberGuard()

    results: List[Dict[str, Any]] = []
    total_q = len(questions)

    tool_correct_count = 0
    answer_correct_count = 0
    guard_pass_count = 0
    lang_correct_count = 0
    not_avail_correct_count = 0
    ambig_correct_count = 0
    unans_total = 0
    ambig_total = 0

    print(f"\n=======================================================")
    print(f" EVALUATING COPILOT BENCHMARK [Provider: {provider.upper()}]")
    print(f" Total Questions: {total_q}")
    print(f"=======================================================\n")

    for idx, q_item in enumerate(questions, 1):
        qid = q_item["id"]
        q_text = q_item["question"]
        q_type = q_item["type"]
        target_run = q_item.get("run", "test_A_trishuli")
        expected_tools = q_item.get("expected_tools", [])
        expected_numbers = q_item.get("expected_numbers", [])
        expected_lang = q_item.get("language", "en")

        agent = agents.get(target_run)
        fs = fact_stores.get(target_run)

        if not agent or not fs:
            logger.error("Run %s not loaded, skipping %s", target_run, qid)
            continue

        # If question is not a follow-up, reset agent context
        if q_type != "follow_up":
            agent.messages.clear()
            agent.active_settlement = None

        response = agent.ask(q_text)

        # 1. Tool selection check
        if q_type == "unanswerable":
            tool_match = len(response.tools_called) == 0
        elif not expected_tools:
            tool_match = True
        else:
            tool_match = any(t in response.tools_called for t in expected_tools)

        if tool_match:
            tool_correct_count += 1

        # 2. Number guard check
        guard_res = guard.check(response.text, response.tool_outputs, extra_numbers=fs.all_numbers())
        guard_valid = guard_res.is_valid
        if guard_valid:
            guard_pass_count += 1

        # 3. Language check
        lang_match = response.language == expected_lang
        if lang_match:
            lang_correct_count += 1

        # 4. Correct answer / numbers check
        answer_correct = True
        if q_type == "unanswerable":
            unans_total += 1
            has_not_avail = any(
                phrase in response.text.lower() or phrase in response.text
                for phrase in ["not available", "उपलब्ध छैन", "उपलब्ध नहीं", "तथ्याङ्कमा उपलब्ध छैन"]
            )
            if has_not_avail:
                not_avail_correct_count += 1
            else:
                answer_correct = False
        elif q_type == "ambiguous":
            ambig_total += 1
            is_clarification = response.clarification_needed or any(
                c in response.text.lower() or c in response.text
                for c in ["multiple", "which location", "कुन बस्ती", "कौन सी"]
            )
            if is_clarification:
                ambig_correct_count += 1
            else:
                answer_correct = False
        else:
            # Check expected numbers
            ext_nums = guard.extract_numbers(response.text)
            for en in expected_numbers:
                if not any(abs(en - an) < 1e-3 for an in ext_nums):
                    answer_correct = False
                    break

        if answer_correct:
            answer_correct_count += 1

        status_flag = "PASS" if (tool_match and guard_valid and answer_correct and lang_match) else "WARN"
        print(f"[{status_flag}] #{idx:02d} ({qid}) | Type: {q_type:12s} | Tool: {str(response.tools_called):20s} | Guard: {guard_valid} | Lang: {response.language}")

        results.append({
            "id": qid,
            "question": q_text,
            "type": q_type,
            "run": target_run,
            "expected_lang": expected_lang,
            "detected_lang": response.language,
            "expected_tools": expected_tools,
            "called_tools": response.tools_called,
            "tool_match": tool_match,
            "guard_valid": guard_valid,
            "violating_numbers": guard_res.violating_numbers,
            "answer_correct": answer_correct,
            "text_sample": response.text[:120].replace("\n", " "),
        })

    tool_accuracy = (tool_correct_count / total_q) * 100
    answer_accuracy = (answer_correct_count / total_q) * 100
    guard_pass_rate = (guard_pass_count / total_q) * 100
    guard_violation_rate = 100.0 - guard_pass_rate
    lang_accuracy = (lang_correct_count / total_q) * 100
    not_avail_accuracy = (not_avail_correct_count / max(unans_total, 1)) * 100
    ambig_accuracy = (ambig_correct_count / max(ambig_total, 1)) * 100

    metrics = {
        "provider": provider,
        "total_questions": total_q,
        "tool_selection_accuracy_pct": round(tool_accuracy, 2),
        "answer_correctness_pct": round(answer_accuracy, 2),
        "number_guard_violation_pct": round(guard_violation_rate, 2),
        "language_match_accuracy_pct": round(lang_accuracy, 2),
        "not_available_behavior_pct": round(not_avail_accuracy, 2),
        "ambiguity_handling_pct": round(ambig_accuracy, 2),
    }

    print("\n" + "=" * 55)
    print(f" BENCHMARK REPORT: {provider.upper()}")
    print("=" * 55)
    print(f" Total Questions:              {total_q}")
    print(f" Tool-Selection Accuracy:       {metrics['tool_selection_accuracy_pct']}%")
    print(f" Answer Correctness:           {metrics['answer_correctness_pct']}%")
    print(f" Number-Guard Violations:       {metrics['number_guard_violation_pct']}% (0.0% is optimal)")
    print(f" Language Match Accuracy:       {metrics['language_match_accuracy_pct']}%")
    print(f" 'Not Available' Correctness:   {metrics['not_available_behavior_pct']}%")
    print(f" Ambiguity Handling:           {metrics['ambiguity_handling_pct']}%")
    print("=" * 55 + "\n")

    return {
        "metrics": metrics,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Situation-Report Copilot")
    parser.add_argument(
        "--questions",
        type=str,
        default="tests/copilot_questions.yaml",
        help="Path to questions YAML",
    )
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--runs-dir",
        type=str,
        default=str(repo_root / "runs"),
        help="Directory containing pipeline runs",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="offline",
        choices=["offline", "gemini", "openai", "anthropic", "compare"],
        help="Provider to evaluate",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default="tests/copilot_eval_report.json",
        help="Output report JSON file path",
    )
    args = parser.parse_args()

    providers_to_test = []
    if args.provider == "compare":
        providers_to_test.append("offline")
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            providers_to_test.append("gemini")
        if os.getenv("OPENAI_API_KEY"):
            providers_to_test.append("openai")
        if os.getenv("ANTHROPIC_API_KEY"):
            providers_to_test.append("anthropic")
    else:
        providers_to_test.append(args.provider)

    comparison_report = {}
    for prov in providers_to_test:
        eval_res = run_evaluation(args.questions, args.runs_dir, provider=prov)
        comparison_report[prov] = eval_res["metrics"]

    # Write JSON report
    out_path = Path(args.output_report).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2)
    print(f"Evaluation report written to: {out_path}")


if __name__ == "__main__":
    main()
