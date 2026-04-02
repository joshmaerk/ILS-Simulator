"""
Response consolidator.
Merges responses from multiple expert agents into a coherent answer.
"""

from __future__ import annotations

# Human-readable names for attribution headers
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "strategist": "Stratege",
    "change_manager": "Change Manager",
    "communications_expert": "Kommunikationsexperte",
    "controller": "Controller",
    "hr_developer": "Personalentwickler",
    "leadership_coach": "Leadership Coach",
    "project_manager": "Projektmanager",
    "program_manager": "Programm-Manager",
    "legal_advisor": "Rechtsberater",
    "innovation_scout": "Innovations-Scout",
}


def consolidate_responses(responses: dict[str, str]) -> str:
    """
    Merge multiple agent responses into a single structured answer.

    If only one agent responded, return its response directly without headers.
    If multiple agents responded, add attribution headers for each.
    """
    if not responses:
        return "Es konnte keine Antwort generiert werden."

    if len(responses) == 1:
        return next(iter(responses.values()))

    # Multiple agents: add section headers with attribution
    sections = []
    for agent_name, response in responses.items():
        display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name.title())
        sections.append(f"### {display_name}\n\n{response.strip()}")

    combined = "\n\n---\n\n".join(sections)
    agent_names = [AGENT_DISPLAY_NAMES.get(n, n) for n in responses]
    footer = f"\n\n---\n*Beantwortet durch: {' + '.join(agent_names)}*"
    return combined + footer
