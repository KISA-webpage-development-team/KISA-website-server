import flask
import server
from .helpers import token_required

# Likes API ------------------------------------------------------------
# /api/v2/likes
@server.application.route("/api/v2/likes/<int:id>", methods=['POST', 'DELETE'])
@token_required
def contrast_like(id):
    '''
    Contrast likes for post or comment. Post or comment mode specified in body.
    Creates likes if it does not exist, deletes like if it does exist.
    '''
    body = flask.request.get_json()
    email = body['email']
    target = body['target'] # 'posts' or 'comments'
    pass

@server.application.route("/api/v2/likes/<int:id>", methods=['GET'])
@token_required
def like_or_not(id):
    '''
    Returns whether the user liked the post / comment or not.
    '''
    body = flask.request.get_json()
    email = body['email']
    target = body['target'] # 'posts' or 'comments'
    pass
