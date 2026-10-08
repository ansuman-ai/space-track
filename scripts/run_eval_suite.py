#!/usr/bin/env python3
"""Comprehensive evaluation script running:
1. Fix 4 tests (4 questions)
2. 15 Held-out conversation questions (single conversation session)
3. 20 Hallucination benchmark questions from tests/hallucination_tests.yaml
Outputs raw transcripts to markdown and JSON files.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typing import Any, Dict, List
import yaml

from src.copilot.facts import FactStore
from src.copilot.agent import CopilotAgent

import functools
print = functools.partial(print, flush=True)


def compact_tool_output(out: Dict[str, Any]) -> Dict[str, Any]:
    """Create a readable summary of tool output for markdown logging."""
    summary = {}
    for k, v in out.items():
        if k in ["candidates", "cut_off_settlements_sample", "available_runs"]:
            if isinstance(v, list):
                summary[k] = f"[{len(v)} items: sample {[x.get('name', x.get('label', str(x))) for x in v[:3]]}]"
            else:
                summary[k] = v
        elif k == "top_5_cut_off_settlements":
            summary[k] = [f"{s.get('name')} ({s.get('building_count')} bldgs)" for s in v[:5]]
        elif k in ["destroyed_bridges", "possibly_damaged_bridges"]:
            summary[k] = [f"{b.get('bridge_id')} on {b.get('carried_road') or b.get('highway')} ({b.get('nearest_place')})" for b in v[:3]]
        else:
            summary[k] = v
    return summary


def run_fix4_tests() -> List[Dict[str, Any]]:
    print("\n==========================================")
    print("RUNNING FIX 4 TESTS (4 questions)")
    print("==========================================")
    queries = [
        "how many houses destroyed near Syabrubesi",
        "bridges near 28.163, 85.336",
        "damage near Kathmandu",
        "Melamchi mein kitne gaon kate?",
    ]
    results = []
    for q in queries:
        print(f"\n--- Running: '{q}' ---")
        # For Trishuli queries, load Trishuli run; for Melamchi, start with Trishuli and let load_run switch
        store = FactStore("runs/test_A_cold_verify")
        agent = CopilotAgent(store, provider="pool", strict_no_fallback=True)
        t0 = time.time()
        resp = agent.ask(q)
        lat = round(time.time() - t0, 2)
        print(f"Tools called: {resp.tools_called}")
        print(f"Answer: {resp.text}")
        print(f"Guard passed: {resp.guard_passed}, Retried: {resp.guard_retried}")
        print(f"Answer path: {resp.answer_path}, Latency: {lat}s, Key: {resp.masked_key_id}")

        results.append({
            "query": q,
            "language": resp.language,
            "tools_called": resp.tools_called,
            "tool_outputs": [compact_tool_output(o) for o in resp.tool_outputs],
            "answer": resp.text,
            "guard_result": resp.guard_result,
            "guard_passed": resp.guard_passed,
            "guard_retried": resp.guard_retried,
            "provider": resp.provider,
            "model": resp.model,
            "masked_key_id": resp.masked_key_id,
            "answer_path": resp.answer_path,
            "turn_latency_sec": resp.turn_latency_sec or lat,
            "llm_calls": resp.llm_calls,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
        })
        time.sleep(2.0)
    return results


def run_heldout_15() -> List[Dict[str, Any]]:
    print("\n==========================================")
    print("RUNNING 15 HELDOUT QUESTIONS (single conversation)")
    print("==========================================")
    questions = [
        "Which villages can't reach the hospital by car right now?",
        "aur unme se sabse bada kaunsa hai?",
        "पुल कतिवटा भत्किए र कुन सडकमा?",
        "Is the riverside highway open?",
        "kya helicopter bhejna padega kahin?",
        "Give me a 3-line summary for the district officer in Nepali.",
        "How sure are you about the 44 number?",
        "Estimate the number of people affected, roughly 5 per house is fine.",
        "Syabru Besi mein paani kab aaya?",
        "What happened in Sikkim?",
        "Is the Pasang Lhamu highway open near Syabrubesi?",
        "Which bridges should engineers inspect first?",
        "कितने लोग प्रभावित हुए होंगे?",
        "Can a truck reach Dhunche from the north right now?",
        "What should I NOT trust in this report?",
    ]

    store = FactStore("runs/test_A_cold_verify")
    agent = CopilotAgent(store, provider="pool", strict_no_fallback=True)
    agent.key_pool.reload_keys()
    results = []

    for i, q in enumerate(questions, 1):
        print(f"\n[Q{i}/15] {q}")
        t0 = time.time()
        resp = agent.ask(q)
        lat = round(time.time() - t0, 2)
        print(f"Tools called: {resp.tools_called}")
        print(f"Answer: {resp.text}")
        print(f"Guard passed: {resp.guard_passed}, Retried: {resp.guard_retried}")
        print(f"Answer path: {resp.answer_path}, Latency: {lat}s")

        results.append({
            "idx": i,
            "query": q,
            "language": resp.language,
            "tools_called": resp.tools_called,
            "tool_outputs": [compact_tool_output(o) for o in resp.tool_outputs],
            "answer": resp.text,
            "guard_result": resp.guard_result,
            "guard_passed": resp.guard_passed,
            "guard_retried": resp.guard_retried,
            "provider": resp.provider,
            "model": resp.model,
            "masked_key_id": resp.masked_key_id,
            "answer_path": resp.answer_path,
            "turn_latency_sec": resp.turn_latency_sec or lat,
            "llm_calls": resp.llm_calls,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
        })
        time.sleep(4.0)
    return results


def run_hallucination_20() -> List[Dict[str, Any]]:
    print("\n==========================================")
    print("RUNNING 20 HALLUCINATION TESTS")
    print("==========================================")
    yaml_path = Path("tests/hallucination_tests.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    test_cases = data.get("questions", [])

    results = []
    for tc in test_cases:
        qid = tc["id"]
        q = tc["query"]
        cat = tc.get("category", "")
        print(f"\n[{qid}] ({cat}) {q}")

        store = FactStore("runs/test_A_cold_verify")
        agent = CopilotAgent(store, provider="pool", strict_no_fallback=True)
        agent.key_pool.reload_keys()
        t0 = time.time()
        resp = agent.ask(q)
        lat = round(time.time() - t0, 2)

        ans_lower = resp.text.lower()
        forbidden_hits = []
        for tok in tc.get("forbidden_tokens", []):
            if tok.isdigit():
                if re.search(r"(?<!\d)" + re.escape(tok) + r"(?!\d)", ans_lower):
                    forbidden_hits.append(tok)
            else:
                if tok.lower() in ans_lower:
                    forbidden_hits.append(tok)
        required_found = any(k.lower() in ans_lower for k in tc.get("required_keywords", []))

        # Hallucination evaluation
        is_hallucination = len(forbidden_hits) > 0 or not resp.guard_passed
        print(f"Tools called: {resp.tools_called}")
        print(f"Answer: {resp.text}")
        print(f"Guard passed: {resp.guard_passed}, Forbidden hits: {forbidden_hits}")
        print(f"Answer path: {resp.answer_path}, Latency: {lat}s")

        results.append({
            "id": qid,
            "category": cat,
            "query": q,
            "language": resp.language,
            "tools_called": resp.tools_called,
            "tool_outputs": [compact_tool_output(o) for o in resp.tool_outputs],
            "answer": resp.text,
            "guard_result": resp.guard_result,
            "guard_passed": resp.guard_passed,
            "forbidden_hits": forbidden_hits,
            "required_found": required_found,
            "is_hallucination": is_hallucination,
            "provider": resp.provider,
            "model": resp.model,
            "masked_key_id": resp.masked_key_id,
            "answer_path": resp.answer_path,
            "turn_latency_sec": resp.turn_latency_sec or lat,
            "llm_calls": resp.llm_calls,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
        })
        time.sleep(3.5)
    return results


def write_fix4_markdown(results: List[Dict[str, Any]], filepath: Path):
    lines = ["# Fix 4 Verification Test Report\n\n"]
    lines.append(f"**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    lines.append("| Query | Tools Called | Guard Result | Path | Latency | Language |\n")
    lines.append("|---|---|---|---|---|---|\n")
    for r in results:
        tc = ", ".join(r["tools_called"]) or "None"
        gp = "PASSED" if r["guard_passed"] else "VIOLATION"
        lines.append(f"| {r['query']} | `{tc}` | **{gp}** | `{r['answer_path']}` | {r['turn_latency_sec']}s | {r['language']} |\n")

    lines.append("\n## Detailed Transcripts\n\n")
    for r in results:
        lines.append(f"### Query: `{r['query']}`\n")
        lines.append(f"- **Language**: `{r['language']}`\n")
        lines.append(f"- **Tools Called**: `{r['tools_called']}`\n")
        lines.append(f"- **Tool Outputs**:\n```json\n{json.dumps(r['tool_outputs'], indent=2, ensure_ascii=False)}\n```\n")
        lines.append(f"- **Final Answer**:\n> {r['answer'].replace(chr(10), chr(10) + '> ')}\n\n")
        lines.append(f"- **Guard Result**: `{r['guard_result']}`\n")
        lines.append(f"- **Answer Path**: `{r['answer_path']}`\n")
        lines.append(f"- **Provider / Model / Key**: `{r['provider']}` / `{r['model']}` / `{r['masked_key_id']}`\n")
        lines.append(f"- **Turn Latency**: {r['turn_latency_sec']}s (LLM calls: {r['llm_calls']}, prompt tokens: {r['prompt_tokens']}, completion tokens: {r['completion_tokens']})\n\n---\n\n")

    filepath.write_text("".join(lines), encoding="utf-8")
    print(f"Saved Fix 4 report to {filepath}")


def write_heldout_markdown(results: List[Dict[str, Any]], filepath: Path):
    lines = ["# Held-Out v3 Live Evaluation Report (15 Questions)\n\n"]
    lines.append(f"**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
    lines.append("| # | Question | Tools Called | Guard | Path | Latency | Lang |\n")
    lines.append("|---|---|---|---|---|---|---|\n")
    for r in results:
        tc = ", ".join(r["tools_called"]) or "None"
        gp = "PASSED" if r["guard_passed"] else "VIOLATION"
        lines.append(f"| {r['idx']} | {r['query']} | `{tc}` | **{gp}** | `{r['answer_path']}` | {r['turn_latency_sec']}s | {r['language']} |\n")

    lines.append("\n## Full Question Transcripts\n\n")
    for r in results:
        lines.append(f"### Q{r['idx']}: {r['query']}\n\n")
        lines.append(f"- **Language**: `{r['language']}`\n")
        lines.append(f"- **Tools Called**: `{r['tools_called']}`\n")
        lines.append(f"- **Tool Outputs**:\n```json\n{json.dumps(r['tool_outputs'], indent=2, ensure_ascii=False)}\n```\n")
        lines.append(f"- **Final Answer**:\n\n{r['answer']}\n\n")
        lines.append(f"- **Guard Result**: `{r['guard_result']}`\n")
        lines.append(f"- **Answer Path**: `{r['answer_path']}`\n")
        lines.append(f"- **Provider / Model / Key**: `{r['provider']}` / `{r['model']}` / `{r['masked_key_id']}`\n")
        lines.append(f"- **Metrics**: Latency = {r['turn_latency_sec']}s | LLM calls = {r['llm_calls']} | Prompt Tokens = {r['prompt_tokens']} | Completion Tokens = {r['completion_tokens']}\n\n---\n\n")

    filepath.write_text("".join(lines), encoding="utf-8")
    print(f"Saved Held-Out report to {filepath}")


def write_hallucination_markdown(results: List[Dict[str, Any]], filepath: Path):
    lines = ["# Hallucination Guard Benchmark Report (20 Questions)\n\n"]
    lines.append(f"**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n")
    total = len(results)
    passed = sum(1 for r in results if not r["is_hallucination"])
    hallucinated = total - passed
    lines.append(f"**Summary**: {passed}/{total} Passed (Hallucinations: **{hallucinated}** | Target: 0)\n\n")
    lines.append("| ID | Category | Question | Guard | Forbidden Hits | Hallucination? | Latency |\n")
    lines.append("|---|---|---|---|---|---|---|\n")
    for r in results:
        gp = "PASSED" if r["guard_passed"] else "VIOLATION"
        hal = "NO (0)" if not r["is_hallucination"] else "**YES**"
        lines.append(f"| {r['id']} | {r['category']} | {r['query']} | {gp} | {r['forbidden_hits']} | **{hal}** | {r['turn_latency_sec']}s |\n")

    lines.append("\n## Detailed Question Transcripts\n\n")
    for r in results:
        lines.append(f"### {r['id']}: {r['query']} ({r['category']})\n\n")
        lines.append(f"- **Tools Called**: `{r['tools_called']}`\n")
        lines.append(f"- **Final Answer**:\n\n{r['answer']}\n\n")
        lines.append(f"- **Guard Status**: {'PASSED' if r['guard_passed'] else 'VIOLATION'}\n")
        lines.append(f"- **Forbidden Token Hits**: `{r['forbidden_hits']}`\n")
        lines.append(f"- **Answer Path**: `{r['answer_path']}`\n")
        lines.append(f"- **Provider / Model / Key**: `{r['provider']}` / `{r['model']}` / `{r['masked_key_id']}`\n")
        lines.append(f"- **Metrics**: Latency = {r['turn_latency_sec']}s | LLM calls = {r['llm_calls']} | Prompt Tokens = {r['prompt_tokens']} | Completion Tokens = {r['completion_tokens']}\n\n---\n\n")

    filepath.write_text("".join(lines), encoding="utf-8")
    print(f"Saved Hallucination benchmark report to {filepath}")


def main():
    Path("tests").mkdir(parents=True, exist_ok=True)

    # 1. Fix 4 tests
    f4_res = run_fix4_tests()
    write_fix4_markdown(f4_res, Path("tests/fix4_verification.md"))

    print("\n[PAUSE 3s before Held-out 15 suite...]")
    time.sleep(3.0)

    # 2. Heldout 15
    ho_res = run_heldout_15()
    write_heldout_markdown(ho_res, Path("tests/heldout_v3_gemini_verified.md"))

    print("\n[PAUSE 3s before Hallucination suite...]")
    time.sleep(3.0)

    # 3. Hallucination 20
    hal_res = run_hallucination_20()
    write_hallucination_markdown(hal_res, Path("tests/hallucination_report_gemini.md"))

    print("\nALL EVALUATIONS COMPLETE.")


if __name__ == "__main__":
    main()
