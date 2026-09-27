from pathlib import Path

import pytest

from app.concept.design_brief import build_default_design_brief, category_group
from app.concept.generator import PLACEHOLDER_MARK, generate_concept
from app.concept.service import ConceptError, delete_concept, generate_new_concept, list_concepts
from app.config import Settings
from app.models.entities import Company, CompanyResearch
from app.services.design_brief_service import get_or_create_design_brief, regenerate_design_brief, update_design_brief


def _make_company(**kwargs) -> Company:
    defaults = dict(
        name="Trattoria Del Borgo", category="ristorante", city="Foggia", source="manual", status="discovered"
    )
    defaults.update(kwargs)
    return Company(**defaults)


def test_category_group_maps_known_categories() -> None:
    assert category_group("ristorante") == "hospitality"
    assert category_group("Studio legale") == "professional"
    assert category_group("elettricista") == "trade"
    assert category_group("qualcosa di sconosciuto") == "default"
    assert category_group(None) == "default"


def test_default_design_brief_uses_brand_color_when_valid() -> None:
    company = _make_company(category="ristorante")
    brief = build_default_design_brief(company, theme_color="#123456")
    assert brief["palette"][0]["hex"] == "#123456"
    assert brief["style"] == "caldo e accogliente"


def test_default_design_brief_ignores_invalid_theme_color() -> None:
    company = _make_company(category="ristorante")
    brief = build_default_design_brief(company, theme_color="not-a-color")
    assert brief["palette"][0]["hex"] != "not-a-color"


def test_generator_never_fabricates_missing_content() -> None:
    company = _make_company(category="ristorante", phone=None, email=None, city=None)
    design_brief = build_default_design_brief(company)
    output = generate_concept(company, brief=None, design_brief=design_brief)
    assert "Concept dimostrativo" in output.html
    assert PLACEHOLDER_MARK in output.html
    assert "hero" in output.sections


def test_generator_uses_real_contact_when_available() -> None:
    company = _make_company(phone="+390881000000", email="info@example.test", city="Foggia")
    design_brief = build_default_design_brief(company)
    output = generate_concept(company, brief=None, design_brief=design_brief)
    assert "+390881000000" in output.html
    assert "info@example.test" in output.html


def test_generator_only_lists_found_digital_channels() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    brief = {
        "value_elements": [],
        "digital_presence": {
            "channels": {
                "instagram": {"found": True, "url": "https://instagram.com/example", "source": "sito"},
                "facebook": {"found": False, "url": None, "source": None},
            }
        },
        "pages_researched": [],
        "website_findings": {"pages": []},
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "instagram.com/example" in output.html
    assert "digital_presence" in output.sections
    assert "facebook.com" not in output.html


def test_design_brief_manual_update_marks_source_manual(db_session) -> None:
    from app.schemas.concept import DesignBriefUpdate

    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    default = get_or_create_design_brief(db_session, company.id)
    assert default.source == "auto"

    updated = update_design_brief(db_session, company.id, DesignBriefUpdate(primary_cta="Chiamaci ora"))
    assert updated.source == "manual"
    assert updated.primary_cta == "Chiamaci ora"

    regenerated = regenerate_design_brief(db_session, company.id)
    assert regenerated.source == "auto"
    assert regenerated.primary_cta != "Chiamaci ora"


def test_generate_new_concept_requires_research(db_session, tmp_path: Path) -> None:
    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    with pytest.raises(ConceptError):
        generate_new_concept(db_session, company.id, Settings(concept_dir=str(tmp_path)))


def test_generate_new_concept_versions_and_delete(db_session, tmp_path: Path) -> None:
    company = _make_company()
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    research = CompanyResearch(company_id=company.id, status="completed", research_version="test", brief=None)
    db_session.add(research)
    db_session.commit()

    settings = Settings(concept_dir=str(tmp_path))
    first = generate_new_concept(db_session, company.id, settings)
    assert first.version == 1
    assert first.is_current is True
    assert Path(first.html_path).exists()
    assert Path(first.css_path).exists()

    second = generate_new_concept(db_session, company.id, settings)
    assert second.version == 2
    assert second.is_current is True

    concepts = list_concepts(db_session, company.id)
    assert {item.version: item.is_current for item in concepts} == {1: False, 2: True}

    delete_concept(db_session, company.id, second.id)
    assert not Path(second.html_path).exists()
    remaining = list_concepts(db_session, company.id)
    assert len(remaining) == 1
    assert remaining[0].is_current is True
