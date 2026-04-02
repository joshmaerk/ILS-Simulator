# Manager-AI – Multi-Agent Management Support System

Ein KI-gestütztes Management-Assistenzsystem auf Basis von **Azure AI Foundry**, bereitgestellt als **Microsoft Teams Bot**. Ein Orchestrator-Agent koordiniert automatisch 10 spezialisierte Experten-Agenten, die eine Führungskraft in allen Dimensionen ihrer Arbeit unterstützen.

---

## Architektur-Überblick

```
Teams-Nutzer (Manager)
        │
        ▼
Azure Bot Service (Teams-Kanal)
        │
        ▼
Bot Framework Adapter (aiohttp)
        │
        ▼
Orchestrator-Agent
  ├── Intent Router (gpt-4o-mini)  ──► Welche Agenten werden benötigt?
  │
  ├── Parallel Fan-Out (asyncio.gather)
  │     ├── Stratege           ──► Bing Search, SharePoint
  │     ├── Change Manager     ──► SharePoint, E-Mail
  │     ├── Kommunikationsexp. ──► E-Mail, SharePoint
  │     ├── Controller         ──► SharePoint, Code Interpreter, Bing
  │     ├── Personalentwickler ──► SharePoint
  │     ├── Leadership Coach   ──► (conversational)
  │     ├── Projektmanager     ──► Kalender, SharePoint
  │     ├── Programm-Manager   ──► Kalender, SharePoint
  │     ├── Rechtsberater      ──► Bing, SharePoint
  │     └── Innovations-Scout  ──► Bing, SharePoint
  │
  └── Consolidator  ──► Finale Antwort
        │
        ▼
Cosmos DB (Gedächtnis)
  ├── sessions         (TTL 24h, kurzfristiger Sitzungskontext)
  └── user_profiles    (persistent, Nutzerprofil + Fakten)
```

---

## Technologie-Stack

| Komponente | Technologie |
|---|---|
| LLM / Agent Runtime | Azure AI Foundry Agent Service (`azure-ai-projects`) |
| Primäres Modell | gpt-4o |
| Routing-Modell | gpt-4o-mini |
| Bot Framework | Bot Framework SDK v4 Python + aiohttp |
| Teams-Kanal | Azure Bot Service |
| Persistentes Gedächtnis | Azure Cosmos DB (NoSQL, serverless) |
| Web-Suche | Bing Grounding Tool (AI Foundry built-in) |
| M365-Integration | Microsoft Graph SDK Python |
| Infrastruktur | Azure Bicep (IaC) |
| Auth | Managed Identity + Azure Key Vault |

---

## Schnellstart (Lokale Entwicklung)

### Voraussetzungen
- Python 3.12+
- Azure CLI (`az login` ausgeführt)
- Bot Framework Emulator (für lokale Tests)
- `.env` Datei (von `.env.example` kopieren und befüllen)

### Setup

```bash
cd manager-ai

# Virtual Environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# .env anlegen
cp .env.example .env
# .env mit deinen Werten befüllen

# Bot starten
python -m bot.app
```

Der Bot läuft auf `http://localhost:3978`. Verbinde den Bot Framework Emulator mit `http://localhost:3978/api/messages`.

### Tests ausführen

```bash
pytest tests/ -v
```

---

## Azure Deployment

### Infrastruktur provisionieren

```bash
cd infra

# Parameter anpassen
nano main.bicepparam

# Deployment
az deployment group create \
  --resource-group <deine-resource-group> \
  --template-file main.bicep \
  --parameters main.bicepparam
```

### App Service Deployment

```bash
cd manager-ai

# ZIP-Paket erstellen und deployen
zip -r ../manager-ai.zip . -x ".venv/*" "__pycache__/*" "*.pyc" ".env"

az webapp deployment source config-zip \
  --resource-group <rg> \
  --name <app-service-name> \
  --src ../manager-ai.zip
```

### Teams-Kanal aktivieren
Nach dem Deployment im Azure Bot Service → Channels → Microsoft Teams → Enable.

---

## Experten-Agenten

| Agent | Expertise | Tools |
|---|---|---|
| **Stratege** | Langfristige Strategie, Wettbewerb, SWOT | Bing, SharePoint |
| **Change Manager** | Veränderungsprozesse, ADKAR, Widerstände | SharePoint, E-Mail |
| **Kommunikationsexperte** | Textentwürfe, Botschaften, Krisenkommunikation | E-Mail, SharePoint |
| **Controller** | Budget, KPIs, Reporting, Forecasting | SharePoint, Code Interpreter, Bing |
| **Personalentwickler** | Talentmanagement, Entwicklungspläne | SharePoint |
| **Leadership Coach** | Führung, Konfliktlösung, Team-Dynamik | – |
| **Projektmanager** | Projektplanung, Risiken, Scrum/Kanban | Kalender, SharePoint |
| **Programm-Manager** | Portfolio, Governance, Abhängigkeiten | Kalender, SharePoint |
| **Rechtsberater** | Compliance, DSGVO, Vertragsrecht | Bing, SharePoint |
| **Innovations-Scout** | Trends, KI, digitale Geschäftsmodelle | Bing, SharePoint |

---

## Gedächtnis-Konzept

- **Kurzzeit (Session):** Azure AI Foundry Threads – jedes Teams-Gespräch hat seinen eigenen Thread
- **Langzeit (Profil):** Cosmos DB `user_profiles` – Nutzerrolle, Präferenzen, aktive Projekte, Entscheidungen
- **Kontext-Injection:** Beim Start jeder Session wird der Langzeit-Kontext als System-Prefix eingebettet

---

## Projektstruktur

```
manager-ai/
├── bot/                    # Teams Bot-Schicht
├── orchestrator/           # Orchestrierung + Routing
├── agents/                 # Experten-Agenten
├── memory/                 # Cosmos DB Speicher
├── tools/                  # Graph & Suche Tools
├── graph/                  # Microsoft Graph Services
├── config/                 # Settings + System-Prompts
├── infra/                  # Bicep IaC
└── tests/                  # Unit + Integration Tests
```

---

## Neue Agenten hinzufügen

1. Neues System-Prompt in `config/agent_prompts.py` unter neuem Key hinzufügen
2. Neue Klasse in `agents/<name>.py` erstellen (`BaseExpertAgent` erweitern)
3. In `agents/__init__.py` zur `agent_classes` Liste hinzufügen
4. In `orchestrator/router.py` `AGENT_REGISTRY` Eintrag hinzufügen
5. Tests schreiben

---

## Sicherheit

- Alle Azure-Dienste nutzen **Managed Identity** (keine gespeicherten Credentials)
- Secrets (Bot-Password, Graph-Secret) ausschließlich in **Azure Key Vault**
- App Service referenziert Key Vault via `@Microsoft.KeyVault(...)` App Settings
- `disableLocalAuth: true` für Cosmos DB (nur Managed Identity)
- HTTPS erzwungen auf App Service
