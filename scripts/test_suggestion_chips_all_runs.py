#!/usr/bin/env python3
import sys
import re
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.copilot.facts import FactStore
from src.copilot.agent import CopilotAgent

RUNS = [
    "test_A_cold_verify",
    "test_B_cold_verify",
    "practice_assam_event",
    "practice_assam_noevent",
    "practice_sikkim_event",
    "practice_sikkim_noevent",
    "run_20261013_194053_chamoli_disaster_2021",
]

CHIPS = [
    "Which settlements need air access?",
    "Which bridges should be inspected first?",
    "Is the main road open?",
    "What should I not trust?",
]

def clean_first_line(text: str) -> str:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    # Filter out header prefixes if present to get the actual substance
    res_lines = []
    for l in lines:
        if l.startswith("[") and l.endswith("]"):
            continue
        res_lines.append(l)
    first = res_lines[0] if res_lines else lines[0]
    # Remove markdown formatting like bolding or bullets if needed, but keep readable
    return first.replace("|", "\\|")

def main():
    print("# Suggestion Chips Evaluation on 7 Verified Runs\n")

    for mode in ["live", "offline"]:
        print(f"## Evaluation Mode: {mode.upper()}\n")
        print("| Run ID | Suggestion Chip | Answer Path | First Line of Answer |")
        print("|---|---|---|---|")

        for run_id in RUNS:
            run_path = ROOT / "runs" / run_id
            if not run_path.exists():
                print(f"| {run_id} | ALL | error | Run path {run_path} not found |")
                continue

            fs = FactStore(run_path)

            for chip in CHIPS:
                try:
                    if mode == "live":
                        agent = CopilotAgent(fs, provider="auto")
                    else:
                        agent = CopilotAgent(fs, provider="offline")

                    resp = agent.ask(chip)
                    path = resp.answer_path or mode
                    first_line = clean_first_line(resp.text)
                    print(f"| `{run_id}` | {chip} | `{path}` | {first_line} |")
                except Exception as e:
                    print(f"| `{run_id}` | {chip} | `error` | Exception: {e} |")

        print("\n")

if __name__ == "__main__":
    main()
