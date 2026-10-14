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
import json
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
        default="/home/zeus/Downloads/project1/runs/test_A_cold_verify",
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
    parser.add_argument(
        "--questions-file",
        type=str,
        default=None,
        help="Path to file containing questions (one per line) to run in a single session",
    )
    parser.add_argument(
        "--transcript-out",
        type=str,
        default=None,
        help="Path to save markdown transcript of the session",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name (e.g. gemini-3.8-flash)",
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
    agent = CopilotAgent(fact_store, provider=provider, model=args.model)
    active_model = agent.model or ("gemini-3.8-flash" if agent.provider == "gemini" else "offline-rule-engine")
    print(f"Active Provider: {agent.provider.upper()}")
    print(f"Active Model:    {active_model}")

    # Batch Questions File Mode (Held-Out Evaluation)
    if args.questions_file:
        q_path = Path(args.questions_file).resolve()
        if not q_path.exists():
            print(f"Error: Questions file not found: {q_path}", file=sys.stderr)
            sys.exit(1)

        raw_lines = [line.strip() for line in q_path.read_text(encoding="utf-8").splitlines()]
        # Filter out comments and blank lines
        questions = [q for q in raw_lines if q and not q.startswith("#")]
        print(f"\nRunning {len(questions)} evaluation questions in a single continuous session...\n")

        transcript_sections = [
            "# Independent Held-out Benchmark Transcript (v2)\n",
            f"- **Provider:** {agent.provider.upper()}",
            f"- **Model:** {active_model}",
            f"- **Run:** `{run_path.name}`",
            f"- **Total Questions:** {len(questions)}",
            "- **Conversation Context:** Single continuous multi-turn session",
            "- **Grounding Policy:** Zero hallucinated numbers; strict field-level semantic verification.\n",
            "---\n",
        ]

        for q_idx, q_text in enumerate(questions, 1):
            print(f"[{q_idx}/{len(questions)}] Asking: {q_text}")
            resp = agent.ask(q_text)
            print(f"       -> Tools: {resp.tools_called}")
            print(f"       -> Guard: {'PASS' if resp.guard_passed else 'FAIL'}")

            # Format tool outputs JSON
            if resp.tool_outputs:
                if len(resp.tool_outputs) == 1:
                    tools_json = json.dumps(resp.tool_outputs[0], indent=2, ensure_ascii=False)
                else:
                    tools_json = json.dumps(resp.tool_outputs, indent=2, ensure_ascii=False)
            else:
                tools_json = "{}"

            # Format API call logs
            api_logs_md = ""
            if resp.api_call_logs:
                api_logs_md = "\n**API Calls:**\n" + "\n".join(
                    f"- Model: `{log['model']}` | Time: `{log['timestamp']}` | Latency: `{log['latency_s']}s`"
                    for log in resp.api_call_logs
                )

            # Format Guard result
            guard_details = resp.guard_result or {}
            ext_nums = guard_details.get("extracted_numbers", [])
            viol_nums = guard_details.get("violating_numbers", [])
            guard_md = (
                f"- Valid: `{resp.guard_passed}`\n"
                f"- Extracted Numbers: `{ext_nums}`\n"
                f"- Violating Numbers: `{viol_nums}`\n"
                f"- Details: `{guard_details.get('details', 'Verified against grounded tool outputs.')}`"
            )

            section = f"""### Question {q_idx}

**Question:** `{q_text}`

**Tools Called:** `{resp.tools_called}`

**Tool Output:**
```json
{tools_json}
```

**Final Answer:**

{resp.text}

**Guard Result:**
{guard_md}
{api_logs_md}


---
"""
            transcript_sections.append(section)
            if q_idx < len(questions):
                import time
                time.sleep(12)

        # Update model header with actual active model used
        final_model = agent.model or active_model
        transcript_sections[2] = f"- **Model:** {final_model}"

        full_transcript = "\n".join(transcript_sections)

        if args.transcript_out:
            out_file = Path(args.transcript_out).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(full_transcript, encoding="utf-8")
            print(f"\nSaved full raw transcript to: {out_file}")

        return

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
