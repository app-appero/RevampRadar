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
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "instagram.com/example" in output.html
    assert "digital_presence" in output.sections
    assert "facebook.com" not in output.html


def test_generator_uses_real_service_items_instead_of_generic_placeholders() -> None:
    company = _make_company(category="parrucchiere")
    design_brief = build_default_design_brief(company)
    brief = {
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [
            {
                "kind": "servizi",
                "url": "https://example.test/servizi",
                "title": "Servizi",
                "text_excerpt": "...",
                "items": [
                    {"heading": "Taglio uomo", "text": "Taglio classico o moderno."},
                    {"heading": "Colore", "text": "Colorazione e balayage."},
                ],
            }
        ],
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "Taglio uomo" in output.html
    assert "Colorazione e balayage" in output.html
    assert "service-card" in output.html
    assert "Servizio 1" not in output.html
    assert "placeholder-card" not in output.html


def test_generator_different_companies_produce_different_content() -> None:
    """Due aziende con brief diversi non devono produrre lo stesso HTML (regressione
    per il caso in cui tutto ricade sullo stesso fallback generico)."""
    company_a = _make_company(name="Trattoria Del Borgo", category="ristorante")
    company_b = _make_company(name="Studio Legale Bianchi", category="studio legale")
    design_a = build_default_design_brief(company_a)
    design_b = build_default_design_brief(company_b)
    brief_a = {
        "what_it_does": "Trattoria di famiglia a conduzione diretta dal 1998.",
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [],
    }
    brief_b = {
        "what_it_does": "Studio legale specializzato in diritto civile e societario.",
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [],
    }
    output_a = generate_concept(company_a, brief=brief_a, design_brief=design_a)
    output_b = generate_concept(company_b, brief=brief_b, design_brief=design_b)
    assert output_a.html != output_b.html
    assert "Trattoria di famiglia" in output_a.html
    assert "Studio legale specializzato" in output_b.html


def test_generator_shows_verified_business_signals_as_numbers() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    brief = {
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [],
        "business_signals": {
            "revenue_available": True,
            "revenue_latest": {
                "value": "850000",
                "unit": "EUR",
                "period": "2024",
                "source": "Visura camerale",
                "confidence": "verified",
                "is_manual": False,
            },
            "employees": {
                "value": "12",
                "unit": None,
                "period": None,
                "source": "Inserito a mano",
                "confidence": "manual",
                "is_manual": True,
            },
            "founding_year": None,
            "legal_form": None,
            "revenue_trend": None,
        },
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "In cifre" in output.html
    assert "850000" in output.html
    assert "Fatturato" in output.html
    assert "fonte: Visura camerale" in output.html
    assert "dato inserito manualmente" in output.html
    assert "numbers" in output.sections


def test_generator_omits_numbers_section_without_business_signals() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    output = generate_concept(company, brief=None, design_brief=design_brief)
    assert "In cifre" not in output.html
    assert "numbers" not in output.sections


def test_generator_builds_about_section_from_real_chi_siamo_page() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    brief = {
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [
            {
                "kind": "homepage",
                "url": "https://example.test/",
                "title": None,
                "text_excerpt": "",
                "items": [],
                "images": [{"url": "https://example.test/foto/hero.jpg", "alt": "Ingresso"}],
            },
            {
                "kind": "chi_siamo",
                "url": "https://example.test/chi-siamo",
                "title": "Chi siamo",
                "text_excerpt": "Siamo una trattoria di famiglia attiva dal 1998 nel centro di Foggia.",
                "items": [],
                "images": [{"url": "https://example.test/foto/sala.jpg", "alt": "La sala"}],
            },
        ],
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "Siamo una trattoria di famiglia" in output.html
    assert "https://example.test/foto/sala.jpg" in output.html
    assert '<section class="about">' in output.html
    assert "about-media" in output.html


def test_generator_strengths_show_real_evidence_quote() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    brief = {
        "value_elements": [
            {
                "label": "Storia/anzianità dichiarata",
                "evidence": "la nostra trattoria è aperta dal 1998",
                "source": "https://example.test/chi-siamo",
            }
        ],
        "digital_presence": {"channels": {}},
        "pages_researched": [],
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "Storia/anzianità dichiarata" in output.html
    assert "aperta dal 1998" in output.html
    assert "strength-card" in output.html


def test_generator_hero_layout_varies_by_category_group() -> None:
    hospitality = _make_company(name="Trattoria Del Borgo", category="ristorante")
    professional = _make_company(name="Studio Legale Bianchi", category="studio legale")
    design_hospitality = build_default_design_brief(hospitality)
    design_professional = build_default_design_brief(professional)
    output_hospitality = generate_concept(hospitality, brief=None, design_brief=design_hospitality)
    output_professional = generate_concept(professional, brief=None, design_brief=design_professional)
    assert "hero--banner" in output_hospitality.html
    assert "hero--centered" in output_professional.html


def test_generator_gallery_only_shown_with_enough_real_images() -> None:
    company = _make_company()
    design_brief = build_default_design_brief(company)
    images = [{"url": f"https://example.test/foto/{i}.jpg", "alt": None} for i in range(5)]
    brief = {
        "value_elements": [],
        "digital_presence": {"channels": {}},
        "pages_researched": [
            {
                "kind": "homepage",
                "url": "https://example.test/",
                "title": None,
                "text_excerpt": "",
                "items": [],
                "images": images[:1],
            },
            {
                "kind": "servizi",
                "url": "https://example.test/servizi",
                "title": None,
                "text_excerpt": "",
                "items": [],
                "images": images[1:],
            },
        ],
    }
    output = generate_concept(company, brief=brief, design_brief=design_brief)
    assert "gallery" in output.sections
    assert "gallery-grid" in output.html


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


def test_generate_new_concept_always_uses_deterministic_generator(db_session, tmp_path: Path) -> None:
    company = _make_company(website_url="https://esempio-reale.test")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(CompanyResearch(company_id=company.id, status="completed", research_version="test", brief=None))
    db_session.commit()

    concept = generate_new_concept(db_session, company.id, Settings(concept_dir=str(tmp_path)))
    assert concept.source == "deterministic"
    assert concept.error_message is None
    assert PLACEHOLDER_MARK in Path(concept.html_path).read_text(encoding="utf-8")


def test_generate_new_concept_uses_template_without_website(db_session, tmp_path: Path) -> None:
    company = _make_company(website_url=None)
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    db_session.add(CompanyResearch(company_id=company.id, status="partial", research_version="test", brief=None))
    db_session.commit()

    concept = generate_new_concept(db_session, company.id, Settings(concept_dir=str(tmp_path)))
    assert concept.source == "deterministic"
    assert concept.error_message is None
    assert PLACEHOLDER_MARK in Path(concept.html_path).read_text(encoding="utf-8")
