import flask
import server

# SAY HELLO API ---------------------------------------------------------
# /api/v2/say-hello
# Deployment smoke test. Touches no database and no AWS service.
@server.application.route("/api/v2/say-hello/", methods=['GET'])
def say_hello():
    return flask.jsonify({'message': 'hello from the KISA api'}), 200
