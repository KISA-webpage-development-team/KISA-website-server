import flask
import server
from .helpers import token_required, boardTag, count_comments
from .image_handler import handle_imgs, delete_imgs

# POSTS API ------------------------------------------------------------
# /api/v1/posts

# @desc    Get specific post using postid
# @route   GET /api/v1/posts/<int:postid>/
# @params  {path} int:postid
# TEST: "http://localhost:8000/api/v1/posts/1/"
@server.application.route("/api/v1/posts/<int:postid>/",
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
    
    count_comments(cursor, post)

    # render context
    context = post
    return flask.jsonify(**context)

@server.application.route("/api/v1/posts/", methods=['POST'])
@token_required
def add_post():
    # Fetch body from request
    body = flask.request.get_json()

    # Fetch next postid by inserting a dummy post
    cursor = server.model.Cursor()
    cursor.execute(
        "INSERT INTO posts (email) VALUES (%(email)s)",
        {"email": body["email"]}
    )
    next_postid = cursor.lastrowid()

    # Handle image upload
    handle_imgs(body, next_postid)

    # Incoming post is from announcement board
    if body['type'] == 'announcement':
        # Error Handling
        if body['isAnnouncement']:
            return flask.jsonify({'error': 'Bad request: Announcement post cannot be an announcement itself'}), 400
        if 'tag' not in body:
            return flask.jsonify({'error': 'Bad request: Announcement post missing tag field'}), 400
        
        # Tag is empty -> custom tagged announcement post
        if not body['tag']:
            # remove 'tag' key from body
            del body['tag']

            # create "parent" post in announcement board
            fields = ", ".join(map(lambda x: f"{x} = %({x})s", body.keys()))
            cursor.execute(
                "UPDATE posts "
                f"SET {fields} "
                "WHERE postid = %(postid)s",
                {
                    **body,
                    'postid': next_postid
                }
            )

            return flask.jsonify({'message': 'post created successfully'}), 201

        # boardtype is announcement + tag is unempty =
        # tagged announcement post
        # 2 different posts are generated
        else:
            # save tag
            orig_type = body['type']
            tag = body['tag']
            del body['tag']

            # create "parent" post in announcement board
            fields = ", ".join(map(lambda x: f"{x} = %({x})s", body.keys()))
            cursor.execute(
                "UPDATE posts "
                f"SET {fields} "
                "WHERE postid = %(postid)s",
                {
                    **body,
                    'postid': next_postid
                }
            )

            # create "child" post in general board
            body['type'] = tag
            body['isAnnouncement'] = True
            body['title'] = "]".join(body['title'].split(']')[1::]).strip()
            
            fields = ", ".join(body.keys())
            fields_format = ", ".join(map(lambda x: "%(" + x + ")s", body.keys()))
            cursor.execute(
                "INSERT INTO posts (" +
                fields + ") VALUES (" +
                fields_format + ") ",
                body
            )

            return flask.jsonify({'message': f'{orig_type} and {tag} posts created successfully'}), 201
        
    # Incoming post is from general boards
    else:
        # tag field from body is unncessary, delete
        del body['tag']
        
        # create "parent" post in announcement board
        fields = ", ".join(map(lambda x: f"{x} = %({x})s", body.keys()))
        cursor.execute(
            "UPDATE posts "
            f"SET {fields} "
            "WHERE postid = %(postid)s",
            {
                **body,
                'postid': next_postid
            }
        )

        return flask.jsonify({'message': 'post created successfully'}), 201

# @desc    Update post with new text
# @route   PUT /api/v1/posts/<int:postid>
@server.application.route("/api/v1/posts/<int:postid>/", methods=['PATCH'])
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

    # Handle image upload
    handle_imgs(body, postid, prev_post['text'])

    # post to be updated is from announcement board
    if prev_post['type'] == 'announcement':
        prev_announcement_post = prev_post
        new_tag_raw = body['title'].split(']')[0][1::]
        prev_tag_raw = body['title'].split(']')[1][2::]
        new_title = body['title'].split(']')[2][1::]

        # handle error: announcement post cannot be an announcement itself
        if body['isAnnouncement']:
            return flask.jsonify({'error': 'Bad request: Announcement post cannot be an announcement itself'}), 400

        # Case 1: prev_tag_raw is custom: post only exists in announcement
        if prev_tag_raw not in boardTag:
            # Case 1-1: new_tag_raw is custom
            # 1) UPDATE post in announcement
            if new_tag_raw not in boardTag:
                cursor.execute(
                    "UPDATE posts "
                    "SET "
                    "title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
                    "WHERE postid = %(postid)s",
                    {
                        'title': f'[{new_tag_raw}] {new_title}',
                        'text': body['text'],
                        'isAnnouncement': body['isAnnouncement'],
                        'postid': prev_announcement_post['postid']
                    }
                )
                
                return flask.jsonify({'message': 'post in announcement board updated'}), 200

            # Case 1-2: new_tag_raw is not custom
            # 1) UPDATE post in announcement
            # 2) INSERT post into boardTag[new_tag_raw]
            else:
                # 1) UPDATE post in announcement
                cursor.execute(
                    "UPDATE posts "
                    "SET "
                    "title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
                    "WHERE postid = %(postid)s",
                    {
                        'title': f'[{new_tag_raw}] {new_title}',
                        'text': body['text'],
                        'isAnnouncement': body['isAnnouncement'],
                        'postid': prev_announcement_post['postid'],
                    }
                )

                # 2) INSERT post into boardTag[new_tag_raw]

                # modify prev_announcement_post to use as placeholder
                # fullname and email is unchanged
                new_post_data = prev_announcement_post
                new_post_data['type'] = boardTag[new_tag_raw]
                new_post_data['title'] = f'{new_title}'
                new_post_data['text'] = body['text']
                new_post_data['isAnnouncement'] = True

                # delete postid field to evade duplicate postid, which is a primary key
                del new_post_data['postid']

                # fetch all fields required to insert new post
                fields = ", ".join(new_post_data.keys())
                fields_format = ", ".join(map(lambda x: "%(" + x + ")s", new_post_data.keys()))

                cursor.execute(
                    "INSERT INTO posts (" +
                    fields + ") VALUES (" +
                    fields_format + ") ",
                    new_post_data
                )
                
                return flask.jsonify(
                    {
                        'message':'post in announcement updated, post inserted into general board'
                    }
                ), 200

        # Case 2: prev_tag_raw is not custom: post exists in announcement AND
        #         boardTag[prev_tag_raw] board
        else:
            # compose title and type of matching post in general boards
            general_title = prev_announcement_post['title'].split(']')[1][1::]

            # Case 2-1: new_tag_raw is custom
            # 1) UPDATE post in announcement
            # 2) DELETE post in boardTag[prev_tag_raw]
            if new_tag_raw not in boardTag:
                # 1) UPDATE post in announcement
                cursor.execute(
                    "UPDATE posts "
                    "SET "
                    "title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
                    "WHERE postid = %(postid)s",
                    {
                        'title': f'[{new_tag_raw}] {new_title}',
                        'text': body['text'],
                        'isAnnouncement': body['isAnnouncement'],
                        'postid': prev_announcement_post['postid'],
                    }
                )

                # 2) DELETE post in boardTag[prev_tag_raw]
                # NOTE: mysql does not throw an exception when a non-existent
                #       row is deleted. To handle this case, we can either explicitly
                #       throw an exception when this happens. However, at the point
                #       this api is written, I think not handling this case at all
                #       makes more sense.

                cursor.execute(
                    "DELETE FROM posts WHERE "
                    "title = %(general_title)s "
                    "AND type = %(general_type)s "
                    "AND isAnnouncement = %(isAnnouncement)s",
                    {
                        'general_title': general_title,
                        'general_type': boardTag[prev_tag_raw],
                        'isAnnouncement': True
                    }
                )
                
                return flask.jsonify(
                    {
                        'message':'post in announcement updated, post deleted from general board'
                    }
                ), 200
            
            # Case 2-2: new_tag_raw is not custom
            # 1) UPDATE post in announcement
            # 2) UPDATE post in boardTag[prev_tag_raw]
            else:
                cursor.execute(
                    "UPDATE posts "
                    "SET "
                    "title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
                    "WHERE postid = %(postid)s",
                    {
                        'title': f'[{new_tag_raw}] {new_title}',
                        'text': body['text'],
                        'isAnnouncement': body['isAnnouncement'],
                        'postid': prev_announcement_post['postid'],
                    }
                )

                # 2) UPDATE post in boardTag[prev_tag_raw]
                cursor.execute(
                    "UPDATE posts "
                    "SET "
                    "type = %(type)s, title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
                    "WHERE title = %(general_title)s"
                    "AND type = %(general_type)s"
                    "AND isAnnouncement = %(general_isAnnouncement)s",
                    {
                        'type': boardTag[new_tag_raw],
                        'title': f'{new_title}',
                        'text': body['text'],
                        'isAnnouncement': True,
                        'general_title': general_title,
                        'general_type': boardTag[prev_tag_raw],
                        'general_isAnnouncement': True,
                    }
                )
                
                return flask.jsonify(
                    {
                        'message':'post in announcement updated, post in general board updated'
                    }
                ), 200

    # post to be updated is from general board
    else:
        cursor.execute(
            "UPDATE posts "
            "SET title = %(title)s, text = %(text)s, isAnnouncement = %(isAnnouncement)s "
            "WHERE postid = %(postid)s ", 
            {
                'title': body['title'],
                'text': body['text'],
                'isAnnouncement': body['isAnnouncement'],
                'postid': postid
            }
        )
        
        return flask.jsonify({'message': 'post in general board updated successfully'}), 200

# @desc    Delete post
# @route   DELETE /api/v1/posts/{postid}
# @params  {path} int:postid
@server.application.route("/api/v1/posts/<int:postid>/", methods=['DELETE'])
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

# @desc    Increment readCount
# @route   PATCH /api/v1/posts/readCount/<int:postid>/
# @params  {path} int:postid
@server.application.route("/api/v1/posts/readCount/<int:postid>/", methods=['PATCH'])
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