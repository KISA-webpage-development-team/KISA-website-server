import flask
import server
from .socket import dashboard_room, user_room
from ..helpers import token_required
from .notification import send_notification
from .order_helpers import fetch_order_items
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/payment

@server.application.route('/api/v2/pocha/payment/<string:email>/<int:pochaID>/check-stock/', methods=['PUT'])
@token_required
def reserve_cart_stock(email, pochaID):
    '''
    Check if all items in cart is in stock and if so, reserve them.
    '''
    # fetch cart of user
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT orderID FROM `order`
        WHERE parentPochaID = %(parentPochaID)s
        AND email = %(email)s
        AND isPaid = %(isPaid)s
        """,
        {
            'parentPochaID': pochaID,
            'email': email,
            'isPaid': False
        }
    )
    order = cursor.fetchone()
    if not order:
        return flask.jsonify({"error": "user cart is empty"}), 404

    # fetch all orderItems with orderID
    cursor.execute(
        """
        SELECT quantity, menuID FROM orderItem
        WHERE parentOrderID = %(parentOrderID)s
        """,
        {
            'parentOrderID': order['orderID']
        }
    )
    orderItems = cursor.fetchall()

    # count quantity of each menuID
    menuIDtoQuantity = defaultdict(int)
    for orderItem in orderItems:
        menuIDtoQuantity[orderItem['menuID']] += orderItem['quantity']

    # subtract quantity from stock, but conditionally
    for menuID in menuIDtoQuantity:
        cursor.execute(
            """
            UPDATE menu
            SET stock = stock - %(quantity)s
            WHERE menuID = %(menuID)s
            AND stock >= %(quantity)s
            """,
            {
                'quantity': menuIDtoQuantity[menuID],
                'menuID': menuID
            }
        )
        # rollback transaction and return failure if there is not enough stock
        if not cursor.rowcount():
            # identify which menu item is out of stock
            cursor.execute(
                """
                SELECT nameKor, nameEng FROM menu
                WHERE menuID = %(menuID)s
                """,
                {
                    'menuID': menuID
                }
            )
            out_of_stock = cursor.fetchone()

            # rollback transaction
            cursor.rollback()

            # return failure message with menu out of stock
            return flask.jsonify({
                "isStocked" : False,
                "outOfStockMenu": out_of_stock
                }), 200
    
    # return success message
    return flask.jsonify({"isStocked" : True}), 200

@server.application.route('/api/v2/pocha/payment/<string:email>/<int:pochaID>/pay-result/', methods=['PUT'])
@token_required
def pay_success_fail(email, pochaID):
    body = flask.request.get_json()
    result = body['result'] # 'success' | 'failure'
    # Case 1: payment is successful
    if result == 'success':
        # fetch cart of user
        cursor = server.model.Cursor()
        cursor.execute(
            """
            SELECT orderID FROM `order`
            WHERE parentPochaID = %(parentPochaID)s
            AND email = %(email)s
            AND isPaid = %(isPaid)s
            """,
            {
                'parentPochaID': pochaID,
                'email': email,
                'isPaid': False
            }
        )
        cart = cursor.fetchone()
        if not cart:
            return flask.jsonify({"error": "user cart is empty"}), 404

        # the items being checked out, with menu and orderer, for the event
        to_checkout = fetch_order_items(cursor, orderID=cart['orderID'], with_orderer=True)

        # change isPaid flag of order to 1
        cursor.execute(
            """
            UPDATE `order`
            SET isPaid = %(isPaidtoSet)s
            WHERE parentPochaID = %(parentPochaID)s
            AND email = %(email)s
            AND isPaid = %(isPaidPrev)s
            """,
            {
                'isPaidtoSet': True,
                'parentPochaID': pochaID,
                'email': email,
                'isPaidPrev': False
            }
        )

        # emit on event "order-created"
        # the staff dashboard for this pocha, and the person who ordered
        server.sio.emit('order-created', {"newOrderItems": to_checkout},
                        to=dashboard_room(pochaID))
        server.sio.emit('order-created', {"newOrderItems": to_checkout},
                        to=user_room(email))

        return flask.jsonify({"message": "success",}), 200

    # Case 2: payment has failed
    else:
        # find order
        cursor = server.model.Cursor()
        cursor.execute(
            """
            SELECT orderID FROM `order`
            WHERE parentPochaID = %(parentPochaID)s
            AND email = %(email)s
            AND isPaid = %(isPaid)s
            """,
            {
                'parentPochaID': pochaID,
                'email': email,
                'isPaid': False
            }
        )
        order = cursor.fetchone()
        if not order:
            return flask.jsonify({"error": "user cart is empty"}), 404

        # find orderItems
        cursor.execute(
            """
            SELECT quantity, menuID FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s
            """,
            {
                'parentOrderID': order['orderID']
            }
        )
        orderItems = cursor.fetchall()

        # iterate through orderItems
        for orderItem in orderItems:
            # for each quantity in orderItems
            quantity_to_restock = orderItem['quantity']
            menu_to_restock = orderItem['menuID']

            # add them into menu stock again
            cursor.execute(
                '''
                UPDATE menu
                SET stock = stock + %(quantity)s
                WHERE menuID = %(menuID)s
                ''',
                {
                    'quantity': quantity_to_restock,
                    'menuID': menu_to_restock,
                }
            )
        
        return flask.jsonify({"message": "items restocked"}), 200
