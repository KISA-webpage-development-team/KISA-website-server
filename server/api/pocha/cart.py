import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/cart

@server.application.route('/api/v2/pocha/cart/<string:email>/<int:pochaID>/', methods=['GET'])
# @token_required
def get_cart(email, pochaID):
    '''
    Return cart information using session email and pochaID
    '''
    # check if order exists
    cursor = server.model.Cursor()
    cursor.execute(
        '''
        SELECT orderID FROM `order` 
        WHERE email = %(email)s
        AND parentPochaID = %(parentPochaID)s
        AND isPaid = %(isPaid)s
        ''',
        {
            'email': email,
            'parentPochaID': pochaID,
            'isPaid': False
        }
    )
    existing_order = cursor.fetchone()
    
    # Case 1: order exists
    if existing_order:
        # find orderItems associated with the order
        cursor.execute(
            '''
            SELECT quantity, menuID FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s
            ''',
            {
                'parentOrderID': existing_order["orderID"]
            }
        )
        orderItems = cursor.fetchall()

        # iterate through list of orderItems
        response = {}
        for orderItem in orderItems:
            # menuID key already exists in response dict
            if orderItem['menuID'] in response:
                response[orderItem['menuID']]['quantity'] += orderItem['quantity']

            # menuID first encounter
            else:
                cursor.execute(
                    '''
                    SELECT menuID, nameKor, nameEng, price,
                    stock, isImmediatePrep, parentPochaID
                    FROM menu
                    WHERE menuID = %(menuID)s
                    ''',
                    {
                        'menuID': orderItem['menuID']
                    }
                )
                menuInfo = cursor.fetchone()
                response[orderItem['menuID']] = {
                    'menu': menuInfo,
                    'quantity': orderItem['quantity']
                }
        return flask.jsonify(response), 200
    
    # Case 2: order does not exists
    else:
        # return empty dictionary
        return flask.jsonify({}), 200

@server.application.route('/api/v2/pocha/cart/<string:email>/<int:pochaID>/', methods=['POST', 'PATCH', 'DELETE'])
# @token_required
def modify_cart(email, pochaID):
    '''
    Add orderItem using session email, invoked when user adds item into cart
    '''
    # fetch body from request
    body = flask.request.get_json()

    # initialize variables from body
    menuID = body["menuID"]
    quantity = body["quantity"]

    # check if user exists
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT * FROM users "
        "WHERE email = %(email)s",
        {
            'email': email
        }
    )
    user = cursor.fetchone()
    if not user:
       return flask.jsonify({"error": "requested user does not exist"}), 404
    
    # check if pochaID exists
    cursor.execute(
        "SELECT * FROM pocha "
        "WHERE pochaID = %(pochaID)s",
        {
            'pochaID': pochaID
        }
    )
    existing_pocha = cursor.fetchone()
    if not existing_pocha:
       return flask.jsonify({"error": "requested pocha does not exist"}), 404

    # check if order exists
    cursor.execute(
        '''
        SELECT * FROM `order` 
        WHERE email = %(email)s 
        AND parentPochaID = %(parentPochaID)s 
        AND isPaid = %(isPaid)s
        ''',
        {
            'email': email,
            'parentPochaID': pochaID,
            'isPaid': False
        }
    )
    existing_order = cursor.fetchone()
    
    # check if menu is immediatePrep
    cursor.execute(
        '''
        SELECT isImmediatePrep FROM menu 
        WHERE menuID=%(menuID)s
        ''',
        {
            'menuID': menuID
        }
    )
    existing_menu = cursor.fetchone()

    if not existing_menu:
        return flask.jsonify({'error': 'Menu not found'}), 404
    
    isImmediatePrep = existing_menu['isImmediatePrep']

    # Case 1: quantity is a positive value (PATCH, POST)
    if quantity > 0:
        # Case 1-1: cart is empty at the moment
        if not existing_order:
            # create order row
            cursor.execute(
                '''
                INSERT INTO `order` 
                (email, parentPochaID) 
                VALUES (%(email)s, %(parentPochaID)s)
                ''',
                {
                    'email': email,
                    'parentPochaID': pochaID
                }
            )
            newOrderID = cursor.lastrowid()
        
            # Case 1-1-1: menu immediatePrep is False
            if not isImmediatePrep:
                # create {quantity} rows of orderItems
                for _ in range(quantity):
                    cursor.execute(
                        '''
                        INSERT INTO orderItem 
                        (status, quantity, parentOrderID, menuID) 
                        VALUES (%(status)s, %(quantity)s, %(parentOrderID)s, %(menuID)s)
                        ''',
                        {
                            'status': 'pending',
                            'quantity': 1,
                            'parentOrderID': newOrderID,
                            'menuID': menuID,
                        }
                    )
                return flask.jsonify(
                    {
                        "message": (
                            f"order with orderID {newOrderID} created, and\n"
                            f"{quantity} rows of menuID: {menuID} successfully\n"
                            "added to cart."
                        )
                    }
                ), 201
    
            # Case 1-1-2: menu immediatePrep is True
            else:
                # create orderItem row with quantity={quantity}
                cursor.execute(
                    '''
                    INSERT INTO orderItem 
                    (status, quantity, parentOrderID, menuID) 
                    VALUES (%(status)s, %(quantity)s, %(parentOrderID)s, %(menuID)s)
                    ''',
                    {
                        'status': 'pending',
                        'quantity': quantity,
                        'parentOrderID': newOrderID,
                        'menuID': menuID,
                    }
                )
                return flask.jsonify(
                    {
                        "message": f"""
                        order with orderID {newOrderID} created, and 
                        orderItems with quantity: {quantity} 
                        with menuID: {menuID} 
                        successfully added to cart.
                        """
                    }
                ), 201

        # Case 1-2: cart is not empty; order and orderItem exists
        else:
            # Case 1-2-1: menu immediatePrep is False
            if not isImmediatePrep:
                # create {quantity} rows of orderItems
                for _ in range(quantity):
                    cursor.execute(
                        """
                        INSERT INTO orderItem
                        (status, quantity, parentOrderID, menuID)
                        VALUES (%(status)s, %(quantity)s, %(parentOrderID)s, %(menuID)s)
                        """,
                        {
                            'status': 'pending',
                            'quantity': 1,
                            'parentOrderID': existing_order["orderID"],
                            'menuID': menuID,
                        }
                    )
                return flask.jsonify(
                    {
                        "message": f"""
                        {quantity} rows of menuID: {menuID} successfully
                        added to order with orderID: {existing_order['orderID']}
                        """
                    }
                ), 201
        
            # Case 1-2-2: menu immediatePrep is True
            else:
                # create orderItem row with quantity={quantity}
                cursor.execute(
                    """
                    UPDATE orderItem
                    SET quantity = quantity + %(quantity)s
                    WHERE parentOrderID = %(parentOrderID)s
                    AND menuID = %(menuID)s
                    AND status = %(status)s
                    """,
                    {
                        'quantity': quantity,
                        'parentOrderID': existing_order["orderID"],
                        'menuID': menuID,
                        'status': 'pending',
                    }
                )

                if cursor.rowcount() == 0:
                    cursor.execute(
                        """
                        INSERT INTO orderItem
                        (status, quantity, parentOrderID, menuID)
                        VALUES (%(status)s, %(quantity)s, %(parentOrderID)s, %(menuID)s)
                        """,
                        {
                            'status': 'pending',
                            'quantity': quantity,
                            'parentOrderID': existing_order["orderID"],
                            'menuID': menuID,
                        }
                    )
                
                # respond with success message
                return flask.jsonify(
                    {
                        "message": f"""
                        orderItem with quantity: {quantity} 
                        with menuID: {menuID} 
                        successfully added to order 
                        with orderID: {existing_order['orderID']}
                        """
                    }
                ), 201
    
    # Case 2: quantity is a negative value (PATCH, DELETE)
    elif quantity < 0:
        # Case 2-1: menu immediatePrep is False
        if not isImmediatePrep:
            # Case 2-1-1: deleting one item from cart:
            if quantity == -1:
                # delete lastly inserted orderItem
                cursor.execute(
                    '''
                    DELETE FROM orderItem 
                    WHERE parentOrderID=%(parentOrderID)s 
                    AND menuID=%(menuID)s 
                    AND status=%(status)s
                    ORDER BY orderItemID DESC 
                    LIMIT 1
                    ''',
                    {
                        'parentOrderID': existing_order['orderID'],
                        'menuID': menuID,
                        'status': 'pending',
                    }
                )
                deleted_rows = cursor.rowcount()

                # error handling: no rows were deleted
                if deleted_rows == 0:
                    # return error message
                    return flask.jsonify(
                        {
                            "error": f"""
                            1 row expected to be deleted, but
                            no row deleted, check if there is a menuItem
                            with pending status, where its parentOrder is not paid yet
                            """
                        }
                    ), 424
                
                # if there no longer exists orderItems for a order,
                # delete the order
                check_orderItems_and_delete(cursor, existing_order['orderID'])
                
                # respond with success message
                return flask.jsonify(
                    {
                        "message": f"""
                        1 orderItem successfully deleted from 
                        order with orderID: {existing_order['orderID']}
                        """
                    }
                ), 204

            # Case 2-1-2: deleting entire menu from cart:
            elif quantity < -1:
                # delete all orderItem rows with matching parentOrderID and menuID
                cursor.execute(
                    '''
                    DELETE FROM orderItem 
                    WHERE parentOrderID=%(parentOrderID)s 
                    AND menuID=%(menuID)s 
                    ''',
                    {
                        'parentOrderID': existing_order['orderID'],
                        'menuID': menuID,
                    }
                )
                deleted_rows = cursor.rowcount()

                # error handling: deleted rows does not match with expected
                if deleted_rows != (-1 * quantity):
                    # first, rollback the most recent execution
                    cursor.rollback()

                    # return error message
                    return flask.jsonify(
                        {
                            "error": f"""
                            {-1 * quantity} rows expected to be deleted, but
                            {deleted_rows} deleted
                            """
                        }
                    ), 424
                
                # if there no longer exists orderItems for a order,
                # delete the order
                check_orderItems_and_delete(cursor, existing_order['orderID'])
                
                return flask.jsonify(
                    {
                        "message": f"""
                        {-1 * quantity} orderItem(s) successfully deleted from 
                        order with orderID: {existing_order['orderID']}
                        """
                    }
                ), 204

        # Case 2-2: menu immediatePrep is True
        else:
            # Case 2-2-1: deleting one item from cart:
            if quantity == -1:
                # decrement quantity or delete row
                cursor.execute(
                    '''
                    UPDATE orderItem
                    SET quantity = quantity - 1
                    WHERE parentOrderID = %(parentOrderID)s
                    AND menuID = %(menuID)s;
                    DELETE FROM orderItem
                    WHERE parentOrderID = %(parentOrderID)s
                    AND menuID = %(menuID)s
                    AND quantity = 0;
                    ''',
                    {
                        'parentOrderID': existing_order['orderID'],
                        'menuID': menuID
                    }
                )

                # if there no longer exists orderItems for a order,
                # delete the order
                check_orderItems_and_delete(cursor, existing_order['orderID'])

                return flask.jsonify(
                    {
                        "message": f"""
                        {-1 * quantity} isImmediatePrep orderItem(s) 
                        successfully deducted from 
                        order with orderID: {existing_order['orderID']}
                        """
                    }
                ), 204
            

            # Case 2-2-2: deleting entire menu from cart:
            elif quantity < -1:
                # delete one row of menuItem
                cursor.execute(
                    '''
                    DELETE FROM orderItem 
                    WHERE parentOrderID=%(parentOrderID)s 
                    AND menuID=%(menuID)s 
                    AND quantity=%(quantity)s
                    ''',
                    {
                        'parentOrderID': existing_order['orderID'],
                        'menuID': menuID,
                        'quantity': -1 * quantity,
                    }
                )
                deleted_rows = cursor.rowcount()

                # error handling: deleted rows does not match with expected
                if deleted_rows == 0:
                    # return error message
                    return flask.jsonify(
                        {
                            "error": f"""
                            1 isImmediatePrep row expected to be deleted, but 
                            no row deleted, check if the quantity to delete 
                            (negative value) is correct
                            """
                        }
                    ), 424
                
                # if there no longer exists orderItems for a order,
                # delete the order
                check_orderItems_and_delete(cursor, existing_order['orderID'])
                
                return flask.jsonify(
                    {
                        "message": (
                            f"{-1 * quantity} isImmediatePrep orderItem(s) "
                            f"successfully deducted from "
                            f"order with orderID: {existing_order['orderID']}"
                        )
                    }
                ), 204

    else:
        return flask.jsonify({"error": "invalid quantity"}), 400

@server.application.route('/api/v2/pocha/cart/<string:email>/<int:pochaID>/check-stock/', methods=['GET'])
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

@server.application.route('/api/v2/pocha/cart/<string:email>/<int:pochaID>/checkout-info/', methods=['GET'])
# @token_required
def get_cart_checkout_info(email, pochaID):
    '''
    Get total price of cart using user email and current pochaID
    '''
    # fetch order
    cursor = server.model.Cursor()
    cursor.execute(
        '''
        SELECT orderID FROM `order`
        WHERE parentPochaID = %(parentPochaID)s
        AND email = %(email)s
        AND isPaid = %(isPaid)s
        ''',
        {
            'parentPochaID': pochaID,
            'email': email,
            'isPaid': False
        }
    )
    orderID = cursor.fetchone()['orderID']

    # fetch all orderItems with parentOrderID as fetched orderID
    cursor.execute(
        '''
        SELECT quantity, menuID FROM orderItem
        WHERE parentOrderID = %(parentOrderID)s
        ''',
        {
            'parentOrderID': orderID
        }
    )
    orderItems = cursor.fetchall() # 모든 orderItem을 가져온다 

    amount = 0.0
    ageCheckRequired = False

    # fetch price and ageCheckRequired with menuID as fetched orderItems' menuID
    for orderItem in orderItems:
        cursor.execute(
            '''
            SELECT price, ageCheckRequired FROM menu
            WHERE menuID = %(menuID)s
            ''',
            {
                'menuID': orderItem['menuID']
            }
        )
        menu_price_ageCheckRequired = cursor.fetchone()

        # add price to total amount
        amount += menu_price_ageCheckRequired['price'] * orderItem['quantity']

        # check ageCheckRequired from menu table (ageCheckRequired가 False인 경우만 들어가면 됨, 이미 True로 업데이트 됐으면 굳이 갈 필요 x)
        if not ageCheckRequired:
            if menu_price_ageCheckRequired['ageCheckRequired']:
                ageCheckRequired = True
    
    # return 404 not found when amount is 0, or cart is empty
    if amount == 0:
        flask.jsonify({"error": "user cart is empty"}), 404

    return flask.jsonify({
        "amount" : amount,
        "ageCheckRequired" : "true" if ageCheckRequired else "false"
    }), 200

@server.application.route('/api/v2/pocha/cart/<string:email>/<int:pochaID>/pay-result/', methods=['PUT'])
# @token_required
def pay_success_fail(email, pochaID):
    body = flask.request.get_json()
    result = body['result'] # 'success' | 'failure'
    # Case 1: payment is successful
        # change isPaid flag of order to 1
        # emit on event "order-created"
        # socket io body is list of added orderItems

    # Case 2: payment has failed