# entry point of flask backend
import flask
import server
from ..helpers import token_required
import boto3

# AUTH APIS ----------------------------------------------------------f
# /api/v2/credentials/auth
@server.application.route('/api/v2/auth/userExists/<string:email>', methods=['GET'])
def check_existing_user(email):
   cursor = server.model.Cursor()
   cursor.execute(
      "SELECT * FROM users "
      "WHERE email = %(email)s",
      {
         'email': email
      }
   )
   user = cursor.fetchone()

   if user:
      return flask.jsonify({
         "message": "requested user exists",
         "fullname": user['fullname']
      }), 200

   # temporary logic for app evaluation
   else:
      # add the user, regardless of email format
      cursor.execute(
         '''
         INSERT INTO users (email, fullname, major, gradYear, bornYear, bornMonth, bornDate)
         values (%(email)s, 'test_user', 'N/A', 0, 0, 0, 0)
         ''',
         {
            'email': email
         }
      )
      user = cursor.fetchone()
      return flask.jsonify({
         "message": "requested user exists",
         "fullname": user['fullname']
      }), 200
   #  return flask.jsonify({
   #     "message": "requested user does not exist"
   #  }), 404
    
@server.application.route('/api/v2/auth/signup/', methods=['POST'])
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

@server.application.route('/api/v2/auth/isAdmin/<string:email>', methods=['GET'])
@token_required
def is_admin(email):
    cursor = server.model.Cursor()

    # Fetch the comment based on commentid
    cursor.execute(
        "SELECT * FROM admins "
        "WHERE email = %(email)s",
        {
            'email': email
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
