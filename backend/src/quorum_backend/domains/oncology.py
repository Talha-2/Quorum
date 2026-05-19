"""
Oncology MDT domain — virtual multidisciplinary tumor board.

This domain pins a fixed clinical ontology so the knowledge graph extracted
from a case packet is always typed against the same auditable schema. The
LLM no longer invents the schema per run, which matters for a clinical
product: the same case always produces the same entity/edge types.

The entity types describe a cancer case (the patient, the diagnosis, its
staging and biomarkers, comorbidities, prior and candidate treatments,
guidelines, trials) plus the ``Specialist`` panel that deliberates on it.
"""

from __future__ import annotations

from quorum_backend.domains.base import DomainProfile, RosterMember
from quorum_backend.pipeline.models import EdgeType, EntityType, Ontology

# --- Entity types --------------------------------------------------------
# Ten types: nine case entities + the deliberating specialist. ``is_individual``
# marks the speaker-capable types (Patient, Specialist).
_ENTITY_TYPES = [
    EntityType(
        name="Patient",
        description="The de-identified patient the tumor board is convened for.",
        examples=["68-year-old patient with a newly diagnosed lung mass"],
        is_individual=True,
    ),
    EntityType(
        name="CancerDiagnosis",
        description="The malignancy under review, including histology and grade.",
        examples=["invasive ductal carcinoma", "stage III non-small-cell lung cancer"],
        is_individual=False,
    ),
    EntityType(
        name="TumorStaging",
        description="The TNM stage or equivalent staging assessment of the diagnosis.",
        examples=["cT2 N1 M0", "stage IIIA"],
        is_individual=False,
    ),
    EntityType(
        name="Biomarker",
        description="A molecular, genomic, or receptor marker that informs therapy.",
        examples=["EGFR exon 19 deletion", "HER2 positive", "MSI-high", "PD-L1 80%"],
        is_individual=False,
    ),
    EntityType(
        name="Comorbidity",
        description="A coexisting condition that affects treatment tolerance or risk.",
        examples=["chronic kidney disease stage 3", "atrial fibrillation", "COPD"],
        is_individual=False,
    ),
    EntityType(
        name="PriorTreatment",
        description="A treatment the patient has already received for this or a related condition.",
        examples=["4 cycles of carboplatin/pemetrexed", "right upper lobectomy"],
        is_individual=False,
    ),
    EntityType(
        name="TreatmentOption",
        description="A candidate treatment the board is weighing for this case.",
        examples=["neoadjuvant chemoradiation", "adjuvant osimertinib", "watchful waiting"],
        is_individual=False,
    ),
    EntityType(
        name="ClinicalGuideline",
        description="A guideline or evidence source that supports a treatment option.",
        examples=["NCCN NSCLC v3.2025", "ESMO breast cancer guideline"],
        is_individual=False,
    ),
    EntityType(
        name="ClinicalTrial",
        description="An open clinical trial the patient may be eligible for.",
        examples=["NCT05012345 — adjuvant immunotherapy trial"],
        is_individual=False,
    ),
    EntityType(
        name="Specialist",
        description="A member of the multidisciplinary panel who deliberates on the case.",
        examples=["medical oncologist", "radiation oncologist", "pathologist"],
        is_individual=True,
    ),
]

# --- Edge types ----------------------------------------------------------
_EDGE_TYPES = [
    EdgeType(
        name="HAS_DIAGNOSIS",
        description="The patient has this cancer diagnosis.",
        source_targets=[["Patient", "CancerDiagnosis"]],
    ),
    EdgeType(
        name="STAGED_AS",
        description="The diagnosis is staged at this level.",
        source_targets=[["CancerDiagnosis", "TumorStaging"]],
    ),
    EdgeType(
        name="EXPRESSES_BIOMARKER",
        description="The diagnosis expresses this molecular or receptor marker.",
        source_targets=[["CancerDiagnosis", "Biomarker"]],
    ),
    EdgeType(
        name="HAS_COMORBIDITY",
        description="The patient has this coexisting condition.",
        source_targets=[["Patient", "Comorbidity"]],
    ),
    EdgeType(
        name="RECEIVED_TREATMENT",
        description="The patient has already received this treatment.",
        source_targets=[["Patient", "PriorTreatment"]],
    ),
    EdgeType(
        name="CANDIDATE_FOR",
        description="The diagnosis is a candidate for this treatment option.",
        source_targets=[["CancerDiagnosis", "TreatmentOption"]],
    ),
    EdgeType(
        name="RECOMMENDED_BY",
        description="A treatment option is supported by this guideline.",
        source_targets=[["TreatmentOption", "ClinicalGuideline"]],
    ),
    EdgeType(
        name="CONTRAINDICATED_BY",
        description="A comorbidity contraindicates or complicates a treatment option.",
        source_targets=[["TreatmentOption", "Comorbidity"]],
    ),
    EdgeType(
        name="ELIGIBLE_FOR",
        description="The patient may be eligible for this clinical trial.",
        source_targets=[["Patient", "ClinicalTrial"]],
    ),
    EdgeType(
        name="EVALUATES",
        description="A specialist evaluates a treatment option during the board.",
        source_targets=[["Specialist", "TreatmentOption"]],
    ),
]

ONCOLOGY_MDT_ONTOLOGY = Ontology(entity_types=_ENTITY_TYPES, edge_types=_EDGE_TYPES)

# --- Fixed MDT panel -----------------------------------------------------
# The standing tumor board roster. Each seat reasons from its specialty and
# is responsible for raising a specific class of concern, so the debate
# surfaces trade-offs no single voice would. All seats start ``neutral`` and
# form a position from the case during the deliberation.
_ROSTER = (
    RosterMember(
        role="Medical Oncologist",
        name="Medical Oncology",
        bio="Leads systemic therapy decisions for the tumor board.",
        persona=(
            "A medical oncologist who anchors every recommendation in current "
            "NCCN/ESMO guidance and the case's biomarker profile. Argues "
            "precisely about regimen choice, sequencing, and line of therapy; "
            "expects claims to be tied to evidence and is quick to flag when a "
            "proposed treatment lacks guideline support for this stage."
        ),
        expertise=("systemic therapy", "chemotherapy", "targeted therapy", "immunotherapy"),
        mandate="Systemic therapy options, regimen sequencing, biomarker-driven choices.",
        caution=0.6,
    ),
    RosterMember(
        role="Radiation Oncologist",
        name="Radiation Oncology",
        bio="Assesses the role and timing of radiotherapy.",
        persona=(
            "A radiation oncologist focused on whether, when, and how "
            "radiotherapy fits the plan — definitive, adjuvant, neoadjuvant, or "
            "palliative. Weighs target volumes against organs at risk and "
            "presses the board on sequencing with surgery and systemic therapy."
        ),
        expertise=("radiotherapy", "treatment sequencing", "organs at risk"),
        mandate="Role, timing, and fields of radiotherapy; sequencing with other modalities.",
        caution=0.6,
    ),
    RosterMember(
        role="Surgical Oncologist",
        name="Surgical Oncology",
        bio="Judges resectability and the surgical approach.",
        persona=(
            "A surgical oncologist who evaluates resectability, the operative "
            "approach, and expected margins. Decisive and outcome-focused; "
            "willing to recommend surgery when it offers the best chance of "
            "cure, but candid about operative risk given the patient's status."
        ),
        expertise=("surgical resection", "operative risk", "margins"),
        mandate="Resectability, surgical approach, margin and operative-risk assessment.",
        risk_tolerance=0.6,
        caution=0.45,
    ),
    RosterMember(
        role="Diagnostic Radiologist",
        name="Radiology",
        bio="Interprets imaging and flags staging ambiguity.",
        persona=(
            "A diagnostic radiologist who reads the imaging reports in the case "
            "packet and states what they do and do not establish. Careful about "
            "staging confidence; will tell the board when an additional or "
            "repeat study is needed before a treatment decision is sound."
        ),
        expertise=("diagnostic imaging", "tumor staging", "response assessment"),
        mandate="Imaging interpretation, staging confidence, gaps that need further imaging.",
        caution=0.7,
    ),
    RosterMember(
        role="Pathologist",
        name="Pathology",
        bio="Confirms histology, grade, and biomarker results.",
        persona=(
            "A pathologist who grounds the discussion in the tissue: histology, "
            "grade, margins, and molecular/receptor results. Precise and "
            "evidence-bound; flags when biomarker testing is incomplete or when "
            "a result should be confirmed before it drives therapy."
        ),
        expertise=("histopathology", "tumor grading", "molecular pathology"),
        mandate="Histology, grade, and biomarker findings; testing completeness.",
        caution=0.7,
    ),
    RosterMember(
        role="Palliative Care Physician",
        name="Palliative Care",
        bio="Keeps symptom burden and goals of care in view.",
        persona=(
            "A palliative care physician who makes sure quality of life, symptom "
            "burden, and the patient's goals of care are weighed alongside "
            "disease control. Will argue for a less aggressive path when the "
            "burden of treatment outweighs the likely benefit."
        ),
        expertise=("symptom management", "goals of care", "quality of life"),
        mandate="Symptom burden, goals of care, when less aggressive treatment is right.",
        caution=0.75,
    ),
    RosterMember(
        role="Clinical Pharmacist",
        name="Clinical Pharmacy",
        bio="Screens for interactions, dosing, and contraindications.",
        persona=(
            "An oncology clinical pharmacist who screens every proposed regimen "
            "for drug interactions, renal and hepatic dose adjustments, and "
            "contraindications against the patient's comorbidities. Detail-"
            "oriented and safety-first; raises concrete safety flags early."
        ),
        expertise=("drug interactions", "dose adjustment", "contraindications"),
        mandate="Interaction, dosing, and contraindication safety checks.",
        caution=0.8,
    ),
    RosterMember(
        role="Oncology Nurse Navigator",
        name="Nurse Navigation",
        bio="Tests feasibility, adherence, and patient barriers.",
        persona=(
            "An oncology nurse navigator who asks whether the plan is actually "
            "deliverable for this patient — travel, support at home, adherence, "
            "financial and logistic barriers. Practical and patient-centered; "
            "surfaces obstacles the purely clinical discussion misses."
        ),
        expertise=("care coordination", "adherence", "patient barriers"),
        mandate="Feasibility, adherence, and social or logistic barriers to the plan.",
        caution=0.6,
    ),
    RosterMember(
        role="Clinical Trials Coordinator",
        name="Clinical Trials",
        bio="Checks the case against open clinical trials.",
        persona=(
            "A clinical trials coordinator who matches the case against open "
            "trials and explains eligibility, logistics, and what a trial would "
            "offer over standard care. Advocates for considering trial "
            "enrollment whenever the case profile fits."
        ),
        expertise=("clinical trials", "eligibility screening", "trial logistics"),
        mandate="Clinical trial eligibility and whether a trial should be offered.",
        optimism=0.6,
    ),
    RosterMember(
        role="Patient Advocate",
        name="Patient Advocate",
        bio="Represents the patient's preferences and equity.",
        persona=(
            "A patient advocate who keeps the patient's stated preferences, "
            "values, and quality of life central, and watches for equity gaps in "
            "access to the proposed plan. Pushes the board to make the patient's "
            "voice explicit rather than assumed."
        ),
        expertise=("patient preferences", "shared decision-making", "health equity"),
        mandate="Patient preferences, quality of life, and equity of access.",
        caution=0.6,
    ),
)

ONCOLOGY_MDT_DOMAIN = DomainProfile(
    key="oncology_mdt",
    name="Oncology MDT (tumor board)",
    description=(
        "Virtual multidisciplinary tumor board. A de-identified cancer case "
        "packet is typed against a fixed oncology ontology and deliberated by "
        "a fixed specialist panel. Decision support and meeting prep — not "
        "autonomous diagnosis."
    ),
    fixed_ontology=ONCOLOGY_MDT_ONTOLOGY,
    fixed_agent_roster=_ROSTER,
)
