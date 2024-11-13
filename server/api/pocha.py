import flask
import server
import datetime
from .helpers import token_required

# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha

@server.application.route('/api/v2/pocha/status-info/', methods=['GET'])
def get_pocha():
    # retrieve the current time from the client request
    currentTime = flask.request.args.get(
        "date",
        type=datetime
    )

    # fetch last row from pocha table
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT * "
        "FROM pocha "
        "ORDER BY pochaId DESC "
        "LIMIT 1"
    )
    pocharow = cursor.fetchone()

    # Case 1: there is no scheduled pocha
    # if endTime <= currentTime || queryResult == None
    if pocharow == None or datetime(pocharow['endTime']) <= currentTime:
        return flask.jsonify({}), 200

    # Case 2-1: there is scheduled pocha
    # if currentTime < startTime
    if currentTime < datetime(pocharow['startTime']):
        pocharow['ongoing'] = False
        return flask.jsonify(pocharow), 200
        # response ... 'ongoing' = False
    



    # Case 2-2: there is ongoing pocha
    # if startTime <= currentTime < endTime

        # response ... 'ongoing' = True