import flask
import server
from ..helpers import fetch_user_posts, fetch_user_comments, token_required

# Users API ------------------------------------------------------------
# /api/v2/credentials/users
@server.application.route("/api/v2/users/<string:email>/",
                  methods=['GET'])
@token_required
def get_user(email):
    cursor = server.model.Cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * "
        "FROM users "
        "WHERE email = %(email)s",
        {
            'email': email
        }
    )
    user = cursor.fetchone()

    print("[LOG-GET-USER] checking existance of user: ", email)

    # return 404 NOT FOUND
    if not user:
        print("[LOG-GET-USER] user does not exist: ", email)
        cursor.execute(
            '''
            INSERT INTO users (email, fullname, major, gradYear, bornYear, bornMonth, bornDate)
            values (%(email)s, 'test_user', 'N/A', 0, 0, 0, 0)
            ''',
            {
                'email': email
            }
        )
        print("[LOG-GET-USER] fake test user made for: ", email)
        # render context
        return flask.jsonify({
            "message": "requested user exists",
        }), 200

    # render context
    user['url'] = flask.request.url
    context = user

    return flask.jsonify(**context), 200

@server.application.route("/api/v2/users/<string:email>/", methods=['PATCH'])
@token_required
def put_user(email):
    # Assuming the incoming data is in JSON format
    body = flask.request.get_json()

    # If the body is empty, do nothing
    if not body:
        return flask.jsonify({'message': 'Bad request, empty body'}), 400

    body['email'] = email

    cursor = server.model.Cursor()
    cursor.execute(
        "UPDATE users SET " +
        ', '.join(map(lambda x: f'{x} = %({x})s', body.keys())) +
        " WHERE email = %(email)s",
        body
    )

    return flask.jsonify({'message': 'User updated successfully'}), 200

@server.application.route("/api/v2/users/<string:email>/", methods=['DELETE'])
@token_required
def delete_user(email):
    cursor = server.model.Cursor()

    # Check if the user exists
    cursor.execute(
        'SELECT * FROM users WHERE email = %(email)s',
        {
            'email': email
        }
    )
    existing_user = cursor.fetchone()

    if existing_user:
        # Delete the user from the database
        cursor.execute(
            'DELETE FROM users WHERE email = %(email)s',
            {
                'email': email
            }
        )

        # Return a success message
        return flask.jsonify({'message': f'user with email {email} deleted successfully'}), 200
    else:
        return flask.jsonify({'error': 'User not found'}), 404
    
@server.application.route("/api/v2/users/<string:email>/posts/",
                  methods=['GET'])
@token_required
def get_user_posts(email):
    cursor = server.model.Cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * "
        "FROM users "
        "WHERE email = %(email)s",
        {
            'email': email
        }
    )
    user = cursor.fetchall()

    # return 404 NOT FOUND (user not found)
    if not user:
        return flask.jsonify({'error': 'No User Found'}), 404
    
    user_posts = fetch_user_posts(email)

    # Check if the user exists
    if user_posts is None:
        return flask.jsonify({'error': 'User posts not found'}), 404
    
    # Return the user's posts
    return flask.jsonify({'posts': user_posts}), 200

@server.application.route("/api/v2/users/<string:email>/comments/",
                  methods=['GET'])
@token_required
def get_user_comments(email):
    cursor = server.model.Cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * FROM users "
        "WHERE email = %(email)s",
        {
            'email': email
        }
    )
    user = cursor.fetchall()

    # return 404 NOT FOUND (user not found)
    if not user:
        return flask.jsonify({'error': 'No User Found'}), 404
    
    user_comments = fetch_user_comments(email)

    # Check if the user exists
    if user_comments is None:
        return flask.jsonify({'error': 'User comments not found'}), 404
    
    # Return the user's posts
    return flask.jsonify({'comments': user_comments}), 200