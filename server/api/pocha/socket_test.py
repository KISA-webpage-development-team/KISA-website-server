from flask import Flask, request, jsonify
from flask_socketio import SocketIO, send, emit
import server 
from server import application

socketio = SocketIO(application, cors_allowed_origins=[
    "https://www.umichkisa.com",
    "http://localhost:3000",
    "http://localhost:80",
    "http://localhost",
    ])

print("wtf")


@socketio.on('connect')
def connect():
    email = request.args.get('email')
    print(f"Client connected with email: {email}")

@socketio.on('disconnect')
def disconnect():
    print("Client disconnected")

if __name__ == "__main__":
    socketio.run(application, port=8000)
