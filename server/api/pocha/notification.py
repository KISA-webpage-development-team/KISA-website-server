import flask
import server
import json

# POCHA APIS -----------------------------------------------------------
# /api/v2/pocha/notification

@server.application.route('/api/v2/pocha/notification/register-token/', methods=['POST'])
# @token_required
def register_token():
    '''
    Register FCM token for inputted user from log in session
    Also used to update FCM token for the user
    '''
    # fetch body content
    body = flask.request.get_json()
    token = body['token']
    email = body['email']

    # error checking: check if user has signed up
    cursor = server.model.Cursor()
    cursor.execute(
        '''
        SELECT email FROM users
        WHERE email = %(email)s
        ''',
        {
            'email': email
        }
    )
    user_signed_up = cursor.fetchone()
    if not user_signed_up:
        return flask.jsonify(
            {
                'error': f"Requested email '{email}' is not signed up.",
            }, 404
        )

    # check if user in body already has token
    cursor.execute(
        '''
        SELECT email FROM notificationARNs
        WHERE email = %(email)s
        ''',
        {
            'email': email
        }
    )
    user_exists = cursor.fetchone()

    # first, create endpoint for the user
    # even if user exists, create_endpoint is idempotent
    client = server.model.AWSClient()
    endpoint_arn = client.create_endpoint(token, email)['EndpointArn']

    # if user does not exist, register new token for the user
    if not user_exists:

        # then save endpoint arn to database, associating it with email
        cursor.execute(
            '''
            INSERT INTO notificationARNs (email, endpointARN)
            VALUES (%(email)s, %(endpoint_arn)s)
            ''',
            {
                'email': email,
                'endpoint_arn': endpoint_arn
            }
        )
        return flask.jsonify(
            {
                'message': f"SNS endpoint successfully registered for {email}.",
            }, 200
        )
    
    # if user exists, update the token for the user
    else:
        cursor.execute(
            '''
            UPDATE notificationARNs
            SET endpointARN = %(endpoint_arn)s
            WHERE email = %(email)s
            ''',
            {
                'email': email,
                'endpoint_arn': endpoint_arn
            }
        )
        return flask.jsonify(
            {
                'message': f"SNS endpoint successfully updated for {email}.",
            }, 200
        )
    
# @server.application.route('/api/v2/pocha/notification/test/', methods=['POST'])
# @token_required
def send_notification(**kwargs):
    """
    :param kwargs: email, subject, title, body, silent, data
    """
    cursor = server.model.Cursor()
    cursor.execute(
        '''
        SELECT endpointARN FROM notificationARNs
        WHERE email = %(email)s
        ''',
        {
            'email': kwargs['email']
        }
    )
    endpoint_arn = cursor.fetchone()['endpointARN']

    client = server.model.AWSClient()
    client.send_notification(
        endpoint_arn,
        subject=kwargs['subject'],
        title=kwargs.get('title'), # only for push notifications
        body=kwargs.get('body'), # only for silent notifications
        silent=kwargs.get('silent'), # denotes if the notification is silent
        data=kwargs.get('data') # only for silent notifications
    )

    return flask.jsonify({'message': 'Test notification sent successfully.'}, 200)