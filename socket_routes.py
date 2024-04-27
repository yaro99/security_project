'''
socket_routes
file containing all the routes related to socket.io
'''

from flask import request, session
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask import copy_current_request_context

try:
    from __main__ import socketio
except ImportError:
    from app import socketio

from models import Room

import db

room = Room()

# when the client connects to a socket
# this event is emitted when the io() function is called in JS


@socketio.on("do_connection")
def do_connection(enctext_connected):
    @copy_current_request_context
    def can_access_session():
        return session.get('user')
    username = can_access_session()
    if not username:
        emit("unauthorized", {'message': 'Authentication required'}, to=request.sid)
        return False  # Disconnect the client
    room_id = request.cookies.get("room_id")
    if room_id:
        join_room(int(room_id))
        emit("incoming", (enctext_connected, "green"), to=int(room_id))
    else:
        return

# event when client disconnects
# quite unreliable use sparingly
@socketio.on('disconnect')
def disconnect():
    @copy_current_request_context
    def can_access_session():
        return session.get('user')
    username = can_access_session()
    room_id = request.cookies.get("room_id")
    if room_id and username:
        emit("incoming", (f"{username} has disconnected", "red"), to=int(room_id))

# send message event handler
@socketio.on("send")
def send(sender_username, receiver_username, message_sender_encrypted, message_receiver_encrypted, hmac, room_id):

    # print(f"sending msg from socket_routes.py: {message_sender_encrypted}")
    #emit("incoming", message_sender_encrypted, to=room_id)
    emit("message_incoming", (sender_username, receiver_username, message_sender_encrypted, message_receiver_encrypted, hmac), to=room_id)

    db.insert_message(sender_username, receiver_username, message_sender_encrypted, message_receiver_encrypted, hmac)

# join room event handler
# sent when the user joins a room
@socketio.on("join")
def join(sender_name, receiver_name, joined_sender_encrypted, joined_receiver_encrypted, joined_talking_to_sender_encrypted, joined_talking_to_receiver_encrypted, joined_hmac, joined_talking_to_hmac):
    receiver = db.get_user(receiver_name)
    if receiver is None:
        return "Unknown receiver!"
    
    sender = db.get_user(sender_name)
    if sender is None:
        return "Unknown sender!"

    room_id = room.get_room_id(receiver_name)

    if room_id is None:
        room_id = room.create_room(sender_name, receiver_name)

    join_room(room_id)
    
    # Fetch past messages and emit them
    messages = db.get_messages(sender_name, receiver_name)
    for message in messages:
        if message.sender_username == sender_name:
            emit("incoming", (message.message_sender_encrypted, message.hmac, "gray"), to=room_id)
        elif message.receiver_username == sender_name:
            emit("incoming", (message.message_receiver_encrypted, message.hmac, "gray"), useKey="recipient", to=room_id)
    
    emit("incoming", (joined_talking_to_sender_encrypted, joined_talking_to_hmac, "green"), to=room_id)
    db.insert_message(sender_name, receiver_name, joined_sender_encrypted, joined_receiver_encrypted, joined_hmac)
    return room_id


# leave room event handler
@socketio.on("leave")
def leave(username, leave_sender_encrypted, leave_receiver_encrypted, leave_hmac, room_id):
    emit("incoming", (leave_sender_encrypted, leave_hmac, "red"), to=room_id)
    leave_room(room_id)
    room.leave_room(username)

@socketio.on("HMAC_failed")
def hmac_failed():
    print("Error: integrity of message could not be verified. Not displaying message.")
