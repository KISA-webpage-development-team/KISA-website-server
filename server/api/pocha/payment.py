import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/payment

@server.application.route('/api/v2/pocha/payment/<string:email>/<int:pochaID>/check-stock/', methods=['GET'])
# @token_required
def check_cart_stock(email, pochaID):
    '''
    Check if all items in cart is in stock.
    '''
    # fetch order with user email and pochaID where isPaid is False
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
    
    # construct dictionary for counting quantity by menu
    menu_quantity = defaultdict(int)
    for orderItem in orderItems:
        menu_quantity[orderItem['menuID']] += orderItem['quantity']

    # check if stock is sufficient for each orderItem
    for menu in menu_quantity:
        cursor.execute(
            """
            SELECT stock FROM menu
            WHERE menuID = %(menuID)s
            """,
            {
                'menuID': int(menu)
            }
        )
        stock = int(cursor.fetchone()['stock'])
        if stock < menu_quantity[menu]:
            return flask.jsonify({"isStocked" : False}), 200
    return flask.jsonify({"isStocked" : True}), 200

@server.application.route('/api/v2/pocha/payment/<string:email>/<int:pochaID>/pay-result/', methods=['PUT'])
# @token_required
def pay_success_fail(email, pochaID):
    body = flask.request.get_json()
    result = body['result'] # 'success' | 'failure'
    # Case 1: payment is successful
    if result == 'success':
        # fetch card of user with email and pochaID
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

        # fetch orderItems associated to order first
        cursor.execute(
            """
            SELECT orderItemID, status, menuID, quantity
            FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s
            """,
            {
                'parentOrderID': cart['orderID'],
            }
        )
        to_checkout = cursor.fetchall()

        # iterate through orderItems to add menu item to response
        for orderItem in to_checkout:
            cursor.execute(
                """
                SELECT * FROM menu
                WHERE menuID = %(menuID)s
                """,
                {
                    'menuID': orderItem['menuID']
                }
            )
            orderItem['menu'] = cursor.fetchone()
            del orderItem['menuID']

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
        server.sio.emit('order-created', {"newOrderItems": to_checkout})

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