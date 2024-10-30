import flask
import server
from .helpers import token_required, count_comments, count_likes
from .image_handler import handle_imgs, delete_imgs

# POSTS API ------------------------------------------------------------
# /api/v2/posts
@server.application.route("/api/v2/posts/<int:postid>/",
                  methods=['GET'])
def get_post(postid):
    cursor = server.model.Cursor()

    # Fetch the post based on postid
    cursor.execute(
        "SELECT * "
        "FROM posts "
        "WHERE postid = %(postid)s",
        {
            'postid': postid
        }
    )
    post = cursor.fetchone()

    # return 404 NOT FOUND if no posts are in board type
    if not post:
        return flask.jsonify({'error': 'No Post Found'}), 404
    
    # Count the number of comments and likes of the post
    count_comments(cursor, post)
    count_likes(cursor, "post", post)

    # render context
    context = post
    return flask.jsonify(**context)

@server.application.route("/api/v2/posts/", methods=['POST'])
@token_required
def add_post():
    # Fetch body from request
    body = flask.request.get_json()

    # Fetch next postid by inserting a dummy post
    cursor = server.model.Cursor()
    cursor.execute(
        "INSERT INTO posts (type, email, title, text, isAnnouncement, fullname, readCount, anonymous) "
        "VALUES (%(type)s, %(email)s, %(title)s, %(text)s, %(isAnnouncement)s, %(fullname)s, %(readCount)s, %(anonymous)s)", 
        {
            "type": body['type'],
            "email": body['email'],
            "title": body['title'],
            "text": body['text'],
            "isAnnouncement": body['isAnnouncement'],
            "fullname": body['fullname'],
            "readCount": body['readCount'],
            "anonymous": body['anonymous']
        }
    )
    next_postid = cursor.lastrowid()

    # Handle image upload
    handle_imgs(body, next_postid)

    return flask.jsonify({'message': 'post created successfully'}), 201

@server.application.route("/api/v2/posts/<int:postid>/", methods=['PATCH'])
@token_required
def update_post(postid):
    # Fetch body from request
    body = flask.request.get_json()

    # Fetch previous post by postid
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT * FROM posts WHERE postid = %(postid)s",
        {
            'postid': postid
        }
    )
    prev_post = cursor.fetchone()

    if not prev_post:
        return flask.jsonify({'error': f'Post {postid} not found'}), 404

    # Handle image upload
    #   Compare the new text with the previous text
    #   Deletes / uploads images accordingly
    #   Text includes raw image pixel values
    handle_imgs(body, postid, prev_post['text'])

    cursor.execute(
        "UPDATE posts SET "
        "title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
        "WHERE postid = %(postid)s",
        {
            'title': body['title'],
            'text': body['text'],
            'isAnnouncement': body['isAnnouncement'],
            'postid': postid,
        }
    )

    return flask.jsonify({'message': f'post {postid} updated successfully'}), 200

@server.application.route("/api/v2/posts/<int:postid>/", methods=['DELETE'])
@token_required
def delete_post(postid):
    cursor = server.model.Cursor()

    # Check if the post with the specified postid exists
    cursor.execute(
        'SELECT * FROM posts WHERE postid = %(postid)s',
        {
            'postid': postid
        }
    )
    existing_post = cursor.fetchone()

    if existing_post:
        # Delete imgs
        delete_imgs(existing_post['text'])

        # Delete the post from the database
        cursor.execute(
            'DELETE FROM posts WHERE postid = %(postid)s',
            {
                'postid': postid
            }
        )

        # Return a success message
        return flask.jsonify({'message': f'Post {postid} deleted successfully'}), 204
    else:
        # Return an error message if the post doesn't exist
        return flask.jsonify({'error': 'Post not found'}), 404

@server.application.route("/api/v2/posts/readCount/<int:postid>/", methods=['PATCH'])
def increment_readcount(postid):
    cursor = server.model.Cursor()
    # Check if the post with the specified postid exists
    cursor.execute(
        'SELECT * FROM posts WHERE postid = %(postid)s',
        {
            'postid': postid
        }
    )
    existing_post = cursor.fetchone()

    if existing_post:
        # get current readCount
        cur_readCount = existing_post['readCount']

        # Update readCount of existing post
        cursor.execute(
            "UPDATE posts "
            "SET readCount = %(readCount)s "
            "WHERE postid = %(postid)s ",
            {
                'readCount': cur_readCount + 1,
                'postid': postid
            }
        )

        # Return a success message
        return flask.jsonify({'message': f'Post {postid} readCount is now {cur_readCount + 1}'}), 200
    else:
        # Return an error message if the post doesn't exist
        return flask.jsonify({'error': 'Post not found'}), 404
    
@server.application.route("/api/v2/posts/likes/<int:postid>/", methods=['GET'])
def count_postlike(postid):
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM postlikes WHERE postid = %(postid)s",
        {
            'postid': postid
        }
    )
    likes_count = cursor.fetchone()['COUNT(*)']
    return flask.jsonify({'likesCount': likes_count}), 200