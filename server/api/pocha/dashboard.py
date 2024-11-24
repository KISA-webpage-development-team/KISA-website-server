import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
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
        SELECT orderID FROM `order`
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
        SELECT orderID FROM `order`
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

            response['closed'].append(orderItem)
            
    return flask.jsonify(response), 200    

@server.application.route('/api/v2/pocha/dashboard/<int:orderItemID>/change-status/', methods=['PUT'])
def put_order_item_status(orderItemID):
    '''
    Change order item's status and emit socket event to appropriate user.
    '''
    # fetch orderItem first and check its status
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT status, parentOrderID FROM orderItem
        WHERE orderItemID = %(orderItemID)s
        """,
        {
            'orderItemID': orderItemID
        }
    )
    orderItem = cursor.fetchone()
    orderID = orderItem['parentOrderID']
    status = orderItem['status']
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

    # find email or order issuer
    cursor.execute(
        """
        SELECT email FROM `order`
        WHERE orderID = %(orderID)s
        """,
        {
            'orderID': orderID
        }
    )
    email = cursor.fetchone()['email']

    # emit to socket event "status-change-{email}"
    server.sio.emit(
        f"status-change-{email}", 
        {
            'status': new_status,
            'orderItemID': orderItemID
        }
    )

    return flask.jsonify({
        'message': f"orderItem {orderItemID} status changed to {new_status}"}
    ), 200

