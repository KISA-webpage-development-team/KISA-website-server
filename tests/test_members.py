"""/about/members board roster: public read and admin management."""
import pathlib

import pytest

ADMIN = "admin@example.com"
STUDENT = "student@example.com"
SEED = pathlib.Path(__file__).resolve().parent.parent / "queries" / "boardmembers_seed.sql"


@pytest.fixture
def board(db):
    """An admin, a student, and helpers that insert board rows directly.

    year(start_year, published=False) inserts a board year.
    entry(start_year, name, tier="member", position=0, ...) inserts an entry
    and returns its id.
    """
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear) VALUES
                ('admin@example.com',   'Admin User',   2000, 1, 1, 'CS', 2026),
                ('student@example.com', 'Student User', 2001, 2, 2, 'EE', 2027);
            INSERT INTO admins (email) VALUES ('admin@example.com');
        """)

    class Board:
        @staticmethod
        def year(start_year, published=False):
            with db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO boardyears (startyear, published) VALUES (%s, %s)",
                    (start_year, published),
                )

        @staticmethod
        def entry(start_year, name, tier="member", position=0, roles=("Event Planning",),
                  is_lead=False, major="Statistics", class_year=2027):
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO boardmembers
                        (startyear, name, major, classyear, roles, islead, tier, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING boardmemberid
                    """,
                    (start_year, name, major, class_year, list(roles), is_lead, tier, position),
                )
                return cursor.fetchone()[0]

    return Board


def new_entry(**overrides):
    body = {
        "name": "Jessica Moon",
        "major": "Information Analysis",
        "classYear": 2027,
        "roles": ["Event Planning Lead/Finance"],
        "isLead": True,
        "tier": "member",
    }
    body.update(overrides)
    return body


def names(year):
    return [entry["name"] for entry in year["entries"]]


def admin_year(client, auth, start_year):
    years = client.get("/api/v2/members/admin/", headers=auth(ADMIN)).json
    return next(year for year in years if year["startYear"] == start_year)


# ---- public read ----------------------------------------------------------------

def test_public_lists_published_years_newest_first_with_ordered_entries(board, client):
    board.year(2024, published=True)
    board.year(2025, published=True)
    board.year(2026)                                    # unpublished: hidden
    board.entry(2025, "Member B", position=3)
    board.entry(2025, "Member A", position=2)
    board.entry(2025, "President", tier="president", position=5, roles=("President Lead",))
    board.entry(2026, "Draft")

    response = client.get("/api/v2/members/")

    assert response.status_code == 200
    years = response.json
    assert [(year["startYear"], year["label"]) for year in years] == [(2025, "25-26"), (2024, "24-25")]
    assert names(years[0]) == ["President", "Member A", "Member B"]
    assert years[1]["entries"] == []


def test_public_entry_fields(board, client):
    board.year(2025, published=True)
    entry_id = board.entry(2025, "Jiwon", roles=("Web Development", "Design"), is_lead=True)

    entry = client.get("/api/v2/members/").json[0]["entries"][0]

    assert entry == {
        "boardMemberID": entry_id,
        "name": "Jiwon",
        "major": "Statistics",
        "classYear": 2027,
        "roles": ["Web Development", "Design"],
        "isLead": True,
        "tier": "member",
    }


def test_label_crosses_the_century(board, client):
    board.year(2099, published=True)
    assert client.get("/api/v2/members/").json[0]["label"] == "99-00"


def test_public_read_is_two_queries(board, client, query_log):
    for start_year in (2023, 2024, 2025):
        board.year(start_year, published=True)
        board.entry(start_year, f"Member {start_year}")

    client.get("/api/v2/members/")

    assert len(query_log) == 2


# ---- admin auth -------------------------------------------------------------------

def test_admin_routes_reject_non_admin(board, client, auth):
    board.year(2026)
    entry_id = board.entry(2026, "Draft")
    attempts = [
        client.get("/api/v2/members/admin/", headers=auth(STUDENT)),
        client.post("/api/v2/members/years/", json={"startYear": 2027}, headers=auth(STUDENT)),
        client.post("/api/v2/members/years/2026/publish/", headers=auth(STUDENT)),
        client.post("/api/v2/members/years/2026/unpublish/", headers=auth(STUDENT)),
        client.delete("/api/v2/members/years/2026/", headers=auth(STUDENT)),
        client.put("/api/v2/members/years/2026/order/", json={"order": [entry_id]}, headers=auth(STUDENT)),
        client.post("/api/v2/members/years/2026/entries/", json=new_entry(), headers=auth(STUDENT)),
        client.put(f"/api/v2/members/entries/{entry_id}/", json=new_entry(), headers=auth(STUDENT)),
        client.delete(f"/api/v2/members/entries/{entry_id}/", headers=auth(STUDENT)),
    ]
    assert [response.status_code for response in attempts] == [403] * len(attempts)


def test_admin_routes_reject_missing_token(board, client):
    response = client.post("/api/v2/members/years/", json={"startYear": 2027})
    assert response.status_code == 401


# ---- admin list -------------------------------------------------------------------

def test_admin_lists_every_year_with_published_state_and_audit_fields(board, client, auth):
    board.year(2025, published=True)
    board.year(2026)
    board.entry(2026, "Draft")

    years = client.get("/api/v2/members/admin/", headers=auth(ADMIN)).json

    assert [(year["startYear"], year["published"]) for year in years] == [(2026, False), (2025, True)]
    entry = years[0]["entries"][0]
    assert entry["startYear"] == 2026
    assert entry["position"] == 0
    assert {"createdBy", "updatedBy", "created", "updated"} <= entry.keys()


# ---- board years ------------------------------------------------------------------

def test_create_empty_year_is_unpublished(board, client, auth):
    response = client.post("/api/v2/members/years/", json={"startYear": 2026}, headers=auth(ADMIN))

    assert response.status_code == 201
    assert response.json == {"startYear": 2026, "label": "26-27", "published": False, "entries": []}
    assert client.get("/api/v2/members/").json == []


def test_create_year_copied_from_existing_year(board, client, auth):
    board.year(2025, published=True)
    board.entry(2025, "President", tier="president", position=0, roles=("President Lead",))
    board.entry(2025, "Member B", position=2)
    board.entry(2025, "Member A", position=1, is_lead=True)

    response = client.post(
        "/api/v2/members/years/", json={"startYear": 2026, "copyFrom": 2025}, headers=auth(ADMIN)
    )

    assert response.status_code == 201
    year = response.json
    assert year["published"] is False
    assert names(year) == ["President", "Member A", "Member B"]
    copied = year["entries"][1]
    assert (copied["startYear"], copied["isLead"], copied["position"]) == (2026, True, 1)
    assert copied["createdBy"] == ADMIN
    assert names(admin_year(client, auth, 2025)) == ["President", "Member A", "Member B"]


def test_create_existing_year_conflicts(board, client, auth):
    board.year(2026)
    response = client.post("/api/v2/members/years/", json={"startYear": 2026}, headers=auth(ADMIN))
    assert response.status_code == 409


@pytest.mark.parametrize("body", [
    {},
    {"startYear": "2026"},
    {"startYear": 26},
    {"startYear": True},
    {"startYear": 2026, "copyFrom": "2025"},
    {"startYear": 2026, "copyFrom": 2019},             # no such year
])
def test_create_year_rejects_bad_input(board, client, auth, body):
    response = client.post("/api/v2/members/years/", json=body, headers=auth(ADMIN))
    assert response.status_code == 400


def test_publish_and_unpublish(board, client, auth):
    board.year(2026)
    board.entry(2026, "Draft")

    published = client.post("/api/v2/members/years/2026/publish/", headers=auth(ADMIN))
    assert published.status_code == 200
    assert published.json["published"] is True
    assert names(client.get("/api/v2/members/").json[0]) == ["Draft"]

    unpublished = client.post("/api/v2/members/years/2026/unpublish/", headers=auth(ADMIN))
    assert unpublished.status_code == 200
    assert unpublished.json["published"] is False
    assert client.get("/api/v2/members/").json == []


def test_publish_state_conflicts_and_missing_year(board, client, auth):
    board.year(2025, published=True)
    board.year(2026)
    responses = [
        client.post("/api/v2/members/years/2025/publish/", headers=auth(ADMIN)),
        client.post("/api/v2/members/years/2026/unpublish/", headers=auth(ADMIN)),
        client.post("/api/v2/members/years/2030/publish/", headers=auth(ADMIN)),
    ]
    assert [response.status_code for response in responses] == [409, 409, 404]


def test_delete_unpublished_year_removes_its_entries(board, client, auth, db):
    board.year(2026)
    board.entry(2026, "Draft")

    response = client.delete("/api/v2/members/years/2026/", headers=auth(ADMIN))

    assert response.status_code == 200
    with db.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM boardmembers")
        assert cursor.fetchone()[0] == 0
    assert client.get("/api/v2/members/admin/", headers=auth(ADMIN)).json == []


def test_delete_published_year_conflicts(board, client, auth):
    board.year(2025, published=True)
    board.entry(2025, "Member")

    response = client.delete("/api/v2/members/years/2025/", headers=auth(ADMIN))

    assert response.status_code == 409
    assert names(client.get("/api/v2/members/").json[0]) == ["Member"]


def test_delete_missing_year(board, client, auth):
    assert client.delete("/api/v2/members/years/2030/", headers=auth(ADMIN)).status_code == 404


# ---- entries ------------------------------------------------------------------------

def test_create_entry_goes_to_end_of_its_tier(board, client, auth):
    board.year(2026)
    board.entry(2026, "President", tier="president", position=0)
    board.entry(2026, "Member", position=4)

    member = client.post(
        "/api/v2/members/years/2026/entries/", json=new_entry(name="New Member"), headers=auth(ADMIN)
    )
    president = client.post(
        "/api/v2/members/years/2026/entries/",
        json=new_entry(name="New President", tier="president", roles=["Vice President - OP"]),
        headers=auth(ADMIN),
    )

    assert member.status_code == 201 and president.status_code == 201
    assert member.json["position"] == 5
    assert president.json["position"] == 1
    assert member.json["createdBy"] == ADMIN and member.json["updatedBy"] == ADMIN
    assert names(admin_year(client, auth, 2026)) == ["President", "New President", "Member", "New Member"]


def test_create_entry_trims_text_and_drops_blank_roles(board, client, auth):
    board.year(2026)
    body = new_entry(name="  Jessica Moon ", major=" IA ", roles=[" Finance ", "  "], isLead=False)

    entry = client.post("/api/v2/members/years/2026/entries/", json=body, headers=auth(ADMIN)).json

    assert (entry["name"], entry["major"], entry["roles"], entry["isLead"]) == (
        "Jessica Moon", "IA", ["Finance"], False,
    )


def test_create_entry_defaults_is_lead_to_false(board, client, auth):
    board.year(2026)
    body = new_entry()
    del body["isLead"]

    entry = client.post("/api/v2/members/years/2026/entries/", json=body, headers=auth(ADMIN)).json

    assert entry["isLead"] is False


@pytest.mark.parametrize("body", [
    new_entry(name=" "),
    new_entry(major=None),
    new_entry(classYear="2027"),
    new_entry(classYear=27),
    new_entry(roles=[]),
    new_entry(roles=["  "]),
    new_entry(roles="Finance"),
    new_entry(roles=["Finance", 3]),
    new_entry(isLead="yes"),
    new_entry(tier="officer"),
])
def test_create_entry_rejects_bad_input(board, client, auth, body):
    board.year(2026)
    response = client.post("/api/v2/members/years/2026/entries/", json=body, headers=auth(ADMIN))
    assert response.status_code == 400


def test_create_entry_in_missing_year(board, client, auth):
    response = client.post("/api/v2/members/years/2030/entries/", json=new_entry(), headers=auth(ADMIN))
    assert response.status_code == 404


def test_update_entry_keeps_position_within_its_tier(board, client, auth):
    board.year(2025, published=True)
    entry_id = board.entry(2025, "Typo Nmae", position=3)

    response = client.put(
        f"/api/v2/members/entries/{entry_id}/", json=new_entry(name="Fixed Name"), headers=auth(ADMIN)
    )

    assert response.status_code == 200
    assert response.json["name"] == "Fixed Name"
    assert response.json["position"] == 3
    assert response.json["updatedBy"] == ADMIN
    assert names(client.get("/api/v2/members/").json[0]) == ["Fixed Name"]


def test_update_entry_tier_change_moves_to_end_of_new_tier(board, client, auth):
    board.year(2026)
    board.entry(2026, "President", tier="president", position=0)
    entry_id = board.entry(2026, "Promoted", position=0)
    board.entry(2026, "Member", position=1)

    response = client.put(
        f"/api/v2/members/entries/{entry_id}/",
        json=new_entry(name="Promoted", tier="president"),
        headers=auth(ADMIN),
    )

    assert response.json["position"] == 1
    assert names(admin_year(client, auth, 2026)) == ["President", "Promoted", "Member"]


def test_update_missing_entry(board, client, auth):
    response = client.put("/api/v2/members/entries/999/", json=new_entry(), headers=auth(ADMIN))
    assert response.status_code == 404


def test_update_entry_rejects_bad_input(board, client, auth):
    board.year(2026)
    entry_id = board.entry(2026, "Member")
    response = client.put(
        f"/api/v2/members/entries/{entry_id}/", json=new_entry(roles=[]), headers=auth(ADMIN)
    )
    assert response.status_code == 400


def test_delete_entry(board, client, auth):
    board.year(2026)
    entry_id = board.entry(2026, "Gone")
    board.entry(2026, "Stays", position=1)

    response = client.delete(f"/api/v2/members/entries/{entry_id}/", headers=auth(ADMIN))

    assert response.status_code == 200
    assert names(admin_year(client, auth, 2026)) == ["Stays"]
    assert client.delete(f"/api/v2/members/entries/{entry_id}/", headers=auth(ADMIN)).status_code == 404


# ---- order --------------------------------------------------------------------------

def test_save_order_reorders_within_each_tier(board, client, auth):
    board.year(2026)
    p1 = board.entry(2026, "P1", tier="president", position=0)
    p2 = board.entry(2026, "P2", tier="president", position=1)
    m1 = board.entry(2026, "M1", position=0)
    m2 = board.entry(2026, "M2", position=1)
    m3 = board.entry(2026, "M3", position=2)

    response = client.put(
        "/api/v2/members/years/2026/order/", json={"order": [p2, p1, m3, m1, m2]}, headers=auth(ADMIN)
    )

    assert response.status_code == 200
    assert names(response.json) == ["P2", "P1", "M3", "M1", "M2"]
    assert names(admin_year(client, auth, 2026)) == ["P2", "P1", "M3", "M1", "M2"]


def test_save_order_conflicts_when_entries_changed(board, client, auth):
    board.year(2026)
    a = board.entry(2026, "A", position=0)
    b = board.entry(2026, "B", position=1)
    board.year(2025)
    other_year_entry = board.entry(2025, "Other")

    stale = [
        [a],                        # missing an entry added since loading
        [a, b, other_year_entry],   # an entry from another year
        [a, b, b],                  # duplicate
    ]
    for order in stale:
        response = client.put("/api/v2/members/years/2026/order/", json={"order": order}, headers=auth(ADMIN))
        assert response.status_code == 409
    assert names(admin_year(client, auth, 2026)) == ["A", "B"]


def test_save_order_bad_body_and_missing_year(board, client, auth):
    board.year(2026)
    bad = client.put("/api/v2/members/years/2026/order/", json={"order": "1,2"}, headers=auth(ADMIN))
    missing = client.put("/api/v2/members/years/2030/order/", json={"order": []}, headers=auth(ADMIN))
    assert (bad.status_code, missing.status_code) == (400, 404)


# ---- seed ---------------------------------------------------------------------------

def test_seed_loads_three_published_years(db, client):
    with db.cursor() as cursor:
        cursor.execute(SEED.read_text())

    years = client.get("/api/v2/members/").json

    assert [(year["label"], len(year["entries"])) for year in years] == [
        ("25-26", 33), ("24-25", 32), ("23-24", 24),
    ]
    latest = years[0]["entries"]
    assert [entry["name"] for entry in latest[:2]] == ["Jin Wook Shin", "Jisang Um"]
    assert [entry["tier"] for entry in latest[:3]] == ["president", "president", "member"]
    assert latest[2] == {
        "boardMemberID": latest[2]["boardMemberID"],
        "name": "Jessica Moon",
        "major": "Information Analysis",
        "classYear": 2027,
        "roles": ["Event Planning Lead/Finance"],
        "isLead": True,
        "tier": "member",
    }
