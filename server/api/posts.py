import flask
import server

# POSTS API ------------------------------------------------------------
# /api/v1/posts

# @desc    Get specific post using postid
# @route   GET /api/v1/posts/<int:postid>/
# @params  {path} int:postid
# TEST: "http://localhost:8000/api/v1/posts/1/"
@server.application.route("/api/v1/posts/<int:postid>/",
                  methods=['GET'])
def get_post(postid):
    cursor = server.model.cursor()

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

    # render context
    context = {
        'postid': postid,
        'type': post['type'],
        'title': post['title'],
        'fullname': post['fullname'],
        'email': post['email'],
        'text': post['text'],
        'readCount': post['readCount'],
        'isAnnouncement': post['isAnnouncement'],
        'created' : post['created']
    }
    return flask.jsonify(**context)
    
# @desc    Create a New Post with Board_type
# @route   POST /api/v1/posts
# @params  {body} {"type", "title", "fullname", "email", "text", "isAnnouncement"}
@server.application.route("/api/v1/posts/", methods=['POST'])
def add_post():
    # Fetch body from request
    body = flask.request.get_json()

    # Incoming post is from announcement board
    if body['type'] == 'announcement':
        # Error Handling
        # announcement posts cannot be an announcement
        if body['isAnnouncement']:
            return flask.jsonify({'error': 'Bad request: Announcement post cannot be an announcement itself'}), 400
        
        # announcement post missing tag field
        if 'tag' not in body:
            return flask.jsonify({'error': 'Bad request: Announcement post missing tag field'}), 400
        
        # fetch tag and see if the tag is custom or not
        # if custom, only one post of type 'announcement' is inserted to db
        if body['tag'] == 'custom':
            cursor = server.model.cursor()

            # remove 'tag' key from body
            del body['tag']
            
            fields = ", ".join(body.keys())
            fields_format = ", ".join(map(lambda x: "%(" + x + ")s", body.keys()))
            cursor.execute(
                "INSERT INTO posts (" +
                fields + ") VALUES (" +
                fields_format + ") ",
                body
            )
            server.model.commit_close(cursor)

            return flask.jsonify({'message': f'{body['type']} post created successfully'}), 201

        # if else, two posts of type 'announcement' and type of tag is inserted to db
        else:
            cursor = server.model.cursor()

            # save tag
            orig_type = body['type']
            tag = body['tag']
            del body['tag']

            fields = ", ".join(body.keys())
            fields_format = ", ".join(map(lambda x: "%(" + x + ")s", body.keys()))
            cursor.execute(
                "INSERT INTO posts (" +
                fields + ") VALUES (" +
                fields_format + ") ",
                body
            )

            # change type to saved tag and set as announcement
            body['type'] = tag
            body['isAnnouncement'] = True
            body['title'] = body['title'].split(']')[1].strip()
            
            cursor.execute(
                "INSERT INTO posts (" +
                fields + ") VALUES (" +
                fields_format + ") ",
                body
            )
            server.model.commit_close(cursor)

            return flask.jsonify({'message': f'{orig_type} and {tag} posts created successfully'}), 201
        
    # Incoming post is from general boards
    else:
        cursor = server.model.cursor()
        
        fields = ", ".join(body.keys())
        fields_format = ", ".join(map(lambda x: "%(" + x + ")s", body.keys()))
        cursor.execute(
            "INSERT INTO posts (" +
            fields + ") VALUES (" +
            fields_format + ") ",
            body
        )
        server.model.commit_close(cursor)

        return flask.jsonify({'message': f'{body['type']} post created successfully'}), 201

# @desc    Update post with new text
# @route   PUT /api/v1/posts/<int:postid>
# @argv    {"title", "text", "isAnnouncement"}
@server.application.route("/api/v1/posts/<int:postid>/", methods=['PATCH'])
def update_post(postid):
    cursor = server.model.cursor()
    # Assuming the new post data is sent in the request body as JSON
    data = flask.request.get_json()
    print(data)

    # Placeholder validation: Check if required fields are present
    if not data or 'text' not in data or 'title' not in data or 'isAnnouncement' not in data:
        return flask.jsonify({'error': 'Missing required fields'}), 400
    
    cursor.execute(
        "UPDATE posts "
        "SET text = %(text)s, title = %(title)s, isAnnouncement = %(isAnnouncement)s "
        "WHERE postid = %(postid)s ", 
        {
            'text': data.get('text'),
            'title': data.get('title'),
            'isAnnouncement': data.get('isAnnouncement'),
            'postid': postid
        }
    )

    server.model.commit_close(cursor)

    # Return a JSON response indicating success
    return flask.jsonify({'message': 'Post updated successfully'}), 200

# @desc    Delete post
# @route   DELETE /api/v1/posts/{postid}
# @params  {path} int:postid
@server.application.route("/api/v1/posts/<int:postid>/", methods=['DELETE'])
def delete_post(postid):
    cursor = server.model.cursor()
    # Check if the post with the specified postid exists

    cursor.execute(
        'SELECT * FROM posts WHERE postid = %(postid)s',
        {
            'postid': postid
        }
    )
    existing_post = cursor.fetchone()

    if existing_post:
        # Delete the post from the database
        cursor.execute(
            'DELETE FROM posts WHERE postid = %(postid)s',
            {
                'postid': postid
            }
        )
        server.model.commit_close(cursor)

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
    cursor = server.model.cursor()
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
        server.model.commit_close(cursor)

        # Return a success message
        return flask.jsonify({'message': f'Post {postid} readCount is now {cur_readCount + 1}'}), 200
    else:
        # Return an error message if the post doesn't exist
        return flask.jsonify({'error': 'Post not found'}), 404