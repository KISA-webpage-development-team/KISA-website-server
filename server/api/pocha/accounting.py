import flask
import server
import datetime
from ..helpers import token_required, check_orderItems_and_delete
from collections import defaultdict


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/accounting

@server.application.route('/api/v2/pocha/accounting/', methods=['GET'])
def get_past_pochas():
    # retrieve the current time from the client request
    currentTime = flask.request.args.get(
            "date",
            type=datetime.datetime.fromisoformat
    )

    if not currentTime:
        return flask.jsonify({'error': 'current time not specified'}), 400
    
    # fetch pochaID, title, and startDate from pocha table where endDate is prior to currentTime
    cursor = server.model.Cursor()
    cursor.execute(
        '''
        SELECT pochaID, title, startDate FROM pocha
        WHERE endDate < %(currentTime)s
        ''',
        {
            'currentTime' : currentTime
        }
    )

    past_pochas = cursor.fetchall()

    return flask.jsonify(past_pochas), 200

@server.application.route('/api/v2/pocha/accounting/<int:pochaID>/', methods=['GET'])
def get_orderItems_by_pochaID(pochaID):
    cursor = server.model.Cursor()

    # Initialize flask request arguments
    size = flask.request.args.get(
        "size",
        default=10,
        type=int
    )
    page = flask.request.args.get(
        "page",
        default=0,
        type=int
    )

    # Sanity check for appropriate flask request arguments
    if (size != 10 and size != 20 and size != 30) or (page < 0):
        return flask.jsonify({'error': 'invalid pagination args'}), 400
    
    # Fetch paid orders of the particular pocha
    cursor.execute(
        '''
        SELECT orderID, email FROM pocha
        WHERE parentPochaID = %(parentPochaID)s
        AND isPaid = %(isPaid)s
        LIMIT %(limit)s
        ''',
        {
            'parentPochaID' : pochaID,
            'isPaid' : True,
            'limit' : size * (page + 1)
        }
    )
    paid_orders = cursor.fetchall()

    orderItems = []

    #Fetch quantity and menuID of paid orderItems from orderItem table 
    for paid_order in paid_orders:
        cursor.execute(
            '''
            SELECT quantity, menuID FROM orderItem
            WHERE parentOrderID = %(parentOrderID)
            ''',
            {
                'parentOrderID' : paid_order['orderID']
            }
        )

        orderItems_by_user = cursor.fetchall()

        # Fetch user's name with an email 
        cursor.execute(
            '''
            SELECT name FROM users 
            WHERE email = %(email)s
            ''',
            {
                'email' : paid_order['email']
            }
        )

        name = cursor.fetchone()

        # Add user's email, name, and menu information to the dictionary        
        for orderItem_by_user in orderItems_by_user:
            orderItem_by_user['email'] = paid_order['email']
            orderItem_by_user['name'] = name

            cursor.execute(
            '''
            SELECT nameKor, nameEng, price FROM menu
            WHERE menuID = %(menuID)s
            ''',
            {
                menuID : orderItem_by_user.pop('menuID')
            }
            )

            menu_info = cursor.fetchone()

            orderItem_by_user.update(menu_info)

        
        orderItems += orderItems_by_user
    
    return flask.jsonify(orderItems), 200

@server.application.route('/api/v2/pocha/accounting/<int:pochaID>/', methods=['GET'])
def get_total_income(pochaID):
    cursor = server.model.Cursor()

    #Fetch all paid orders of a particular pocha from order table 
    cursor.execute(
        '''
        SELECT orderID FROM order
        WHERE parentPochaID = %(parentPochaID)s AND isPaid = %(isPaid)s
        ''',
        {
            'parentPochaID' : pochaID,
            'isPaid' : True
        }
    )

    paid_orders = cursor.fetchall()

    # Fetch all menu's prices of a particular pocha from menu table
    cursor.execute(
        '''
        SELECT menuID, price FROM menu
        WHERE parentPochaID = %(parentPochaID)s
        ''',
        {
            'parentPochaID' : pochaID
        }
    )

    menus = cursor.fetchall()
    price_dict = {}
    for menu in menus:
        price_dict[menu['menuID']] = menu['price']

    # Sum up individual orderItem's final price 
    total_income = 0
    for paid_order in paid_orders:
        cursor.execute(
            '''
            SELECT quantity, menuID FROM orderItem
            WHERE parentOrderID = %(parentOrderID)s
            ''',
            {
                'parentOrderID' : paid_order['orderID']
            }
        )
        orderItems = cursor.fetchall()

        for orderItem in orderItems:
            total_income += orderItem['quantity'] * price_dict[orderItem['menuID']]

    return flask.jsonify(total_income), 200

    