"""
Quorum Dx (education) — diagnostic-reasoning gym.

Education mode only: a learner feeds in a *synthetic* or published case
vignette; a panel of reasoning archetypes (generalist, specialists,
skeptic, epidemiologist, can't-miss, bayesian) debates the differential
and produces a Differential Diagnosis Brief.

This module is explicitly NOT a clinical-grade diagnostic tool: it is
framed for teaching, USMLE-style case practice, and clinical-reasoning
curricula. No PHI; no patient-specific recommendations.
"""

from __future__ import annotations

from quorum_backend.domains.base import DomainProfile, ReportSectionSpec, RosterMember
from quorum_backend.pipeline.models import EdgeType, EntityType, Ontology

# --- Diagnostic ontology -------------------------------------------------
_ENTITY_TYPES = [
    EntityType(
        name="Presentation",
        description="The chief complaint and arc of the case as presented.",
        examples=["acute chest pain in a 56-year-old"],
        is_individual=False,
    ),
    EntityType(
        name="Symptom",
        description="A patient-reported subjective complaint.",
        examples=["substernal pressure", "shortness of breath", "headache"],
        is_individual=False,
    ),
    EntityType(
        name="Sign",
        description="An objective finding on physical examination.",
        examples=["pedal edema", "diminished breath sounds", "neck stiffness"],
        is_individual=False,
    ),
    EntityType(
        name="Finding",
        description="A laboratory, imaging, or other test result.",
        examples=["troponin elevation", "CT pulmonary embolism positive"],
        is_individual=False,
    ),
    EntityType(
        name="RiskFactor",
        description="A factor that raises the prior for one or more diagnoses.",
        examples=["heavy smoker", "recent long-haul travel"],
        is_individual=False,
    ),
    EntityType(
        name="PriorCondition",
        description="A documented past or family condition that shapes the differential.",
        examples=["diabetes mellitus type 2", "first-degree relative with VTE"],
        is_individual=False,
    ),
    EntityType(
        name="CandidateDiagnosis",
        description="A diagnosis under consideration in the differential.",
        examples=["acute coronary syndrome", "pulmonary embolism"],
        is_individual=False,
    ),
    EntityType(
        name="RedFlag",
        description="A 'can't-miss' diagnosis that must be ranked regardless of likelihood.",
        examples=["aortic dissection", "subarachnoid hemorrhage"],
        is_individual=False,
    ),
    EntityType(
        name="DiscriminatingTest",
        description="A test that would meaningfully narrow the differential.",
        examples=["D-dimer", "CT angiography", "lumbar puncture"],
        is_individual=False,
    ),
    EntityType(
        name="Reasoner",
        description="A reasoning-archetype seat in the diagnostic panel.",
        examples=["generalist", "skeptic", "epidemiologist"],
        is_individual=True,
    ),
]

_EDGE_TYPES = [
    EdgeType(
        name="PRESENTS_WITH",
        description="The case presents with this symptom or sign.",
        source_targets=[["Presentation", "Symptom"], ["Presentation", "Sign"]],
    ),
    EdgeType(
        name="HAS_RISK_FACTOR",
        description="The case carries this risk factor.",
        source_targets=[["Presentation", "RiskFactor"]],
    ),
    EdgeType(
        name="HAS_PRIOR",
        description="The case has this prior condition.",
        source_targets=[["Presentation", "PriorCondition"]],
    ),
    EdgeType(
        name="SUGGESTS",
        description="A symptom, sign, or finding raises the prior for a diagnosis.",
        source_targets=[
            ["Symptom", "CandidateDiagnosis"],
            ["Sign", "CandidateDiagnosis"],
            ["Finding", "CandidateDiagnosis"],
        ],
    ),
    EdgeType(
        name="ARGUES_AGAINST",
        description="A finding lowers the prior for a diagnosis.",
        source_targets=[["Finding", "CandidateDiagnosis"]],
    ),
    EdgeType(
        name="INDICATED_BY",
        description="A test would help differentiate between candidates.",
        source_targets=[["DiscriminatingTest", "CandidateDiagnosis"]],
    ),
    EdgeType(
        name="RAISES",
        description="A red flag elevates a dangerous diagnosis on the differential.",
        source_targets=[["RedFlag", "CandidateDiagnosis"]],
    ),
    EdgeType(
        name="COMPLICATES",
        description="A prior condition complicates a candidate diagnosis.",
        source_targets=[["PriorCondition", "CandidateDiagnosis"]],
    ),
    EdgeType(
        name="EVALUATES",
        description="A reasoner evaluates a candidate diagnosis.",
        source_targets=[["Reasoner", "CandidateDiagnosis"]],
    ),
]

DX_EDUCATION_ONTOLOGY = Ontology(entity_types=_ENTITY_TYPES, edge_types=_EDGE_TYPES)


# --- Reasoning-archetype panel ------------------------------------------
_ROSTER = (
    RosterMember(
        role="Generalist / Internist",
        name="Generalist",
        bio="Builds the broad initial differential.",
        persona=(
            "A general internist who casts a wide net up front, weights "
            "candidates by epidemiology and presentation shape, and resists "
            "narrowing the differential too early."
        ),
        expertise=("clinical reasoning", "broad differential", "intake"),
        mandate=(
            "Generate the initial broad differential before specialists narrow it."
        ),
        caution=0.55,
    ),
    RosterMember(
        role="Cardiologist",
        name="Cardiology",
        bio="Argues for cardiovascular diagnoses where features fit.",
        persona=(
            "A cardiologist who pushes hard for cardiovascular candidates "
            "when the presentation, risk factors, or findings fit, and is "
            "explicit about which features are pathognomonic versus suggestive."
        ),
        expertise=("cardiology", "ACS", "heart failure", "arrhythmia"),
        mandate="Raise cardiovascular candidates and the evidence for/against.",
    ),
    RosterMember(
        role="Neurologist",
        name="Neurology",
        bio="Argues for neurological diagnoses where features fit.",
        persona=(
            "A neurologist who watches for focal deficits, headache features, "
            "and time-course patterns that distinguish vascular, infectious, "
            "and structural neurological causes."
        ),
        expertise=("neurology", "stroke", "headache", "neuro exam"),
        mandate="Raise neurological candidates and the evidence for/against.",
    ),
    RosterMember(
        role="Infectious Disease Specialist",
        name="Infectious Disease",
        bio="Argues for infectious diagnoses where features fit.",
        persona=(
            "An infectious-disease physician who anchors on host factors, "
            "exposure history, time course, and the inflammatory pattern; "
            "candid about when imaging or cultures should drive the call."
        ),
        expertise=("infectious disease", "sepsis", "exposure history"),
        mandate="Raise infectious candidates and the evidence for/against.",
    ),
    RosterMember(
        role="Skeptic",
        name="Skeptic",
        bio="Attacks the leading hypothesis to fight anchoring bias.",
        persona=(
            "A devil's-advocate reasoner whose job is to attack whichever "
            "diagnosis the panel currently favors. Forces the group to "
            "explicitly defend their leading hypothesis instead of drifting "
            "into premature closure."
        ),
        expertise=("debiasing", "anchoring", "premature closure"),
        mandate=(
            "Attack the leading hypothesis. Insist on explicit refuting features."
        ),
        stance="oppose",
        risk_tolerance=0.55,
        caution=0.5,
    ),
    RosterMember(
        role="Epidemiologist",
        name="Epidemiology",
        bio="Enforces base rates and pretest probability.",
        persona=(
            "A clinical epidemiologist who keeps prior probability in view: "
            "'common things are common'. Quick to point out when the panel "
            "is reaching for a zebra without justifying the prior."
        ),
        expertise=("pretest probability", "base rates", "epidemiology"),
        mandate="Hold the panel to base rates; flag low-prior reaches.",
        caution=0.7,
    ),
    RosterMember(
        role="Can't-Miss Agent",
        name="Can't-Miss",
        bio="Pushes dangerous diagnoses to the top regardless of likelihood.",
        persona=(
            "A safety-first reasoner whose job is to ensure the can't-miss "
            "diagnoses (aortic dissection, PE, subarachnoid hemorrhage, "
            "sepsis, MI, ectopic pregnancy, and the others matched to the "
            "presentation) are on the list and explicitly ruled in or out."
        ),
        expertise=("worst-case-first", "patient safety", "red flags"),
        mandate=(
            "Maintain the can't-miss list. No diagnosis is too unlikely to "
            "consider if its consequence is catastrophic."
        ),
        caution=0.85,
    ),
    RosterMember(
        role="Bayesian",
        name="Bayesian",
        bio="Keeps probability discipline and proposes discriminating tests.",
        persona=(
            "A Bayesian reasoner who insists on combining priors with "
            "likelihood ratios from each new piece of evidence, and proposes "
            "the test that would shift the posterior the most for the least "
            "cost or risk."
        ),
        expertise=("Bayesian reasoning", "likelihood ratios", "test selection"),
        mandate=(
            "Recommend the next discriminating test and justify it in terms "
            "of expected posterior shift."
        ),
        caution=0.6,
    ),
)


# --- Differential Diagnosis Brief outline -------------------------------
_REPORT_OUTLINE = (
    ReportSectionSpec(
        title="Presentation summary",
        description=(
            "A tight clinical summary of the case as it was presented: chief "
            "complaint, key features, risk factors, and relevant priors."
        ),
    ),
    ReportSectionSpec(
        title="Initial differential",
        description=(
            "The broad first-pass differential the generalist proposed, with "
            "rough priors and the shape of the case that drove each entry."
        ),
    ),
    ReportSectionSpec(
        title="Can't-miss differentials",
        description=(
            "The dangerous diagnoses that must be considered regardless of "
            "likelihood, each with the rule-in / rule-out test, preserved "
            "verbatim from the can't-miss reasoner."
        ),
    ),
    ReportSectionSpec(
        title="Discriminating tests",
        description=(
            "The next-best tests the panel recommends and how each would "
            "narrow the differential. Frame in terms of expected posterior "
            "shift, not just protocol."
        ),
    ),
    ReportSectionSpec(
        title="Evidence for and against the leading hypotheses",
        description=(
            "For each of the top 2-3 candidate diagnoses, the supporting "
            "features and the refuting features, including any direct "
            "challenges from the skeptic."
        ),
    ),
    ReportSectionSpec(
        title="Cognitive-bias flags",
        description=(
            "Explicit bias risks the panel raised: anchoring, premature "
            "closure, base-rate neglect, availability. Naming them is the point."
        ),
    ),
    ReportSectionSpec(
        title="Open questions and teaching points",
        description=(
            "What the panel could not resolve without more information, plus "
            "the one or two clinical-reasoning takeaways a learner should "
            "leave with."
        ),
    ),
)


DX_EDUCATION_DOMAIN = DomainProfile(
    key="quorum_dx_education",
    name="Quorum Dx (education)",
    description=(
        "Diagnostic-reasoning gym for medical students, residents, and "
        "clinical-reasoning curricula. A reasoning-archetype panel debates "
        "the differential and emits a Differential Diagnosis Brief. "
        "Education only — synthetic cases, no PHI, no clinical decisions."
    ),
    fixed_ontology=DX_EDUCATION_ONTOLOGY,
    fixed_agent_roster=_ROSTER,
    fixed_report_outline=_REPORT_OUTLINE,
    report_title_template="Differential Diagnosis Brief — {project_title}",
    report_summary=(
        "Reasoning-archetype panel deliberation on the case below. "
        "Education only — not for use with real patients."
    ),
    report_section_system_prompt=(
        "You are writing one section of a Differential Diagnosis Brief from "
        "a virtual reasoning panel. Write in clinical-tutor prose: factual, "
        "specific, and oriented toward clinical-reasoning instruction. Quote "
        "reasoner agents verbatim with `>` blockquote syntax where their "
        "argument supports a point. Do not invent clinical details the panel "
        "did not produce. This brief is for education only — do not give "
        "advice that should drive care for a real patient. Output 200-400 "
        "words of markdown body — no headings."
    ),
    report_provenance_footer=True,
)
