"""Dashboard and user order listings: same JSON as before, bounded query count."""
import pytest

ADMIN = "admin@example.com"
STUDENT = "student@example.com"


def test_dashboard_active_orders(pocha_scenario, client, auth, query_log, golden):
    response = client.get("/api/v2/pocha/dashboard/1/", headers=auth(ADMIN))
    assert response.status_code == 200
    golden("dashboard_active_orders", response.data)
    # admin check + one query for the orders, however many orders and items there are
    assert len(query_log) == 2, query_log


def test_dashboard_closed_orders(pocha_scenario, client, auth, query_log, golden):
    response = client.get("/api/v2/pocha/dashboard/1/closed/", headers=auth(ADMIN))
    assert response.status_code == 200
    golden("dashboard_closed_orders", response.data)
    assert len(query_log) == 2, query_log


def test_dashboard_lists_items_whose_orderer_was_deleted(pocha_scenario, client, auth):
    # Deleting a user sets order.email to NULL; the dashboard must still show
    # the order rather than fail for the whole pocha.
    with pocha_scenario.cursor() as cursor:
        cursor.execute("DELETE FROM users WHERE email = %s", (STUDENT,))
    response = client.get("/api/v2/pocha/dashboard/1/", headers=auth(ADMIN))
    assert response.status_code == 200
    orphaned = [item for item in response.json["pending"] if item["ordererEmail"] is None]
    assert orphaned and orphaned[0]["ordererName"] is None


def test_user_active_orders(pocha_scenario, client, auth, query_log, golden):
    response = client.get(f"/api/v2/pocha/order/{STUDENT}/1/", headers=auth(STUDENT))
    assert response.status_code == 200
    golden("user_active_orders", response.data)
    assert len(query_log) == 1, query_log


def test_user_closed_orders(pocha_scenario, client, auth, query_log, golden):
    response = client.get(f"/api/v2/pocha/order/{STUDENT}/1/closed/", headers=auth(STUDENT))
    assert response.status_code == 200
    golden("user_closed_orders", response.data)
    assert len(query_log) == 1, query_log


def test_user_with_no_orders_gets_empty_buckets(pocha_scenario, client, auth, golden):
    response = client.get("/api/v2/pocha/order/other@example.com/1/", headers=auth("other@example.com"))
    assert response.status_code == 200
    golden("user_active_orders_empty", response.data)
