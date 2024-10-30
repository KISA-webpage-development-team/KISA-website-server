import flask
import server
from .helpers import token_required

# Likes API ------------------------------------------------------------
# /api/v2/likes
@server.application.route("/api/v2/likes/<int:id>/", methods=['POST'])
@token_required
def post_like(id):
    '''
    Like a post or comment.
    Email and target specified in body.
    '''
    # Fetch email and target from the request body
    body = flask.request.get_json()
    email = body['email']
    target = body['target'] # 'post' or 'comment'

    # Handle bad request
    if not email or not target or target not in ['post', 'comment']:
        return flask.jsonify({"error": "Missing required request body key"}), 400

    # Query database to insert like
    cursor = server.model.Cursor()
    cursor.execute(
        f'''
        INSERT INTO {target}likes (email, {target}id) VALUES (%(email)s, %(id)s)
        ''',
        {
            'email': email,
            'id': id
        }
    )

    # Return success message
    return flask.jsonify({"message": f"{target} liked successfully"}), 201

@server.application.route("/api/v2/likes/<int:id>/", methods=['DELETE'])
@token_required
def delete_like(id):
    '''
    Unlike a post or comment.
    Email and target specified in url parameter.
    '''
    # Fetch email and target from the url arguments
    email = flask.request.args.get("email", type=str)
    target = flask.request.args.get("target", type=str)

    # Handle bad request
    if not email or not target or target not in ['post', 'comment']:
        return flask.jsonify({"error": "Missing required request body key"}), 400

    # Query database to insert like
    cursor = server.model.Cursor()
    cursor.execute(
        f'''
        DELETE FROM {target}likes
        WHERE email = %(email)s AND {target}id = %(id)s
        ''',
        {
            'email': email,
            'id': id
        }
    )

    # Return success message
    return flask.jsonify({"message": f"{target} unliked successfully"}), 204

@server.application.route("/api/v2/likes/<int:id>/", methods=['GET'])
@token_required
def like_or_not(id):
    '''
    Returns whether the user liked the post / comment or not.
    '''
    # Fetch email and target from the request body
    email = flask.request.args.get("email", type=str)
    target = flask.request.args.get("target", type=str)

    # Handle bad request
    if not email or not target or target not in ['post', 'comment']:
        return flask.jsonify({"error": "Missing required request body key"}), 400
    
    # Query database to check if the user liked the post / comment
    cursor = server.model.Cursor()
    cursor.execute(
        f'''
        SELECT * FROM {target}likes
        WHERE email = %(email)s AND {target}id = %(id)s
        ''',
        {
            'email': email,
            'id': id
        }
    )
    like = cursor.fetchone()

    if not like:
        return flask.jsonify({"liked": False}), 200
    else:
        return flask.jsonify({"liked": True}), 200