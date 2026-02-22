import flask
import server
from ..helpers import count_comments, count_likes

# BOARDS API ------------------------------------------------------------
# /api/v2/bulletin/boards
@server.application.route("/api/v2/boards/<string:board_type>/posts/",
                  methods=['GET'])
def get_posts_by_board_type(board_type):
    cursor = server.model.Cursor()

    # Initialize flask request arguments
    size = flask.request.args.get(
        "size",
        default=10,
        type=int
    )
    page = flask.request.args.get(
        "page",
        default=0,
        type=int
    )

    # Sanity check for appropriate flask request arguments
    if (size != 10 and size != 20 and size != 30) or (page < 0):
        return flask.jsonify({'error': 'invalid pagination args'}), 400

    # Fetch posts of the particular board type
    cursor.execute(
        "SELECT postid, type, title, fullname, readCount, isAnnouncement, created "
        "FROM posts "
        "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s "
        "ORDER BY postid DESC "
        "LIMIT %(limit)s",
        {
            'type': board_type,
            'isAnnouncement': 0,
            'limit': size * (page + 1)
        }
    )
    posts = cursor.fetchall()

    # Return 204 NO CONTENT if no posts are in board type
    if not posts:
        return flask.jsonify({'response': 'No posts in board'}), 204
    
    # sort posts by postid
    posts_in_page = sorted(posts[page * size : (page + 1) * size],
                           key=lambda e : e["postid"],
                           reverse=True)
    
    if not posts_in_page:
        return flask.jsonify({'error': 'No posts in requested page'}), 404

    # Count the number of comments and likes of each post
    for post in posts_in_page:
        count_likes(cursor, 'post', post)
        count_comments(cursor, post)

    # render context
    context_url = flask.request.path
    if flask.request.query_string:
        context_url += f"?{flask.request.query_string.decode()}"
    context = {
        "results": posts_in_page,
        "url": context_url
    }
    return flask.jsonify(**context), 200

@server.application.route("/api/v2/boards/<string:board_type>/announcements/",
                          methods=['GET'])
def get_announcements_by_board_type(board_type):
    cursor = server.model.Cursor()

    cursor.execute(
        "SELECT postid, type, title, fullname, readCount, isAnnouncement, created "
        "FROM posts "
        "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s "
        "ORDER BY postid DESC",
        {
            'type': board_type,
            'isAnnouncement': 1
        }
    )
    announcements = cursor.fetchall()

    if not announcements:
        return flask.jsonify({'response': f'No announcements for board type {board_type}'}), 204

    # Count the number of comments of each post and add to response result
    for announcement in announcements:
        count_comments(cursor, announcement)
    
    # render context
    context = {
        "results": announcements,
        "url": flask.request.path
    }
    return flask.jsonify(**context), 200

@server.application.route("/api/v2/boards/<string:board_type>/count/",
                  methods=['GET'])
def get_post_count(board_type):
    cursor = server.model.Cursor()

    cursor.execute(
        "SELECT COUNT(*) "
        "FROM posts "
        "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s",
        {
            'type': board_type,
            'isAnnouncement': False
        }
    )
    post_count = cursor.fetchone()['COUNT(*)']
    
    # render context
    context = {
        'postCount': post_count
    }
    return flask.jsonify(**context), 200
    