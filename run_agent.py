"""
OpsPilot AI — Run Agent
CLI interface to execute IT admin tasks via browser automation.

Usage:
    python run_agent.py --task "Reset password for john@company.com"
    python run_agent.py  # Interactive mode
"""

import asyncio
import argparse
import sys
import os
import logging

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.logging import RichHandler
from config import config
from agent.llm_wrapper import LLMWrapper
from agent.browser_controller import BrowserController
from agent.agent import OpsPilotAgent

console = Console()


def setup_logging():
    """Configure rich logging for beautiful console output."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_path=False,
        )],
    )


def get_llm() -> LLMWrapper:
    """Initialize the LLM wrapper based on config."""
    provider = config.LLM_PROVIDER

    if provider == "openai":
        api_key = config.OPENAI_API_KEY
        model = config.OPENAI_MODEL
        if not api_key or api_key.startswith("sk-your"):
            console.print("[red]❌ OPENAI_API_KEY not set. Please set it in .env file.[/red]")
            sys.exit(1)
    elif provider == "anthropic":
        api_key = config.ANTHROPIC_API_KEY
        model = config.ANTHROPIC_MODEL
        if not api_key or api_key.startswith("sk-ant-your"):
            console.print("[red]❌ ANTHROPIC_API_KEY not set. Please set it in .env file.[/red]")
            sys.exit(1)
    else:
        console.print(f"[red]❌ Unknown LLM provider: '{provider}'[/red]")
        sys.exit(1)

    return LLMWrapper(provider=provider, api_key=api_key, model=model)


async def run_task(task: str):
    """Execute a single task."""
    # Initialize components
    llm = get_llm()
    browser = BrowserController()

    try:
        # Start browser
        await browser.start(headless=config.AGENT_HEADLESS)

        # Create agent
        agent = OpsPilotAgent(
            llm=llm,
            browser=browser,
            admin_url=config.ADMIN_PANEL_URL,
            max_iterations=config.AGENT_MAX_ITERATIONS,
        )

        # Execute task
        result = await agent.execute_task(task)

        # Display result
        if result["success"]:
            console.print(Panel(
                f"[green]✅ {result['message']}[/green]\n"
                f"[dim]Completed in {result.get('iterations', '?')} iterations[/dim]",
                title="Task Completed",
                border_style="green",
            ))
        else:
            console.print(Panel(
                f"[red]❌ {result['message']}[/red]\n"
                f"[dim]Stopped after {result.get('iterations', '?')} iterations[/dim]",
                title="Task Failed",
                border_style="red",
            ))

        return result

    finally:
        await browser.stop()


async def interactive_mode():
    """Run the agent in interactive REPL mode."""
    console.print(Panel(
        "[bold cyan]OpsPilot AI — Autonomous IT Admin Agent[/bold cyan]\n\n"
        "[dim]Enter natural language IT support requests.\n"
        "Type 'quit' or 'exit' to stop.[/dim]\n\n"
        "[yellow]Example prompts:[/yellow]\n"
        "  • Reset password for john@company.com\n"
        "  • Create a new user jane@company.com as admin\n"
        "  • Disable user mark@company.com\n"
        "  • If sarah@company.com exists, reset password, else create user",
        title="⚡ OpsPilot AI",
        border_style="blue",
    ))

    while True:
        console.print()
        try:
            task = console.input("[bold cyan]opspilot>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break

        if not task:
            continue
        if task.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye! 👋[/dim]")
            break

        await run_task(task)


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="OpsPilot AI — Autonomous IT Admin Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_agent.py --task "Reset password for john@company.com"
  python run_agent.py --task "Create a new user jane@company.com as admin"
  python run_agent.py --task "Disable user mark@company.com"
  python run_agent.py  # Start interactive mode
        """,
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        help="Natural language IT support task to execute",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )

    args = parser.parse_args()

    if args.headless:
        config.AGENT_HEADLESS = True

    if args.task:
        asyncio.run(run_task(args.task))
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
