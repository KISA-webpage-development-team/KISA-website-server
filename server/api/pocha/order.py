import flask
import server
from ..helpers import token_required
from .order_helpers import active_orders_by_status, closed_orders


# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/order

@server.application.route('/api/v2/pocha/order/<string:email>/<int:pochaID>/', methods=['GET'])
@token_required
def get_user_orders(email, pochaID):
    '''
    Fetch user's active orders by email and pochaID
    '''
    cursor = server.model.Cursor()
    response = active_orders_by_status(cursor, pochaID, email=email)
    return flask.jsonify(response), 200
    
@server.application.route('/api/v2/pocha/order/<string:email>/<int:pochaID>/closed/', methods=['GET'])
@token_required
def get_user_closed_orders(email, pochaID):
    '''
    Fetch user's paid orders by email and pochaID
    '''
    cursor = server.model.Cursor()
    response = closed_orders(cursor, pochaID, email=email)
    return flask.jsonify(response), 200
