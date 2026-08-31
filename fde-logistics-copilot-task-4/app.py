#!/usr/bin/env python3
"""Logistics Operations Copilot - command line interface.

Run the assignment prototype with no API keys and no infrastructure::

    python app.py                     # interactive copilot
    python app.py --demo              # run the five demo queries and exit
    python app.py --query "..."       # answer one query and exit

Everything the copilot can do is available through :func:`agent.handle_query`;
this module only handles terminal input/output.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional

from agent import INTENT_PRICING, handle_query
from core.config import APP_NAME, APP_VERSION, CLIENT_NAME, ENVIRONMENT, LOG_FILE
from services.monitoring_service import monitoring

EXAMPLE_QUERIES: List[str] = [
    "Where is shipment SH1024?",
    "Which shipments are delayed?",
    "What is our delivery policy?",
    "Calculate delivery cost.",
    "Escalate this issue.",
]

HELP_TEXT = """
Commands
  help     show this help
  examples show example questions
  stats    show monitoring metrics for this session
  log      show where the monitoring log is written
  exit     leave the copilot (also: quit, q)

Example questions
""" + "\n".join(f"  - {q}" for q in EXAMPLE_QUERIES)

SEPARATOR = "-" * 70


def print_banner() -> None:
    """Print the copilot banner."""
    print("=" * 70)
    print(f" {APP_NAME} v{APP_VERSION}")
    print(f" Client: {CLIENT_NAME}   |   Environment: {ENVIRONMENT}")
    print("=" * 70)
    print(" Ask an operations question in plain English.")
    print(" Try:")
    for query in EXAMPLE_QUERIES:
        print(f"   - {query}")
    print(" Type 'help' for commands, 'exit' to quit.")
    print("=" * 70)


def print_result(result: Dict[str, Any]) -> None:
    """Render one agent result for the terminal."""
    status = "OK" if result["success"] else "NEEDS ATTENTION"
    print(SEPARATOR)
    print(f"intent: {result['intent']} | tool: {result['tool_selected']} | "
          f"status: {status} | {result['execution_time_ms']:.2f} ms")
    print(SEPARATOR)
    print(result["response"])
    print()


def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user, returning ``default`` on empty input or EOF."""
    try:
        answer = input(prompt).strip()
    except EOFError:
        return default
    return answer or default


def collect_pricing_inputs() -> Optional[Dict[str, Any]]:
    """Interactively collect weight / distance / priority for a quote.

    Returns ``None`` if the employee cancels, so the copilot can simply
    continue instead of failing.
    """
    print("I need three inputs for a delivery quote (press Enter to cancel).")
    weight = _ask("  Weight (kg): ")
    if not weight:
        return None
    distance = _ask("  Distance (km): ")
    if not distance:
        return None
    priority = _ask("  Priority [standard/express/urgent] (default standard): ", "standard")
    return {"weight": weight, "distance": distance, "priority": priority}


def answer(query: str, interactive: bool = False) -> Dict[str, Any]:
    """Answer one query, optionally collecting missing pricing inputs."""
    result = handle_query(query)

    needs_input = isinstance(result.get("data"), dict) and result["data"].get("needs_input")
    if interactive and result["intent"] == INTENT_PRICING and needs_input:
        print_result(result)
        context = collect_pricing_inputs()
        if context is None:
            print("Quote cancelled.\n")
            return result
        return handle_query(query, context=context)

    return result


def print_stats() -> None:
    """Print monitoring metrics collected during this session."""
    snapshot = monitoring.snapshot()
    print(SEPARATOR)
    print("Session monitoring metrics")
    for key, value in snapshot.items():
        print(f"  {key:24}: {value}")
    print(f"  {'log_file':24}: {LOG_FILE}")
    print(SEPARATOR + "\n")


def run_interactive() -> int:
    """Run the interactive copilot loop."""
    print_banner()
    while True:
        try:
            query = input("\ncopilot> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0

        if not query:
            continue

        command = query.lower()
        if command in {"exit", "quit", "q"}:
            print("Goodbye.")
            return 0
        if command == "help":
            print(HELP_TEXT)
            continue
        if command == "examples":
            print("\n".join(f"  - {q}" for q in EXAMPLE_QUERIES))
            continue
        if command == "stats":
            print_stats()
            continue
        if command == "log":
            print(f"Monitoring log: {LOG_FILE}")
            continue

        print_result(answer(query, interactive=True))


def run_demo() -> int:
    """Run the five mandatory demo queries plus the unknown-query fallback."""
    print_banner()
    demo_queries = EXAMPLE_QUERIES + ["Book me a flight to Paris"]
    for query in demo_queries:
        print(f"\ncopilot> {query}")
        print_result(handle_query(query))
    print_stats()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=f"{APP_NAME} CLI")
    parser.add_argument("--query", "-q", help="answer a single query and exit")
    parser.add_argument("--demo", action="store_true", help="run the demo queries and exit")
    args = parser.parse_args(argv)

    if args.demo:
        return run_demo()
    if args.query:
        print_result(answer(args.query))
        return 0
    return run_interactive()


if __name__ == "__main__":
    sys.exit(main())
