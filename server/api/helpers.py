import flask
import jwt
import server
import os
import re
from functools import wraps
from urllib.parse import unquote

def _authenticated_email():
    """Return (email, None) for a valid bearer token, or (None, error response)."""
    token = flask.request.headers.get('Authorization')
    if not token:
        return None, (flask.jsonify({'message': 'Missing token'}), 401)
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        return None, (flask.jsonify({'error': 'Server auth is not configured'}), 500)
    try:
        token = token.split(' ')[1]
        claims = jwt.decode(token, secret_key, algorithms='HS256')
    except Exception as error:
        print(error)
        return None, (flask.jsonify({'error': 'Decode failed'}), 401)
    auth_email = claims.get('email') or claims.get('id') or claims.get('sub')
    if not auth_email:
        return None, (flask.jsonify({'error': 'Token missing user identity'}), 401)
    return auth_email, None

def token_required(func):
    """Require a valid token whose user is the email in the path."""
    @wraps(func)
    def token_test(*args, **kwargs):
        auth_email, error = _authenticated_email()
        if error:
            return error
        flask.g.auth_email = auth_email
        requested_email = kwargs.get('email')
        if requested_email and unquote(requested_email) != auth_email:
            return flask.jsonify({'error': 'Token user does not match requested user'}), 403
        return func(*args, **kwargs)
    return token_test

def login_required(func):
    """Require a valid token for any member; the path email need not be theirs.

    The member directory lets a signed-in member view another member's profile,
    posts and comments. Anything that changes a user's data still goes through
    token_required.
    """
    @wraps(func)
    def login_test(*args, **kwargs):
        auth_email, error = _authenticated_email()
        if error:
            return error
        flask.g.auth_email = auth_email
        return func(*args, **kwargs)
    return login_test

def authenticated_email():
    return getattr(flask.g, 'auth_email', None)

def admin_required(func):
    @token_required
    @wraps(func)
    def admin_test(*args, **kwargs):
        cursor = server.model.Cursor()
        cursor.execute(
            "SELECT email FROM admins WHERE email = %(email)s",
            {
                'email': authenticated_email()
            }
        )
        if not cursor.fetchone():
            return flask.jsonify({'error': 'Admin privileges required'}), 403
        return func(*args, **kwargs)
    return admin_test

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

def count_likes(cursor, target, item):
    id = item['postid'] if target == 'post' else item['commentid']
    
    cursor.execute(
        f'''
        SELECT COUNT(*) FROM {target}likes WHERE {target}id = %(id)s
        ''',
        {
            'id': id
        }
    )
    likes_count = cursor.fetchone()['COUNT(*)']
    item['likesCount'] = likes_count

def fetch_user_posts(email):
    cursor = server.model.Cursor()

    # The user's posts, newest first, each with its comment count
    cursor.execute(
        '''
            SELECT postid, title, created, fullname, type, readCount, isAnnouncement,
            (SELECT COUNT(*) FROM comments WHERE comments.postid = posts.postid) AS "commentsCount"
            FROM posts 
            WHERE email = %(email)s AND anonymous = %(anonymous)s
            ORDER BY postid DESC
        ''',
        {
            'email': email,
            'anonymous': False
        }
    )
    return cursor.fetchall()

def fetch_user_comments(email):
    cursor = server.model.Cursor()

    # Fetch comments associated with the given email
    cursor.execute(
        'SELECT * FROM comments WHERE email = %(email)s AND anonymous = %(anonymous)s',
        {
            'email': email,
            'anonymous': False
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

def fetch_comment_tree(cursor, postid):
    """Top-level comments of a post, each carrying its nested childComments.

    Every comment of the post comes back in one query with the commenter's
    name and like count; the tree is assembled here by parentCommentid.
    """
    cursor.execute(
        "SELECT comments.*, users.fullname, "
        "(SELECT COUNT(*) FROM commentlikes WHERE commentlikes.commentid = comments.commentid) AS \"likesCount\" "
        "FROM comments "
        "LEFT JOIN users ON users.email = comments.email "
        "WHERE comments.postid = %(postid)s "
        "ORDER BY comments.commentid",
        {
            'postid': postid
        }
    )
    comments = cursor.fetchall()

    children = {}
    for comment in comments:
        comment['childComments'] = []
        if comment['isCommentOfComment']:
            children.setdefault(comment['parentCommentid'], []).append(comment)
    for comment in comments:
        comment['childComments'] = children.get(comment['commentid'], [])

    return [comment for comment in comments if not comment['isCommentOfComment']]

def check_orderItems_and_delete(cursor, existing_orderID):
    # check if orderItems are left for existing order
    cursor.execute(
        '''
        SELECT * FROM orderItem 
        WHERE parentOrderID=%(parentOrderID)s
        ''',
        {
            'parentOrderID': existing_orderID
        }
    )
    orderItems = cursor.fetchall()

    # if there no longer exists orderItems for a order,
    # delete the order
    if not orderItems:
        cursor.execute(
            '''
            DELETE FROM `order` 
            WHERE orderID=%(orderID)s
            ''',
            {
                'orderID': existing_orderID
            }
        )

def extract_temp_keys(text):
    # Temporary images for the editor starts with s3 URL
    base_url = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.amazonaws.com"

    # Regex pattern to match the full S3 key before any query parameters
    pattern = rf'<img[^>]+src=["\']{re.escape(base_url)}/([^"\']+?)(?:\?[^"\']*)?["\']'
    
    # Find all matches
    matches = re.findall(pattern, text)

    # Decode URL-encoded characters in matches
    matches = [unquote(match) for match in matches]
    
    return matches


def extract_uploaded_keys(text):
    # Images that are already uploaded starts with CloudFront URL
    base_url = os.getenv('CLOUDFRONT_URL')

    # Regex pattern to extract the image key, stopping at query params if any
    pattern = rf'<img[^>]+src=["\']{re.escape(base_url)}/([^"\']+?)(?:\?[^"\']*)?["\']'

    # Find all matches (keys)
    matches = re.findall(pattern, text)

    # Decode URL-encoded characters in matches
    matches = [unquote(match) for match in matches]

    return matches

def replace_temp_srcs(text, new_urls):
    # Temporary object srcs are stored in s3
    base_url = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.amazonaws.com"

    # Regex pattern to match the full `src="..."` value
    pattern = rf'<img[^>]+src=["\']({re.escape(base_url)}/[^"\']+)["\']'

    # Find all existing image src URLs
    matches = re.findall(pattern, text)

    # Replace each matched src with the corresponding new URL
    for old_src, new_src in zip(matches, new_urls):
        text = text.replace(old_src, new_src)

    return text
