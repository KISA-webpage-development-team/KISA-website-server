import flask
import server
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/order

@server.application.route('/api/v2/pocha/order/<string:email>/<int:pochaID>/', methods=['GET'])
# @token_required
def get_user_orders(email, pochaID):
    '''
    Fetch user's active orders by email and pochaID
    '''
    # check if active order exists 
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT orderID FROM `order`
        WHERE email = %(email)s 
        AND parentPochaID = %(parentPochaID)s 
        AND isPaid = %(isPaid)s
        """,
        {
            'email': email,
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

    '''
    있으면 list of dictionaries 없으면 empty list
    {
        pending: [
            {
                orderItemID : int,
                status : string,
                quantity: int,
                menu: {               
                    menuID: number;
                    nameKor: string;
                    nameEng: string;
                    price: number;
                    stock: number;
                    isImmediatePrep: boolean;
                    parentPochaId: number;
            }
            }, {}, {}, ...],
        preparing: { ...  위와 같다. }
        ready: { ...  위와 같다. }
    }
    '''
    

