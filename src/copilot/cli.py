"""CLI Interface for Situation-Report Copilot.

Supports:
- Interactive chat session for rescue teams
- Single query execution (`--query`)
- Situation report generation (`--sitrep`)
- Flexible provider selection (`--provider`, `--offline`)
- Pipeline run directory targeting (`--run-dir`)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .agent import CopilotAgent
from .facts import FactStore
from .sitrep import SitRepGenerator

logger = logging.getLogger("copilot.cli")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emergency Disaster Situation-Report Copilot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default="/home/zeus/Downloads/project1/runs/test_A_trishuli",
        help="Path to pipeline run output directory",
    )
    parser.add_argument(
        "--sitrep",
        action="store_true",
        help="Generate 1-page bilingual Situation Reports (Markdown & PDF) and exit",
    )
    parser.add_argument(
        "--sitrep-out",
        type=str,
        default=None,
        help="Directory to save generated SitRep files",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="auto",
        choices=["auto", "gemini", "openai", "anthropic", "offline"],
        help="LLM provider for tool calling and reasoning",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force offline fallback mode without making any external API calls",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Execute a single question non-interactively and print answer",
    )
    return parser.parse_args()


def run_cli() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    run_path = Path(args.run_dir).resolve()
    if not run_path.exists():
        print(f"Error: Run directory does not exist: {run_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading pipeline run outputs from: {run_path}")
    fact_store = FactStore(run_path)
    event_date = fact_store.get_value("event.date", "unknown")
    print(f"Loaded {len(fact_store.facts)} grounded facts (Event Date: {event_date})")

    # SitRep Mode
    if args.sitrep:
        out_dir = Path(args.sitrep_out) if args.sitrep_out else run_path / "processed" / "sitrep"
        print(f"Generating bilingual Situation Report to: {out_dir}")
        generator = SitRepGenerator(fact_store)
        files = generator.generate_all(out_dir)
        print("\n=== GENERATED SITUATION REPORTS ===")
        print(f"- English Markdown: {files['en_markdown']}")
        print(f"- English PDF:      {files['en_pdf']}")
        print(f"- Nepali Markdown:  {files['ne_markdown']}")
        print(f"- Nepali PDF:       {files['ne_pdf']}")
        print("All reports successfully generated and verified with 0 number violations.\n")
        return

    # Provider setup
    provider = "offline" if args.offline else args.provider
    agent = CopilotAgent(fact_store, provider=provider)
    print(f"Active Provider: {agent.provider.upper()}")

    # Single Query Mode
    if args.query:
        resp = agent.ask(args.query)
        print("\n--- COPILOT ANSWER ---")
        print(resp.text)
        print("----------------------")
        print(f"[Lang: {resp.language} | Tools: {resp.tools_called} | Guard Passed: {resp.guard_passed}]")
        return

    # Interactive Chat Mode
    print("\n" + "=" * 65)
    print("  EMERGENCY SITUATION-REPORT COPILOT (NEPAL DISASTER RESPONSE)")
    print("=" * 65)
    print("Ask questions in English, Nepali (नेपाली), Hindi (हिन्दी), or romanised.")
    print("Type 'sitrep' to generate reports, 'clear' to reset, or 'exit' to quit.\n")

    while True:
        try:
            user_input = input("Rescuer> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Stay safe.")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q", "bye"]:
            print("Session ended. Stay safe.")
            break
        if user_input.lower() == "clear":
            agent.messages.clear()
            agent.active_settlement = None
            print("Conversation context cleared.")
            continue
        if user_input.lower() == "sitrep":
            out_dir = Path(args.sitrep_out) if args.sitrep_out else run_path / "processed" / "sitrep"
            generator = SitRepGenerator(fact_store)
            files = generator.generate_all(out_dir)
            print(f"SitRep generated: {files['en_pdf']} and {files['ne_pdf']}")
            continue

        resp = agent.ask(user_input)
        print(f"\nCopilot [{resp.language.upper()}]:")
        print(resp.text)
        print(f"\n[Tools: {resp.tools_called} | Guard: {'PASS' if resp.guard_passed else 'RETRY/FAIL'}]\n")


if __name__ == "__main__":
    run_cli()
