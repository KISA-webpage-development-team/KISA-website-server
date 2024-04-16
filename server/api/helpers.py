import flask
import jwt

def token_required(func):
    def token_test(*args, **kwargs):
        token = flask.request.headers.get('Authorization')
        if not token:
            return flask.jsonify({'message': 'Missing token'}), 401
        with open('secret_key.txt', 'r') as file:
            secret_key = file.read()
            try:
                token = token.split(' ')[1]
                decode_message = jwt.decode(token, secret_key, algorithms=['HS256'])
                print(decode_message)
                func(*args, **kwargs)
            except:
                return flask.jsonify({'message': 'Decode failed'}), 401
    return token_test