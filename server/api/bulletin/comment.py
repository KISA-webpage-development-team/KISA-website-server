import flask
import server
from ..helpers import delete_child_comments, get_child_comments, token_required


# COMMENTS API ------------------------------------------------------------
# /api/v2/bulletin/comments
@server.application.route("/api/v2/comments/<int:postid>/", methods=["POST"])
@token_required
def post_comment(postid):
    cursor = server.model.Cursor()
    # Assuming the incoming data is in JSON format
    data = flask.request.get_json()

    # Extract relevant information from the JSON data
    email = data.get("email")
    fullname = data.get("fullname")
    text = data.get("text")
    isCommentOfComment = data.get("isCommentOfComment")
    parentCommentid = data.get("parentCommentid")
    anonymous = data.get("anonymous")
    secret = data.get("secret")

    # Perform validation on the input data
    if not email or not fullname or not text:
        return flask.jsonify({"error": "Missing required fields"}), 400

    # Perform the actual logic of posting a comment (insert into the database)
    cursor.execute(
        "INSERT INTO comments (email, postid, text, isCommentOfComment, parentCommentid, anonymous, secret) "
        "VALUES (%(email)s, %(postid)s, %(text)s, %(isCommentOfComment)s, %(parentCommentid)s, %(anonymous)s, %(secret)s) ",
        {
            "email": email,
            "postid": postid,
            "text": text,
            "isCommentOfComment": isCommentOfComment,
            "parentCommentid": parentCommentid,
            "anonymous": anonymous,
            "secret": secret,
        },
    )

    # Return a JSON response indicating success
    return flask.jsonify({"message": "Comment posted successfully"}), 201


@server.application.route("/api/v2/comments/<int:commentid>/", methods=["PUT"])
@token_required
def update_comment(commentid):
    cursor = server.model.Cursor()
    # Assuming the new comment data is sent in the request body as JSON
    data = flask.request.get_json()

    # Placeholder validation: Check if required fields are present
    if not data or "text" not in data:
        return flask.jsonify({"error": "Missing required fields"}), 400

    cursor.execute(
        """
            UPDATE comments
            SET text = %(text)s
            WHERE commentid = %(commentid)s
        """,
        {"text": data["text"], "commentid": commentid},
    )

    # Update the comment with the new data (replace this with your actual update logic)
    updated_comment_data = {
        "commentid": commentid,
        "text": data["text"],
    }

    # Return a JSON response indicating success
    return flask.jsonify(updated_comment_data)


@server.application.route("/api/v2/comments/<int:commentid>/", methods=["DELETE"])
@token_required
def delete_comment(commentid):
    cursor = server.model.Cursor()
    # Check if the comment with the specified commentid exists
    cursor.execute(
        "SELECT * FROM comments WHERE commentid = %(commentid)s",
        {"commentid": commentid},
    )
    existing_comment = cursor.fetchone()

    if not existing_comment:
        # Return an error message if the comment doesn't exist
        return flask.jsonify({"error": "Comment not found"}), 404
    else:
        # Delete the comment from the database
        delete_child_comments(existing_comment, cursor)

        # Return a success message
        return flask.jsonify(
            {"message": f"Comment with ID {commentid} deleted successfully"}
        ), 204


@server.application.route("/api/v2/comments/<int:postid>/", methods=["GET"])
def get_comments(postid):
    cursor = server.model.Cursor()

    # Fetch comments of depth 1 as list (not comment of comment)
    cursor.execute(
        "SELECT * FROM comments WHERE postid = %(postid)s "
        "AND isCommentOfComment = %(isCommentOfComment)s",
        {"postid": postid, "isCommentOfComment": False},
    )
    comments = cursor.fetchall()

    # Return empty list if there is no comments
    if not comments:
        return flask.jsonify([])

    # Convert SQL row object to a dictionary for JSON serialization
    comments = [dict(comment) for comment in comments]

    # Iterate through post comments
    for comment_depth1 in comments:
        get_child_comments(comment_depth1, cursor)

    return flask.jsonify(comments)

@server.application.route("/api/v2/comments/likes/<int:commentid>/", methods=['GET'])
def count_commentlike(commentid):
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM commentlikes WHERE commentid = %(commentid)s",
        {
            'commentid': commentid
        }
    )
    likes_count = cursor.fetchone()['COUNT(*)']
    return flask.jsonify({'likesCount': likes_count}), 200