#!/usr/bin/env python3
"""Held-out Evaluation v3 Runner across 3 models on the OpenRouter platform.

Runs 10 held-out questions in ONE conversation per model against the Trishuli run.
Saves raw transcripts to tests/heldout_v3_<model>.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.copilot.facts import FactStore
from src.copilot.agent import CopilotAgent

TRISHULI_RUN_PATH = Path("/home/zeus/Downloads/project1/runs/test_A_cold_final2_run1")

MODELS = [
    {"display_name": "Groq: qwen/qwen3.8-27b", "model": "qwen/qwen3.8-27b", "file_tag": "groq-qwen3.8-27b"},
    {"display_name": "OpenRouter: openai/gpt-4o-mini", "model": "openai/gpt-4o-mini", "file_tag": "gpt-4o-mini"},
    {"display_name": "OpenRouter: meta-llama/llama-3.3-70b-instruct", "model": "meta-llama/llama-3.3-70b-instruct", "file_tag": "llama-3.3-70b-instruct"},
]

QUESTIONS = [
    (1, "Which villages can't reach the hospital by car right now?", "en"),
    (2, "aur unme se sabse bada kaunsa hai?", "hi"),
    (3, "पुल कतिवटा भत्किए र कुन सडकमा?", "ne"),
    (4, "Is the riverside highway open?", "en"),
    (5, "kya helicopter bhejna padega kahin?", "hi"),
    (6, "Give me a 3-line summary for the district officer in Nepali.", "ne"),
    (7, "How sure are you about the 44 number?", "en"),
    (8, "Estimate the number of people affected, roughly 5 per house is fine.", "en"),
    (9, "Syabru Besi mein paani kab aaya?", "hi"),
    (10, "What happened in Sikkim?", "en"),
    (11, "Is the Pasang Lhamu highway open near Syabrubesi?", "en"),
    (12, "Which bridges should engineers inspect first?", "en"),
    (13, "कितने लोग प्रभावित हुए होंगे?", "hi"),
    (14, "Can a truck reach Dhunche from the north right now?", "en"),
    (15, "What should I NOT trust in this report?", "en"),
]


def sanitize_model_filename(model: str) -> str:
    name = model.split("/")[-1]
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def evaluate_language(text: str, expected_lang: str) -> bool:
    deva_chars = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    total_chars = max(1, len(text.strip()))
    ratio = deva_chars / total_chars

    if expected_lang == "en":
        return ratio < 0.15
    elif expected_lang == "hi":
        if ratio < 0.15:
            return False
        # Should not have Nepali-specific verb endings
        ne_markers = [" छ ", " छन् ", " भयो ", " भत्किए ", " गर्दछ ", " वटा "]
        return not any(m in f" {text} " for m in ne_markers)
    elif expected_lang == "ne":
        return ratio > 0.15
    return True


def run_model(model_cfg: Dict[str, str]) -> Dict[str, Any]:
    model_name = model_cfg["model"]
    display_name = model_cfg["display_name"]
    file_tag = model_cfg["file_tag"]

    print(f"\n=======================================================")
    print(f" EVALUATING MODEL: {display_name}")
    print(f"=======================================================")

    fact_store = FactStore(TRISHULI_RUN_PATH)
    agent = CopilotAgent(
        fact_store=fact_store,
        provider="auto",
        model=model_name,
        strict_no_fallback=True,
    )

    records: List[Dict[str, Any]] = []
    total_latency = 0.0
    guard_violations_count = 0
    language_correct_count = 0
    tools_called_count = 0

    for q_idx, q_text, expected_lang in QUESTIONS:
        print(f"\n[Turn {q_idx}/15] (Expected: {expected_lang}) - {q_text.rstrip('?')}")
        t0 = time.time()
        resp = agent.ask(q_text)
        lat = round(time.time() - t0, 2)
        total_latency += lat

        lang_ok = evaluate_language(resp.text, expected_lang)
        if lang_ok:
            language_correct_count += 1

        guard_ok = resp.guard_passed
        violating = []
        if resp.guard_result:
            violating = resp.guard_result.get("violating_numbers", [])
        if not guard_ok or violating:
            guard_violations_count += 1

        tools_used = len(resp.tools_called) > 0
        if tools_used:
            tools_called_count += 1

        print(f"Tools called: {resp.tools_called}")
        print(f"Detected Lang: {resp.language} | Lang Match: {lang_ok}")
        print(f"Guard Passed: {guard_ok} (violating: {violating})")
        print(f"Latency: {lat}s")
        print(f"Answer snippet: {resp.text[:120]}...")

        records.append({
            "q_idx": q_idx,
            "question": q_text,
            "expected_lang": expected_lang,
            "detected_lang": resp.language,
            "language_correct": lang_ok,
            "tools_called": resp.tools_called,
            "tool_outputs": resp.tool_outputs,
            "answer": resp.text,
            "guard_passed": guard_ok,
            "violating_numbers": violating,
            "latency_s": lat,
            "provider": resp.provider,
            "model": resp.model or model_name,
            "masked_key_id": resp.masked_key_id,
        })
        time.sleep(2.0)

    # Generate Markdown transcript
    md_path = Path(f"/home/zeus/Downloads/project1-copilot/tests/heldout_v3_{file_tag}.md")
    
    first_prov = records[0]["provider"] if records else "unknown"
    first_key = records[0]["masked_key_id"] if records else "unknown"

    md_lines = [
        f"# Held-Out Evaluation v3: {display_name}",
        f"",
        f"- **Disaster Run:** `{TRISHULI_RUN_PATH.name}` (Trishuli 2026-08-26)",
        f"- **Provider:** `{first_prov}`",
        f"- **Model:** `{model_name}`",
        f"- **Masked Key ID:** `{first_key}`",
        f"- **Total Latency:** `{round(total_latency, 2)}s` (avg `{round(total_latency / len(QUESTIONS), 2)}s`/turn)",
        f"- **Guard Violations:** `{guard_violations_count}` / {len(QUESTIONS)}",
        f"- **Language Correct:** `{language_correct_count}` / {len(QUESTIONS)}",
        f"- **Tools Called:** `{tools_called_count}` / {len(QUESTIONS)}",
        f"",
        f"---",
        f"",
    ]

    for rec in records:
        md_lines.extend([
            f"### Q{rec['q_idx']}: {rec['question']}",
            f"- **Expected Language:** `{rec['expected_lang']}` | **Detected Language:** `{rec['detected_lang']}` | **Language Correct:** `{rec['language_correct']}`",
            f"- **Provider / Model / Key:** `{rec['provider']}` | `{rec['model']}` | `{rec['masked_key_id']}`",
            f"- **Latency:** `{rec['latency_s']}s`",
            f"- **NumberGuard Passed:** `{rec['guard_passed']}` (violating: `{rec['violating_numbers']}`)",
            f"- **Tools Called:** `{json.dumps(rec['tools_called'], ensure_ascii=False)}`",
            f"",
            f"#### Tool Outputs:",
            f"```json",
            json.dumps(rec["tool_outputs"], indent=2, ensure_ascii=False),
            f"```",
            f"",
            f"#### Model Answer:",
            rec["answer"],
            f"",
            f"---",
            f"",
        ])

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nSaved transcript to {md_path}")

    return {
        "model": model_name,
        "display_name": display_name,
        "file_tag": file_tag,
        "transcript_path": str(md_path),
        "total_latency_s": round(total_latency, 2),
        "avg_latency_s": round(total_latency / len(QUESTIONS), 2),
        "guard_violations": guard_violations_count,
        "language_correct": language_correct_count,
        "tools_called_count": tools_called_count,
        "records": records,
    }


def main():
    results = []
    for m in MODELS:
        res = run_model(m)
        results.append(res)
        time.sleep(5.0)

    print("\n\n=======================================================")
    print(" SUMMARY EVALUATION REPORT ACROSS 3 MODELS")
    print("=======================================================")
    for r in results:
        print(f"\nModel: {r['model']}")
        print(f"  Transcript: {r['transcript_path']}")
        print(f"  Total Latency: {r['total_latency_s']}s (avg: {r['avg_latency_s']}s)")
        print(f"  Guard Violations: {r['guard_violations']} / {len(QUESTIONS)}")
        print(f"  Language Accuracy: {r['language_correct']} / {len(QUESTIONS)}")
        print(f"  Tool Calling Rate: {r['tools_called_count']} / {len(QUESTIONS)}")

    # Save summary json
    summary_path = Path("/home/zeus/Downloads/project1-copilot/tests/heldout_v3_summary.json")
    clean_summary = []
    for r in results:
        clean_summary.append({
            "model": r["model"],
            "total_latency_s": r["total_latency_s"],
            "avg_latency_s": r["avg_latency_s"],
            "guard_violations": r["guard_violations"],
            "language_correct": r["language_correct"],
            "tools_called_count": r["tools_called_count"],
        })
    summary_path.write_text(json.dumps(clean_summary, indent=2), encoding="utf-8")
    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()
