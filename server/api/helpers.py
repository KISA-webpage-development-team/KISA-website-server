import flask
import jwt
import server
import os
import re
from functools import wraps
from urllib.parse import unquote

def token_required(func):
    @wraps(func)
    def token_test(*args, **kwargs):
        token = flask.request.headers.get('Authorization')
        if not token:
            return flask.jsonify({'message': 'Missing token'}), 401
        secret_key = os.getenv("SECRET_KEY")
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

    # Fetch posts associated with the given email
    cursor.execute(
        '''
            SELECT postid, title, created, fullname, type, readCount, isAnnouncement 
            FROM posts 
            WHERE email = %(email)s AND anonymous = %(anonymous)s
        ''',
        {
            'email': email,
            'anonymous': False
        }
    )
    user_posts = cursor.fetchall()[::-1]

    # Add commentsCount to each post
    for post in user_posts:
        count_comments(cursor, post)

    return user_posts

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

def get_child_comments(comment, cursor):
    # Before adding child comments, count likes for each comment
    count_likes(cursor, "comment", comment)

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