'''
app.py contains all of the server application
this is where you'll find all of the get/post request handlers
the socket event handlers are inside of socket_routes.py
'''

from flask import Flask, render_template, request, abort, url_for, jsonify, session, make_response, redirect
from flask_socketio import SocketIO
from itsdangerous import URLSafeTimedSerializer
from functools import wraps
import db
import secrets
import bcrypt

import logging

# this turns off Flask Logging, uncomment this to turn off Logging
# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)

app = Flask(__name__)
# I randomly generated this secret key using python to generate 24 random bytes then convert to a string
app.secret_key = '7pMIu4rniQ1uWrd6NQOMRwMV2Xcosbe0' 
app.serializer = URLSafeTimedSerializer(app.secret_key)

# secret key used to sign the session cookie

# app.config['SESSION_COOKIE_SECURE'] = True
# app.config['REMEMBER_COOKIE_SECURE'] = True
# app.config['SESSION_COOKIE_HTTPONLY'] = True
# app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
socketio = SocketIO(app, manage_session=False)

# don't remove this!!
import socket_routes

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return 'Authentication required', 401
        # No need to deserialize anything; just get the username from the session
        ss_username = session['user']
        
        # Add additional checks if necessary, e.g., checking if the user exists
        return f(ss_username, *args, **kwargs)
    return decorated_function


# index page
@app.route("/")
def index():
    return render_template("index.jinja")

# login page
@app.route("/login")
def login():    
    return render_template("login.jinja")

# getting public key when needed
@app.route('/api/get_public_key')
@login_required
def get_public_key(ss_username):
    username = ss_username
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    public_key = db.get_public_key(username)
    if public_key:
        return jsonify({'publicKey': public_key})
    else:
        return jsonify({'error': 'Public key not found'}), 404

@app.route('/friends')
@login_required
def friend_list(ss_username):

    user = db.get_user(ss_username)
    if not user:
        return "User does not exist", 404

    # Assuming get_friends function returns a dictionary containing the friend lists
    friends_data = db.get_friends(ss_username)
    
    # Render the friend list template with the data
    return render_template('friend_list.jinja', 
                           username=ss_username,
                           accepted_friends=friends_data['accepted_friends'], 
                           pending_requests=friends_data['pending_requests'], 
                           pending_friends=friends_data['pending_friends'])


@app.route('/handle_friend_request', methods=['POST'])
@login_required
def handle_friend_request(ss_username):
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    username = ss_username  # The user that is logged in
    friend_username = request.json.get('friend_username')  # The friend username to approve/reject
    is_accepted = request.json.get('is_accepted')  # Boolean, True if approving, False if rejecting

    if not username or not friend_username or is_accepted is None:
        return jsonify({'error': 'Missing data'}), 400

    # Assuming db.handle_friend_request handles the logic for approving or rejecting
    try:
        result = db.handle_friend_request(username, friend_username, is_accepted)
        if result:
            return jsonify('Success')
        else:
            return jsonify({'error': 'Failed to update the friend request'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_friend', methods=['POST'])
@login_required
def add_friend(ss_username):
    if not request.is_json:
        return jsonify({'error': 'Invalid request format'}), 400

    username = ss_username
    friend_username = request.json.get('friend_username')

    if not username or not friend_username:
        return jsonify({'error': 'Missing data'}), 400

    # Call the function to add a friend request
    try:
        success, message = db.add_friend_request(username, friend_username)
        if success:
            return jsonify('Success')
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route("/login/user", methods=["POST"])
def login_user():
    if not request.is_json:
        abort(404)

    username = request.json.get("username")
    password = request.json.get("password")

    user = db.get_user(username)
    if user is None:
        return "Error: User does not exist!"

    if not bcrypt.checkpw(password.encode('utf-8'), user.password):
        return "Error: Password does not match!"

    # Store the user's identity in the session, Flask will handle the cookie
    session['user'] = username

    response_data = {
            'url': url_for('friend_list', username=username)
    }
    return jsonify(response_data), 200





# handles a get request to the signup page
@app.route("/signup")
def signup():
    return render_template("signup.jinja")

# handles a post request when the user clicks the signup button
@app.route("/signup/user", methods=["POST"])
def signup_user():
    if not request.is_json:
        abort(404)
    username = request.json.get("username")
    password = request.json.get("password")

    if db.get_user(username) is None:
        db.insert_user(username, password)
        return url_for('login')
    return "Error: User already exists!"

# handler when a "404" error happens
@app.errorhandler(404)
def page_not_found(_):
    return render_template('404.jinja'), 404

@app.route('/api/get_shared_key')
@login_required
def get_shared_key(ss_username):
    # Get the friend's username from the request parameters
    friend_username = request.args.get('friend_username')

    if not friend_username:
        return jsonify({'error': 'Friend username is required'}), 400

    # Retrieve the shared key for this user and the friend from the database
    shared_key_info = db.get_shared_key(ss_username, friend_username)

    if shared_key_info:
        # Send back the shared key encrypted for the user
        return jsonify({
            'key_sender_encrypted': shared_key_info.key_sender_encrypted,
            'key_receiver_encrypted': shared_key_info.key_receiver_encrypted
        })
    else:
        # If no key exists, it could be an error, or you may want to generate a new key here
        return jsonify({'oops': 'Shared key not found'})


@app.route('/api/save_shared_key', methods=['POST'])
@login_required
def api_save_shared_key(ss_username):
    receiver_username = request.json.get('receiver_username')
    key_sender_encrypted = request.json.get('key_sender_encrypted')
    key_receiver_encrypted = request.json.get('key_receiver_encrypted')
    print("saving shared key")

    db.insert_shared_key(ss_username, receiver_username, key_sender_encrypted, key_receiver_encrypted)

    return jsonify(success=True)


# home page, where the messaging app is
@app.route("/home")
@login_required
def home(ss_username):
    if ss_username is None:
        abort(404)
    return render_template("home.jinja", username=ss_username)


@app.route('/api/send_public_key', methods=['POST'])
@login_required
def receive_public_key(ss_username):
    username = ss_username  
    public_key = request.json.get('publicKey')
    
    # You might want to store this key in a database associated with the user
    save_public_key(username, public_key)

    return jsonify(success=True)

def save_public_key(username, public_key):


    db.insert_public_key(username, public_key)




if __name__ == '__main__':
    socketio.run(app)
