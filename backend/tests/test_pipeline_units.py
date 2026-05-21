"""Unit tests for pure helpers across the pipeline stages (Phase 1).

These tests target individual functions so a failure points at one place
without needing the full e2e flow.
"""

from quorum_backend.pipeline.env_setup import (
    _coerce_age,
    _coerce_float,
    _coerce_gender,
    _coerce_mbti,
    _fallback_profile,
    _is_speaker_capable,
    _persona_dict_to_profile,
    _slugify_username,
    _tokenize_type,
)
from quorum_backend.pipeline.file_parser import (
    SUPPORTED_EXTENSIONS,
    aggregate_documents,
    extract_text_from_bytes,
)
from quorum_backend.pipeline.models import GraphEntityNode
from quorum_backend.pipeline.ontology_generator import _validate_and_normalize


# --- Ontology validator --------------------------------------------------

def test_ontology_pads_to_ten_entity_types_with_fallbacks():
    parsed = {
        "entity_types": [
            {"name": "Custom1", "description": "x", "is_individual": True},
            {"name": "Custom2", "description": "x", "is_individual": False},
        ],
        "edge_types": [
            {
                "name": "RELATES_TO",
                "description": "x",
                "source_targets": [["Custom1", "Custom2"]],
            }
        ],
    }
    ontology = _validate_and_normalize(parsed)
    assert ontology is not None
    names = [e.name for e in ontology.entity_types]
    assert len(names) == 10
    assert "Person" in names and "Organization" in names


def test_ontology_clips_excess_concrete_types_keeping_fallbacks():
    entity_types = [
        {"name": f"Type{i}", "description": "x", "is_individual": True}
        for i in range(12)
    ]
    parsed = {"entity_types": entity_types, "edge_types": []}
    ontology = _validate_and_normalize(parsed)
    assert ontology is not None
    names = [e.name for e in ontology.entity_types]
    assert len(names) == 10
    # Person and Organization are added; concrete types are clipped to 8.
    assert "Person" in names and "Organization" in names


def test_ontology_padded_with_default_edges_when_too_few():
    parsed = {
        "entity_types": [
            {"name": "A", "description": "x", "is_individual": True}
        ],
        "edge_types": [],
    }
    ontology = _validate_and_normalize(parsed)
    assert ontology is not None
    edge_names = {e.name for e in ontology.edge_types}
    # Defaults like RELATES_TO are inserted.
    assert "RELATES_TO" in edge_names


def test_ontology_normalizes_edge_names_to_upper_snake():
    parsed = {
        "entity_types": [{"name": "X", "description": "", "is_individual": True}],
        "edge_types": [
            {"name": "reports-on", "description": "", "source_targets": [["X", "X"]]},
        ],
    }
    ontology = _validate_and_normalize(parsed)
    assert ontology is not None
    assert any(e.name == "REPORTS_ON" for e in ontology.edge_types)


# --- Type / speaker detection -------------------------------------------

def test_tokenize_pascal_case_to_lowercase_tokens():
    assert _tokenize_type("MediaOutlet") == ["media", "outlet"]
    assert _tokenize_type("Person") == ["person"]
    assert _tokenize_type("") == []


def test_speaker_detection_uses_head_pattern():
    # "Outlet" is a speaker pattern -> MediaOutlet is a speaker.
    assert _is_speaker_capable("MediaOutlet", is_individual=False) is True
    # "Location" is a non-speaker pattern.
    assert _is_speaker_capable("Location", is_individual=False) is False
    # Plain person -> always speaker.
    assert _is_speaker_capable("Person", is_individual=True) is True
    # Unknown -> falls back to is_individual.
    assert _is_speaker_capable("Mystery", is_individual=True) is True
    assert _is_speaker_capable("Mystery", is_individual=False) is False


# --- Coercion helpers ----------------------------------------------------

def test_coerce_float_clamps_to_unit_interval():
    assert _coerce_float(0.5) == 0.5
    assert _coerce_float(2.0) == 1.0
    assert _coerce_float(-0.3) == 0.0
    assert _coerce_float("not a number", default=0.42) == 0.42


def test_coerce_age_handles_organizations_and_invalid_input():
    assert _coerce_age(45, is_individual=True) == 45
    assert _coerce_age("garbage", is_individual=False) == 30
    # Bounded to [18, 95]
    assert _coerce_age(-5, is_individual=True) == 18
    assert _coerce_age(200, is_individual=True) == 95


def test_coerce_gender_normalizes_and_defaults_for_groups():
    assert _coerce_gender("Female", is_individual=True) == "female"
    assert _coerce_gender("xyz", is_individual=False) == "other"


def test_coerce_mbti_validates_known_types():
    assert _coerce_mbti("intj", is_individual=True) == "INTJ"
    # Organization with garbage -> ISTJ (rigorous-conservative default).
    assert _coerce_mbti("???", is_individual=False) == "ISTJ"


def test_slugify_username_strips_and_appends_suffix():
    slug = _slugify_username("Patient Advocate")
    assert slug.startswith("patientadvocate_")
    # Suffix is a 3-digit number.
    assert slug.split("_")[-1].isdigit() and len(slug.split("_")[-1]) == 3


def test_slugify_empty_name_falls_back_to_agent():
    assert _slugify_username("!!!").startswith("agent_")


# --- Persona builders ----------------------------------------------------

def _entity(name="Aria", type_="Expert", is_individual=True):
    return GraphEntityNode(
        id="ent_test", name=name, type=type_, description="", is_individual=is_individual
    )


def test_persona_dict_to_profile_coerces_and_unescapes_persona():
    persona_dict = {
        "role": "Senior Analyst",
        "bio": "Tracks risk closely.",
        "persona": "Background: x.\\n\\nBehavior: precise.",
        "expertise": ["risk", "policy", "evidence"],
        "stance": "Support",
        "age": "47",
        "gender": "female",
        "mbti": "intp",
        "optimism": "0.6",
        "risk_tolerance": "9",  # out-of-range, clamps to 1.0
    }
    profile = _persona_dict_to_profile(persona_dict, _entity())
    assert profile.role == "Senior Analyst"
    assert profile.stance == "support"
    assert profile.age == 47
    assert profile.mbti == "INTP"
    assert profile.optimism == 0.6
    assert profile.risk_tolerance == 1.0
    assert "\n\n" in profile.persona
    assert profile.source_entity_id == "ent_test"


def test_persona_dict_to_profile_defaults_stance_when_unknown():
    profile = _persona_dict_to_profile({"stance": "wavering"}, _entity())
    assert profile.stance == "neutral"


def test_fallback_profile_uses_entity_metadata():
    profile = _fallback_profile(_entity(name="Org X", type_="Company", is_individual=False))
    assert profile.name == "Org X"
    assert profile.role == "Company"
    assert profile.is_individual is False
    assert profile.gender == "other"


# --- File parser ---------------------------------------------------------

def test_extract_text_from_bytes_decodes_utf8_text():
    text = "Hello, swarm.\nThis is a seed."
    out = extract_text_from_bytes("seed.txt", text.encode("utf-8"))
    assert out == text


def test_extract_text_from_bytes_falls_back_for_non_utf8():
    out = extract_text_from_bytes("seed.txt", "café".encode("latin-1"))
    assert "caf" in out


def test_extract_text_from_bytes_rejects_unsupported_extensions():
    try:
        extract_text_from_bytes("seed.exe", b"x")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_extract_text_from_bytes_rejects_oversize_input():
    big = b"a" * (8 * 1024 * 1024 + 1)
    try:
        extract_text_from_bytes("seed.txt", big)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_supported_extensions_covers_documented_set():
    assert {".pdf", ".md", ".markdown", ".txt"} <= SUPPORTED_EXTENSIONS


def test_aggregate_documents_skips_empties_and_writes_headers():
    out = aggregate_documents([("a.txt", "first"), ("b.txt", ""), ("c.txt", "third")])
    # Empty docs are skipped; remaining docs keep their original numbering.
    assert "Document 1: a.txt" in out
    assert "Document 3: c.txt" in out
    assert "b.txt" not in out
    assert "first" in out and "third" in out


def test_aggregate_documents_truncates_when_over_budget():
    docs = [(f"doc{i}.txt", "x" * 30_000) for i in range(5)]
    out = aggregate_documents(docs, max_total_chars=40_000)
    assert "additional documents truncated" in out
    assert len(out) <= 40_500  # small overhead for headers
