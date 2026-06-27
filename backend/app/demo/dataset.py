"""Versioned deterministic synthetic demo dataset."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.contracts.classification import DataClassification
from app.contracts.partner import PartnerCreate
from app.contracts.project import ProjectCreate
from app.contracts.source import TextSourceCreate

SEED_VERSION = "demo-dataset-v1"
SEED_NAMESPACE = uuid.UUID("0fef17a7-6de1-56c4-a53e-3d3e6ef7c611")
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

DEMO_CLASSIFICATION = DataClassification(
    sensitivity="public",
    origin="synthetic",
    processing_mode="deterministic_only",
    web_research_mode="off",
    nda_applies=False,
)


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, f"{SEED_VERSION}:{kind}:{key}"))


def fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class DemoSource:
    key: str
    name: str
    fixture_name: str

    @property
    def source_id(self) -> str:
        return stable_id("source", self.key)

    @property
    def source_version_id(self) -> str:
        return stable_id("source-version", self.key)

    def payload(self) -> TextSourceCreate:
        return TextSourceCreate(
            name=self.name,
            text=fixture(self.fixture_name),
            data_classification=DEMO_CLASSIFICATION,
        )


@dataclass(frozen=True)
class DemoPartner:
    key: str
    payload: PartnerCreate

    @property
    def partner_id(self) -> str:
        return stable_id("partner", self.key)


@dataclass(frozen=True)
class DemoProject:
    key: str
    title: str
    description: str
    innovation_field: str
    budget_framework_chf: float
    partners: tuple[DemoPartner, ...]
    sources: tuple[DemoSource, ...]
    draft_edits: dict[str, str]
    link_fields: tuple[str, ...]

    @property
    def project_id(self) -> str:
        return stable_id("project", self.key)

    @property
    def run_id(self) -> str:
        return stable_id("run", self.key)

    @property
    def operation_id(self) -> str:
        return stable_id("operation", self.key)

    def payload(self, funding_profile_id: str) -> ProjectCreate:
        return ProjectCreate(
            title=self.title,
            description=self.description,
            innovation_field=self.innovation_field,
            funding_instrument_profile_id=funding_profile_id,
            data_classification=DEMO_CLASSIFICATION,
            budget_framework_chf=self.budget_framework_chf,
        )


PROJECT_A = DemoProject(
    key="circular-composites",
    title="KI-gestützte Entwicklung kreislauffähiger Verbundwerkstoffe (Demo)",
    description=(
        "Synthetisches Demo-Projekt für kreislauffähige Verbundwerkstoffe, "
        "Prozessmonitoring und nachvollziehbare Antragserstellung."
    ),
    innovation_field="Werkstofftechnik und Kreislaufwirtschaft",
    budget_framework_chf=620000.0,
    partners=(
        DemoPartner(
            key="alpina-composite",
            payload=PartnerCreate(
                name="Alpina Composite Solutions AG (Demo)",
                partner_type="implementation_partner",
                project_role="Industrialisierung und Pilotproduktion",
                country="CH",
                location="Aarau",
                contribution="Pilotanlage, Prozessdaten, Bauteildemonstrator",
                uid="CHE-000.000.101",
                industry="Advanced Manufacturing",
                fte=42.0,
                startup_status=False,
                swiss_value_creation=True,
                personnel_independence_status="confirmed",
                financial_independence_status="confirmed",
            ),
        ),
        DemoPartner(
            key="materials-institute",
            payload=PartnerCreate(
                name="Schweizer Institut für Werkstoffsysteme (Demo)",
                partner_type="research_partner",
                project_role="Materialcharakterisierung und Validierung",
                country="CH",
                location="Windisch",
                contribution="Laborprüfungen und wissenschaftliche Auswertung",
                research_partner_eligibility_status="eligible",
                personnel_independence_status="confirmed",
                financial_independence_status="confirmed",
            ),
        ),
    ),
    sources=(
        DemoSource("a-overview", "Demo A - Projektüberblick.txt", "project_a_overview.txt"),
        DemoSource("a-workplan", "Demo A - Arbeitsplan.txt", "project_a_workplan.txt"),
        DemoSource("a-market", "Demo A - Markt und Verwertung.txt", "project_a_market.txt"),
        DemoSource("a-solution", "Demo A - Lösung und Innovation.txt", "project_a_solution.txt"),
    ),
    draft_edits={
        "INTRO.APP.NAME": "Circular Composite AI (Demo)",
        "INTRO.APP.ABSTRACT": (
            "Das synthetische Demo-Projekt entwickelt kreislauffähige "
            "Verbundwerkstoffe und eine nachvollziehbare Prozessüberwachung. "
            "Ein Schweizer Umsetzungspartner und ein beitragsberechtigter "
            "Forschungspartner sind eingebunden."
        ),
        "SOL.INNOVATION_SOLUTION.EDITOR": (
            "Die Lösung verbindet Materialrezeptur, Prozessfenster und "
            "deterministische Qualitätsprüfung. Sensorwerte aus der Herstellung "
            "werden genutzt, um Ausschuss zu reduzieren und Demonstratorbauteile "
            "für kreislauffähige Anwendungen zu validieren.\n\n"
            "[[Angabe ergänzen: detaillierte Validierungsmetriken]]"
        ),
    },
    link_fields=("INTRO.APP.ABSTRACT", "SOL.INNOVATION_SOLUTION.EDITOR"),
)

PROJECT_B = DemoProject(
    key="condition-monitoring",
    title="Zustandsüberwachung für Produktionsanlagen (Demo)",
    description=(
        "Synthetisches Demo-Projekt für deterministische Zustandsüberwachung; "
        "absichtlich ohne beitragsberechtigten Forschungspartner."
    ),
    innovation_field="Produktionssysteme und Monitoring",
    budget_framework_chf=410000.0,
    partners=(
        DemoPartner(
            key="helvetic-monitoring",
            payload=PartnerCreate(
                name="Helvetic Monitoring Systems AG (Demo)",
                partner_type="implementation_partner",
                project_role="Pilotanlage und Umsetzung",
                country="CH",
                location="Biel",
                contribution="Maschinenzugang und Wartungsprozess",
                uid="CHE-000.000.202",
                industry="Industrial IoT",
                fte=28.0,
                startup_status=False,
                swiss_value_creation=True,
                personnel_independence_status="confirmed",
                financial_independence_status="confirmed",
            ),
        ),
    ),
    sources=(
        DemoSource("b-overview", "Demo B - Projektüberblick.txt", "project_b_overview.txt"),
        DemoSource("b-signals", "Demo B - Signale.txt", "project_b_signals.txt"),
    ),
    draft_edits={},
    link_fields=(),
)

DEMO_PROJECTS = (PROJECT_A, PROJECT_B)
