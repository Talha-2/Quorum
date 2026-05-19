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

from quorum_backend.domains.base import DomainProfile
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

ONCOLOGY_MDT_DOMAIN = DomainProfile(
    key="oncology_mdt",
    name="Oncology MDT (tumor board)",
    description=(
        "Virtual multidisciplinary tumor board. A de-identified cancer case "
        "packet is typed against a fixed oncology ontology and deliberated by "
        "a specialist panel. Decision support and meeting prep — not autonomous "
        "diagnosis."
    ),
    fixed_ontology=ONCOLOGY_MDT_ONTOLOGY,
)
