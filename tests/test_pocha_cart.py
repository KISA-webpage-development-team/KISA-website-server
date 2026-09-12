"""Cart contents and checkout totals: same JSON as before, one query each."""

STUDENT = "student@example.com"
OTHER = "other@example.com"    # has an unpaid order with no items
ADMIN = "admin@example.com"    # has no unpaid order


def test_cart_aggregates_quantity_per_menu(pocha_scenario, client, auth, query_log, golden):
    response = client.get(f"/api/v2/pocha/cart/{STUDENT}/1/", headers=auth(STUDENT))
    assert response.status_code == 200
    golden("cart_student", response.data)
    assert len(query_log) == 1, query_log


def test_cart_with_order_but_no_items_is_empty(pocha_scenario, client, auth, golden):
    response = client.get(f"/api/v2/pocha/cart/{OTHER}/1/", headers=auth(OTHER))
    assert response.status_code == 200
    golden("cart_empty", response.data)


def test_cart_without_order_is_empty(pocha_scenario, client, auth, golden):
    response = client.get(f"/api/v2/pocha/cart/{ADMIN}/1/", headers=auth(ADMIN))
    assert response.status_code == 200
    golden("cart_empty", response.data)


def test_checkout_info_totals_and_age_check(pocha_scenario, client, auth, query_log, golden):
    response = client.get(f"/api/v2/pocha/cart/{STUDENT}/1/checkout-info/", headers=auth(STUDENT))
    assert response.status_code == 200
    golden("checkout_info_student", response.data)
    assert len(query_log) == 1, query_log


def test_checkout_info_for_empty_cart_is_404(pocha_scenario, client, auth, golden):
    for email in (OTHER, ADMIN):
        response = client.get(f"/api/v2/pocha/cart/{email}/1/checkout-info/", headers=auth(email))
        assert response.status_code == 404
        golden("checkout_info_empty", response.data)
