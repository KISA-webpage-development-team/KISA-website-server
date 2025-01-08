import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/payment

@server.application.route('/api/v2/pocha/payment/<string:email>/<int:pochaID>/check-stock/', methods=['PUT'])
# @token_required
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
# @token_required
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

            # fetch user information and append into orderItem
            cursor.execute(
                """
                SELECT fullname FROM users
                WHERE email = %(email)s
                """,
                {
                    'email': email
                }
            )
            orderItemFullname = cursor.fetchone()['fullname']
            orderItem['ordererName'] = orderItemFullname
            orderItem['ordererEmail'] = email

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