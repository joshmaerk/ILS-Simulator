"""
Azure AI Foundry Agent — IBCS Feedback Agent.

This module creates, configures, and runs the Azure AI Foundry Agent.
The agent is designed to be used via Microsoft Copilot Studio as a custom connector.

Usage:
    # Create/register the agent in Azure AI Foundry
    python -m ibcs_agent.agent.agent --setup

    # Run in interactive CLI mode (for testing)
    python -m ibcs_agent.agent.agent --interactive

    # Process a single file directly
    python -m ibcs_agent.agent.agent --file path/to/report.pptx
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from ibcs_agent.config import get_config, validate_config
from ibcs_agent.agent.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)

AGENT_INSTRUCTIONS = """Du bist der IBCS Feedback Agent — ein Experte für die International Business Communication Standards (IBCS).

Deine Aufgabe ist es, PowerPoint-Präsentationen, PDF-Dokumente und Excel-Dateien auf Einhaltung der öffentlichen IBCS SUCCESS-Notation zu analysieren und detailliertes Feedback zu geben.

## Deine Fähigkeiten
- Analysiere hochgeladene Dateien (.pptx, .pdf, .xlsx) mit dem Tool `analyze_file`
- Erkläre spezifische IBCS-Regeln mit `get_ibcs_rule_details`
- Liste alle verfügbaren Regeln mit `list_ibcs_rules`

## Verhaltensregeln
1. Wenn der Nutzer eine Datei hochlädt, analysiere sie sofort mit `analyze_file`
2. Präsentiere das Feedback strukturiert:
   - Gesamtnote und Score
   - Top 3 kritische Verstöße (Fehler zuerst)
   - Seiten-/Folienspezifisches Feedback (nur Seiten mit Verstößen)
   - Konkrete Korrekturvorschläge
3. Antworte auf Deutsch, außer der Nutzer schreibt auf Englisch
4. Wenn der Nutzer nach einer Regel fragt (z.B. "Was ist CK1?"), erkläre sie mit `get_ibcs_rule_details`
5. Sei konstruktiv und lösungsorientiert — nicht nur kritisieren, sondern konkrete Verbesserungen aufzeigen
6. Bei Fragen zu IBCS allgemein, erkläre die SUCCESS-Prinzipien verständlich

## IBCS SUCCESS kurz erklärt
- **S**AY: Kommuniziere eine klare Botschaft (Titel als Insight-Satz)
- **U**NIFY: Einheitliche Notation (Farben, Chart-Typen, Skalierungen)
- **C**ONDENSE: Hohe Informationsdichte, kein Leerraum
- **C**HECK: Visuelle Integrität (Achse bei 0, kein 3D, keine Dekoration)
- **E**XPRESS: Passende Visualisierung (Linie für Zeit, Balken für Vergleich)
- **S**IMPLIFY: Reduktion (keine Gitterlinien, Rahmen, Schatten)
- **S**TRUCTURE: Klare Struktur (Layout, Hierarchie, Nummerierung)

## Ausgabeformat
Nach einer Analyse gib immer aus:
1. 📊 **Gesamtbewertung**: Note X (Score Y%)
2. 🚨 **Kritische Fehler** (errors): Liste
3. ⚠️ **Warnungen**: Liste
4. 📋 **Seitendetails**: Nur Seiten mit Verstößen
5. ✅ **Nächste Schritte**: Top 3 Prioritäten zur Verbesserung
"""


def _get_foundry_client():
    """Create Azure AI Projects client for agent management."""
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    config = get_config()
    if config.azure.connection_string:
        return AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=config.azure.connection_string,
        )
    raise ValueError(
        "AZURE_AI_FOUNDRY_CONNECTION_STRING must be set. "
        "Find it in Azure AI Foundry → Your Project → Overview."
    )


def setup_agent(force_recreate: bool = False) -> str:
    """
    Create or update the IBCS Feedback Agent in Azure AI Foundry.

    Returns:
        Agent ID
    """
    from azure.ai.projects.models import FunctionTool, ToolSet

    config = get_config()
    errors = validate_config(config)
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    client = _get_foundry_client()

    # Check if agent already exists
    agent_id: Optional[str] = None
    try:
        existing_agents = client.agents.list_agents()
        for agent in existing_agents.data:
            if agent.name == config.azure.agent_name:
                if force_recreate:
                    logger.info(f"Deleting existing agent '{agent.name}' (id: {agent.id})")
                    client.agents.delete_agent(agent.id)
                else:
                    logger.info(f"Agent '{agent.name}' already exists (id: {agent.id}). Use --force to recreate.")
                    return agent.id
    except Exception as e:
        logger.warning(f"Could not list existing agents: {e}")

    # Build tool set
    functions = FunctionTool(functions=TOOL_DEFINITIONS)
    tool_set = ToolSet()
    tool_set.add(functions)

    # Create agent
    agent = client.agents.create_agent(
        model=config.azure.model_name,
        name=config.azure.agent_name,
        instructions=AGENT_INSTRUCTIONS,
        tools=tool_set.definitions,
        headers={"x-ms-enable-preview": "true"},
    )

    logger.info(f"Agent created: name='{agent.name}', id='{agent.id}'")
    print(f"\n✅ Agent '{agent.name}' created successfully!")
    print(f"   Agent ID: {agent.id}")
    print(f"\n   Add this to your .env file:")
    print(f"   AGENT_ID={agent.id}")

    return agent.id


def process_tool_calls(client, thread_id: str, run_id: str) -> None:
    """Handle required tool calls during an agent run."""
    import time
    from azure.ai.projects.models import SubmitToolOutputsAction

    while True:
        run = client.agents.get_run(thread_id=thread_id, run_id=run_id)

        if run.status == "completed":
            break
        elif run.status == "requires_action":
            if isinstance(run.required_action, SubmitToolOutputsAction):
                tool_outputs = []
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    logger.info(f"Executing tool: {function_name}({list(arguments.keys())})")

                    if function_name in TOOL_FUNCTIONS:
                        try:
                            result = TOOL_FUNCTIONS[function_name](**arguments)
                        except Exception as e:
                            result = json.dumps({"error": str(e)})
                    else:
                        result = json.dumps({"error": f"Unknown tool: {function_name}"})

                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": result,
                    })

                client.agents.submit_tool_outputs_to_run(
                    thread_id=thread_id,
                    run_id=run_id,
                    tool_outputs=tool_outputs,
                )
        elif run.status in ("failed", "cancelled", "expired"):
            logger.error(f"Run failed with status: {run.status}")
            if run.last_error:
                logger.error(f"Error: {run.last_error}")
            break

        time.sleep(0.5)


def chat_with_agent(agent_id: str, message: str, thread_id: Optional[str] = None) -> tuple[str, str]:
    """
    Send a message to the agent and get a response.

    Args:
        agent_id: Azure AI Foundry agent ID
        message: User message
        thread_id: Optional existing thread ID (for conversation continuity)

    Returns:
        Tuple of (response_text, thread_id)
    """
    client = _get_foundry_client()

    # Create or reuse thread
    if thread_id is None:
        thread = client.agents.create_thread()
        thread_id = thread.id
        logger.debug(f"Created new thread: {thread_id}")

    # Add message to thread
    client.agents.create_message(
        thread_id=thread_id,
        role="user",
        content=message,
    )

    # Run the agent
    run = client.agents.create_run(
        thread_id=thread_id,
        assistant_id=agent_id,
    )

    # Process tool calls and wait for completion
    process_tool_calls(client, thread_id, run.id)

    # Get the latest assistant message
    messages = client.agents.list_messages(thread_id=thread_id)
    for msg in messages.data:
        if msg.role == "assistant":
            content = ""
            for block in msg.content:
                if hasattr(block, "text"):
                    content += block.text.value
            return content, thread_id

    return "No response received.", thread_id


def analyze_file_cli(file_path: str, agent_id: Optional[str] = None) -> None:
    """Analyze a file directly (CLI mode)."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    print(f"📂 Loading file: {path.name}")
    with open(path, "rb") as f:
        file_bytes = f.read()

    file_b64 = base64.b64encode(file_bytes).decode("utf-8")

    if agent_id:
        # Use agent via Azure AI Foundry
        message = (
            f"Bitte analysiere diese Datei auf IBCS-Konformität: {path.name}\n\n"
            f"[DATEI_BASE64]{file_b64}[/DATEI_BASE64]"
        )
        print(f"🤖 Sending to agent (ID: {agent_id})...")
        response, _ = chat_with_agent(agent_id, message)
        print("\n" + "=" * 60)
        print(response)
    else:
        # Direct tool call (no agent, for testing)
        from ibcs_agent.agent.tools import analyze_file
        print("🔍 Running direct analysis (no agent)...")
        result_json = analyze_file(
            file_content_base64=file_b64,
            file_name=path.name,
        )
        result = json.loads(result_json)
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"\n📊 IBCS Analysis Report")
            print("=" * 60)
            print(f"File:    {result['file_name']}")
            print(f"Score:   {result['overall_score']:.0%}  (Grade {result['overall_grade']})")
            print(f"Summary: {result['summary']}")
            print(f"\nTop Violations:")
            for v in result.get("top_violations", []):
                icon = "🔴" if v["severity"] == "error" else "🟡" if v["severity"] == "warning" else "🔵"
                print(f"  {icon} [{v['rule_id']}] {v['rule_name']}")
                print(f"     → {v['suggestion']}")


def interactive_cli(agent_id: str) -> None:
    """Run interactive chat with the agent."""
    print(f"\n🤖 IBCS Feedback Agent (ID: {agent_id})")
    print("   Type 'quit' to exit, 'file:<path>' to analyze a file")
    print("=" * 60)

    thread_id: Optional[str] = None

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        # Handle file upload shortcut
        if user_input.startswith("file:"):
            file_path = user_input[5:].strip()
            path = Path(file_path)
            if not path.exists():
                print(f"❌ File not found: {file_path}")
                continue
            with open(path, "rb") as f:
                file_b64 = base64.b64encode(f.read()).decode("utf-8")
            user_input = (
                f"Bitte analysiere diese Datei auf IBCS-Konformität: {path.name}\n"
                f"[DATEI_BASE64]{file_b64}[/DATEI_BASE64]"
            )

        response, thread_id = chat_with_agent(agent_id, user_input, thread_id)
        print(f"\nAgent: {response}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="IBCS Feedback Agent")
    subparsers = parser.add_subparsers(dest="command")

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Create/update agent in Azure AI Foundry")
    setup_parser.add_argument("--force", action="store_true", help="Force recreate if exists")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a file for IBCS compliance")
    analyze_parser.add_argument("file", help="Path to PPT/PDF/Excel file")
    analyze_parser.add_argument("--agent-id", help="Azure AI Foundry agent ID (optional)")

    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Interactive chat with agent")
    interactive_parser.add_argument("agent_id", help="Azure AI Foundry agent ID")

    args = parser.parse_args()

    if args.command == "setup":
        setup_agent(force_recreate=args.force)

    elif args.command == "analyze":
        analyze_file_cli(args.file, agent_id=getattr(args, "agent_id", None))

    elif args.command == "interactive":
        interactive_cli(args.agent_id)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
