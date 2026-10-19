from app.models.entities import Company, Opportunity


def seed(db, name, category, city="Verona", status="discovered", favorite=False):
    company = Company(name=name, category=category, city=city, source="fake", status="discovered")
    db.add(company)
    db.flush()
    db.add(Opportunity(company_id=company.id, status=status, is_favorite=favorite))
    db.commit()


def test_category_facets_follow_filters_and_group_variants(client, db_session):
    seed(db_session, "A", "Hotel")
    seed(db_session, "B", "hotel")
    seed(db_session, "C", "barbiere")
    seed(db_session, "D", "barbieri")
    seed(db_session, "E", "ristorante", city="Roma")
    seed(db_session, "F", "bar", status="contacted")
    params = {"city": "Verona", "status": "discovered", "segment": "greenfield"}
    response = client.get("/opportunities/categories", params=params)
    assert response.status_code == 200
    categories = response.json()
    assert [(item["value"], item["count"]) for item in categories] == [("barbiere", 2), ("hotel", 2)]
    for category in categories:
        results = client.get("/opportunities", params={**params, "category": category["value"]}).json()
        assert len(results) == category["count"]
    assert client.get("/opportunities/categories", params={**params, "favorite": True}).json() == []
    assert client.get("/opportunities/categories", params={**params, "min_score": 100}).json() == []


def test_exact_sector_does_not_include_substrings(client, db_session):
    seed(db_session, "A", "bar")
    seed(db_session, "B", "barbiere")
    seed(db_session, "C", "barbieri")
    assert len(client.get("/opportunities", params={"category": "bar"}).json()) == 1
    assert len(client.get("/opportunities", params={"category": " BARBIERI "}).json()) == 2


def test_facets_ignore_category_itself(client, db_session):
    seed(db_session, "A", "Hotel")
    seed(db_session, "B", "bar")
    data = client.get("/opportunities/categories", params={"category": "hotel"}).json()
    assert len(data) == 2
