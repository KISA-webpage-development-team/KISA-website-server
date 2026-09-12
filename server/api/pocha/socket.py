"""Socket.IO connection handling for pocha order events.

Every connected client lands in its own per-user room, and admins additionally
join the dashboard room for the pocha they opened. Emits target those rooms, so
an order event reaches the person it belongs to and the staff dashboard, and
nobody else.
"""
import os

import flask
import jwt
import server
from flask_socketio import join_room


def user_room(email):
    return f"user:{email}"


def dashboard_room(pochaID):
    return f"dashboard:{pochaID}"


def _email_from_token(token):
    secret_key = os.getenv("SECRET_KEY")
    if not token or not secret_key:
        return None
    try:
        claims = jwt.decode(token, secret_key, algorithms='HS256')
    except Exception:
        return None
    return claims.get('email') or claims.get('id') or claims.get('sub')


def is_admin(email):
    cursor = server.model.Cursor()
    cursor.execute(
        "SELECT email FROM admins WHERE email = %(email)s",
        {
            'email': email
        }
    )
    return cursor.fetchone() is not None


@server.sio.on('connect')
def on_connect(auth):
    # Identity comes from the signed token, never from the query string. The
    # client also sends its email as a query parameter, and trusting that would
    # let anyone subscribe to anyone else's orders.
    email = _email_from_token((auth or {}).get('token'))
    if not email:
        return False

    join_room(user_room(email))

    pochaID = flask.request.args.get('pochaId', type=int)
    if pochaID is not None and is_admin(email):
        join_room(dashboard_room(pochaID))
