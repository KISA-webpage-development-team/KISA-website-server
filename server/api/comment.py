import flask
import server


# COMMENTS API ------------------------------------------------------------
# /api/v1/comments

# @desc    Create new comment
# @route   GET /api/v1/comments
# @argv    {"fullname", "postid", "text"}
# TEST:  curl -X POST -H "Content-Type: application/json" -d 
# '{"fullname": "ajys", "postid":"0", "text":"I love KISA"}' http://localhost:8000/api/post/comments
@server.application.route("/api/v1/comments/<int:postid>/", methods=['POST'])
def post_comment(postid):
    db = server.model.get_db()
    cursor = db.cursor()
    # Assuming the incoming data is in JSON format
    data = flask.request.get_json()

    # Extract relevant information from the JSON data
    email = data.get('email')
    fullname = data.get('fullname')
    text = data.get('text')
    isCommentOfComment = data.get('isCommentOfComment')
    parentCommentid = data.get('parentCommentid')

    # Perform validation on the input data
    if not email or not fullname or not text:
        return flask.jsonify({'error': 'Missing required fields'}), 400

    # Perform the actual logic of posting a comment (insert into the database)
    cursor.execute(
        "INSERT INTO comments (email, postid, text, isCommentOfComment, parentCommentid) "
        "VALUES (?, ?, ?, ?, ?) ", 
        (email, postid, text, isCommentOfComment, parentCommentid)
    )

    db.commit()

    # Return a JSON response indicating success
    return flask.jsonify({'message': 'Comment posted successfully'}), 201

# @desc    Update comment with new text
# @route   PUT /api/v1/comments/{commentid}
# @argv    {"commentid", "text"} ???  [NEED TO REVIEW IT AGAIN]
@server.application.route("/api/v1/comments/<int:commentid>/", methods=['PUT'])
def update_comment(commentid):
    db = server.model.get_db()
    cursor = db.cursor()
    # Assuming the new comment data is sent in the request body as JSON
    data = flask.request.get_json()

    # Placeholder validation: Check if required fields are present
    if not data or 'text' not in data:
        return flask.jsonify({'error': 'Missing required fields'}), 400
    
    cursor.execute('''
            UPDATE comments
            SET text = ?
            WHERE commentid = ?
        ''', (data['text'], commentid))

    db.commit()

    # Update the comment with the new data (replace this with your actual update logic)
    updated_comment_data = {
        'commentid': commentid,
        'text': data['text'],
    }

    # Return a JSON response indicating success
    return flask.jsonify(updated_comment_data)

def delete_child_comments(comment, cursor, db):
    # search for any child comments of this comment
    cursor.execute(
        "SELECT * FROM comments WHERE parentCommentid = ?",
        (comment['commentid'],)
    )
    childComments = cursor.fetchall()

    # recursively delete child comments
    for childComment in childComments:
        delete_child_comments(childComment, cursor, db)

    # delete comment itself
    cursor.execute(
        'DELETE FROM comments WHERE commentid = ?',
        (comment['commentid'],)
    )
    db.commit()


# @desc    Delete comment
# @route   DELETE /api/v1/comments/{commentid}
# @argv    int:commentid
# TEST: curl -X DELETE http://localhost:8000/api/post/comments/1/
@server.application.route("/api/v1/comments/<int:commentid>/", methods=['DELETE'])
def delete_comment(commentid):
    db = server.model.get_db()
    cursor = db.cursor()
    # Check if the comment with the specified commentid exists
    cursor.execute('SELECT * FROM comments WHERE commentid = ?', (commentid,))
    existing_comment = cursor.fetchone()

    if not existing_comment:
        # Return an error message if the comment doesn't exist
        return flask.jsonify({'error': 'Comment not found'}), 404
    else:
        # Delete the comment from the database
        delete_child_comments(existing_comment, cursor, db)

        # Return a success message
        return flask.jsonify({'message': f'Comment with ID {commentid} deleted successfully'}), 204
    

def add_child_comments(comment, cursor):
    # Set fullname according to email of the commenter
    cursor.execute(
        "SELECT fullname FROM users WHERE email = ?",
        (comment['email'],)
    )
    fullname = cursor.fetchone()
    comment['fullname'] = fullname['fullname']

    # check for base case (if child comments does not exist)
    cursor.execute(
        "SELECT * FROM comments WHERE postid = ?"
        "AND isCommentOfComment = ? AND parentCommentid = ?",
        (comment['postid'], True, comment['commentid'],)
    )
    child_comments = cursor.fetchall()

    # base case
    if not child_comments:
        comment['childComments'] = []
    
    # recursive case
    else:
        comment['childComments'] = [dict(child_comment) for child_comment in child_comments]
        for child_comment in comment['childComments']:
            add_child_comments(child_comment, cursor)

    
# @desc   Get all comments of specified post
# @route  GET /api/v1/comments/{postid}
# @argv   int:postid
# TEST: http "http://localhost:8000/api/v1/comments/1/"
@server.application.route("/api/v1/comments/<int:postid>/", methods=['GET'])
def get_comments(postid):
    db = server.model.get_db()
    cursor = db.cursor()

    # Fetch comments of depth 1 as list (not comment of comment)
    cursor.execute(
        "SELECT * FROM comments WHERE postid = ?"
        "AND isCommentOfComment = ?",
        (postid, False,)
    )
    comments = cursor.fetchall()

    # Return empty list if there is no comments
    if not comments:
        return flask.jsonify([])
    
    # Convert SQLite Row object to a dictionary for JSON serialization
    comments = [dict(comment) for comment in comments]
    
    # Iterate through post comments
    for comment_depth1 in comments:
        add_child_comments(comment_depth1, cursor)
    
    return flask.jsonify(comments)
