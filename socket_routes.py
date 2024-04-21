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
    print("in do connection")
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
        print(f"enctext_connected: {enctext_connected}")
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
def send(sender_username, receiver_username, message_sender_encrypted, message_receiver_encrypted, room_id):

    # print(f"sending msg from socket_routes.py: {message_sender_encrypted}")
    emit("incoming", message_sender_encrypted, to=room_id)

    db.insert_message(sender_username, receiver_username, message_sender_encrypted, message_receiver_encrypted)

# join room event handler
# sent when the user joins a room
@socketio.on("join")
def join(sender_name, receiver_name, enctext_joined, enctext_joined_talking_to):
    
    receiver = db.get_user(receiver_name)
    if receiver is None:
        return "Unknown receiver!"
    
    sender = db.get_user(sender_name)
    if sender is None:
        return "Unknown sender!"

    room_id = room.get_room_id(receiver_name)

    # If the user is already inside of a room
    if room_id is not None:
        
        room.join_room(sender_name, room_id)
        print(f"roomid was set, receiver: {receiver_name}, sender: {sender_name}, room_id: {room_id}")
        join_room(room_id)
        # emit to everyone in room except sender
        emit("incoming", (enctext_joined, "green"), to=room_id, include_self=False)

        # emit only to the sender
        print("before enc_joined_talking_to")
        emit("incoming", (enctext_joined_talking_to, "green"))
        print("after enc_joined_talking_to")
        return room_id
    
    # if the user isn't inside of any room, 
    # perhaps this user has recently left a room
    # or is simply a new user looking to chat with someone

    room_id = room.create_room(sender_name, receiver_name)
    
    join_room(room_id)
    print(f"roomid wasn't set, receiver: {receiver_name}, sender: {sender_name}, room_id: {room_id}")
    print("beforeinc")
    # ATTN definite source of error
    emit("incoming", (enctext_joined_talking_to, "green"), to=room_id)
    print("afterinc")
    return room_id

# leave room event handler
@socketio.on("leave")
def leave(username, enctext_leave, room_id):
    emit("incoming", (enctext_leave, "red"), to=room_id)
    leave_room(room_id)
    room.leave_room(username)
