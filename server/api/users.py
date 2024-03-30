import flask
import server

# TODO: We need a way to authenticate admin users
def is_admin(authorization_header):
    admin_token = "your_admin_token"
    return authorization_header == f"Bearer {admin_token}"

def fetch_user_posts(email):
    # Assuming you have a database connection and cursor
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch posts associated with the given email
    cursor.execute("SELECT * FROM posts WHERE email = ?", (email,))
    user_posts = cursor.fetchall()

    return user_posts

def fetch_user_comments(email):
    # Assuming you have a database connection and cursor
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch comments associated with the given email
    cursor.execute("SELECT * FROM comments WHERE email = ?", (email,))
    user_comments = cursor.fetchall()


    return user_comments

# Users API ------------------------------------------------------------
# /api/v1/users/{email}

# @desc    Get user's basic info using email
# @route   GET /api/v1/users/<string:email>/
# @argv    string:email
# TEST: http "http://localhost:8000/api/v1/users/wookwan@umich.edu/"
@server.app.route("/api/v1/users/<string:email>/",
                  methods=['GET'])
def get_user(email):
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * "
        "FROM users "
        "WHERE email = ?",
        (email, )
    )
    user = cursor.fetchall()

    # return 404 NOT FOUND
    if not user:
        return flask.jsonify({'error': 'No User Found'}), 404

    # render context
    context = {
        'email': email,
        'fullname': user[0]['fullname'],
        'created': user[0]['created']
    }

    return flask.jsonify(**context), 200

# @desc    Update user's fullname
# @route   PUT /api/v1/users/<string:email>/
# @argv    string:email
# TEST:  curl -X PUT -H "Content-Type: application/json" -d '{"fullname": "지윤성"}' http://localhost:8000/api/v1/users/wookwan@umich.edu/
@server.app.route("/api/v1/users/<string:email>/", methods=['PUT'])
def put_user(email):
    # Assuming the incoming data is in JSON format
    data = flask.request.get_json()

    # Extract relevant information from the JSON data
    fullname = data.get('fullname')

    # Perform validation on the input data
    if not fullname or not email:
        return flask.jsonify({'error': 'Missing required fields'}), 400
    
    # Authenticate Admin
    # if not is_admin(flask.request.headers.get('Authorization')):
    #     return flask.jsonify({'error': 'Unauthorized'}), 401
    
    db = server.model.get_db()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE users "
        "SET fullname = ? "
        "WHERE email = ? ", 
        (fullname, email)
    )

    db.commit()

    # Return a JSON response indicating success
    return flask.jsonify({'message': 'User updated successfully'}), 200

# @desc    Delete user TODO: only admin?
# @route   DELETE /api/v1/users/{email}
# @argv    string:email
# TEST: curl -X DELETE http://localhost:8000/api/v1/users/wookwan@umich.edu/
@server.app.route("/api/v1/users/<string:email>/", methods=['DELETE'])
def delete_user(email):
    db = server.model.get_db()
    cursor = db.cursor()

    # Check if the user exists
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        # Delete the user from the database
        cursor.execute('DELETE FROM users WHERE email = ?', (email,))
        db.commit()

        # Return a success message
        return flask.jsonify({'message': f'user with email {email} deleted successfully'}), 200
    else:

        return flask.jsonify({'error': 'User not found'}), 404
    
# @desc    Get all posts created by user
# @route   GET /api/v1/users/<string:email>/posts
# @argv    string:email
# TEST: http "http://localhost:8000/api/v1/users/wookwan@umich.edu/posts
@server.app.route("/api/v1/users/<string:email>/posts/",
                  methods=['GET'])
def get_user_posts(email):
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * "
        "FROM users "
        "WHERE email = ?",
        (email, )
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

# @desc    Get all comments created by user
# @route   GET /api/v1/users/<string:email>/comments
# @argv    string:email
# TEST: http "http://localhost:8000/api/v1/users/wookwan@umich.edu/comments
@server.app.route("/api/v1/users/<string:email>/comments/",
                  methods=['GET'])
def get_user_comments(email):
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch the user based on email
    cursor.execute(
        "SELECT * "
        "FROM users "
        "WHERE email = ?",
        (email, )
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