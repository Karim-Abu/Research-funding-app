"""Vollständig synthetisches Innolink-PDF für den strukturierten Golden-Import."""
from __future__ import annotations

from tests.fixtures import make_text_pages_pdf


PERSONNEL_QUESTIONS = (
    "Are any of the employees involved in the project on the part of a research partner also an employee of an implementation partner?",
    "Are any of the employees involved in the project on the part of the research partners a member of an involved implementation partner's executive board, supervisory board or scientific committee?",
    "Have any of the employees involved in the project on the part of the research partners been commissioned by an involved implementation partner to perform another role?",
)
FINANCIAL_QUESTIONS = (
    "I confirm that none of the employees involved in the project on behalf of the research partners holds 20% or more of the ownership interest (e.g., shares) in any implementation partner",
    "I confirm that the research partner, as a legal entity, does not hold 20% or more of the ownership interest (e.g., shares) in any implementation partner",
)
SCIENTIFIC_QUESTION = (
    "Has any staff member who will be collaborating on the application been severely "
    "sanctioned for violation of scientific integrity in the last three years?"
)

CONTACT_MARKER = "main-contact-marker@example.test"

GOLDEN_STRUCTURED_PDF = make_text_pages_pdf(
    [
        [
            "ORBIT / Application",
            "Title in English:",
            "ORBIT Synthetic Collaboration",
            "Project Start Date: 01.01.2026",
            "Project End Date: 30.06.2027",
            "Project Duration: 18 months",
            "Requested Innosuisse Funding incl. Overhead: CHF 171'560",
            "1. Introduction",
            "Abstract",
            "A synthetic project develops a reproducible test instrument.",
            "Management Summary",
            "Context",
            "Context is deliberately not an executive summary.",
        ],
        [
            "Scientific Integrity",
            SCIENTIFIC_QUESTION,
            "No",
            "Intellectual Property Rights",
        ],
        [
            "2. Organisations and People",
            "Research Partner",
            "Name: Alpine Research Lab",
            "Country: CH",
            "Department: Applied Systems",
            "Industry: Research",
            "FTE: 41",
            "Official Representative: Robin Example",
            "Project Role: Experimental validation",
            "Implementation Partner 1",
            "Name: Helios Devices AG",
            "Country: CH",
            "Department: Product Engineering",
            "Industry: Electronics",
            "FTE: 82",
            "Official Representative: Morgan Sample",
            "Project Role: Product integration",
            "Implementation Partner 2",
            "Name: Juniper Services GmbH",
            "Country: CH",
            "Department: Field Operations",
            "Industry: Services",
            "FTE: 27",
            "Official Representative: Taylor Fixture",
            "Project Role: Pilot operation",
            "Independence of Research and Implementation Partners",
        ],
        [
            "Personnel Independence",
            PERSONNEL_QUESTIONS[0],
            "No",
            PERSONNEL_QUESTIONS[1],
            "No",
            PERSONNEL_QUESTIONS[2],
            "No",
            "Financial Independence",
            FINANCIAL_QUESTIONS[0],
            "Checked",
            FINANCIAL_QUESTIONS[1],
            "Checked",
            "Main Contacts",
            f"Primary Contact: {CONTACT_MARKER}",
            "Innovation Mentor",
        ],
        [
            "5. Project Setup",
            "Partner | Research | Development | Management",
            "Alpine Research Lab | 1000 | 400 | 0",
            "Helios Devices AG | 1200 | 600 | 0",
            "Juniper Services GmbH | 900 | 600 | 0",
            "Explanation",
            "Risk Management",
        ],
        [
            "Financial Overview",
            "Direct total project costs excluding overhead: CHF 309'734",
            "Implementation Partner Own Contribution: CHF 142'680",
            "Cash Contribution: CHF 20'000",
            "Requested Innosuisse Funding: CHF 147'054",
            "Salary Costs",
            "Material Costs",
        ],
    ]
)
