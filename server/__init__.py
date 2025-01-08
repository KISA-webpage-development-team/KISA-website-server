"""KISA package initializer."""

import flask
from flask_cors import CORS
from flask_mysqldb import MySQL
from flask_socketio import SocketIO


# index page texts
header_text = '''
    <html>\n<head> <title>KISAWEB server API</title> </head>\n<body>'''
footer_text = '</body>\n</html>'

# instructions for the API goes here
instructions = '''
    <p>This is the production API server for the KISA website.
    Instructions are to be implemented. Still in development.</p>\n
    '''

# EB looks for an 'application' callable by default.
application = flask.Flask(__name__)

application.config.from_object('server.config')
db = MySQL(application)
CORS(application, origins=[
    "https://kisa-website-client-git-dev-umich-kisas-projects.vercel.app/",
    "https://www.umichkisa.com",
    "http://localhost:3000",
    "http://localhost:80",
    "http://localhost",
    ])

sio = SocketIO(application, cors_allowed_origins=[
    "https://kisa-website-client-git-dev-umich-kisas-projects.vercel.app/",
    "https://www.umichkisa.com",
    "http://localhost:3000",
    "http://localhost:80",
    "http://localhost",
    ])

# add a rule for the index page.
application.add_url_rule('/', 'index', (lambda: header_text +
    instructions + footer_text))





import server.api
import server.model





