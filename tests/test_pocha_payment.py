"""Payment result: the order-created event carries the same items as before."""
import json

import pytest

import server

STUDENT = "student@example.com"
ADMIN = "admin@example.com"


@pytest.fixture
def emitted(monkeypatch):
    calls = []
    monkeypatch.setattr(server.sio, "emit", lambda event, data=None, **kwargs: calls.append((event, data, kwargs.get("to"))))
    return calls


def test_payment_success_emits_order_items_and_marks_order_paid(pocha_scenario, client, auth, query_log, golden, emitted):
    response = client.put(f"/api/v2/pocha/payment/{STUDENT}/1/pay-result/", json={"result": "success"}, headers=auth(STUDENT))
    assert response.status_code == 200
    golden("payment_success_response", response.data)

    assert [(event, to) for event, _, to in emitted] == [("order-created", "dashboard:1"), ("order-created", f"user:{STUDENT}")]
    assert emitted[0][1] == emitted[1][1]
    golden("payment_success_event", emitted[0][1])

    with pocha_scenario.cursor() as cursor:
        cursor.execute('SELECT ispaid FROM "order" WHERE orderid = 3')
        assert cursor.fetchone()[0] is True
    # find the cart, load its items with menu and orderer, mark it paid
    assert len(query_log) == 3, query_log


def test_payment_success_without_cart_is_404(pocha_scenario, client, auth, golden, emitted):
    response = client.put(f"/api/v2/pocha/payment/{ADMIN}/1/pay-result/", json={"result": "success"}, headers=auth(ADMIN))
    assert response.status_code == 404
    golden("payment_no_cart", response.data)
    assert emitted == []
