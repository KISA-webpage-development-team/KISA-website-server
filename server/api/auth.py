# entry point of flask backend
import flask
import jwt
from functools import wraps
import server

# decorator for verifying the JWT (유저가 웹사이트에서 로그인하면 JWT 토큰을 발급해줌 )
# JWT는 API call의 Authroization Header에 담겨서 서버에 보내짐
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = flask.request.headers.get('Authorization')
        if not token:
          return flask.jsonify({'message': 'Missing token'}), 401
  
        try:
            token = token.split(' ')[1]
            # decoding the payload to fetch the stored details
            # 'secret' is a same secret in client side
      # need to hide
            data = jwt.decode(token, 'secret', algorithms=['HS256'])
            # search for current user using data...
            # data.id = user email (get_data(userid))
            # temporary current user
            current_user = {'email': data['id']}
        except:
            return flask.jsonify({
                'message' : 'Token is invalid !!'
            }), 401
        # returns the current logged in users context to the routes
        return  f(current_user, *args, **kwargs)
  
    return decorated

# AUTH APIS ----------------------------------------------------------f
# /api/v1/auth

# @desc    Check whether user already exists in database
# @route   GET /api/v1/auth/userExists?email={email}
# @params  {query} string:email
@server.app.route('/api/v1/auth/userExists/', methods=['GET'])
def check_existing_user():
    request_email = flask.request.args["email"]

    db = server.model.get_db()
    cursor = db.cursor()


    # Fetch the comment based on commentid
    cursor.execute(
        "SELECT * FROM users "
        "WHERE email = ?",
        (request_email,)
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
@server.app.route('/api/v1/auth/signup/', methods=['POST'])
def add_user():
    data = flask.request.get_json()

    if not data:
            return flask.jsonify({
                "message": "Invalid request body"
            }), 400
    
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch the comment based on commentid
    # data['name'] = korean fullname
    cursor.execute(
        "INSERT INTO users "
        "(email, fullname) "
        "VALUES (?, ?) ",
        (data['email'], data['name'])
    )

    return flask.jsonify({
       "message": f"user {data['email']} created"
    }), 201

# @desc    Check whether user is admin using email
# @route   GET /api/v1/auth/isAdmin?email={email}
# @params  {query} string:email
@server.app.route('/api/v1/auth/isAdmin/', methods=['GET'])
def is_admin():
    request_email = flask.request.args["email"]

    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch the comment based on commentid
    cursor.execute(
        "SELECT * FROM admins "
        "WHERE email = ?",
        (request_email,)
    )
    email = cursor.fetchone()

    if email:
       return flask.jsonify({
          "message": "user is admin",
       }), 200
    return flask.jsonify({
       "message": "user is not admin"
    }), 401


# TEST APIs ---------------------------------------------------------
@server.app.route('/api/v1/auth/token-test/', methods=['POST'])
def token_test():
    token = flask.request.headers.get('Authorization')
    if not token:
      return flask.jsonify({'message': 'Missing token'}), 401

    try:
      token = token.split(' ')[1]
      # 'secret' is a same secret in client side
      # need to hide
      payload = jwt.decode(token, 'secret', algorithms=['HS256'])
      return flask.jsonify(payload), 200
    except jwt.ExpiredSignatureError:
      return flask.jsonify({'message': 'Token expired'}), 401
    except jwt.InvalidTokenError:
      return flask.jsonify({'message': 'Invalid token'}), 401

# token_required decorator example
@server.app.route('/api/v1/auth/decorate-test/', methods=['GET'])
@token_required # 이걸 붙이면 token (유저가 로그인된 상태)이 없으면 401 Missing Token 에러가 뜸
def decorate_test(current_user):
   return flask.jsonify({'message': 'WOW DECORATE PLEASE~'}), 200

if __name__ == "__main__":
    server.app.run(debug=True, port=8000)
# -----------------------------------------------------------------
