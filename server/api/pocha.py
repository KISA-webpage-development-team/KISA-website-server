import flask
import server
import datetime
from .helpers import token_required
from collections import defaultdict

# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha

@server.application.route('/api/v2/pocha/status-info/', methods=['GET'])
def get_pocha():
    # retrieve the current time from the client request
    currentTime = flask.request.args.get(
        "date",
        type=datetime.datetime.fromisoformat
    )

    if not currentTime:
        return flask.jsonify({'error': 'current time not specified'}), 400

    # fetch last row from pocha table
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT * "
        "FROM pocha "
        "ORDER BY pochaId DESC "
        "LIMIT 1",
        {}
    )
    pocharow = cursor.fetchone()

    # Case 1: there is no scheduled pocha
    # if endTime <= currentTime || queryResult == None
    if pocharow == None or pocharow['endDate'] <= currentTime:
        return flask.jsonify({}), 204

    # Case 2-1: there is scheduled pocha
    # if currentTime < startTime
    if currentTime < pocharow['startDate']:
        pocharow['ongoing'] = False
        return flask.jsonify(pocharow), 200

    # Case 2-2: there is ongoing pocha
    # if startTime <= currentTime < endTime
    if currentTime < pocharow['endDate'] and pocharow['startDate'] <= currentTime:
        pocharow['ongoing'] = True
        return flask.jsonify(pocharow), 200
    
@server.application.route('/api/v2/pocha/menu/<int:pochaid>/', methods=['GET'])
@token_required
def get_pocha_menu(pochaid):
    # error handling: there is no pocha with the given pochaid
    cursor = server.model.Cursor()
    cursor.execute(
        """
        SELECT * FROM pocha WHERE pochaId = %(pochaid)s
        """,
        {
            'pochaid': pochaid
        }
    )
    existing_pocha = cursor.fetchone()
    if not existing_pocha:
        return flask.jsonify({'error': 'Pocha not found'}), 404
    
    # fetch all rows with parentPochaID == pochaid from menu table
    cursor.execute(
        """
        SELECT * FROM menu WHERE parentPochaID = %(pochaid)s
        """,
        {
            'pochaid': pochaid
        }
    )
    menus = cursor.fetchall()

    # sort raw table data by its categories into a temporary dictionary
    category_dict = defaultdict(list)
    for menu in menus:
        category = menu["category"]
        del menu["category"]
        category_dict[category].append(menu)

    # build response in right format
    response = []
    for key in category_dict:
        response.append(
            {
                "category": key,
                "menusList": category_dict[key]
            }
        )

    return flask.jsonify(response), 200

# @server.application.route('/api/v2/pocha/status-info/', methods=['GET'])
# def get_pocha():
#     pass