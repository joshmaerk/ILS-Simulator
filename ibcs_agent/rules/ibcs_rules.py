"""
IBCS SUCCESS rule definitions.

Based on the public IBCS (International Business Communication Standards) notation.
Reference: https://www.ibcs.com/standards/

Each rule contains:
- id: Unique rule identifier
- category: SUCCESS category (SAY, UNIFY, CONDENSE, CHECK, EXPRESS, SIMPLIFY, STRUCTURE)
- name: Short name (German)
- description: What the rule requires
- check_type: "metadata" (structural/text), "visual" (requires Vision), or "both"
- severity: Default severity when violated
- violation_hint: What a violation looks like
- suggestion_template: Template for correction suggestion
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal


@dataclass
class IBCSRule:
    id: str
    category: str
    name: str
    description: str
    check_type: Literal["metadata", "visual", "both"]
    severity: Literal["error", "warning", "info"]
    violation_hint: str
    suggestion_template: str
    applies_to: List[str] = field(default_factory=lambda: ["pptx", "pdf", "xlsx"])


# ---------------------------------------------------------------------------
# SAY — Aussage kommunizieren
# ---------------------------------------------------------------------------
SAY_RULES: List[IBCSRule] = [
    IBCSRule(
        id="S1",
        category="SAY",
        name="Kein Aussage-Titel",
        description=(
            "Chart- und Folientitel sollen eine konkrete Aussage/Insight formulieren "
            "(z.B. 'Umsatz steigt um 12% YoY'), nicht nur ein Thema nennen (z.B. 'Umsatz')."
        ),
        check_type="both",
        severity="error",
        violation_hint="Titel ist nur ein Substantiv oder allgemeiner Begriff ohne Verb oder Aussage.",
        suggestion_template=(
            "Formuliere den Titel als vollständige Aussage mit Verb, z.B. "
            "'{thema} {entwicklung} um {wert} im Zeitraum {periode}'."
        ),
    ),
    IBCSRule(
        id="S2",
        category="SAY",
        name="Fehlender Zeitraum oder Einheit im Titel",
        description=(
            "Titel sollen den dargestellten Zeitraum und die Maßeinheit enthalten, "
            "sofern nicht durch Achsenbeschriftungen eindeutig klar."
        ),
        check_type="metadata",
        severity="warning",
        violation_hint="Zeitraum (Jahr, Quartal, Monat) oder Einheit (€, %, Tsd.) fehlt im Titel.",
        suggestion_template=(
            "Ergänze Zeitraum und Einheit im Titel, z.B. 'Umsatz Jan–Dez {jahr} in Mio. €'."
        ),
    ),
]

# ---------------------------------------------------------------------------
# UNIFY — Semantische Notation einheitlich anwenden
# ---------------------------------------------------------------------------
UNIFY_RULES: List[IBCSRule] = [
    IBCSRule(
        id="U1",
        category="UNIFY",
        name="Fehlende IBCS-Farbsemantik",
        description=(
            "IBCS definiert eine Farbsemantik: Ist-Werte = dunkel/schwarz, "
            "Plan/Budget = schraffiert oder leer, Vorjahr = hellgrau, "
            "Abweichungen positiv = dunkelgrün/dunkel, negativ = rot/dunkel."
        ),
        check_type="visual",
        severity="error",
        violation_hint=(
            "Bunte Farben (Blau, Orange, Grün) ohne semantische Bedeutung; "
            "kein erkennbares Farbschema nach IBCS."
        ),
        suggestion_template=(
            "Verwende IBCS-Farbsemantik: Ist=schwarz/dunkelgrau, Plan=schraffiert, "
            "Vorjahr=hellgrau, positive Abweichung=dunkelgrün, negative=rot."
        ),
    ),
    IBCSRule(
        id="U2",
        category="UNIFY",
        name="Inkonsistente Chart-Typen",
        description=(
            "Gleiche Datentypen (z.B. Ist-Werte über Zeit) sollen immer mit demselben "
            "Chart-Typ dargestellt werden."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Ähnliche Datenkategorien werden auf verschiedenen Folien unterschiedlich visualisiert.",
        suggestion_template=(
            "Vereinheitliche Chart-Typen: Zeitreihen immer als Linien- oder Säulendiagramm, "
            "Vergleiche immer als Balkendiagramm."
        ),
    ),
    IBCSRule(
        id="U3",
        category="UNIFY",
        name="Inkonsistente Achsenskalierung",
        description=(
            "Vergleichbare Charts sollen dieselbe Achsenskalierung verwenden, "
            "um visuelle Verzerrungen zu vermeiden."
        ),
        check_type="both",
        severity="error",
        violation_hint="Verschiedene Charts mit ähnlichen Daten haben unterschiedliche Y-Achsen-Maxima.",
        suggestion_template=(
            "Setze für vergleichbare Charts eine einheitliche Achsenskalierung. "
            "Dokumentiere die Skala explizit im Titel oder Untertitel."
        ),
    ),
    IBCSRule(
        id="U4",
        category="UNIFY",
        name="Mischung absoluter und relativer Werte",
        description=(
            "Absolute Werte (€, Stück) und relative Werte (%, Index) sollen nicht "
            "im selben Chart ohne klare Kennzeichnung gemischt werden."
        ),
        check_type="both",
        severity="warning",
        violation_hint="Chart zeigt Balken für absolute Werte und Linie für Prozentwerte ohne klare zweite Achse.",
        suggestion_template=(
            "Trenne absolute und relative Werte in separate Charts oder kennzeichne "
            "eine zweite Y-Achse eindeutig."
        ),
    ),
]

# ---------------------------------------------------------------------------
# CONDENSE — Informationsdichte erhöhen
# ---------------------------------------------------------------------------
CONDENSE_RULES: List[IBCSRule] = [
    IBCSRule(
        id="C1",
        category="CONDENSE",
        name="Geringe Informationsdichte / übermäßiger Leerraum",
        description=(
            "Folien/Seiten sollen eine hohe Informationsdichte aufweisen. "
            "Große Leerräume, die keinen strukturellen Zweck haben, verschwenden Platz."
        ),
        check_type="visual",
        severity="info",
        violation_hint="Weniger als 40% der Folienfläche wird für Inhalt genutzt; viel leerer Hintergrund.",
        suggestion_template=(
            "Erhöhe die Informationsdichte: Füge weitere relevante Daten hinzu, "
            "verkleinere Abstände oder kombiniere verwandte Charts auf einer Folie."
        ),
    ),
    IBCSRule(
        id="C2",
        category="CONDENSE",
        name="Redundante Legende statt direkter Beschriftung",
        description=(
            "Legenden sollen vermieden werden, wenn Datenserien direkt beschriftet werden können. "
            "Direkte Beschriftungen reduzieren Augenbewegungen und erhöhen die Lesbarkeit."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Chart hat eine separate Legende, obwohl die Linien/Balken direkt beschriftet werden könnten.",
        suggestion_template=(
            "Entferne die Legende und beschrifte Datenserien direkt am Endpunkt der Linie "
            "oder am Balken."
        ),
    ),
]

# ---------------------------------------------------------------------------
# CHECK — Visuelle Integrität sicherstellen
# ---------------------------------------------------------------------------
CHECK_RULES: List[IBCSRule] = [
    IBCSRule(
        id="CK1",
        category="CHECK",
        name="Achse beginnt nicht bei Null",
        description=(
            "Y-Achsen von Balken- und Säulendiagrammen müssen bei Null beginnen. "
            "Eine abgeschnittene Achse verzerrt visuelle Verhältnisse und täuscht den Leser."
        ),
        check_type="both",
        severity="error",
        violation_hint="Y-Achse eines Balken- oder Säulendiagramms beginnt nicht bei 0.",
        suggestion_template=(
            "Setze den Y-Achsen-Ursprung auf 0. Bei kleinen Unterschieden zwischen Werten "
            "verwende ein Abweichungsdiagramm (Variance Chart) statt eines abgeschnittenen Balkendiagramms."
        ),
    ),
    IBCSRule(
        id="CK2",
        category="CHECK",
        name="3D-Effekte in Charts",
        description=(
            "3D-Effekte in Charts verzerren Datenwerte visuell und erschweren das Ablesen. "
            "IBCS verbietet 3D-Charts kategorisch."
        ),
        check_type="visual",
        severity="error",
        violation_hint="Chart ist als 3D-Variante dargestellt (3D-Balken, 3D-Torte, 3D-Fläche).",
        suggestion_template=(
            "Konvertiere alle 3D-Charts in ihre 2D-Äquivalente. "
            "In Excel/PowerPoint: Rechtsklick auf Chart → Diagrammtyp ändern → 2D-Variante wählen."
        ),
    ),
    IBCSRule(
        id="CK3",
        category="CHECK",
        name="Chart-Junk / Dekorationselemente",
        description=(
            "Dekorative Elemente ohne Informationswert (Cliparts, Hintergrundbilder in Charts, "
            "dekorative Rahmen, Wassermuster) sollen vermieden werden."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Chart oder Folie enthält dekorative Grafiken, Hintergrundbilder oder ornamentale Elemente.",
        suggestion_template=(
            "Entferne alle Dekorationselemente. Jedes visuelle Element soll Daten repräsentieren "
            "oder strukturell notwendig sein."
        ),
    ),
    IBCSRule(
        id="CK4",
        category="CHECK",
        name="Inkonsistente oder fehlende Zeitachsen",
        description=(
            "Zeitachsen sollen konsistente Intervalle verwenden und lückenlos sein. "
            "Fehlende Zeitperioden müssen explizit gekennzeichnet werden."
        ),
        check_type="both",
        severity="warning",
        violation_hint="Zeitachse hat unregelmäßige Abstände oder fehlende Perioden ohne Kennzeichnung.",
        suggestion_template=(
            "Stelle sicher, dass die Zeitachse gleichmäßige Intervalle hat. "
            "Fehlende Daten als 'n/a' oder mit Lücke kennzeichnen."
        ),
    ),
]

# ---------------------------------------------------------------------------
# EXPRESS — Passende Visualisierung wählen
# ---------------------------------------------------------------------------
EXPRESS_RULES: List[IBCSRule] = [
    IBCSRule(
        id="E1",
        category="EXPRESS",
        name="Zeitreihe als Balkendiagramm statt Liniendiagramm",
        description=(
            "Kontinuierliche Zeitreihen sollen als Linien- oder Flächendiagramm dargestellt werden, "
            "nicht als Balkendiagramm (außer bei diskreten Perioden wie Quartalen/Jahren)."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Kontinuierliche Zeitreihendaten (Monate, Wochen) sind als Balkendiagramm dargestellt.",
        suggestion_template=(
            "Verwende ein Liniendiagramm für kontinuierliche Zeitreihen. "
            "Balkendiagramme sind für diskrete Perioden (Jahre, Quartale) akzeptabel."
        ),
    ),
    IBCSRule(
        id="E2",
        category="EXPRESS",
        name="Vergleiche ohne Balken-/Säulendiagramm",
        description=(
            "Strukturvergleiche (verschiedene Kategorien zum selben Zeitpunkt) "
            "sollen als horizontales Balkendiagramm dargestellt werden."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Kategorienvergleich wird als Liniendiagramm, Bubble Chart oder andere ungeeignete Form dargestellt.",
        suggestion_template=(
            "Verwende horizontale Balkendiagramme für Kategorienvergleiche. "
            "Sortiere nach Wertgröße für bessere Lesbarkeit."
        ),
    ),
    IBCSRule(
        id="E3",
        category="EXPRESS",
        name="Zusammensetzung ohne Wasserfall-Chart",
        description=(
            "Wenn Wertveränderungen erklärt werden (z.B. Umsatzbrücke, EBIT-Bridge), "
            "ist ein Wasserfall-Chart die IBCS-konforme Darstellung."
        ),
        check_type="visual",
        severity="info",
        violation_hint="Beiträge zu einer Gesamtveränderung werden als gestapeltes Balkendiagramm oder Torte dargestellt.",
        suggestion_template=(
            "Verwende ein Wasserfall-Diagramm (Waterfall Chart) um Beiträge zu einer "
            "Gesamtveränderung darzustellen."
        ),
    ),
    IBCSRule(
        id="E4",
        category="EXPRESS",
        name="Tortendiagramm mit mehr als 2 Segmenten",
        description=(
            "Tortendiagramme sind nach IBCS nur für 2 Segmente (Ja/Nein, Anteil/Rest) akzeptabel. "
            "Bei mehr als 2 Segmenten sind Balkendiagramme überlegen."
        ),
        check_type="visual",
        severity="error",
        violation_hint="Tortendiagramm hat 3 oder mehr Segmente.",
        suggestion_template=(
            "Ersetze das Tortendiagramm durch ein horizontales Balkendiagramm. "
            "Sortiere die Kategorien nach Größe (absteigend)."
        ),
        applies_to=["pptx", "pdf", "xlsx"],
    ),
    IBCSRule(
        id="E5",
        category="EXPRESS",
        name="Keine Abweichungsdarstellung trotz Plan/Ist-Vergleich",
        description=(
            "Wenn Plan- und Ist-Werte verglichen werden, soll zusätzlich ein "
            "Abweichungsdiagramm (Variance Chart) gezeigt werden."
        ),
        check_type="visual",
        severity="info",
        violation_hint="Plan und Ist werden nebeneinander gestellt, aber keine explizite Abweichung dargestellt.",
        suggestion_template=(
            "Füge ein Abweichungsdiagramm (ΔPlan) unter oder neben dem Hauptchart hinzu, "
            "das absolute und/oder relative Abweichungen zeigt."
        ),
    ),
]

# ---------------------------------------------------------------------------
# SIMPLIFY — Überflüssiges entfernen
# ---------------------------------------------------------------------------
SIMPLIFY_RULES: List[IBCSRule] = [
    IBCSRule(
        id="SI1",
        category="SIMPLIFY",
        name="Übermäßige Gitterlinien",
        description=(
            "Gitterlinien sollen minimal oder nicht vorhanden sein. "
            "Sie lenken vom Inhalt ab. Wenn vorhanden, sehr hell und dünn."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Prominente, dunkle oder viele Gitterlinien im Chart-Hintergrund.",
        suggestion_template=(
            "Entferne Gitterlinien oder mache sie sehr dezent (hellgrau, 0.25pt). "
            "In Excel: Diagramm → Gitterlinien → Formatieren → sehr helle Farbe."
        ),
    ),
    IBCSRule(
        id="SI2",
        category="SIMPLIFY",
        name="Rahmen um Charts",
        description=(
            "Rahmen (Borders) um Charts sind überflüssig und erzeugen visuelles Rauschen. "
            "Charts sollen ohne umgebenden Rahmen dargestellt werden."
        ),
        check_type="visual",
        severity="info",
        violation_hint="Chart hat einen sichtbaren Rahmen/Border.",
        suggestion_template=(
            "Entferne den Chart-Rahmen. In Excel: Diagrammbereich formatieren → Rahmen → Kein Rahmen."
        ),
    ),
    IBCSRule(
        id="SI3",
        category="SIMPLIFY",
        name="Zu viele Schriftgrößen",
        description=(
            "Auf einer Folie sollen maximal 2-3 Schriftgrößen verwendet werden "
            "(Titel, Beschriftung, Fußnote). Mehr erzeugt visuelles Chaos."
        ),
        check_type="both",
        severity="warning",
        violation_hint="Mehr als 3 verschiedene Schriftgrößen auf einer Folie/Seite.",
        suggestion_template=(
            "Reduziere auf maximal 3 Schriftgrößen: Titel (größer), "
            "Haupttext/Beschriftungen (mittel), Fußnoten/Quellenangaben (klein)."
        ),
    ),
    IBCSRule(
        id="SI4",
        category="SIMPLIFY",
        name="Schatten, Verläufe oder Texturen in Charts",
        description=(
            "Schatten-Effekte, Farbverläufe und Texturen auf Datenelementen "
            "sind nach IBCS nicht erlaubt — sie lenken ab und verfälschen die Wahrnehmung."
        ),
        check_type="visual",
        severity="error",
        violation_hint="Balken, Flächen oder Datenpunkte haben Schatten, Farbverläufe oder Texturen.",
        suggestion_template=(
            "Verwende ausschließlich einfarbige Füllung für Datenelemente. "
            "Entferne alle Schatten und Verlaufsfüllungen."
        ),
    ),
]

# ---------------------------------------------------------------------------
# STRUCTURE — Berichte strukturieren
# ---------------------------------------------------------------------------
STRUCTURE_RULES: List[IBCSRule] = [
    IBCSRule(
        id="ST1",
        category="STRUCTURE",
        name="Inkonsistentes Layout über Folien",
        description=(
            "Das Layout soll über alle Folien konsistent sein: "
            "gleiche Position für Titel, Charts, Kommentarboxen, Logos."
        ),
        check_type="visual",
        severity="warning",
        violation_hint="Titel, Charts oder Beschriftungen befinden sich auf verschiedenen Folien an unterschiedlichen Positionen.",
        suggestion_template=(
            "Verwende PowerPoint-Folienmaster oder definierte Layouts. "
            "Stelle sicher, dass alle Folien demselben Raster folgen."
        ),
        applies_to=["pptx"],
    ),
    IBCSRule(
        id="ST2",
        category="STRUCTURE",
        name="Fehlende Hierarchie (Überschriften)",
        description=(
            "Berichte sollen eine klare visuelle Hierarchie haben: "
            "Haupttitel > Untertitel/Beschriftung. Ohne Hierarchie sind Folien schwer zu scannen."
        ),
        check_type="both",
        severity="warning",
        violation_hint="Folie hat keinen erkennbaren Haupttitel oder alle Texte haben die gleiche Größe.",
        suggestion_template=(
            "Füge einen klaren Haupttitel hinzu, der die Aussage der Folie kommuniziert. "
            "Verwende Schriftgrößen-Hierarchie zur Strukturierung."
        ),
    ),
    IBCSRule(
        id="ST3",
        category="STRUCTURE",
        name="Fehlende Seitennummerierung",
        description=(
            "Professionelle Berichte sollen Seitennummern enthalten, "
            "um Referenzierbarkeit im Meeting zu gewährleisten."
        ),
        check_type="metadata",
        severity="info",
        violation_hint="Keine Seitennummern im Dokument gefunden.",
        suggestion_template=(
            "Füge Seitennummern hinzu (PowerPoint: Einfügen → Kopf- und Fußzeile → Foliennummer)."
        ),
    ),
    IBCSRule(
        id="ST4",
        category="STRUCTURE",
        name="Fehlende Quellenangabe",
        description=(
            "Datenquellen sollen auf jeder Folie/Seite mit Daten angegeben werden, "
            "um Nachvollziehbarkeit zu gewährleisten."
        ),
        check_type="both",
        severity="info",
        violation_hint="Keine Quellenangabe auf der Folie/Seite vorhanden.",
        suggestion_template=(
            "Füge eine Quellenangabe in kleiner Schrift am unteren Rand jeder Datenseite ein, "
            "z.B. 'Quelle: SAP BW, Stand: {datum}'."
        ),
    ),
]

# ---------------------------------------------------------------------------
# All rules combined
# ---------------------------------------------------------------------------
ALL_RULES: List[IBCSRule] = list(
    SAY_RULES
    + UNIFY_RULES
    + CONDENSE_RULES
    + CHECK_RULES
    + EXPRESS_RULES
    + SIMPLIFY_RULES
    + STRUCTURE_RULES
)

RULES_BY_ID: Dict[str, IBCSRule] = {rule.id: rule for rule in ALL_RULES}
RULES_BY_CATEGORY: Dict[str, List[IBCSRule]] = {}
for _rule in ALL_RULES:
    RULES_BY_CATEGORY.setdefault(_rule.category, []).append(_rule)

SUCCESS_CATEGORIES = ["SAY", "UNIFY", "CONDENSE", "CHECK", "EXPRESS", "SIMPLIFY", "STRUCTURE"]

# Import and merge table-specific rules
# Uses sys.modules to avoid circular import: if ibcs_rules_tables is already
# being loaded (circular), we skip. The merge will be retried lazily via
# ensure_table_rules_merged() which is called by get_rule() and other accessors.
_TABLE_RULES_MERGED: bool = False


def _try_merge_table_rules() -> bool:
    """Try to merge table rules. Returns True if successful."""
    global ALL_RULES, RULES_BY_ID, RULES_BY_CATEGORY, _TABLE_RULES_MERGED
    if _TABLE_RULES_MERGED:
        return True
    import sys
    # Check if ibcs_rules_tables is fully loaded (not mid-import)
    _tbl_mod = sys.modules.get("ibcs_agent.rules.ibcs_rules_tables")
    if _tbl_mod is None:
        # Not yet imported - try to import it now
        try:
            import importlib
            _tbl_mod = importlib.import_module("ibcs_agent.rules.ibcs_rules_tables")
        except Exception:
            return False
    _table_rules = getattr(_tbl_mod, "ALL_TABLE_RULES", None)
    if not _table_rules:
        return False  # Module partially loaded (circular) - try later
    # Check if already merged
    if _table_rules[0].id in RULES_BY_ID:
        _TABLE_RULES_MERGED = True
        return True
    # Merge in-place so existing references to ALL_RULES see the update
    ALL_RULES.extend(_table_rules)
    RULES_BY_ID.update({rule.id: rule for rule in _table_rules})
    for _rule in _table_rules:
        RULES_BY_CATEGORY.setdefault(_rule.category, []).append(_rule)
    _TABLE_RULES_MERGED = True
    return True


# Attempt immediate merge at module load time
_try_merge_table_rules()


def get_rule(rule_id: str) -> IBCSRule:
    """Return a rule by ID. Raises KeyError if not found."""
    return RULES_BY_ID[rule_id]


def get_rules_for_file_type(file_type: str) -> List[IBCSRule]:
    """Return all rules applicable to a given file type."""
    return [r for r in ALL_RULES if file_type in r.applies_to]


def get_visual_rules() -> List[IBCSRule]:
    return [r for r in ALL_RULES if r.check_type in ("visual", "both")]


def get_metadata_rules() -> List[IBCSRule]:
    return [r for r in ALL_RULES if r.check_type in ("metadata", "both")]
