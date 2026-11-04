import copy

from app.models.entities import Company, Opportunity, OpportunityNote
from app.services.crm_service import add_note, add_tag, ensure_opportunity, update_opportunity


def _company(session, name="Hotel Sole", city="Palermo", website="https://hotelsole.test", **kwargs) -> Company:
    company = Company(
        name=name, city=city, category="hotel", source="fake", external_id=name.lower(),
        status="discovered", website_url=website, **kwargs,
    )
    session.add(company)
    session.flush()
    ensure_opportunity(session, company)
    session.commit()
    return company


def test_export_contains_full_company_data(client, db_session) -> None:
    company = _company(db_session, phone="+39 091 123456")
    opportunity = ensure_opportunity(db_session, company)
    add_note(db_session, opportunity.id, "Nota esistente")
    add_tag(db_session, opportunity.id, "Boutique")
    update_opportunity(db_session, opportunity.id, status="shortlisted", is_favorite=True)

    data = client.get("/opportunities/export", params={"city": "palermo"}).json()

    assert data["format"] == "revampradar.pipeline"
    assert data["total"] == 1
    item = data["companies"][0]
    assert item["company_id"] == str(company.id)
    assert item["phone"] == "+39091123456" or item["phone"]
    assert item["status"] == "shortlisted" and item["is_favorite"] is True
    assert item["tags"] == ["boutique"]
    assert [n["body"] for n in item["notes"]] == ["Nota esistente"]
    assert item["activities"][0]["type"] == "status_change"
    assert item["new_notes"] == []


def test_export_respects_filters(client, db_session) -> None:
    _company(db_session, "Hotel Sole", "Palermo")
    _company(db_session, "Hotel Luna", "Roma", website="https://hotelluna.test")
    data = client.get("/opportunities/export", params={"city": "Roma"}).json()
    assert [c["name"] for c in data["companies"]] == ["Hotel Luna"]
    assert client.get("/opportunities/export", params={"status": "nope"}).status_code == 422


def test_import_updates_without_erasing_existing_data(client, db_session) -> None:
    company = _company(db_session, phone="+390911", email="old@hotelsole.test")
    data = client.get("/opportunities/export").json()
    item = data["companies"][0]
    item.update(
        phone="", email="", city="Bagheria", status="uncontactable",
        social_links=[{"label": "Instagram", "url": "instagram.com/hotelsole"}],
        tags=["Chiuso"], new_notes=["Risulta chiuso", "Risulta chiuso"], is_favorite=True,
        website_url="www.hotelsole-nuovo.it",
    )

    result = client.post("/opportunities/import", json=data)

    assert result.status_code == 200
    assert result.json()["updated"] == 1 and result.json()["errors"] == []
    db_session.expire_all()
    company = db_session.get(Company, company.id)
    assert company.phone == "+390911" and company.email == "old@hotelsole.test"
    assert company.city == "Bagheria"
    assert company.website_url.startswith("https://www.hotelsole-nuovo.it")
    assert company.extra["social_links"] == [{"label": "Instagram", "url": "https://instagram.com/hotelsole"}]
    opportunity = db_session.query(Opportunity).filter_by(company_id=company.id).one()
    assert opportunity.status == "uncontactable" and opportunity.is_favorite is True
    assert [n.body for n in db_session.query(OpportunityNote).all()] == ["Risulta chiuso"]

    again = client.post("/opportunities/import", json=client.get("/opportunities/export").json())
    assert again.json()["updated"] == 0 and again.json()["unchanged"] == 1


def test_import_reports_errors_and_keeps_other_rows(client, db_session) -> None:
    _company(db_session, "Hotel Sole", "Palermo")
    _company(db_session, "Hotel Luna", "Roma", website="https://hotelluna.test")
    data = client.get("/opportunities/export").json()
    bad, good = copy.deepcopy(data["companies"])
    bad["status"], bad["phone"] = "boh", "+39 333 0000000"
    good["email"] = "info@hotelluna.test"
    data["companies"] = [bad, good, {"name": "Fantasma", "company_id": "x"}]

    body = client.post("/opportunities/import", json=data).json()

    assert body["updated"] == 1 and len(body["errors"]) == 2
    db_session.expire_all()
    assert db_session.query(Company).filter_by(phone="+393330000000").count() == 0
    assert db_session.query(Company).filter_by(email="info@hotelluna.test").count() == 1


def test_import_rejects_foreign_file(client) -> None:
    assert client.post("/opportunities/import", json={"hello": 1}).status_code == 422
    assert client.post("/opportunities/import", json=[1, 2]).status_code == 422
