# entry point of flask backend
import flask
import jwt
from functools import wraps
import server

# AUTH APIS ----------------------------------------------------------f
# /api/v1/auth

# @desc    Check whether user already exists in database
# @route   GET /api/v1/auth/userExists?email={email}
# @params  {query} string:email
@server.application.route('/api/v1/auth/userExists/', methods=['GET'])
def check_existing_user():
    request_email = flask.request.args["email"]
    cursor = server.model.Cursor()

    # Fetch the comment based on commentid
    cursor.execute(
        "SELECT * FROM users "
        "WHERE email = %(email)s",
        {
            'email': request_email
        }
    )
    user = cursor.fetchone()
    
    if user:
       return flask.jsonify({
          "message": "requested user exists",
          "fullname": user['fullname']
       }), 200
    return flask.jsonify({
       "message": "requested user does not exist"
    }), 409
    
# @desc    Check whether user already exists in database
# @route   GET /api/v1/auth/signup
# @params  {body} string:email string:name
# @test    curl -X POST -H "Content-Type: application/json" -d '{"fullname": "권우관", "email": "wookwan@umich.edu", "bornYear": 2000, "bornMonth": 9, "bornDate": 20, "major": "Computer Science", "gradYear": 2025}' http://localhost:8000/api/v1/auth/signup/
@server.application.route('/api/v1/auth/signup/', methods=['POST'])
def add_user():
    body = flask.request.get_json()

    # No body in request
    if not body:
        return flask.jsonify({'message': 'Bad request, empty body'}), 400
    
    # Missing required fields
    if not (
       body['fullname'] or
       body['email'] or
       body['bornYear'] or
       body['bornMonth'] or
       body['bornDate'] or
       body['major'] or
       body['gradYear']
    ):
       return flask.jsonify({'message': 'Bad request, required fields missing'}), 400

    cursor = server.model.Cursor()

    cursor.execute(
        "INSERT INTO users (" +
        ', '.join(body.keys()) +
        ") VALUES (" +
        ', '.join(map(lambda x: '%(' + x + ')s', body.keys())) + ")",
        body
    )

    return flask.jsonify({
       "message": f"user {body['email']} created"
    }), 201

# @desc    Check whether user is admin using email
# @route   GET /api/v1/auth/isAdmin?email={email}
# @params  {query} string:email
@server.application.route('/api/v1/auth/isAdmin/', methods=['GET'])
def is_admin():
    request_email = flask.request.args["email"]

    cursor = server.model.Cursor()

    # Fetch the comment based on commentid
    cursor.execute(
        "SELECT * FROM admins "
        "WHERE email = %(email)s",
        {
            'email': request_email
        }
    )
    email = cursor.fetchone()

    if email:
       return flask.jsonify({
          "message": "user is admin",
       }), 200
    return flask.jsonify({
       "message": "user is not admin"
    }), 401
