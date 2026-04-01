"""
Visual IBCS analyzer using GPT-4o Vision.

Sends rendered slide/page images to Azure OpenAI GPT-4o and asks it to
identify IBCS violations that are only detectable visually:
- Color semantics (U1)
- 3D effects (CK2)
- Chart junk / decorations (CK3)
- Gridlines (SI1)
- Chart borders (SI2)
- Shadows/gradients (SI4)
- Pie charts (E4)
- Inconsistent chart types (U2)
- Correct chart type for data type (E1, E2, E3)
- Legend vs. direct labeling (C2)
- Information density (C1)
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from openai import AzureOpenAI

from ibcs_agent.config import AzureConfig
from ibcs_agent.models.feedback import RuleViolation
from ibcs_agent.rules.ibcs_rules import RULES_BY_ID, get_visual_rules

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for GPT-4o
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du bist ein IBCS (International Business Communication Standards) Experte.
Du analysierst Folien und Seiten aus Präsentationen und Berichten auf Einhaltung der öffentlichen IBCS SUCCESS-Notation.

IBCS SUCCESS steht für:
- SAY: Kommuniziere eine Kernaussage (Titel als Insight-Satz)
- UNIFY: Einheitliche semantische Notation (Farben, Chart-Typen, Skalierungen)
- CONDENSE: Hohe Informationsdichte, kein unnötiger Leerraum
- CHECK: Visuelle Integrität (Achsen bei Null, keine 3D, keine Dekoration)
- EXPRESS: Passende Visualisierung (Linien für Zeitreihen, Balken für Vergleiche)
- SIMPLIFY: Reduktion (keine Gitterlinien, keine Rahmen, keine Schatten)
- STRUCTURE: Klare Struktur (konsistentes Layout, Hierarchie)

Für jede erkannte Verletzung gibst du aus:
- rule_id: Eine der folgenden: S1, S2, U1, U2, U3, U4, C1, C2, CK1, CK2, CK3, CK4, E1, E2, E3, E4, E5, SI1, SI2, SI3, SI4, ST1, ST2, ST3, ST4
- description: Was genau auf dieser Folie verletzt wird (konkret und spezifisch)
- suggestion: Wie es korrigiert werden soll
- element: Welches Element betroffen ist (z.B. "Chart 1", "Tabelle", "Folie gesamt")
- confidence: Deine Sicherheit als Zahl 0.0-1.0

Antworte AUSSCHLIESSLICH mit einem validen JSON-Array. Kein Text davor oder danach.

Beispiel:
[
  {
    "rule_id": "CK2",
    "description": "Das Balkendiagramm in der Mitte der Folie ist als 3D-Variante dargestellt.",
    "suggestion": "Konvertiere das Chart in ein 2D-Balkendiagramm.",
    "element": "Chart 1 (Mitte)",
    "confidence": 0.95
  }
]

Falls keine Verstöße erkennbar sind, antworte mit einem leeren Array: []
"""

USER_PROMPT_TEMPLATE = """Analysiere diese Folie/Seite auf IBCS-Verstöße.

Seitenkontext (optional):
- Seitennummer: {page_number}
- Erkannter Titel: {page_title}
- Dateityp: {file_type}

Prüfe insbesondere:
1. Farb-Semantik (IBCS: Ist=schwarz/dunkel, Plan=schraffiert, Vorjahr=hellgrau)
2. 3D-Effekte in Charts
3. Tortendiagramme mit mehr als 2 Segmenten
4. Achsen die nicht bei Null beginnen (bei Balken/Säulen)
5. Übermäßige Gitterlinien oder Chart-Rahmen
6. Schatten, Farbverläufe, Texturen auf Datenelementen
7. Legenden statt direkter Beschriftung
8. Falsche Chart-Typen (z.B. Balken für Zeitreihen statt Linie)
9. Chart-Junk (Cliparts, Bilder ohne Informationswert)
10. Niedrige Informationsdichte / viel Leerraum

Antworte nur mit JSON."""


# ---------------------------------------------------------------------------
# Visual analyzer class
# ---------------------------------------------------------------------------

class VisualAnalyzer:
    """Analyzes slide/page images using GPT-4o Vision for IBCS violations."""

    def __init__(self, azure_config: AzureConfig):
        self.config = azure_config
        self._client: Optional[AzureOpenAI] = None

    def _get_client(self) -> AzureOpenAI:
        if self._client is None:
            self._client = AzureOpenAI(
                azure_endpoint=self.config.openai_endpoint,
                api_key=self.config.openai_api_key,
                api_version=self.config.openai_api_version,
            )
        return self._client

    def analyze_image(
        self,
        image_base64: str,
        page_number: int,
        page_title: Optional[str],
        file_type: str,
    ) -> List[RuleViolation]:
        """
        Analyze a single slide/page image for IBCS violations.

        Args:
            image_base64: Base64-encoded PNG image
            page_number: 1-based page/slide number
            page_title: Inferred title of the page
            file_type: "pptx", "pdf", or "xlsx"

        Returns:
            List of RuleViolation objects found visually
        """
        client = self._get_client()

        user_message = USER_PROMPT_TEMPLATE.format(
            page_number=page_number,
            page_title=page_title or "unbekannt",
            file_type=file_type,
        )

        try:
            response = client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": user_message},
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,  # Low temperature for consistent, factual analysis
                response_format={"type": "json_object"} if "json_object" in str(self.config.model_name) else None,
            )
        except Exception as e:
            logger.error(f"GPT-4o Vision call failed for page {page_number}: {e}")
            return []

        raw_content = response.choices[0].message.content.strip()
        return self._parse_violations(raw_content, page_number)

    def _parse_violations(self, raw_json: str, page_number: int) -> List[RuleViolation]:
        """Parse GPT-4o response into RuleViolation objects."""
        violations: List[RuleViolation] = []

        # Extract JSON array from response (handle markdown fences)
        json_str = raw_json
        if "```json" in raw_json:
            json_str = raw_json.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_json:
            json_str = raw_json.split("```")[1].split("```")[0].strip()

        try:
            # Handle both array and object with array wrapper
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                # GPT may wrap in {"violations": [...]}
                parsed = parsed.get("violations", parsed.get("items", []))
            if not isinstance(parsed, list):
                logger.warning(f"Page {page_number}: Unexpected JSON structure from GPT-4o")
                return []
        except json.JSONDecodeError as e:
            logger.warning(f"Page {page_number}: Could not parse GPT-4o response as JSON: {e}")
            logger.debug(f"Raw response: {raw_json[:500]}")
            return []

        for item in parsed:
            rule_id = item.get("rule_id", "").strip().upper()
            if rule_id not in RULES_BY_ID:
                logger.debug(f"Unknown rule_id from GPT-4o: {rule_id}")
                continue

            confidence = float(item.get("confidence", 0.5))
            if confidence < 0.4:
                # Skip low-confidence findings
                continue

            rule = RULES_BY_ID[rule_id]
            violations.append(RuleViolation(
                rule_id=rule.id,
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                description=item.get("description", rule.violation_hint),
                suggestion=item.get("suggestion", rule.suggestion_template),
                source="visual",
                element=item.get("element"),
            ))

        return violations

    def analyze_pages(
        self,
        pages: list,
        file_type: str,
        timeout_sec: int = 60,
    ) -> List[List[RuleViolation]]:
        """
        Analyze multiple pages/slides in sequence.

        Args:
            pages: List of page data objects (SlideData, PDFPageData, or SheetData)
            file_type: "pptx", "pdf", or "xlsx"
            timeout_sec: Per-page timeout

        Returns:
            List of violation lists, one per page (same order as input)
        """
        results: List[List[RuleViolation]] = []

        for page in pages:
            image_b64 = getattr(page, "image_base64", None)
            page_num = (
                getattr(page, "slide_number", None)
                or getattr(page, "page_number", None)
                or getattr(page, "sheet_index", 0) + 1
            )
            title = getattr(page, "title", None)

            if not image_b64:
                logger.info(f"Page {page_num}: No image available, skipping visual analysis")
                results.append([])
                continue

            violations = self.analyze_image(
                image_base64=image_b64,
                page_number=page_num,
                page_title=title,
                file_type=file_type,
            )
            results.append(violations)
            logger.info(f"Page {page_num}: {len(violations)} visual violations found")

        return results
