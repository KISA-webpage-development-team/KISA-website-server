import flask
import jwt

boardTag = {
    '자유게시판': 'community',
    '학업 정보': 'academics',
    '사고팔기': 'buyandsell',
    '하우징/룸메이트': 'housing'
}

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
                func(*args, **kwargs)
            except:
                return flask.jsonify({'message': 'Decode failed'}), 401
    return token_test