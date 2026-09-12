import flask
import server

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

    # One page of posts with their like and comment counts in a single query
    cursor.execute(
        "SELECT postid, type, title, fullname, readCount, isAnnouncement, created, "
        "(SELECT COUNT(*) FROM postlikes WHERE postlikes.postid = posts.postid) AS \"likesCount\", "
        "(SELECT COUNT(*) FROM comments WHERE comments.postid = posts.postid) AS \"commentsCount\" "
        "FROM posts "
        "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s "
        "ORDER BY postid DESC "
        "LIMIT %(limit)s OFFSET %(offset)s",
        {
            'type': board_type,
            'isAnnouncement': False,
            'limit': size,
            'offset': page * size
        }
    )
    posts_in_page = cursor.fetchall()

    if not posts_in_page:
        # Distinguish an empty board from a page past the end
        cursor.execute(
            "SELECT postid FROM posts "
            "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s "
            "LIMIT 1",
            {
                'type': board_type,
                'isAnnouncement': False
            }
        )
        if not cursor.fetchone():
            return flask.jsonify({'response': 'No posts in board'}), 204
        return flask.jsonify({'error': 'No posts in requested page'}), 404

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
        "SELECT postid, type, title, fullname, readCount, isAnnouncement, created, "
        "(SELECT COUNT(*) FROM comments WHERE comments.postid = posts.postid) AS \"commentsCount\" "
        "FROM posts "
        "WHERE type = %(type)s AND isAnnouncement = %(isAnnouncement)s "
        "ORDER BY postid DESC",
        {
            'type': board_type,
            'isAnnouncement': True
        }
    )
    announcements = cursor.fetchall()

    if not announcements:
        return flask.jsonify({'response': f'No announcements for board type {board_type}'}), 204

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
    