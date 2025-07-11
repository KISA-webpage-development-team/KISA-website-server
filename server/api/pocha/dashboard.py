import flask
import server
from ..helpers import token_required
from .notification import send_notification
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/dashboard

@server.application.route('/api/v2/pocha/dashboard/<int:pochaID>/', methods=['GET'])
def get_pocha_orders(pochaID):
    '''
    Fetch all active orders by pochaID
    '''
    # check if active order exists
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT email, orderID FROM `order`
        WHERE parentPochaID = %(parentPochaID)s 
        AND isPaid = %(isPaid)s
        """,
        {
            'parentPochaID': pochaID,
            'isPaid': True
        }
    )
    active_orders = cursor.fetchall()
    
    response = {
        'pending': [],
        'preparing': [],
        'ready': []
    }
    
    # fetch all orderItems with orderID
    for active_order in active_orders:
        cursor.execute(
            """
            SELECT orderItemID, status, quantity, menuID
            FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s 
            AND status != %(status)s
            """,
            {
                'parentOrderID': active_order['orderID'],
                'status': 'closed'
            }
        )
        orderItems = cursor.fetchall()

        # append into response based on status
        for orderItem in orderItems:
            # fetch menu information using menuID first
            cursor.execute(
                """
                SELECT * FROM menu
                WHERE menuID = %(menuID)s 
                """,
                {
                    'menuID': orderItem['menuID']
                }
            )
            menu_info = cursor.fetchone()
            del orderItem["menuID"]
            orderItem['menu'] = menu_info

            # fetch user information and append into orderItem
            cursor.execute(
                """
                SELECT fullname FROM users
                WHERE email = %(email)s
                """,
                {
                    'email': active_order['email']
                }
            )
            orderItemFullname = cursor.fetchone()['fullname']
            orderItem['ordererName'] = orderItemFullname
            orderItem['ordererEmail'] = active_order['email']

            response[orderItem['status']].append(orderItem)

    return flask.jsonify(response), 200


@server.application.route('/api/v2/pocha/dashboard/<int:pochaID>/closed/', methods=['GET'])
def get_pocha_closed_orders(pochaID):
    '''
    Fetch all paid orders by pochaID
    '''
    # check if paid order exists 
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT email, orderID FROM `order`
        WHERE parentPochaID = %(parentPochaID)s 
        AND isPaid = %(isPaid)s
        """,
        {
            'parentPochaID': pochaID,
            'isPaid': True
        }
    )
    paid_orders = cursor.fetchall()

    response = {'closed' : []}

    # fetch all orderItems with orderID
    for paid_order in paid_orders:
        cursor.execute(
            """
            SELECT orderItemID, status, quantity, menuID
            FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s 
            AND status = %(status)s
            """,
            {
                'parentOrderID': paid_order['orderID'],
                'status': 'closed'
            }
        )
        orderItems = cursor.fetchall()

        # append into response 
        for orderItem in orderItems:
            # fetch menu information using menuID first
            cursor.execute(
                """
                SELECT * FROM menu
                WHERE menuID = %(menuID)s 
                """,
                {
                    'menuID': orderItem['menuID']
                }
            )
            menu_info = cursor.fetchone()
            del orderItem["menuID"]
            orderItem['menu'] = menu_info

            # fetch user information and append into orderItem
            cursor.execute(
                """
                SELECT fullname FROM users
                WHERE email = %(email)s
                """,
                {
                    'email': paid_order['email']
                }
            )
            orderItemFullname = cursor.fetchone()['fullname']
            orderItem['ordererName'] = orderItemFullname
            orderItem['ordererEmail'] = paid_order['email']

            response['closed'].append(orderItem)
            
    return flask.jsonify(response), 200    

@server.application.route('/api/v2/pocha/dashboard/<int:orderItemID>/change-status/', methods=['PUT'])
def put_order_item_status(orderItemID):
    '''
    Change order item's status and emit socket event to appropriate user.
    '''
    # fetch orderItem first and check its status
    cursor = server.model.Cursor()
    # cursor.execute(
    #     """
    #     SELECT status, parentOrderID FROM orderItem
    #     WHERE orderItemID = %(orderItemID)s
    #     """,
    #     {
    #         'orderItemID': orderItemID
    #     }
    # )
    # orderItem = cursor.fetchone()
    # orderID = orderItem['parentOrderID']
    # status = orderItem['status']
    # new_status = None

    cursor.execute(
        """
        SELECT 
            oi.status, 
            o.email, 
            m.isImmediatePrep
        FROM orderItem oi
        JOIN `order` o ON oi.parentOrderID = o.orderID
        JOIN menu m ON oi.menuID = m.menuID
        WHERE oi.orderItemID = %(orderItemID)s
        """,
        {
            'orderItemID': orderItemID
        }
    )
    orderItem = cursor.fetchone()
    status = orderItem['status']
    email = orderItem['email']
    is_immediate_prep = orderItem['isImmediatePrep']
    new_status = None

    match status:
        case 'pending':
            new_status = 'preparing'
        case 'preparing':
            new_status = 'ready'
        case 'ready':
            new_status = 'closed'
        case 'closed':
            return flask.jsonify({'error': 'Order item already closed'}), 400
        case _:
            return flask.jsonify({'error': 'Invalid status'}), 400
        
    if status == 'pending' and is_immediate_prep:
        new_status = 'ready'
    
    # change status of orderItem
    cursor.execute(
        """
        UPDATE orderItem
        SET status = %(new_status)s
        WHERE orderItemID = %(orderItemID)s
        """,
        {
            'new_status': new_status,
            'orderItemID': orderItemID
        }
    )

    # 

    # send notification (silent) when order status is changed
    send_notification(
        email=email,
        subject="order-status-update",
        silent=True,
        data={
            'event': 'order-status-update',
            'orderItemID': orderItemID,
            'status': new_status
        }
    )

    # emit socket event to dashboard (web)
    server.sio.emit(
        f"status-change-{email}", 
        {
            'status': new_status,
            'orderItemID': orderItemID
        }
    )
    
    # send push notification (alert) when order is ready
    if new_status == 'ready':
        send_notification(
            email=email,
            subject="Order Status Changed",
            title="Your Order is Ready!",
            body="Please pick up your order at the booth."
        )

    return flask.jsonify({
        "orderItemID": orderItemID,
        'newStatus': new_status
    }
    ), 200

@server.application.route('/api/v2/pocha/dashboard/change-stock/', methods=['PUT'])
def put_menu_stock():
    '''
    Change stock quantity of menu
    '''
    # fetch body from request
    body = flask.request.get_json()

    # initialize variables from body
    menuID = body["menuID"]
    quantity = body["quantity"]
    
    # change stock quantity of menu
    cursor = server.model.Cursor()
    cursor.execute(
        """
        UPDATE menu
        SET stock = %(quantity)s
        WHERE menuID = %(menuID)s
        """,
        {
            'quantity': quantity,
            'menuID': menuID
        }
    )

    # return success message
    return flask.jsonify({"message": "stock quantity changed"}), 200