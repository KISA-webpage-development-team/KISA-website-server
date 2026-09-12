"""Order item queries shared by the dashboard, order and payment endpoints.

One query returns every item with its menu row and, for staff views, the
orderer's name, so the query count no longer grows with the number of orders
or items.
"""
import server

# Keys that belong to the item itself; every other column in a joined row is
# a menu column and is nested under 'menu', matching `SELECT * FROM menu`.
_ITEM_KEYS = {"orderItemID", "status", "quantity", "ordererEmail", "ordererName"}


def _shape(row):
    item = {key: value for key, value in row.items() if key in _ITEM_KEYS}
    item["menu"] = {key: value for key, value in row.items() if key not in _ITEM_KEYS}
    return item


def fetch_order_items(cursor, pochaID=None, email=None, orderID=None, closed=None, with_orderer=False):
    """Order items with their menu row, oldest order and item first.

    pochaID and email select paid orders of that pocha and, optionally, user;
    orderID selects one order whatever its paid state. closed keeps only
    'closed' items (order history) or, when False, only items still in
    progress; None keeps every status. with_orderer adds ordererName and
    ordererEmail; the users row is joined with LEFT JOIN so an order whose
    account was deleted still appears.
    """
    conditions = []
    if orderID is not None:
        conditions.append("o.orderID = %(orderID)s")
    else:
        conditions.append("o.parentPochaID = %(pochaID)s AND o.isPaid = %(isPaid)s")
    if email is not None:
        conditions.append("o.email = %(email)s")
    if closed is not None:
        conditions.append(f"oi.status {'=' if closed else '!='} %(status)s")
    orderer_columns = ', o.email AS "ordererEmail", u.fullname AS "ordererName"' if with_orderer else ""

    cursor.execute(
        f"""
        SELECT oi.orderItemID, oi.status, oi.quantity{orderer_columns}, m.*
        FROM orderItem oi
        JOIN `order` o ON o.orderID = oi.parentOrderID
        JOIN menu m ON m.menuID = oi.menuID
        LEFT JOIN users u ON u.email = o.email
        WHERE {" AND ".join(conditions)}
        ORDER BY o.orderID, oi.orderItemID
        """,
        {
            'orderID': orderID,
            'pochaID': pochaID,
            'isPaid': True,
            'email': email,
            'status': 'closed',
        }
    )
    return [_shape(row) for row in cursor.fetchall()]


def active_orders_by_status(cursor, pochaID, email=None, with_orderer=False):
    """{'pending': [...], 'preparing': [...], 'ready': [...]} for a pocha."""
    response = {'pending': [], 'preparing': [], 'ready': []}
    for item in fetch_order_items(cursor, pochaID, closed=False, email=email, with_orderer=with_orderer):
        response[item['status']].append(item)
    return response


def closed_orders(cursor, pochaID, email=None, with_orderer=False):
    """{'closed': [...]} for a pocha."""
    return {'closed': fetch_order_items(cursor, pochaID, closed=True, email=email, with_orderer=with_orderer)}
