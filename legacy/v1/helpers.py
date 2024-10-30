import flask
import jwt
import server
from functools import wraps

boardTag = {
    '자유게시판': 'community',
    '학업/취업': 'academic-job',
    '사고팔기': 'buyandsell',
    '하우징/룸메이트': 'housing'
}

def token_required(func):
    @wraps(func)
    def token_test(*args, **kwargs):
        token = flask.request.headers.get('Authorization')
        if not token:
            return flask.jsonify({'message': 'Missing token'}), 401
        with open('secret_key.txt', 'r') as file:
            secret_key = file.read()
            try:
                token = token.split(' ')[1]
                jwt.decode(token, secret_key, algorithms='HS256')
                return func(*args, **kwargs)
            except Exception as error:
                print(error)
                return flask.jsonify({'error': 'Decode failed'}), 401
    return token_test

def count_comments(cursor, post):
    cursor.execute(
        "SELECT COUNT(*) "
        "FROM comments "
        "WHERE postid = %(comment_postid)s",
        {
            'comment_postid': post["postid"]
        }
    )
    comments_count = cursor.fetchone()["COUNT(*)"]
    post["commentsCount"] = comments_count

def fetch_user_posts(email):
    cursor = server.model.Cursor()

    # Fetch posts associated with the given email
    cursor.execute(
        'SELECT * FROM posts WHERE email = %(email)s',
        {
            'email': email
        }
    )
    user_posts = cursor.fetchall()[::-1]

    return user_posts

def fetch_user_comments(email):
    cursor = server.model.Cursor()

    # Fetch comments associated with the given email
    cursor.execute(
        'SELECT * FROM comments WHERE email = %(email)s',
        {
            'email': email
        }
    )
    user_comments = cursor.fetchall()[::-1]

    return user_comments

def delete_child_comments(comment, cursor):
    # search for any child comments of this comment
    cursor.execute(
        "SELECT * FROM comments WHERE parentCommentid = %(parentCommentid)s",
        {
            'parentCommentid': comment['commentid']
        }
    )
    childComments = cursor.fetchall()

    # recursively delete child comments
    for childComment in childComments:
        delete_child_comments(childComment, cursor)

    # delete comment itself
    cursor.execute(
        'DELETE FROM comments WHERE commentid = %(commentid)s',
        {
            'commentid': comment['commentid']
        }
    )

def get_child_comments(comment, cursor):
    # Set fullname according to email of the commenter
    cursor.execute(
        "SELECT fullname FROM users WHERE email = %(email)s",
        {
            'email': comment['email']
        }
    )
    fullname = cursor.fetchone()
    comment['fullname'] = fullname['fullname']

    # check for base case (if child comments does not exist)
    cursor.execute(
        "SELECT * FROM comments WHERE postid = %(postid)s "
        "AND isCommentOfComment = %(isCommentOfComment)s "
        "AND parentCommentid = %(parentCommentid)s",
        {
            'postid': comment['postid'],
            'isCommentOfComment': True,
            'parentCommentid': comment['commentid']
        }
    )
    child_comments = cursor.fetchall()

    # base case
    if not child_comments:
        comment['childComments'] = []
    
    # recursive case
    else:
        comment['childComments'] = [dict(child_comment) for child_comment in child_comments]
        for child_comment in comment['childComments']:
            get_child_comments(child_comment, cursor)