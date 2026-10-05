"""Pocha create/update: only the admin named by the token may write."""

ADMIN = "admin@example.com"
STUDENT = "student@example.com"


def pocha_body(menus):
    return {
        "startDate": "2026-11-01T18:00:00",
        "endDate": "2026-11-01T23:00:00",
        "title": "New Pocha",
        "description": "created by the test",
        "menus": menus,
    }


NEW_MENU = {"nameKor": "떡볶이", "nameEng": "Tteokbokki", "category": "food",
            "price": 6.0, "stock": 10, "isImmediatePrep": False}

# The three menus pocha 1 already has, so an update deletes nothing.
POCHA_1_MENUS = [
    {"nameKor": "김밥", "nameEng": "Kimbap", "category": "food",
     "price": 5.0, "stock": 20, "isImmediatePrep": False},
    {"nameKor": "소주", "nameEng": "Soju", "category": "drink",
     "price": 12.5, "stock": 10, "isImmediatePrep": True, "ageCheckRequired": True},
    {"nameKor": "콜라", "nameEng": "Cola", "category": "drink",
     "price": 2.0, "stock": 30, "isImmediatePrep": True},
]


def pocha_count(db):
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM pocha")
        return cursor.fetchone()[0]


def pocha_title(db, pocha_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT title FROM pocha WHERE pochaid = %s", (pocha_id,))
        return cursor.fetchone()[0]


def test_create_rejects_non_admin_claiming_admin_email(pocha_scenario, client, auth):
    body = {**pocha_body([NEW_MENU]), "email": ADMIN}
    response = client.post("/api/v2/pocha/", json=body, headers=auth(STUDENT))
    assert response.status_code == 403
    assert pocha_count(pocha_scenario) == 2


def test_create_rejects_missing_token(pocha_scenario, client):
    body = {**pocha_body([NEW_MENU]), "email": ADMIN}
    response = client.post("/api/v2/pocha/", json=body)
    assert response.status_code == 401
    assert pocha_count(pocha_scenario) == 2


def test_create_allows_admin_token_without_body_email(pocha_scenario, client, auth):
    response = client.post("/api/v2/pocha/", json=pocha_body([NEW_MENU]), headers=auth(ADMIN))
    assert response.status_code == 201
    assert pocha_count(pocha_scenario) == 3


def test_update_rejects_non_admin_claiming_admin_email(pocha_scenario, client, auth):
    body = {**pocha_body(POCHA_1_MENUS), "email": ADMIN}
    response = client.put("/api/v2/pocha/1/", json=body, headers=auth(STUDENT))
    assert response.status_code == 403
    assert pocha_title(pocha_scenario, 1) == "Test Pocha"


def test_update_allows_admin_token_without_body_email(pocha_scenario, client, auth):
    response = client.put("/api/v2/pocha/1/", json=pocha_body(POCHA_1_MENUS), headers=auth(ADMIN))
    assert response.status_code == 200
    assert pocha_title(pocha_scenario, 1) == "New Pocha"
