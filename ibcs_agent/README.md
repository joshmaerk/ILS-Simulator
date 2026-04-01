# IBCS Feedback Agent

Ein Azure AI Foundry Agent, der PowerPoint-, PDF- und Excel-Dateien auf Einhaltung der **IBCS SUCCESS**-Standards analysiert und detailliertes Feedback mit Korrekturvorschlägen liefert.

## Features

- **Dateiformate**: `.pptx`, `.pdf`, `.xlsx`
- **Analyse**: Metadaten (regelbasiert) + Visuelle Analyse (GPT-4o Vision)
- **IBCS-Regelwerk**: Alle 7 SUCCESS-Kategorien (25+ Regeln)
- **Output**: Strukturierter JSON-Report mit seitenspezifischem Feedback und Compliance-Score
- **Integration**: Microsoft Copilot Studio via Custom Connector

---

## Schnellstart

### 1. Voraussetzungen

- Python 3.11+
- Azure AI Foundry Projekt (eingerichtet)
- Azure OpenAI Deployment mit GPT-4o (Vision-fähig)
- Für PDF-Rendering: `poppler-utils` (`sudo apt-get install poppler-utils` / `brew install poppler`)

### 2. Installation

```bash
cd ibcs_agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Konfiguration

```bash
cp .env.example .env
# .env mit deinen Azure-Werten befüllen
```

Mindestanforderungen in `.env`:
```env
AZURE_AI_FOUNDRY_CONNECTION_STRING=...
AZURE_OPENAI_ENDPOINT=https://<dein-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_MODEL_NAME=gpt-4o
```

### 4. Agent in Azure AI Foundry erstellen

```bash
python -m ibcs_agent.agent.agent setup
```

Notiere die zurückgegebene **Agent ID** und trage sie in `.env` ein:
```env
AGENT_ID=asst_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Testen

```bash
# Direkte Dateianalyse (ohne Agent, für schnelle Tests)
python -m ibcs_agent.agent.agent analyze bericht.pptx

# Mit Agent
python -m ibcs_agent.agent.agent analyze bericht.pptx --agent-id asst_xxx

# Interaktiver Chat
python -m ibcs_agent.agent.agent interactive asst_xxx
```

---

## Output-Format (JSON)

```json
{
  "file_name": "Q1_Report.pptx",
  "file_type": "pptx",
  "overall_score": 0.62,
  "overall_grade": "C",
  "summary": "Das Dokument erhält einen IBCS-Score von 62% (Note C)...",
  "total_violations": 14,
  "total_errors": 5,
  "total_warnings": 7,
  "total_infos": 2,
  "top_violations": [
    {
      "rule_id": "CK2",
      "rule_name": "3D-Effekte in Charts",
      "category": "CHECK",
      "severity": "error",
      "description": "Folie 3 – Chart 1: 3D-Säulendiagramm erkannt.",
      "suggestion": "Konvertiere in 2D-Säulendiagramm.",
      "source": "visual"
    }
  ],
  "pages": [
    {
      "page_number": 1,
      "page_title": "Umsatz",
      "score": 0.4,
      "has_charts": true,
      "violations": [...]
    }
  ],
  "category_summary": [
    { "category": "CHECK", "total_violations": 3, "errors": 3, "score": 0.0 }
  ]
}
```

---

## IBCS SUCCESS Regelwerk

| ID | Kategorie | Regel | Typ |
|----|-----------|-------|-----|
| S1 | SAY | Kein Aussage-Titel | metadata+visual |
| S2 | SAY | Fehlender Zeitraum/Einheit | metadata |
| U1 | UNIFY | Fehlende Farbsemantik | visual |
| U2 | UNIFY | Inkonsistente Chart-Typen | visual |
| U3 | UNIFY | Inkonsistente Achsenskalierung | metadata+visual |
| U4 | UNIFY | Mischung absolut/relativ | metadata+visual |
| C1 | CONDENSE | Geringe Informationsdichte | visual |
| C2 | CONDENSE | Redundante Legende | visual |
| CK1 | CHECK | Achse beginnt nicht bei Null | metadata+visual |
| CK2 | CHECK | 3D-Effekte | visual |
| CK3 | CHECK | Chart-Junk/Dekorationselemente | visual |
| CK4 | CHECK | Inkonsistente Zeitachsen | metadata+visual |
| E1 | EXPRESS | Zeitreihe als Balken | visual |
| E2 | EXPRESS | Vergleich ohne Balkendiagramm | visual |
| E3 | EXPRESS | Composition ohne Waterfall | visual |
| E4 | EXPRESS | Tortendiagramm >2 Segmente | metadata+visual |
| E5 | EXPRESS | Fehlende Abweichungsdarstellung | visual |
| SI1 | SIMPLIFY | Übermäßige Gitterlinien | visual |
| SI2 | SIMPLIFY | Rahmen um Charts | visual |
| SI3 | SIMPLIFY | Zu viele Schriftgrößen | metadata |
| SI4 | SIMPLIFY | Schatten/Verläufe | visual |
| ST1 | STRUCTURE | Inkonsistentes Layout | visual |
| ST2 | STRUCTURE | Fehlende Hierarchie | metadata |
| ST3 | STRUCTURE | Keine Seitennummerierung | metadata |
| ST4 | STRUCTURE | Keine Quellenangabe | metadata |

---

## Microsoft Copilot Studio Integration

### Voraussetzung
Der Agent läuft als Azure AI Foundry Agent und ist über eine REST API erreichbar.

### Schritte

1. **Agent deployen** (siehe Schnellstart Schritt 4)

2. **In Copilot Studio: Custom Connector erstellen**
   - Copilot Studio → Settings → Custom Connectors → New Connector
   - Ziel: Azure AI Foundry REST API Endpoint
   - Authentication: API Key oder Azure AD

3. **Action definieren**: `Analyze IBCS File`
   - Input: Datei als base64-String + Dateiname
   - Tool: `analyze_file`
   - Output: IBCSFeedbackReport JSON

4. **Topic erstellen**: "IBCS Datei analysieren"
   - Trigger: "Analysiere meine Präsentation" / "IBCS Check" / Datei-Upload
   - Action: Custom Connector → Analyze IBCS File
   - Response: Formatiertes Feedback aus JSON

### Copilot Studio Power Fx (Beispiel)
```
Set(varReport, IBCSConnector.AnalyzeFile({
    file_content_base64: varFileBase64,
    file_name: varFileName
}));
```

---

## Projektstruktur

```
ibcs_agent/
├── agent/
│   ├── agent.py          # Azure AI Foundry Agent (CLI + Setup)
│   └── tools.py          # Tool-Definitionen und Orchestrierung
├── processors/
│   ├── ppt_processor.py  # PPTX → Text + Metadaten + Bilder
│   ├── pdf_processor.py  # PDF → Text + Metadaten + Bilder
│   └── excel_processor.py # Excel → Text + Chart-Metadaten
├── analysis/
│   ├── metadata_analyzer.py # Regelbasierte IBCS-Checks
│   └── visual_analyzer.py   # GPT-4o Vision Analyse
├── rules/
│   └── ibcs_rules.py        # Vollständiges Regelwerk
├── models/
│   └── feedback.py          # Pydantic Output-Modelle
├── config.py                # Konfigurationsmanagement
├── requirements.txt
├── .env.example
└── README.md
```
