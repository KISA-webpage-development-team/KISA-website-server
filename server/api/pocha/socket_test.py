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

@server.application.route('/api/v2/pocha/socket-test/', methods=['GET'])
def socket_test():
    email = ""
    socketio.emit(f'order-created-{email}', {'newOrderItems': [
        {"orderItemID": 10, "status": "pending", "menu": { 
            "menuID": 22,
            "nameKor": "김치전",
            "nameEng": "Kimchi Pancake",
            "price": 15,
            "stock": 999,
            "isImmediatePrep": False,
            "parentPochaId":1,
            "ageCheckRequired": False,
        }, "quantity": 1},
    ]})
    return jsonify({'message': 'test emitted'})
