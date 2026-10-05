"""Home carousel: public read and admin management.

Cloudinary is faked at the SDK boundary; everything else (routes, SQL,
effective status, placement) runs for real.
"""
import datetime
import itertools
from zoneinfo import ZoneInfo

import cloudinary
import cloudinary.uploader
import pytest

ADMIN = "admin@example.com"
STUDENT = "student@example.com"


def detroit_today():
    return datetime.datetime.now(ZoneInfo("America/Detroit")).date()


def days(n):
    return (detroit_today() + datetime.timedelta(days=n)).isoformat()


class FakeCloudinary:
    """Records SDK calls and hands out increasing versions."""

    def __init__(self):
        self.calls = []
        self.fail = False
        self._versions = itertools.count(1000)

    def rename(self, from_public_id, to_public_id, **options):
        self.calls.append(("rename", from_public_id, to_public_id))
        if self.fail:
            raise RuntimeError("cloudinary down")
        return {"public_id": to_public_id, "version": next(self._versions)}

    def upload(self, source, **options):
        self.calls.append(("upload", source, options.get("public_id")))
        if self.fail:
            raise RuntimeError("cloudinary down")
        return {"public_id": options.get("public_id"), "version": next(self._versions)}

    def destroy(self, public_id, **options):
        self.calls.append(("destroy", public_id))
        if self.fail:
            raise RuntimeError("cloudinary down")
        return {"result": "ok"}


@pytest.fixture
def fake_cloudinary(monkeypatch):
    fake = FakeCloudinary()
    monkeypatch.setattr(cloudinary.uploader, "rename", fake.rename)
    monkeypatch.setattr(cloudinary.uploader, "upload", fake.upload)
    monkeypatch.setattr(cloudinary.uploader, "destroy", fake.destroy)
    cloudinary.config(cloud_name="test-cloud")
    return fake


@pytest.fixture
def carousel(db, fake_cloudinary):
    """An admin, a student, and a helper that inserts carousel rows directly.

    add(title, ...) inserts a row and returns its id. Rows are live unless
    status="archive" is passed.
    """
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear) VALUES
                ('admin@example.com',   'Admin User',   2000, 1, 1, 'CS', 2026),
                ('student@example.com', 'Student User', 2001, 2, 2, 'EE', 2027);
            INSERT INTO admins (email) VALUES ('admin@example.com');
        """)

    def add(title, position=None, end_date=None, status="live", archived_at=None, created=None):
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO carouselitems
                    (title, description, link, imagepublicid, imageversion, enddate,
                     status, position, archivedat, createdby, updatedby, created, updated)
                VALUES (%s, %s, NULL, 'placeholder', 1, %s, %s, %s, %s, %s, %s,
                        COALESCE(%s, now()), COALESCE(%s, now()))
                RETURNING carouselitemid
                """,
                (title, f"<p>{title}</p>", end_date, status, position, archived_at,
                 ADMIN, ADMIN, created, created),
            )
            item_id = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE carouselitems SET imagepublicid = %s WHERE carouselitemid = %s",
                (f"carousel/item-{item_id}", item_id),
            )
        return item_id

    return add


def new_item(**overrides):
    body = {
        "title": "Mass Meeting",
        "description": "<p>Come <strong>meet</strong> us</p>",
        "link": "https://forms.gle/example",
        "endDate": days(10),
        "imageTempPublicID": "temp/carousel-123",
    }
    body.update(overrides)
    return {key: value for key, value in body.items() if value is not None}


def titles(items):
    return [item["title"] for item in items]


def row(db, item_id):
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT status, position, enddate, imagepublicid, imageversion, createdby, updatedby, archivedat "
            "FROM carouselitems WHERE carouselitemid = %s",
            (item_id,),
        )
        return cursor.fetchone()


# ---- public read ------------------------------------------------------------

def test_public_lists_effective_live_items_in_stored_order(carousel, client):
    carousel("Second", position=1)
    carousel("First", position=0, end_date=days(0))      # ends today: still live
    carousel("Expired", position=2, end_date=days(-1))   # stored live, but expired
    carousel("Archived", status="archive", archived_at="2026-01-01")

    response = client.get("/api/v2/carousel/")

    assert response.status_code == 200
    assert titles(response.json) == ["First", "Second"]


def test_public_item_has_ready_versioned_image_url(carousel, client):
    item_id = carousel("Only", position=0)

    item = client.get("/api/v2/carousel/").json[0]

    assert item["carouselItemID"] == item_id
    assert item["description"] == "<p>Only</p>"
    assert item["link"] is None
    url = item["imageUrl"]
    assert url.startswith("https://res.cloudinary.com/test-cloud/image/upload/")
    assert "f_auto" in url and "q_auto" in url
    assert f"/v1/carousel/item-{item_id}" in url


# ---- admin auth ---------------------------------------------------------------

def test_admin_routes_reject_non_admin(carousel, client, auth):
    item_id = carousel("Only", position=0)
    attempts = [
        client.get("/api/v2/carousel/admin/", headers=auth(STUDENT)),
        client.get(f"/api/v2/carousel/{item_id}/", headers=auth(STUDENT)),
        client.post("/api/v2/carousel/", json=new_item(), headers=auth(STUDENT)),
        client.put(f"/api/v2/carousel/{item_id}/", json=new_item(), headers=auth(STUDENT)),
        client.post(f"/api/v2/carousel/{item_id}/archive/", headers=auth(STUDENT)),
        client.post(f"/api/v2/carousel/{item_id}/restore/", json={}, headers=auth(STUDENT)),
        client.delete(f"/api/v2/carousel/{item_id}/", headers=auth(STUDENT)),
        client.put("/api/v2/carousel/order/", json={"order": [item_id]}, headers=auth(STUDENT)),
    ]
    assert [response.status_code for response in attempts] == [403] * len(attempts)


def test_admin_routes_reject_missing_token(carousel, client):
    response = client.post("/api/v2/carousel/", json=new_item())
    assert response.status_code == 401


# ---- create ---------------------------------------------------------------------

def test_create_claims_temp_image_and_records_creator(carousel, client, auth, fake_cloudinary, db):
    response = client.post("/api/v2/carousel/", json=new_item(), headers=auth(ADMIN))

    assert response.status_code == 201
    item = response.json
    item_id = item["carouselItemID"]
    assert fake_cloudinary.calls == [("rename", "temp/carousel-123", f"carousel/item-{item_id}")]
    stored = row(db, item_id)
    assert stored[0] == "live"
    assert stored[3] == f"carousel/item-{item_id}"
    assert stored[4] == 1000
    assert stored[5] == ADMIN and stored[6] == ADMIN
    assert item["status"] == "live"
    assert item["endDate"] == days(10)
    assert f"/v1000/carousel/item-{item_id}" in item["imageUrl"]
    assert titles(client.get("/api/v2/carousel/").json) == ["Mass Meeting"]


@pytest.mark.parametrize("body", [
    new_item(title="  "),
    new_item(description=""),
    new_item(link="javascript:alert(1)"),
    new_item(link="forms.gle/no-scheme"),
    new_item(endDate="not-a-date"),
    new_item(endDate=days(-1)),
    new_item(imageTempPublicID=None),
    new_item(imageTempPublicID="pocha/menu-1"),
])
def test_create_rejects_invalid_input(carousel, client, auth, fake_cloudinary, db, body):
    response = client.post("/api/v2/carousel/", json=body, headers=auth(ADMIN))

    assert response.status_code == 400
    assert fake_cloudinary.calls == []
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM carouselitems")
        assert cursor.fetchone()[0] == 0


def test_create_without_link_or_end_date(carousel, client, auth):
    response = client.post(
        "/api/v2/carousel/", json=new_item(link=None, endDate=None), headers=auth(ADMIN)
    )

    assert response.status_code == 201
    assert response.json["link"] is None
    assert response.json["endDate"] is None


def test_create_places_item_by_end_date_rule(carousel, client, auth):
    carousel("Ends in 5", position=0, end_date=days(5))
    carousel("Ends in 20", position=1, end_date=days(20))
    carousel("Undated old", position=2, created="2026-01-01")

    client.post("/api/v2/carousel/", json=new_item(title="Ends in 10", endDate=days(10)),
                headers=auth(ADMIN))
    client.post("/api/v2/carousel/", json=new_item(title="Undated new", endDate=None),
                headers=auth(ADMIN))

    assert titles(client.get("/api/v2/carousel/").json) == [
        "Ends in 5", "Ends in 10", "Ends in 20", "Undated new", "Undated old",
    ]


def test_create_placement_scans_the_current_order(carousel, client, auth):
    # Live items are in a manual order the rule would not produce. The new item
    # goes before the first item, in the current order, that it precedes under
    # the rule; everything else keeps its relative order.
    carousel("Ends in 20", position=0, end_date=days(20))
    carousel("Ends in 5", position=1, end_date=days(5))

    client.post("/api/v2/carousel/", json=new_item(title="Ends in 10", endDate=days(10)),
                headers=auth(ADMIN))

    assert titles(client.get("/api/v2/carousel/").json) == [
        "Ends in 10", "Ends in 20", "Ends in 5",
    ]


def test_create_from_template_copies_the_source_image(carousel, client, auth, fake_cloudinary):
    source_id = carousel("Last year", status="archive", archived_at="2026-01-01")

    response = client.post(
        "/api/v2/carousel/",
        json=new_item(imageTempPublicID=None, copyImageFrom=source_id),
        headers=auth(ADMIN),
    )

    assert response.status_code == 201
    new_id = response.json["carouselItemID"]
    assert new_id != source_id
    [(kind, source_url, target)] = fake_cloudinary.calls
    assert kind == "upload"
    assert f"carousel/item-{source_id}" in source_url
    assert target == f"carousel/item-{new_id}"


def test_create_from_template_of_missing_item_is_rejected(carousel, client, auth, fake_cloudinary):
    response = client.post(
        "/api/v2/carousel/",
        json=new_item(imageTempPublicID=None, copyImageFrom=999),
        headers=auth(ADMIN),
    )

    assert response.status_code == 400
    assert fake_cloudinary.calls == []


def test_create_fails_cleanly_when_cloudinary_fails(carousel, client, auth, fake_cloudinary, db):
    fake_cloudinary.fail = True

    response = client.post("/api/v2/carousel/", json=new_item(), headers=auth(ADMIN))

    assert response.status_code == 502
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM carouselitems")
        assert cursor.fetchone()[0] == 0


# ---- read one / admin list ---------------------------------------------------------

def test_admin_gets_one_item(carousel, client, auth):
    item_id = carousel("Only", position=0, end_date=days(3))

    response = client.get(f"/api/v2/carousel/{item_id}/", headers=auth(ADMIN))

    assert response.status_code == 200
    assert response.json["title"] == "Only"
    assert response.json["endDate"] == days(3)
    assert response.json["createdBy"] == ADMIN
    assert client.get("/api/v2/carousel/999/", headers=auth(ADMIN)).status_code == 404


def test_admin_list_splits_live_and_archive(carousel, client, auth):
    carousel("Live B", position=1)
    carousel("Live A", position=0)
    carousel("Archived long ago", status="archive", archived_at="2025-01-01")
    carousel("Expired yesterday", position=2, end_date=days(-1))
    carousel("Archived recently", status="archive",
             archived_at=f"{days(-3)}T12:00:00")

    response = client.get("/api/v2/carousel/admin/", headers=auth(ADMIN))

    assert response.status_code == 200
    assert titles(response.json["live"]) == ["Live A", "Live B"]
    assert titles(response.json["archive"]) == [
        "Expired yesterday", "Archived recently", "Archived long ago",
    ]
    assert {item["status"] for item in response.json["archive"]} == {"archive"}
    live = response.json["live"][0]
    assert live["createdBy"] == ADMIN and live["updatedBy"] == ADMIN
    assert live["created"] and live["updated"]


# ---- update -------------------------------------------------------------------------

def test_update_changes_fields_and_records_editor(carousel, client, auth, fake_cloudinary, db):
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO users (email, fullname, bornyear, bornmonth, borndate, major, gradyear)
            VALUES ('admin2@example.com', 'Second Admin', 2000, 1, 1, 'CS', 2026);
            INSERT INTO admins (email) VALUES ('admin2@example.com');
        """)
    carousel("Other", position=0)
    item_id = carousel("Typo", position=1)

    response = client.put(
        f"/api/v2/carousel/{item_id}/",
        json=new_item(title="Fixed", imageTempPublicID=None),
        headers=auth("admin2@example.com"),
    )

    assert response.status_code == 200
    assert response.json["title"] == "Fixed"
    stored = row(db, item_id)
    assert stored[1] == 1                       # position unchanged
    assert stored[5] == ADMIN and stored[6] == "admin2@example.com"
    assert fake_cloudinary.calls == []


def test_update_replaces_image_under_the_same_id(carousel, client, auth, fake_cloudinary, db):
    item_id = carousel("Only", position=0)

    response = client.put(
        f"/api/v2/carousel/{item_id}/",
        json=new_item(imageTempPublicID="temp/carousel-new"),
        headers=auth(ADMIN),
    )

    assert response.status_code == 200
    assert fake_cloudinary.calls == [("rename", "temp/carousel-new", f"carousel/item-{item_id}")]
    assert row(db, item_id)[4] == 1000
    assert "/v1000/" in response.json["imageUrl"]


def test_update_rejects_invalid_input_and_missing_item(carousel, client, auth):
    item_id = carousel("Only", position=0)

    bad = client.put(f"/api/v2/carousel/{item_id}/", json=new_item(title=""), headers=auth(ADMIN))
    missing = client.put("/api/v2/carousel/999/", json=new_item(), headers=auth(ADMIN))

    assert bad.status_code == 400
    assert missing.status_code == 404


# ---- archive / restore -----------------------------------------------------------------

def test_archive_takes_item_off_the_carousel(carousel, client, auth, db):
    item_id = carousel("Only", position=0)

    response = client.post(f"/api/v2/carousel/{item_id}/archive/", headers=auth(ADMIN))

    assert response.status_code == 200
    assert response.json["status"] == "archive"
    stored = row(db, item_id)
    assert stored[0] == "archive" and stored[1] is None and stored[7] is not None
    assert client.get("/api/v2/carousel/").json == []


def test_restore_returns_item_with_new_end_date_placed_by_rule(carousel, client, auth, db):
    carousel("Ends in 5", position=0, end_date=days(5))
    carousel("Ends in 20", position=1, end_date=days(20))
    item_id = carousel("Old", status="archive", archived_at="2026-01-01", end_date="2026-01-01")

    response = client.post(
        f"/api/v2/carousel/{item_id}/restore/", json={"endDate": days(10)}, headers=auth(ADMIN)
    )

    assert response.status_code == 200
    assert response.json["status"] == "live"
    assert row(db, item_id)[7] is None
    assert titles(client.get("/api/v2/carousel/").json) == ["Ends in 5", "Old", "Ends in 20"]


def test_restore_of_expired_item_without_end_date(carousel, client, auth):
    item_id = carousel("Expired", position=0, end_date=days(-2))

    response = client.post(
        f"/api/v2/carousel/{item_id}/restore/", json={"endDate": None}, headers=auth(ADMIN)
    )

    assert response.status_code == 200
    assert response.json["endDate"] is None
    assert titles(client.get("/api/v2/carousel/").json) == ["Expired"]


def test_restore_rejects_past_end_date_and_live_item(carousel, client, auth):
    archived_id = carousel("Old", status="archive", archived_at="2026-01-01")
    live_id = carousel("Live", position=0)

    past = client.post(f"/api/v2/carousel/{archived_id}/restore/",
                       json={"endDate": days(-1)}, headers=auth(ADMIN))
    live = client.post(f"/api/v2/carousel/{live_id}/restore/", json={}, headers=auth(ADMIN))

    assert past.status_code == 400
    assert live.status_code == 409


# ---- remove ---------------------------------------------------------------------------------

def test_remove_deletes_row_and_image(carousel, client, auth, fake_cloudinary, db):
    item_id = carousel("Only", position=0)

    response = client.delete(f"/api/v2/carousel/{item_id}/", headers=auth(ADMIN))

    assert response.status_code == 200
    assert fake_cloudinary.calls == [("destroy", f"carousel/item-{item_id}")]
    assert row(db, item_id) is None
    assert client.delete("/api/v2/carousel/999/", headers=auth(ADMIN)).status_code == 404


def test_remove_keeps_row_when_image_delete_fails(carousel, client, auth, fake_cloudinary, db):
    item_id = carousel("Only", position=0)
    fake_cloudinary.fail = True

    response = client.delete(f"/api/v2/carousel/{item_id}/", headers=auth(ADMIN))

    assert response.status_code == 502
    assert row(db, item_id) is not None


# ---- save order ---------------------------------------------------------------------------------

def test_save_order_applies_positions(carousel, client, auth):
    a = carousel("A", position=0)
    b = carousel("B", position=1)
    c = carousel("C", position=2)

    response = client.put("/api/v2/carousel/order/", json={"order": [c, a, b]}, headers=auth(ADMIN))

    assert response.status_code == 200
    assert titles(response.json) == ["C", "A", "B"]
    assert titles(client.get("/api/v2/carousel/").json) == ["C", "A", "B"]


@pytest.mark.parametrize("make_order", [
    lambda a, b, expired: [a],                  # an item created meanwhile is missing
    lambda a, b, expired: [a, b, 999],          # an item removed meanwhile is still listed
    lambda a, b, expired: [a, b, expired],      # an expired item is not live
    lambda a, b, expired: [a, a, b],            # duplicates
])
def test_save_order_rejects_stale_live_set(carousel, client, auth, make_order):
    a = carousel("A", position=0)
    b = carousel("B", position=1)
    expired = carousel("Expired", position=2, end_date=days(-1))

    response = client.put("/api/v2/carousel/order/", json={"order": make_order(a, b, expired)},
                          headers=auth(ADMIN))

    assert response.status_code == 409
    assert titles(client.get("/api/v2/carousel/").json) == ["A", "B"]
