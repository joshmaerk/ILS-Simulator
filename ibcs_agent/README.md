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

Der Agent wird als REST API (FastAPI) deployt und über einen **Custom Connector** in Enterprise Copilot Studio eingebunden.

---

### Phase 1 – REST API starten (lokal testen)

```bash
cd ibcs_agent
pip install -r requirements.txt -r requirements-api.txt
uvicorn ibcs_agent.api.main:app --reload --port 8000
```

Verfügbare Endpunkte:

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `GET` | `/health` | Health Check (Liveness/Readiness Probe) |
| `POST` | `/v1/analyze-file` | Datei analysieren → `IBCSFeedbackReport` |
| `GET` | `/v1/rules` | Alle IBCS-Regeln abrufen |
| `GET` | `/v1/rules/{rule_id}` | Details zu einer Regel |
| `GET` | `/openapi.json` | OpenAPI 3.0 Spec (für Connector-Import) |
| `GET` | `/docs` | Swagger UI |

---

### Phase 2 – Container bauen & auf Azure Container Apps deployen

```bash
# 1. Container bauen
docker build -f Dockerfile.api -t ibcs-feedback-api .

# 2. In ACR pushen
az acr login --name <ACR_NAME>
docker tag ibcs-feedback-api <ACR_NAME>.azurecr.io/ibcs-feedback-api:latest
docker push <ACR_NAME>.azurecr.io/ibcs-feedback-api:latest

# 3. Container App deployen (Platzhalter in container-app.yaml vorher befüllen)
az containerapp create \
  --yaml ibcs_agent/container-app.yaml \
  -g <RESOURCE_GROUP> \
  --environment <CONTAINER_APPS_ENV>
```

Notiere die **HTTPS-URL** der Container App (z.B. `https://ibcs-feedback-api.xxx.germanywestcentral.azurecontainerapps.io`).

---

### Phase 3 – Azure AD App Registrations anlegen

**3a. App Registration für die API**

1. Azure Portal → Azure Active Directory → App-Registrierungen → Neue Registrierung
2. Name: `ibcs-feedback-api-app`
3. Unterstützte Kontotypen: *Nur Konten in diesem Organisationsverzeichnis*
4. Redirect URI: leer lassen
5. Nach Erstellung: **Anwendungs-ID (Client-ID)** notieren → `API_APP_CLIENT_ID`
6. API verfügbar machen → Application ID URI: `api://<API_APP_CLIENT_ID>`
7. Bereich hinzufügen: `analyze` (Anzeigename: "IBCS Datei analysieren")

**3b. App Registration für den Connector**

1. Neue Registrierung: `copilot-studio-ibcs-connector`
2. **Anwendungs-ID** notieren → `CONNECTOR_CLIENT_ID`
3. Zertifikate & Geheimnisse → Neues Clientgeheimnis → Wert notieren → `CONNECTOR_CLIENT_SECRET`
4. API-Berechtigungen → Berechtigung hinzufügen → Eigene APIs → `ibcs-feedback-api-app` → `analyze` → Delegiert → Administratorzustimmung erteilen

---

### Phase 4 – Custom Connector in Power Platform anlegen

1. **make.powerautomate.com** → Daten → Benutzerdefinierte Connectors → **+ Neuer benutzerdefinierter Connector** → OpenAPI-Datei importieren

2. OpenAPI-Datei exportieren:
   ```bash
   curl https://<DEINE-URL>/openapi.json -o ibcs_openapi.json
   ```
   → Datei hochladen

3. **Allgemein** Tab:
   - Beschreibung: *IBCS Feedback Agent – analysiert PPT/PDF/Excel auf IBCS-Konformität*
   - Schema: HTTPS
   - Host: `<DEINE-URL>` (ohne `https://`)

4. **Sicherheit** Tab:
   - Authentifizierungstyp: **OAuth 2.0**
   - Identitätsanbieter: **Azure Active Directory**
   - Client-ID: `<CONNECTOR_CLIENT_ID>`
   - Geheimer Clientschlüssel: `<CONNECTOR_CLIENT_SECRET>`
   - Ressourcen-URL: `api://<API_APP_CLIENT_ID>`
   - Bereich: leer lassen (wird automatisch ausgefüllt)

5. **Definition** Tab – folgende 3 Aktionen müssen erscheinen:
   - `analyzeFile` – POST /v1/analyze-file
   - `listRules` – GET /v1/rules
   - `getRuleDetails` – GET /v1/rules/{rule_id}

6. **Connector erstellen** → **Testen** → Neue Verbindung → Anmelden → `GET /v1/rules` testen → JSON-Array erwartet

---

### Phase 5 – Topic in Copilot Studio anlegen

1. **copilotstudio.microsoft.com** → Deinen Bot öffnen → Themen → **+ Neues Thema**
2. Name: *IBCS Datei analysieren*
3. Triggerphrasen:
   - "Analysiere meine Präsentation"
   - "IBCS Check"
   - "Prüfe meine Datei auf IBCS"
   - "Foliensatz prüfen"

4. **Frageknoten** hinzufügen:
   - Frage: "Bitte lade deine Datei hoch (PPTX, PDF oder Excel)."
   - Variable: `varDatei` (Typ: Datei / Anhang)

5. **Aktionsknoten** hinzufügen:
   - Aktion: Benutzerdefinierter Connector → **IBCS Feedback Agent** → `analyzeFile`
   - Eingaben:
     - `file_content_base64` ← `System.Activity.Attachments.First().content`
     - `file_name` ← `System.Activity.Attachments.First().name`
   - Ausgabe speichern in: `varReport`

6. **Nachrichtenknoten** hinzufügen (Ergebnis anzeigen):
   ```
   Dein IBCS-Report für „{varReport.file_name}":
   Note: {varReport.overall_grade} | Score: {varReport.overall_score * 100}%
   Verstöße: {varReport.total_violations} ({varReport.total_errors} Fehler, {varReport.total_warnings} Warnungen)
   
   {varReport.summary}
   ```

7. Optional – Detailtabelle mit **Adaptive Card**:
   ```json
   {
     "type": "AdaptiveCard",
     "body": [
       {"type": "TextBlock", "text": "Top-Verstöße", "weight": "Bolder"},
       {"type": "FactSet", "facts": [
         {"title": "{varReport.top_violations[0].rule_id}", "value": "{varReport.top_violations[0].description}"}
       ]}
     ]
   }
   ```

---

### Power Fx Beispiel (Power Apps / Canvas App)

```
// Datei analysieren und Report speichern
Set(
  varReport,
  IBCSConnector.analyzeFile({
    file_content_base64: First(varDateiUpload).Value,
    file_name: First(varDateiUpload).Name
  })
);

// Note anzeigen
Notify(
  Concatenate("IBCS Note: ", varReport.overall_grade, " (", Text(varReport.overall_score * 100, "[$-de-DE]0"), "%)"),
  NotificationType.Success
)
```

---

### Umgebungsvariablen (Produktiv)

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Ja | GPT-4o Endpoint |
| `AZURE_OPENAI_API_KEY` | Ja | GPT-4o API-Key |
| `AZURE_OPENAI_MODEL_NAME` | Ja | Deployment-Name (z.B. `gpt-4o`) |
| `AZURE_AD_TENANT_ID` | Prod | AAD Tenant-ID für JWT-Validierung |
| `AZURE_AD_CLIENT_ID` | Prod | Client-ID der API App Registration |
| `API_BASE_URL` | Empfohlen | HTTPS-URL der Container App (für OpenAPI `servers`) |
| `ENABLE_VISUAL_ANALYSIS` | Nein | `true`/`false`, Standard: `true` |
| `MAX_FILE_SIZE_MB` | Nein | Standard: `20` (Power Platform Limit) |
| `LOG_LEVEL` | Nein | Standard: `INFO` |

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
